"""Station: one step = (maybe) read a frame -> features -> LED rule -> Observation dict."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, Optional

from .camera import Camera
from .clock import Clock
from .features import FeatureExtractor, FrameFeatures
from .led import LedController, MotionLedRule

log = logging.getLogger("ghostbuild_pi.runner")

SCHEMA_V = 2
SEQ_RATE_CEILING_HZ = 10  # seq base assumes < 20 observations/s (see initial_seq)
REOPEN_INTERVAL_MS = 2000.0
SCENE_CHANGE_LUMA = 30.0  # mean-luma jump between frames that cancels motion counting (lens cover/uncover)


def initial_seq(wall_ms: int) -> int:
    """Strictly greater than any seq an earlier process could have reached (core drops seq <= last).

    20 per wall second, while the station is capped at 10 Hz, so a restart can never go backwards.
    """
    return max(0, (wall_ms // 1000 - 1_700_000_000)) * 20


class Station:
    def __init__(self, camera: Camera, extractor: FeatureExtractor, source: str, dev: str = "pi-01",
                 led: Optional[LedController] = None, rule: Optional[MotionLedRule] = None,
                 clock: Optional[Clock] = None, report_led: bool = True,
                 scene_change_luma: float = SCENE_CHANGE_LUMA, seq_start: Optional[int] = None):
        self.camera, self.extractor, self.source, self.dev = camera, extractor, source, dev
        self.led, self.rule = led, rule
        self.clock = clock or Clock()
        self.report_led = report_led and led is not None
        self.scene_change_luma = scene_change_luma
        self._seq = seq_start if seq_start is not None else initial_seq(self.clock.wall_ms())
        self._frame_seq = 0
        self._last_ts: Optional[float] = None
        self._last_feats: Optional[FrameFeatures] = None
        self._prev_mean: Optional[float] = None
        self._open = False
        self._cam_error: Optional[str] = "camera_open_failed"
        self._next_open_at = 0.0
        self.open_failures = 0
        self.frames = 0
        self._try_open()

    # lifecycle ------------------------------------------------------------
    def _try_open(self) -> None:
        now = self.clock.now_ms()
        try:
            self.camera.open()
        except Exception as e:
            self.open_failures += 1
            self._next_open_at = now + REOPEN_INTERVAL_MS
            log.warning("camera open failed (%s): %s", self.camera.name, e)
        else:
            self._open, self._cam_error = True, None
            self._last_ts = None
            self.extractor.reset()
            self._prev_mean = None
            log.info("camera open: %s", self.camera.info())

    def _mark_failed(self, why: str) -> None:
        try:
            self.camera.close()
        except Exception:
            pass
        self._open, self._cam_error = False, why
        self._next_open_at = self.clock.now_ms() + REOPEN_INTERVAL_MS
        self.extractor.reset()
        self._prev_mean = None
        if self.rule:
            self.rule.reset()

    def status(self) -> Dict[str, Any]:
        return {"camera_open": self._open, "backend": self.camera.name, "error": self._cam_error,
                "frames": self.frames, "obs_seq": self._seq, "info": self.camera.info()}

    def close(self) -> None:
        try:
            self.camera.close()
        finally:
            if self.led:
                self.led.shutdown()

    # one observation ------------------------------------------------------
    def step(self) -> Dict[str, Any]:
        now = self.clock.now_ms()
        camera_obs: Optional[Dict[str, Any]] = None
        error: Optional[str] = None

        if not self._open and now >= self._next_open_at:
            self._try_open()

        if self._open:
            res = None
            try:
                res = self.camera.read()
            except Exception as e:
                log.warning("camera read raised: %s", e)
            if res is None:
                self._mark_failed("camera_read_failed")
            else:
                frame, ts = res
                camera_obs = self._camera_obs(frame, ts, now)

        if camera_obs is None:
            error = self._cam_error or "camera_read_failed"
            if self.rule:
                self.rule.tick(now)

        self._seq += 1
        obs: Dict[str, Any] = {
            "v": SCHEMA_V,
            "dev": self.dev,
            "seq": self._seq,
            "ms": int(now),
            "at": self.clock.wall_ms(),
            "source": self.source,
            "camera": camera_obs,
            "led": self.led.obs() if (self.report_led and self.led) else None,
            "error": error,
        }
        return obs

    def _camera_obs(self, frame, ts: float, now: float) -> Dict[str, Any]:
        is_new = self._last_ts is None or ts > self._last_ts
        if is_new:
            feats = self.extractor.process(frame)
            self._frame_seq += 1
            self.frames += 1
            scene_change = (self._prev_mean is not None
                            and abs(feats.mean_luma - self._prev_mean) > self.scene_change_luma)
            self._prev_mean, self._last_ts, self._last_feats = feats.mean_luma, ts, feats
            if self.rule:
                self.rule.on_frame(feats.motion, now, scene_change)
        else:
            # Not a new frame: describe the last real frame, with its true (growing) age and a stuck frame_seq.
            feats = self._last_feats.with_motion(0.0)
            if self.rule:
                self.rule.tick(now)
        return {
            "frame_seq": self._frame_seq,
            "frame_age_ms": max(0, int(round(now - (self._last_ts if self._last_ts is not None else ts)))),
            "mean_luma": feats.mean_luma,
            "luma_std": feats.luma_std,
            "detail": feats.detail,
            "motion": feats.motion,
            "marker_found": None,
            "marker_id": None,
        }


def run_loop(step: Callable[[], Dict[str, Any]], sink: Callable[[Dict[str, Any]], None], clock: Clock, hz: float,
             should_stop: Callable[[], bool], duration_s: Optional[float] = None) -> int:
    """Pace step() at hz (no catch-up bursts). Returns the number of observations emitted."""
    period = 1000.0 / hz
    started = clock.now_ms()
    next_t = started
    n = 0
    while not should_stop():
        if duration_s is not None and clock.now_ms() - started >= duration_s * 1000.0:
            break
        sink(step())
        n += 1
        next_t += period
        delay = next_t - clock.now_ms()
        if delay < 0:
            next_t = clock.now_ms()
        else:
            clock.sleep(delay / 1000.0)
    return n


def dumps(obs: Dict[str, Any]) -> str:
    return json.dumps(obs, separators=(",", ":"))
