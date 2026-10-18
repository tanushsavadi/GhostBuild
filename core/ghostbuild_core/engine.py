"""Deterministic repair engine. Driven ONLY by a Card and Observations (+ G2 input and the clock).

Public API (stable; the sponsor harness extends it):
    eng = Engine(card, clock)
    eng.ingest(obs)            -> bool (False if dropped as a stale/duplicate seq)
    eng.tick()                 -> advance timers (link loss, offer, ttl) without an observation
    eng.handle_input(g2_input) -> Optional[HudFrame]
    eng.frames                 -> every HudFrame emitted so far
    eng.state                  -> "NO_LINK" | "HEALTHY" | "FAULT" | "EXHAUSTED" | "AWAIT_FUNC"

Evidence rules: a verified frame is only produced after a MEASURED pass (camera non-null, not frozen,
predicates false for pass_after_ms) or a MEASURED functional trigger. A G2 press is navigation or a recheck,
never a commit. camera null / frozen / stale link => honest error frame, never success.
"""

from __future__ import annotations

import hashlib
import io
import logging
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from contracts.models import (
    Card,
    Check,
    Cue,
    Evidence,
    EvidenceLabel,
    G2Input,
    Guide,
    GuideView,
    HudFrame,
    ImageRef,
    Observation,
    Predicate,
    Source,
)
from contracts.models import Test as CardTest

from .clock import Clock, as_clock
from .hud import Hud, Screen

log = logging.getLogger("ghostbuild.engine")

VERIFIED_TTL_MS = 3000
STATUS_TTL_MS = 3000
PROMPT_TTL_MS = 15000


# --------------------------------------------------------------------------- predicates
def resolve_path(obs: Any, path: str) -> Any:
    """Dotted path into an Observation. Any null on the way (or an unknown attribute) => None."""
    cur: Any = obs
    for part in path.split("."):
        if cur is None:
            return None
        cur = getattr(cur, part, None)
    return cur


def eval_predicate(p: Predicate, obs: Observation) -> bool:
    v = resolve_path(obs, p.signal)
    if p.op == "is_null":
        return v is None
    if p.op == "not_null":
        return v is not None
    if v is None:
        return False  # a null path never satisfies a comparison
    try:
        if p.op == "lt":
            return bool(v < p.value)  # type: ignore[operator]
        if p.op == "gt":
            return bool(v > p.value)  # type: ignore[operator]
        if p.op == "eq":
            return bool(v == p.value)
    except TypeError:
        return False
    return False


def eval_all(preds: list[Predicate], obs: Observation) -> bool:
    return all(eval_predicate(p, obs) for p in preds)


def measured_label(source: Source) -> EvidenceLabel:
    return {"pi_live": "MEASURED LIVE", "replay": "REPLAY", "simulated": "SIMULATED"}[source]  # type: ignore[return-value]


def source_word(source: Source) -> str:
    return {"pi_live": "LIVE", "replay": "REPLAY", "simulated": "SIMULATED"}[source]


def _describe(preds: list[Predicate]) -> str:
    sym = {"lt": "<", "gt": ">", "eq": "=", "is_null": " is null", "not_null": " not null"}
    out = []
    for p in preds:
        s = p.signal.split(".")[-1]
        out.append(f"{s}{sym[p.op]}{'' if p.value is None else p.value}")
    return " and ".join(out)


# --------------------------------------------------------------------------- per-test tracker
@dataclass
class _Track:
    test: CardTest
    idx: int
    fail_since: Optional[int] = None
    pass_since: Optional[int] = None
    in_fault: bool = False
    fault_at: Optional[int] = None
    check_idx: int = 0
    offered: bool = False
    help_requested: bool = False
    help_open: bool = False
    help_index: int = 0
    fail_values: dict = field(default_factory=dict)

    def reset_windows(self) -> None:
        self.fail_since = None
        self.pass_since = None

    def reset_episode(self) -> None:
        self.in_fault = False
        self.fault_at = None
        self.offered = False
        self.help_requested = False
        self.help_open = False
        self.help_index = 0


