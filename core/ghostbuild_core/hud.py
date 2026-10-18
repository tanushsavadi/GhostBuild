"""THE single HUD writer. Nothing else in the repo constructs a HudFrame.

Owners (engine, session UI) describe what they want shown as a `Screen` on a named layer.
The Hud merges layers (ui over engine), and emits a HudFrame only when the effective picture
CHANGES (mode/cue/image/menu/source/stale). Throttle: at most one new non-quiet cue per
`min_gap_ms`, except immediate screens (direct responses to input, error frames) and the first
frame after leaving an error.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Callable, Optional

from contracts.models import Cue, HudFrame, ImageRef, Menu, Source, StepRef

from .clock import Clock, as_clock

log = logging.getLogger("ghostbuild.hud")

LAYER_ORDER = ("voice", "ui", "engine")  # first present layer wins; "voice" = optional hold-to-ask overlay (voice.py)


def clip(cue: Cue) -> Cue:
    """Defensive: contract lengths are validated by pydantic; never let a long string kill the HUD."""
    return Cue(line1=(cue.line1 or "?")[:24], line2=(cue.line2 or "")[:26])


@dataclass(frozen=True)
class Screen:
    """What an owner wants on the glasses. Pure data; only Hud turns it into a HudFrame."""

    mode: str
    cue: Optional[Cue] = None
    image: Optional[ImageRef] = None
    menu: Optional[Menu] = None
    step: Optional[StepRef] = None
    cue_id: Optional[str] = None
    ttl_ms: Optional[int] = None
    immediate: bool = False
    stale: bool = False
    source: Optional[Source] = None  # per-screen override; None = the Hud's current source (set from observations). Playbook screens use "manual".

    # ---- constructors -----------------------------------------------------
    @staticmethod
    def quiet() -> "Screen":
        return Screen(mode="quiet")

    @staticmethod
    def intervene(cue: Cue, cue_id: Optional[str] = None, ttl_ms: Optional[int] = None, immediate: bool = False) -> "Screen":
        return Screen(mode="intervene", cue=clip(cue), cue_id=cue_id, ttl_ms=ttl_ms, immediate=immediate)

    @staticmethod
    def verified(cue: Cue, ttl_ms: int = 3000, cue_id: Optional[str] = None, immediate: bool = False) -> "Screen":
        return Screen(mode="verified", cue=clip(cue), cue_id=cue_id, ttl_ms=ttl_ms, immediate=immediate)

    @staticmethod
    def error(line1: str, line2: str) -> "Screen":
        return Screen(mode="error", cue=Cue(line1=line1, line2=line2), immediate=True, stale=True)

    @staticmethod
    def uncertain(cue: Cue, ttl_ms: Optional[int] = None) -> "Screen":
        return Screen(mode="uncertain", cue=clip(cue), ttl_ms=ttl_ms, immediate=True)

    @staticmethod
    def welcome(cue: Cue, ttl_ms: int) -> "Screen":
        return Screen(mode="welcome", cue=clip(cue), ttl_ms=ttl_ms, immediate=True)

    @staticmethod
    def ask(cue: Cue, ttl_ms: Optional[int] = None) -> "Screen":
        """Voice overlay (LISTENING / THINKING / a short grounded answer). Cue text only; never an instruction on its own."""
        return Screen(mode="ask", cue=clip(cue), ttl_ms=ttl_ms, immediate=True)

    @staticmethod
    def make_menu(prompt: str, options: list[str], selected: int) -> "Screen":
        return Screen(
            mode="menu",
            cue=Cue(line1=prompt[:24], line2="SWIPE · PRESS"),
            menu=Menu(prompt=prompt[:24], options=options, selected=selected),
            immediate=True,
        )

    @staticmethod
    def visual(cue: Cue, image: ImageRef, cue_id: Optional[str] = None, immediate: bool = True, step: Optional[StepRef] = None) -> "Screen":
        return Screen(mode="visual", cue=clip(cue), image=image, step=step, cue_id=cue_id, immediate=immediate)

    @staticmethod
    def step_screen(cue: Cue, step: StepRef, cue_id: Optional[str] = None, immediate: bool = False) -> "Screen":
        """Playbook step: stays on screen until the wearer or measured evidence moves on (no ttl)."""
        return Screen(mode="step", cue=clip(cue), step=step, cue_id=cue_id, immediate=immediate)

    def with_immediate(self, immediate: bool = True) -> "Screen":
        return replace(self, immediate=immediate)


FrameKey = tuple


def _frame_key(f: HudFrame) -> FrameKey:
    img = None
    if f.image is not None:
        img = (f.image.guide_id, f.image.view, f.image.index, f.image.count, f.image.url, f.image.sha256, f.image.w, f.image.h)
    menu = None
    if f.menu is not None:
        menu = (f.menu.prompt, tuple(f.menu.options), f.menu.selected)
    cue = (f.cue.line1, f.cue.line2) if f.cue else None
    st = (f.step.index, f.step.count, f.step.step_id, f.step.check, f.step.confirmed) if f.step else None
    return (f.mode, cue, img, menu, st, f.source, f.stale)


class Hud:
    def __init__(self, clock: Clock | Callable[[], int] | None = None, *, source: Source = "pi_live", min_gap_ms: int = 2000) -> None:
        self.clock = as_clock(clock)
        self.min_gap_ms = min_gap_ms
        self.source: Source = source
        self.frames: list[HudFrame] = []  # emitted frames only (seq >= 1)
        self._current = HudFrame(mode="quiet", seq=0, source=source)
        self._layers: dict[str, Optional[Screen]] = {}
        self._subs: list[Callable[[HudFrame], None]] = []
        self._last_nonquiet_ms: Optional[int] = None
        self.session_id: Optional[str] = None  # stamped on frames; not part of the change key

    # ---- public ------------------------------------------------------------
    @property
    def current(self) -> HudFrame:
        if self._current.session_id != self.session_id:
            self._current = self._current.model_copy(update={"session_id": self.session_id})
        return self._current

    def subscribe(self, fn: Callable[[HudFrame], None]) -> Callable[[], None]:
        self._subs.append(fn)

        def unsubscribe() -> None:
            if fn in self._subs:
                self._subs.remove(fn)

        return unsubscribe

    def set_source(self, source: Source) -> None:
        self.source = source

    def set_layer(self, name: str, screen: Optional[Screen]) -> None:
        if name not in LAYER_ORDER:
            raise ValueError(f"unknown HUD layer {name}")
        self._layers[name] = screen

    def layer(self, name: str) -> Optional[Screen]:
        return self._layers.get(name)

    def tick(self) -> Optional[HudFrame]:
        return self.sync()

    def sync(self) -> Optional[HudFrame]:
        """Emit the effective screen iff it differs from what is on the glasses and the throttle allows."""
        desired = self._desired()
        candidate = self._build(desired, self._current.seq + 1)
        if candidate is None:
            return None
        if _frame_key(candidate) == _frame_key(self._current):
            return None
        now = self.clock.now_ms()
        if self._current.seq == 0 and desired.mode == "quiet":
            # Before anything was ever shown, adopting the first observation's source is not a "frame".
            self._current = candidate.model_copy(update={"seq": 0})
            return None
        immediate = desired.immediate or desired.mode == "error" or self._current.mode == "error"
        if desired.mode != "quiet" and not immediate and self._last_nonquiet_ms is not None and now - self._last_nonquiet_ms < self.min_gap_ms:
            return None  # deferred; a later sync() emits it if it is still wanted
        return self._emit(candidate, now)

    # ---- internals ---------------------------------------------------------
    def _desired(self) -> Screen:
        for name in LAYER_ORDER:
            s = self._layers.get(name)
            if s is not None:
                return s
        return Screen.quiet()

    def _build(self, s: Screen, seq: int) -> Optional[HudFrame]:
        try:
            return HudFrame(
                seq=seq,
                mode=s.mode,  # type: ignore[arg-type]
                cue=None if s.mode == "quiet" else s.cue,
                image=s.image,
                menu=s.menu,
                step=s.step,
                cue_id=s.cue_id,
                ttl_ms=s.ttl_ms,
                source=s.source or self.source,
                session_id=self.session_id,
                stale=s.stale,
            )
        except Exception:  # a malformed screen is a bug; never take the HUD down
            log.exception("invalid HUD screen dropped: %r", s)
            return None

    def _emit(self, frame: HudFrame, now: int) -> HudFrame:
        self._current = frame
        self.frames.append(frame)
        if frame.mode != "quiet":
            self._last_nonquiet_ms = now
        for fn in list(self._subs):
            try:
                fn(frame)
            except Exception:
                log.exception("HUD subscriber failed")
        return frame
