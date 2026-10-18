"""Camera backends. Contract: open(); read() -> (frame, captured_at_ms) | None; close().

read() returning None, or any exception, means "no frame". The station turns that into an
Observation with camera=null and an error. Nothing here ever invents or repeats a frame to
hide a failure. captured_at_ms is on the same monotonic clock as Clock.now_ms().

Real backends (auto order): picamera2 -> OpenCV VideoCapture -> rpicam-still/libcamera-still.
Nothing here is verified against real hardware yet; tools/spike.py is the check.
"""

from __future__ import annotations

import importlib
import io
import logging
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .clock import Clock

log = logging.getLogger("ghostbuild_pi.camera")

Frame = np.ndarray
FrameResult = Optional[Tuple[Frame, float]]

REAL_BACKENDS = ("picamera2", "opencv", "rpicam")
FAKE_SCENARIOS = ("blocked", "clear", "flicker", "frozen", "disconnect", "wave")


class CameraError(Exception):
    pass


class CameraOpenError(CameraError):
    pass


class CameraReadError(CameraError):
    pass


class Camera:
    name = "camera"
    is_fake = False

    def open(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def read(self) -> FrameResult:  # pragma: no cover - interface
        raise NotImplementedError

    def close(self) -> None:
        pass

    def info(self) -> Dict[str, Any]:
        return {"backend": self.name}


# --------------------------------------------------------------------------- fakes
class FakeCamera(Camera):
    """Deterministic synthetic scenes. Its data is SIMULATED and the CLI labels it so."""

    is_fake = True

    def __init__(self, scenario: str, clock: Clock, size: Tuple[int, int] = (320, 240), seed: int = 7,
                 flicker_blocked_ms: float = 1000.0, disconnect_after_ms: float = 3000.0,
                 wave_period_ms: float = 4000.0, wave_burst_ms: float = 1500.0):
        if scenario not in FAKE_SCENARIOS:
            raise ValueError("unknown fake scenario %r (choose from %s)" % (scenario, ", ".join(FAKE_SCENARIOS)))
        self.scenario = scenario
        self.name = "fake:" + scenario
        self.clock = clock
        self.w, self.h = size
        self.seed = seed
        self.flicker_blocked_ms = flicker_blocked_ms
        self.disconnect_after_ms = disconnect_after_ms
        self.wave_period_ms = wave_period_ms
        self.wave_burst_ms = wave_burst_ms
        self._opened_at: Optional[float] = None
        self._n = 0
        self._frozen: FrameResult = None
        self._disconnected = False

    # scene builders -------------------------------------------------------
    def _noise(self, sigma: float) -> np.ndarray:
        rng = np.random.default_rng(self.seed + self._n)
        return rng.normal(0.0, sigma, (self.h, self.w))

    def _blocked(self) -> np.ndarray:
        return 6.0 + self._noise(0.6)

    def _clear(self) -> np.ndarray:
        yy, xx = np.mgrid[0 : self.h, 0 : self.w]
        checker = (((xx // 16) + (yy // 16)) % 2) * 70.0
        ripple = 18.0 * np.sin(xx / 5.0) * np.cos(yy / 7.0)
        return 85.0 + checker + ripple + self._noise(2.0)

    def _wave_scene(self, burst: bool) -> np.ndarray:
        img = self._clear()
        if burst:
            bw, bh = int(self.w * 0.31), int(self.h * 0.58)
            x0 = int(self.w * 0.04) if self._n % 2 == 0 else int(self.w * 0.65)
            y0 = (self.h - bh) // 2
            img[y0 : y0 + bh, x0 : x0 + bw] = 195.0
        return img

    @staticmethod
    def _to_rgb(gray: np.ndarray) -> np.ndarray:
        g = np.clip(np.rint(gray), 0, 255).astype(np.uint8)
        return np.stack([g, g, g], axis=2)

    # Camera API -----------------------------------------------------------
    def open(self) -> None:
        if self._disconnected:
            raise CameraOpenError("fake camera is disconnected")
        self._opened_at = self.clock.now_ms()

    def close(self) -> None:
        self._opened_at = None

    def info(self) -> Dict[str, Any]:
        return {"backend": self.name, "fake": True}

    def read(self) -> FrameResult:
        if self._opened_at is None:
            raise CameraReadError("fake camera not open")
        now = self.clock.now_ms()
        t = now - self._opened_at
        if self.scenario == "disconnect" and t >= self.disconnect_after_ms:
            self._disconnected = True
            return None
        if self.scenario == "frozen" and self._frozen is not None:
            return self._frozen  # same frame, same timestamp: a stuck feed
        self._n += 1
        if self.scenario == "blocked":
            gray = self._blocked()
        elif self.scenario == "flicker":
            gray = self._blocked() if t < self.flicker_blocked_ms else self._clear()
        elif self.scenario == "wave":
            gray = self._wave_scene(burst=(t % self.wave_period_ms) < self.wave_burst_ms)
        else:  # clear, frozen (first frame), disconnect (before the cut)
            gray = self._clear()
        result = (self._to_rgb(gray), now)
        if self.scenario == "frozen":
            self._frozen = result
        return result


# --------------------------------------------------------------------------- real backends
def _can_import(mod: str) -> bool:
    try:
        importlib.import_module(mod)
        return True
    except Exception:
        return False


class Picamera2Camera(Camera):
    name = "picamera2"

    def __init__(self, clock: Clock, size: Tuple[int, int] = (640, 480), index: int = 0):
        self.clock, self.size, self.index = clock, size, index
        self._cam = None
        self._info: Dict[str, Any] = {}
        self._last_sensor_ts: Optional[int] = None
        self._last_captured: Optional[float] = None

    def open(self) -> None:
        try:
            from picamera2 import Picamera2  # type: ignore
        except Exception as e:
            raise CameraOpenError("picamera2 not importable: %s" % e)
        try:
            infos = list(Picamera2.global_camera_info())
        except Exception as e:
            raise CameraOpenError("picamera2 camera enumeration failed: %s" % e)
        if not infos:
            raise CameraOpenError("picamera2 sees no camera")
        if self.index >= len(infos):
            raise CameraOpenError("camera index %d not present (%d found)" % (self.index, len(infos)))
        self._info = {k: str(v) for k, v in dict(infos[self.index]).items()}
        try:
            cam = Picamera2(self.index)
            cfg = cam.create_video_configuration(main={"size": self.size, "format": "RGB888"})
            cam.configure(cfg)
            cam.start()
        except Exception as e:
            raise CameraOpenError("picamera2 open/start failed: %s" % e)
        self._cam = cam
        self._last_sensor_ts = None
        self._last_captured = None

    def read(self) -> FrameResult:
        if self._cam is None:
            raise CameraReadError("picamera2 not open")
        try:
            req = self._cam.capture_request()
        except Exception as e:
            raise CameraReadError("capture_request failed: %s" % e)
        try:
            arr = req.make_array("main")
            try:
                sensor_ts = req.get_metadata().get("SensorTimestamp")
            except Exception:
                sensor_ts = None
        except Exception as e:
            raise CameraReadError("make_array failed: %s" % e)
        finally:
            try:
                req.release()
            except Exception:
                pass
        now = self.clock.now_ms()
        # Same sensor timestamp as last time => not a new frame; keep the old capture time.
        if sensor_ts is not None and sensor_ts == self._last_sensor_ts and self._last_captured is not None:
            return (arr, self._last_captured)
        self._last_sensor_ts, self._last_captured = sensor_ts, now
        return (arr, now)

    def close(self) -> None:
        cam, self._cam = self._cam, None
        if cam is not None:
            for fn in ("stop", "close"):
                try:
                    getattr(cam, fn)()
                except Exception:
                    pass

    def info(self) -> Dict[str, Any]:
        return {"backend": self.name, "camera": dict(self._info)}


class OpenCVCamera(Camera):
    name = "opencv"

    def __init__(self, clock: Clock, size: Tuple[int, int] = (640, 480), index: int = 0):
        self.clock, self.size, self.index = clock, size, index
        self._cap = None

    def open(self) -> None:
        try:
            import cv2  # type: ignore
        except Exception as e:
            raise CameraOpenError("cv2 not importable: %s" % e)
        cap = cv2.VideoCapture(self.index)
        if not cap.isOpened():
            cap.release()
            raise CameraOpenError("cv2.VideoCapture(%d) did not open" % self.index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.size[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.size[1])
        ok, frame = cap.read()
        if not ok or frame is None:
            cap.release()
            raise CameraOpenError("cv2 opened device %d but cannot read a frame (not a usable camera?)" % self.index)
        self._cap = cap

    def read(self) -> FrameResult:
        if self._cap is None:
            raise CameraReadError("opencv not open")
        ok, frame = self._cap.read()
        if not ok or frame is None:
            return None
        return (frame, self.clock.now_ms())

    def close(self) -> None:
        cap, self._cap = self._cap, None
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass

    def info(self) -> Dict[str, Any]:
        return {"backend": self.name, "index": self.index}


class RpicamStillCamera(Camera):
    """Slow fallback: spawns rpicam-still / libcamera-still per frame (about 1 fps at best)."""

    name = "rpicam"

    def __init__(self, clock: Clock, size: Tuple[int, int] = (640, 480), timeout_s: float = 10.0):
        self.clock, self.size, self.timeout_s = clock, size, timeout_s
        self._exe: Optional[str] = None

    @staticmethod
    def find_exe() -> Optional[str]:
        for exe in ("rpicam-still", "libcamera-still"):
            p = shutil.which(exe)
            if p:
                return p
        return None

    @staticmethod
    def _decode(data: bytes) -> np.ndarray:
        try:
            from PIL import Image  # type: ignore

            return np.asarray(Image.open(io.BytesIO(data)).convert("RGB"))
        except ImportError:
            pass
        try:
            import cv2  # type: ignore

            arr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if arr is None:
                raise CameraReadError("cv2 could not decode JPEG")
            return arr
        except ImportError:
            raise CameraReadError("need Pillow or OpenCV to decode rpicam-still output")

    def _capture(self) -> np.ndarray:
        cmd = [self._exe, "-n", "-t", "1", "--width", str(self.size[0]), "--height", str(self.size[1]),
               "-e", "jpg", "-o", "-"]
        try:
            p = subprocess.run(cmd, capture_output=True, timeout=self.timeout_s)
        except Exception as e:
            raise CameraReadError("%s failed: %s" % (self._exe, e))
        if p.returncode != 0 or not p.stdout:
            tail = (p.stderr or b"").decode("utf-8", "replace").strip().splitlines()[-1:]
            raise CameraReadError("%s exit %s %s" % (self._exe, p.returncode, tail))
        return self._decode(p.stdout)

    def open(self) -> None:
        self._exe = self.find_exe()
        if not self._exe:
            raise CameraOpenError("neither rpicam-still nor libcamera-still found on PATH")
        try:
            self._capture()
        except CameraReadError as e:
            raise CameraOpenError("test capture failed: %s" % e)

    def read(self) -> FrameResult:
        if not self._exe:
            raise CameraReadError("rpicam not open")
        frame = self._capture()
        return (frame, self.clock.now_ms())

    def close(self) -> None:
        self._exe = None

    def info(self) -> Dict[str, Any]:
        return {"backend": self.name, "exe": self._exe}


class AutoCamera(Camera):
    """Tries real backends in order; first that opens wins. Records why others failed."""

    def __init__(self, clock: Clock, size: Tuple[int, int] = (640, 480), index: int = 0,
                 order: Tuple[str, ...] = REAL_BACKENDS):
        self.clock, self.size, self.index, self.order = clock, size, index, order
        self.active: Optional[Camera] = None
        self.tried: List[str] = []

    @property
    def name(self) -> str:  # type: ignore[override]
        return self.active.name if self.active else "auto"

    def open(self) -> None:
        self.tried = []
        for b in self.order:
            cam = make_backend(b, self.clock, self.size, self.index)
            try:
                cam.open()
            except CameraError as e:
                self.tried.append("%s: %s" % (b, e))
                continue
            self.active = cam
            log.info("camera backend in use: %s", cam.name)
            return
        self.active = None
        raise CameraOpenError("no camera backend opened (%s)" % "; ".join(self.tried))

    def read(self) -> FrameResult:
        if self.active is None:
            raise CameraReadError("camera not open")
        return self.active.read()

    def close(self) -> None:
        if self.active is not None:
            self.active.close()
            self.active = None

    def info(self) -> Dict[str, Any]:
        d = self.active.info() if self.active else {"backend": None}
        d["tried"] = list(self.tried)
        return d


def make_backend(name: str, clock: Clock, size: Tuple[int, int] = (640, 480), index: int = 0) -> Camera:
    if name == "picamera2":
        return Picamera2Camera(clock, size, index)
    if name == "opencv":
        return OpenCVCamera(clock, size, index)
    if name == "rpicam":
        return RpicamStillCamera(clock, size)
    if name == "auto":
        return AutoCamera(clock, size, index)
    raise ValueError("unknown camera backend %r" % name)


def detect_backends() -> Dict[str, Any]:
    """Capability detection without opening a camera."""
    return {
        "picamera2_importable": _can_import("picamera2"),
        "cv2_importable": _can_import("cv2"),
        "pillow_importable": _can_import("PIL"),
        "rpicam_still": RpicamStillCamera.find_exe(),
        "rpicam_hello": shutil.which("rpicam-hello") or shutil.which("libcamera-hello"),
    }