class Engine:
    def __init__(
        self,
        card: Card,
        clock: Clock | Callable[[], int] | None = None,
        *,
        hud: Optional[Hud] = None,
        asset_root: Path | str | None = None,
        force_source: Optional[Source] = None,
        link_timeout_ms: int = 5000,
        frozen_after_ms: int = 2000,
        null_after_ms: int = 500,
        max_gap_ms: int = 2000,
        on_event: Optional[Callable[[Evidence], None]] = None,
        passive: bool = False,
    ) -> None:
        self.card = card
        self.passive = passive  # True: keeps link/camera bookkeeping for Health but never writes a HUD screen (a playbook owns the glasses)
        self.clock = as_clock(clock)
        self.hud = hud if hud is not None else Hud(self.clock)
        self.asset_root = Path(asset_root) if asset_root is not None else Path.cwd()
        self.force_source = force_source
        self.link_timeout_ms = link_timeout_ms
        self.frozen_after_ms = frozen_after_ms
        self.null_after_ms = null_after_ms
        self.max_gap_ms = max_gap_ms
        self.on_event = on_event

        self.events: deque[Evidence] = deque(maxlen=200)
        self._tracks = [_Track(test=t, idx=i) for i, t in enumerate(card.tests)]
        self._started = self.clock.now_ms()
        self._last_rx: Optional[int] = None
        self.last_obs: Optional[Observation] = None
        self._last_seq: dict[str, int] = {}
        # camera health
        self._null_since: Optional[int] = None
        self._last_frame_seq: Optional[int] = None
        self._frame_changed_at: Optional[int] = None
        self.camera_status = "unknown"  # ok | unavailable | frozen | unknown
        self._link_lost = False
        # transient screens
        self._flash: Optional[tuple[Screen, int]] = None
        # functional
        self.await_func = False
        self._prompt_from = 0
        self._prompt_until = 0
        self._func_trigger_at: Optional[int] = None
        self._func_trigger_motion: Optional[float] = None
        # last time a measured pass of every test was seen on the latest observation
        self.measured_pass_ok = False
        self._image_cache: dict[str, tuple[tuple[int, int], Optional[tuple[int, int, str]]]] = {}

    # ------------------------------------------------------------------ public API
    @property
    def frames(self) -> list[HudFrame]:
        return self.hud.frames

    @property
    def state(self) -> str:
        if self._link_is_lost(self.clock.now_ms()):
            return "NO_LINK"
        if self._current_fault() is not None:
            return "FAULT"
        if self.await_func:
            return "AWAIT_FUNC"
        return "HEALTHY"

    @property
    def last_seq(self) -> Optional[int]:
        return self.last_obs.seq if self.last_obs is not None else None

    def link_age_ms(self) -> Optional[int]:
        return None if self._last_rx is None else self.clock.now_ms() - self._last_rx

    def link_status(self) -> str:
        now = self.clock.now_ms()
        if self._link_is_lost(now):
            return "down"
        age = self.link_age_ms()
        if age is None:
            return "down"
        return "up" if age <= 2000 else "stale"

    def ingest(self, obs: Observation) -> bool:
        now = self.clock.now_ms()
        if self.force_source is not None:
            obs = obs.model_copy(update={"source": self.force_source})
        last = self._last_seq.get(obs.dev)
        if last is not None and last - 50 <= obs.seq <= last:
            return False  # duplicate / reordered within a boot
        self._last_seq[obs.dev] = obs.seq  # seq < last-50 => device rebooted, accept

        self._update_link(now)  # notice a gap that happened before this observation
        gap = None if self._last_rx is None else now - self._last_rx
        if gap is not None and gap > self.max_gap_ms:
            for t in self._tracks:
                t.reset_windows()  # data was not continuous: windows start over
            self._func_trigger_at = None
        self._last_rx = now
        self.last_obs = obs
        self.hud.set_source(obs.source)
        was_lost = self._link_lost
        self._link_lost = False
        if was_lost:
            self._event("Pi link restored", "DETERMINISTIC", {"seq": obs.seq})

        usable = self._update_camera(obs, now)
        if usable:
            self._evaluate_tests(obs, now)
            self._evaluate_functional(obs, now)
        else:
            for t in self._tracks:
                t.reset_windows()
            self._func_trigger_at = None
            self.measured_pass_ok = False
        self._housekeeping(now)
        self._refresh()
        return True

    def tick(self) -> None:
        now = self.clock.now_ms()
        self._update_link(now)
        self._expire_functional(now)
        self._housekeeping(now)
        self._refresh()

    def handle_input(self, gi: G2Input) -> Optional[HudFrame]:
        """Navigation / recheck only. Never changes fault state or declares anything fixed."""
        now = self.clock.now_ms()
        self._update_link(now)
        if gi.gesture in ("hold_start", "hold_end"):
            return None  # voice lane, later
        before = self.hud.current.seq
        if self._link_is_lost(now) or self.camera_status in ("unavailable", "frozen"):
            self._refresh(immediate=True)  # error stays on screen; a press does not hide it
            return self._emitted_since(before)
        tr = self._current_track()
        if tr is not None:
            self._flash = None
            guide = self._guide_for(tr)
            if guide is not None:
                last = len(guide.views) - 1
                if gi.gesture == "press":
                    if tr.help_open:
                        tr.help_open = False
                    else:
                        tr.help_open = True
                        tr.help_requested = True
                        tr.help_index = min(tr.help_index, last)
                elif gi.gesture == "swipe_down" and tr.help_open:
                    tr.help_index = min(tr.help_index + 1, last)
                elif gi.gesture == "swipe_up" and tr.help_open:
                    if tr.help_index == 0:
                        tr.help_open = False
                    else:
                        tr.help_index -= 1
        elif gi.gesture == "press":
            if self.await_func and self.card.functional is not None:
                self._flash = None
                self._prompt_from = now
                self._prompt_until = now + PROMPT_TTL_MS
            elif self.measured_pass_ok:
                src = self.last_obs.source if self.last_obs else self.hud.source
                self._flash = (
                    Screen.verified(Cue(line1="ALL TESTS PASSING", line2=source_word(src)), ttl_ms=STATUS_TTL_MS, cue_id="status"),
                    now + STATUS_TTL_MS,
                )
        self._housekeeping(now)
        self._refresh(immediate=True)
        return self._emitted_since(before)

    def help_goto(self, target: str) -> bool:
        """Voice navigation: open the guide at a view name, or "next"/"previous". Navigation only; never touches fault state.
        False if there is nothing to navigate (no fault, no guide, no such view, error showing)."""
        now = self.clock.now_ms()
        self._update_link(now)
        if self._link_is_lost(now) or self.camera_status in ("unavailable", "frozen"):
            return False
        tr = self._current_track()
        g = self._guide_for(tr) if tr is not None else None
        if tr is None or g is None:
            return False
        last = len(g.views) - 1
        names = [v.view for v in g.views]
        if target in names:
            idx = names.index(target)
        elif target == "next":
            idx = min(tr.help_index + 1, last) if tr.help_open else 0
        elif target == "previous":
            if not tr.help_open:
                return False
            if tr.help_index == 0:
                tr.help_open = False
                self._flash = None
                self._refresh(immediate=True)
                return True
            idx = tr.help_index - 1
        else:
            return False
        tr.help_open, tr.help_requested, tr.help_index = True, True, idx
        self._flash = None
        self._housekeeping(now)
        self._refresh(immediate=True)
        return True

    def recheck_status(self) -> bool:
        """Healthy-state status request (same effect as a press while healthy). True if a measured status flash was shown."""
        if self._current_track() is not None:
            return False
        before = self.hud.current.seq
        self.handle_input(G2Input(gesture="press", seq_seen=before))
        return self._flash is not None and self._flash[0].cue_id == "status"

    def note(self, text: str, label: EvidenceLabel, evidence: Optional[dict] = None) -> None:
        """Public evidence-event hook (phone-visible via State.events)."""
        self._event(text, label, evidence)

    # ------------------------------------------------------------------ introspection for State
    def current_track(self) -> Optional[_Track]:
        return self._current_track()

    def help_view(self) -> Optional[str]:
        tr = self._current_track()
        if tr is None or not tr.help_open:
            return None
        g = self._guide_for(tr)
        return g.views[min(tr.help_index, len(g.views) - 1)].view if g else None

    def step_id(self) -> Optional[str]:
        tr = self._current_track()
        if tr is None:
            return None
        g = self._guide_for(tr)
        if g is None:
            return None
        i = tr.help_index if tr.help_open else 0
        return g.views[min(i, len(g.views) - 1)].step_id

    # ------------------------------------------------------------------ link / camera
    def _link_is_lost(self, now: int) -> bool:
        if self._last_rx is None:
            return now - self._started > self.link_timeout_ms
        return now - self._last_rx > self.link_timeout_ms

    def _update_link(self, now: int) -> None:
        lost = self._link_is_lost(now)
        if lost and not self._link_lost:
            self._link_lost = True
            for t in self._tracks:
                t.reset_windows()
            self._func_trigger_at = None
            self.measured_pass_ok = False
            self._event("no observation from the Pi for more than 5 s", "DETERMINISTIC", {"age_ms": self.link_age_ms() or -1})

    def _update_camera(self, obs: Observation, now: int) -> bool:
        cam = obs.camera
        prev = self.camera_status
        if cam is None:
            self._last_frame_seq = None
            self._frame_changed_at = None
            if self._null_since is None:
                self._null_since = now
            self.camera_status = "unavailable" if now - self._null_since >= self.null_after_ms else "unknown"
            if self.camera_status == "unavailable" and prev != "unavailable":
                self._event(f"camera unavailable ({obs.error or 'no reason given'})", measured_label(obs.source), {"error": obs.error})
            return False
        self._null_since = None
        if cam.frame_seq != self._last_frame_seq:
            self._last_frame_seq = cam.frame_seq
            self._frame_changed_at = now
        frozen = self._frame_changed_at is not None and now - self._frame_changed_at > self.frozen_after_ms
        if frozen:
            self.camera_status = "frozen"
            if prev != "frozen":
                self._event(f"camera frame_seq stuck at {cam.frame_seq} for more than 2 s", measured_label(obs.source), {"frame_seq": cam.frame_seq})
            return False
        self.camera_status = "ok"
        if prev in ("unavailable", "frozen"):
            self._event("camera feed back", measured_label(obs.source), {"frame_seq": cam.frame_seq})
        return True

    # ------------------------------------------------------------------ tests
    def _evaluate_tests(self, obs: Observation, now: int) -> None:
        all_pass = True
        for tr in self._tracks:
            t = tr.test
            failing = eval_all(t.fail_when, obs)
            if failing:
                all_pass = False
                tr.pass_since = None
                if tr.fail_since is None:
                    tr.fail_since = now
                    tr.fail_values = {p.signal: resolve_path(obs, p.signal) for p in t.fail_when}
                if not tr.in_fault and now - tr.fail_since >= t.fail_after_ms:
                    self._open_fault(tr, obs, now)
            else:
                tr.fail_since = None
                if tr.pass_since is None:
                    tr.pass_since = now
                if tr.in_fault and now - tr.pass_since >= t.pass_after_ms:
                    self._recover(tr, obs, now)
        self.measured_pass_ok = all_pass

    def _open_fault(self, tr: _Track, obs: Observation, now: int) -> None:
        tr.in_fault = True
        tr.fault_at = now
        tr.offered = False
        tr.help_requested = False
        tr.help_open = False
        tr.help_index = 0
        tr.check_idx = 0
        for i, c in enumerate(tr.test.checks):
            if eval_all(c.when, obs):
                tr.check_idx = i
                break
        self.await_func = False  # a new fault invalidates a pending functional test
        self._func_trigger_at = None
        self._flash = None
        held = (now - (tr.fail_since or now)) / 1000.0
        vals = {k: v for k, v in tr.fail_values.items() if isinstance(v, (int, float, str, bool)) or v is None}
        txt = ", ".join(f"{k.split('.')[-1]} {v:g}" if isinstance(v, (int, float)) and not isinstance(v, bool) else f"{k.split('.')[-1]} {v}" for k, v in vals.items())
        self._event(f"{txt} for {held:.1f} s", measured_label(obs.source), vals)
        self._event(
            f"test {tr.test.id} treated as failing ({_describe(tr.test.fail_when)})",
            "INFERRED" if obs.source == "pi_live" else measured_label(obs.source),
            {"test": tr.test.id},
        )

    def _recover(self, tr: _Track, obs: Observation, now: int) -> None:
        cam = obs.camera
        vals: dict = {"test": tr.test.id}
        if cam is not None:
            vals.update({"mean_luma": cam.mean_luma, "luma_std": cam.luma_std, "frame_seq": cam.frame_seq})
        held = (now - (tr.pass_since or now)) / 1000.0
        self._event(f"test {tr.test.id} passing on measured frames for {held:.1f} s", measured_label(obs.source), vals)
        if obs.source == "pi_live":
            self._event(f"test {tr.test.id} treated as recovered (predicates no longer hold)", "INFERRED", {"test": tr.test.id})
        tr.reset_episode()
        ok = tr.test.ok if tr.test.ok.line1 else Cue(line1="TEST PASSING")
        self._flash = (Screen.verified(ok, ttl_ms=VERIFIED_TTL_MS, cue_id=f"{tr.test.id}/ok"), now + VERIFIED_TTL_MS)
        if self.card.functional is not None:
            self.await_func = True
            self._func_trigger_at = None
            self._prompt_from = now + VERIFIED_TTL_MS
            self._prompt_until = now + VERIFIED_TTL_MS + PROMPT_TTL_MS

    # ------------------------------------------------------------------ functional
    def _evaluate_functional(self, obs: Observation, now: int) -> None:
        f = self.card.functional
        if f is None or not self.await_func or self._current_fault() is not None:
            return
        if self._func_trigger_at is None:
            if eval_all(f.trigger, obs):
                self._func_trigger_at = now
                cam = obs.camera
                self._func_trigger_motion = cam.motion if cam else None
            else:
                return
        commanded = f.expect_commanded is None or eval_predicate(f.expect_commanded, obs)
        if commanded and now - self._func_trigger_at <= f.within_ms:
            led = obs.led
            if f.expect_commanded is not None:
                self._event(
                    f"LED commanded on (cmd {led.cmd_seq if led else '?'}) after {f.id} trigger; commanded, not measured light",
                    "COMMANDED",
                    {"cmd_seq": led.cmd_seq if led else None, "reason": led.reason if led else None},
                )
            self._event(f"{f.id} trigger seen on measured frames", measured_label(obs.source), {"motion": self._func_trigger_motion})
            self.await_func = False
            self._func_trigger_at = None
            self._flash = (Screen.verified(f.ok, ttl_ms=VERIFIED_TTL_MS, cue_id=f"{f.id}/ok"), now + VERIFIED_TTL_MS)
        else:
            self._expire_functional(now)

    def _expire_functional(self, now: int) -> None:
        f = self.card.functional
        if f is None or self._func_trigger_at is None:
            return
        if now - self._func_trigger_at > f.within_ms:
            self._event(
                f"{f.id} trigger seen but the expected command was not observed within {f.within_ms} ms; no success claimed",
                measured_label(self.last_obs.source) if self.last_obs else "DETERMINISTIC",
                {"within_ms": f.within_ms},
            )
            self._func_trigger_at = None

    # ------------------------------------------------------------------ housekeeping / screens
    def _housekeeping(self, now: int) -> None:
        if self._flash is not None:
            if now >= self._flash[1]:
                self._flash = None
            elif self._link_is_lost(now) or self.camera_status in ("unavailable", "frozen"):
                self._flash = None  # an error ends any success flash; it never resurfaces afterwards
            elif self._flash[0].cue_id == "status" and not self.measured_pass_ok:
                self._flash = None  # a status claim is only shown while the latest measurement still passes
        for tr in self._tracks:
            if tr.in_fault and not tr.offered and not tr.help_requested and tr.fault_at is not None:
                if now - tr.fault_at >= tr.test.offer_help_after_ms and self._guide_for(tr) is not None:
                    tr.offered = True
                    self._event(f"offered a picture for {tr.test.id}", "DETERMINISTIC", {"test": tr.test.id})

    def _current_track(self) -> Optional[_Track]:
        for tr in self._tracks:  # card order = priority
            if tr.in_fault:
                return tr
        return None

    def _current_fault(self) -> Optional[CardTest]:
        tr = self._current_track()
        return tr.test if tr else None

    def _guide_for(self, tr: _Track) -> Optional[Guide]:
        check = tr.test.checks[min(tr.check_idx, len(tr.test.checks) - 1)]
        if not check.guide_id:
            return None
        for g in self.card.guides:
            if g.id == check.guide_id and g.views:
                return g
        return None

    def _refresh(self, immediate: bool = False) -> None:
        if self.passive:
            return
        now = self.clock.now_ms()
        screen = self._compute_screen(now)
        if immediate:
            screen = screen.with_immediate(True)
        self.hud.set_layer("engine", screen)
        self.hud.sync()

    def _compute_screen(self, now: int) -> Screen:
        if self._link_is_lost(now):
            return Screen.error("PI LINK LOST", "CHECK PI POWER")
        if self.camera_status == "unavailable":
            return Screen.error("CAMERA FEED LOST", "CHECK CAMERA CABLE")
        if self.camera_status == "frozen":
            return Screen.error("CAMERA FEED FROZEN", "RESTART CAMERA")
        if self._flash is not None and now < self._flash[1]:
            return self._flash[0]
        tr = self._current_track()
        if tr is not None:
            check = tr.test.checks[min(tr.check_idx, len(tr.test.checks) - 1)]
            cue_id = f"{tr.test.id}/{tr.check_idx}"
            if tr.help_open:
                g = self._guide_for(tr)
                if g is not None:
                    return self._help_screen(g, min(tr.help_index, len(g.views) - 1), cue_id)
            if tr.offered and not tr.help_requested:
                return Screen.intervene(Cue(line1=tr.test.fact.line1, line2="PRESS FOR PICTURE"), cue_id=cue_id)
            return Screen.intervene(check.action, cue_id=cue_id)
        if self.await_func and self.card.functional is not None and self._prompt_from <= now < self._prompt_until:
            return Screen.intervene(self.card.functional.prompt, cue_id=self.card.functional.id, ttl_ms=PROMPT_TTL_MS)
        return Screen.quiet()

    # ------------------------------------------------------------------ guides / help
    def _help_screen(self, guide: Guide, idx: int, cue_id: str) -> Screen:
        view = guide.views[idx]
        ref = self._image_ref(guide, idx, view)
        if ref is None:
            return Screen.intervene(view.fallback, cue_id=cue_id, immediate=True)
        nxt = guide.views[idx + 1].view.upper() if idx + 1 < len(guide.views) else None
        cue = Cue(
            line1=f"{view.title}: {guide.title}".upper()[:24],
            line2=(f"SWIPE FOR {nxt}" if nxt else "PRESS TO GO BACK")[:26],
        )
        return Screen.visual(cue, ref, cue_id=cue_id)

    def _image_ref(self, guide: Guide, idx: int, view: GuideView) -> Optional[ImageRef]:
        path = (self.asset_root / view.image)
        key = str(path)
        try:
            st = path.stat()
            sig = (st.st_mtime_ns, st.st_size)
        except OSError:
            sig = None
        cached = self._image_cache.get(key)
        if cached is not None and cached[0] == sig:
            meta = cached[1]
        else:
            meta = self._read_png(path) if sig is not None else None
            if meta is None and (cached is None or cached[0] != sig):
                self._event(f"guide image unavailable, using text fallback: {view.image}", "DETERMINISTIC", {"image": view.image})
            self._image_cache[key] = (sig, meta)  # type: ignore[assignment]
        if meta is None:
            return None
        w, h, sha = meta
        return ImageRef(
            guide_id=guide.id,
            view=view.view,
            index=idx,
            count=len(guide.views),
            title=view.title[:24],
            url=f"/guides/{guide.id}/{view.view}.png",
            w=w,
            h=h,
            sha256=sha,
            provenance=view.provenance,
            step_id=view.step_id,
        )

    @staticmethod
    def _read_png(path: Path) -> Optional[tuple[int, int, str]]:
        try:
            from PIL import Image

            data = path.read_bytes()
            im = Image.open(io.BytesIO(data))
            im.load()
            w, h = im.size
            if not (1 <= w <= 288 and 1 <= h <= 144):
                return None
            return w, h, hashlib.sha256(data).hexdigest()
        except Exception:
            return None

    # ------------------------------------------------------------------ misc
    def _emitted_since(self, seq_before: int) -> Optional[HudFrame]:
        cur = self.hud.current
        return cur if cur.seq > seq_before else None

    def _event(self, text: str, label: EvidenceLabel, evidence: Optional[dict] = None) -> None:
        ev = Evidence(at=self.clock.epoch_ms(), text=text, label=label, evidence=evidence or {})
        self.events.append(ev)
        if self.on_event is not None:
            try:
                self.on_event(ev)
            except Exception:
                log.exception("event sink failed")
