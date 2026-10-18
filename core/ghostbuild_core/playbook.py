"""Playbook engine: a Card with `steps` navigated by the wearer on the glasses.

Not a fault engine. It never needs telemetry:
- manual step (no `verify`): the wearer confirms with swipe-down; recorded as HUMAN CONFIRMED, never VERIFIED.
- measured step (`verify`): advances ONLY when the predicates hold on fresh observations for `hold_ms`
  (same dotted-path semantics as engine.py). A gesture never completes it.
- Pi link / camera loss never produces an error frame here; a measured step simply keeps its step frame and
  a swipe on it explains why it is not met (NO PI DATA vs NOT MET YET).
Everything on the glasses goes through hud.py (layer "engine"). Cue text is card data only.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Optional

from contracts.models import (
    Card,
    Cue,
    Evidence,
    EvidenceLabel,
    G2Input,
    Guide,
    GuideView,
    HudFrame,
    ImageRef,
    Observation,
    PlaybookState,
    Source,
    Step,
    StepRef,
)

from . import intent as intent_mod
from .clock import Clock, as_clock
from .engine import Engine, _describe, eval_all, measured_label, resolve_path
from .hud import Hud, Screen

log = logging.getLogger("ghostbuild.playbook")

GUARD_MS = 1500  # a swipe-down this soon after a step frame appears is treated as accidental
VERIFIED_TTL_MS = 2000
UNCERTAIN_TTL_MS = 2000
ASK_TTL_MS = 4000
DONE_TTL_MS = 4000
COMPLETE_STATUS_TTL_MS = 3000
LINK_TIMEOUT_MS = 5000
MAX_GAP_MS = 2000
FROZEN_AFTER_MS = 2000

NOT_MET = Cue(line1="NOT MET YET", line2="WAITING FOR CHECK")
NO_DATA = Cue(line1="NO PI DATA", line2="CHECK THE STATION")


@dataclass
class _Flash:
    screen: Screen
    start: int
    end: int
    kind: str  # verified | done | uncertain | ask | status
    consumes_input: bool = False  # a gesture dismisses it and does nothing else (the wearer has not seen the step yet)


@dataclass
class AskResult:
    intent: str
    answered: bool
    cue: Cue
    text: str
    detail: str
    label: EvidenceLabel
    step_id: str
    card_id: str

    def as_json(self) -> dict[str, Any]:
        """POST /ask response (matches the phone page): answer = the Cue shown on the glasses, or null when the playbook has no answer;
        text = the full card text for the phone (a troubleshoot answer carries its `why`)."""
        return {
            "answer": {"line1": self.cue.line1, "line2": self.cue.line2} if self.answered else None,
            "text": self.text if not self.detail else f"{self.text}. {self.detail}",
            "intent": self.intent,
        }


def _cue_text(cue: Cue) -> str:
    return (cue.line1 + " " + cue.line2).strip()


class PlaybookEngine:
    def __init__(
        self,
        card: Card,
        clock: Clock | Callable[[], int] | None = None,
        *,
        hud: Optional[Hud] = None,
        asset_root: Path | str | None = None,
        force_source: Optional[Source] = None,
        progress: Optional[dict] = None,
        on_event: Optional[Callable[[Evidence], None]] = None,
        on_progress: Optional[Callable[[dict], None]] = None,
        guard_ms: int = GUARD_MS,
    ) -> None:
        if not card.steps:
            raise ValueError("PlaybookEngine needs a card with steps")
        self.card = card
        self.clock = as_clock(clock)
        self.hud = hud if hud is not None else Hud(self.clock)
        self.asset_root = Path(asset_root) if asset_root is not None else Path.cwd()
        self.force_source = force_source
        self.on_event = on_event
        self.on_progress = on_progress
        self.guard_ms = guard_ms

        self.events: deque[Evidence] = deque(maxlen=200)
        self.index = 0
        self.confirmed: list[str] = []
        self.verified: list[str] = []
        self.done = False
        self.view_idx: Optional[int] = None  # None = no picture open
        self._flashes: list[_Flash] = []
        # measured-step tracking
        self.last_obs: Optional[Observation] = None
        self._last_rx: Optional[int] = None
        self._last_seq: dict[str, int] = {}
        self._sat_since: Optional[int] = None
        self._last_frame_seq: Optional[int] = None
        self._frame_changed_at: Optional[int] = None
        # what the wearer has actually seen
        self._shown_key: Optional[tuple] = None
        self._shown_at: int = 0
        self._image_cache: dict[str, tuple[Any, Optional[tuple[int, int, str]]]] = {}

        self._restore(progress)
        self._unsub = self.hud.subscribe(self._on_frame)
        self._refresh()

    # ------------------------------------------------------------------ introspection
    @property
    def step(self) -> Step:
        return self.card.steps[min(self.index, len(self.card.steps) - 1)]

    @property
    def count(self) -> int:
        return len(self.card.steps)

    @property
    def frames(self) -> list[HudFrame]:
        return self.hud.frames

    @property
    def current_is_measured(self) -> bool:
        return not self.done and self.step.verify is not None and self.step.id not in self.verified

    def playbook_state(self) -> PlaybookState:
        return PlaybookState(
            card_id=self.card.card_id,
            step_index=self.index,
            step_count=self.count,
            step_id=self.step.id,
            confirmed=list(self.confirmed),
            verified=list(self.verified),
        )

    def progress(self) -> dict:
        return {
            "card_id": self.card.card_id,
            "step_index": self.index,
            "confirmed": list(self.confirmed),
            "verified": list(self.verified),
            "done": self.done,
        }

    def help_view(self) -> Optional[str]:
        g = self._guide()
        if self.view_idx is None or g is None:
            return None
        return g.views[min(self.view_idx, len(g.views) - 1)].view

    def reveal(self) -> None:
        """The wearer dismissed an overlay: show the current screen now (a direct response to input)."""
        self._refresh(immediate=True)

    def detach(self) -> None:
        self._unsub()
        self.hud.set_layer("engine", None)
        self.hud.sync()

    # ------------------------------------------------------------------ persistence
    def _restore(self, progress: Optional[dict]) -> None:
        if not progress or progress.get("card_id") != self.card.card_id:
            return
        ids = {s.id for s in self.card.steps}
        self.confirmed = [i for i in progress.get("confirmed", []) if i in ids]
        self.verified = [i for i in progress.get("verified", []) if i in ids]
        self.index = max(0, min(int(progress.get("step_index", 0)), self.count - 1))
        self.done = bool(progress.get("done", False))

    def _save(self) -> None:
        if self.on_progress is not None:
            try:
                self.on_progress(self.progress())
            except Exception:
                log.exception("progress sink failed")

    # ------------------------------------------------------------------ observations (optional telemetry)
    def ingest(self, obs: Observation) -> bool:
        now = self.clock.now_ms()
        if self.force_source is not None:
            obs = obs.model_copy(update={"source": self.force_source})
        last = self._last_seq.get(obs.dev)
        if last is not None and last - 50 <= obs.seq <= last:
            return False
        self._last_seq[obs.dev] = obs.seq
        if self._last_rx is not None and now - self._last_rx > MAX_GAP_MS:
            self._sat_since = None  # data was not continuous: the hold starts over
        self._last_rx = now
        self.last_obs = obs
        if obs.camera is not None:
            if obs.camera.frame_seq != self._last_frame_seq:
                self._last_frame_seq = obs.camera.frame_seq
                self._frame_changed_at = now
        else:
            self._last_frame_seq = None
            self._frame_changed_at = None
        self._eval_measured(obs, now)
        self._refresh()
        return True

    def tick(self) -> None:
        now = self.clock.now_ms()
        if self._last_rx is not None and now - self._last_rx > MAX_GAP_MS:
            self._sat_since = None  # nothing fresh: never carry a hold across silence
        self._refresh()

    def _telemetry_state(self, now: int) -> str:
        """'absent' (nothing usable), or 'fresh'. Used only to word the not-met screen."""
        if self.last_obs is None or self._last_rx is None or now - self._last_rx > LINK_TIMEOUT_MS:
            return "absent"
        st = self.step
        if st.verify is not None:
            if not self._usable(self.last_obs, now, st):
                return "absent"
        return "fresh"

    def _usable(self, obs: Observation, now: int, st: Step) -> bool:
        """Fresh data for every signal family the step reads: a null camera or a frozen frame is never evidence."""
        assert st.verify is not None
        roots = {p.signal.split(".")[0] for p in st.verify.when}
        if "camera" in roots:
            if obs.camera is None:
                return False
            if self._frame_changed_at is not None and now - self._frame_changed_at > FROZEN_AFTER_MS:
                return False
            if obs.camera.frame_age_ms > FROZEN_AFTER_MS:
                return False
        return True

    def _eval_measured(self, obs: Observation, now: int) -> None:
        if not self.current_is_measured:
            self._sat_since = None
            return
        st = self.step
        assert st.verify is not None
        if not (self._usable(obs, now, st) and eval_all(st.verify.when, obs)):
            self._sat_since = None
            return
        if self._sat_since is None:
            self._sat_since = now
        if now - self._sat_since >= st.verify.hold_ms:
            self._complete_measured(st, obs, now)

    def _complete_measured(self, st: Step, obs: Observation, now: int) -> None:
        assert st.verify is not None
        src_label = measured_label(obs.source)
        by_root: dict[str, dict[str, Any]] = {}
        for p in st.verify.when:
            v = resolve_path(obs, p.signal)
            by_root.setdefault(p.signal.split(".")[0], {})[p.signal] = v if isinstance(v, (int, float, str, bool)) or v is None else str(v)
        for root, vals in by_root.items():
            if obs.source != "pi_live":
                label: EvidenceLabel = src_label
            elif root == "led":
                label = "COMMANDED"
            else:
                label = "MEASURED LIVE"
            txt = ", ".join(f"{k}={v:g}" if isinstance(v, float) else f"{k}={v}" for k, v in vals.items())
            suffix = " (commanded state, not measured)" if label == "COMMANDED" else ""
            self._event(f"step {st.id}: {txt}{suffix}", label, dict(vals))
        self._event(
            f"step {st.id} treated as met ({_describe(st.verify.when)}) for {st.verify.hold_ms} ms",
            "INFERRED" if obs.source == "pi_live" else src_label,
            {"step": st.id},
        )
        self.verified.append(st.id)
        self._sat_since = None
        self._flash(replace(Screen.verified(st.verify.ok, ttl_ms=VERIFIED_TTL_MS, cue_id=f"{self.card.card_id}/{st.id}/ok", immediate=True), source=obs.source),
                    VERIFIED_TTL_MS, "verified", consumes_input=True, now=now)
        self._after_step_done(now)

    # ------------------------------------------------------------------ navigation
    def handle_input(self, gi: G2Input, *, from_ask: bool = False) -> Optional[HudFrame]:
        """Navigation / confirmation only. hold_* belong to the voice lane."""
        if gi.gesture in ("hold_start", "hold_end"):
            return None
        now = self.clock.now_ms()
        before = self.hud.current.seq
        fl = self._active_flash(now)
        if fl is not None and fl.consumes_input and not from_ask:
            self._flashes.remove(fl)  # dismiss only; the wearer has not seen the step yet
            self._refresh(immediate=True)
            return self._emitted_since(before)
        if fl is not None:
            self._flashes = [f for f in self._flashes if f.consumes_input]  # drop ask/uncertain overlays, keep queued results
        {"press": self._press, "swipe_down": self._swipe_down, "swipe_up": self._swipe_up}[gi.gesture](now, from_ask)
        self._refresh(immediate=True)
        return self._emitted_since(before)

    def _press(self, now: int, from_ask: bool) -> None:
        if self.done:
            self._flash(Screen.ask(Cue(line1="TASK COMPLETE", line2=self.card.title[:26]), ttl_ms=COMPLETE_STATUS_TTL_MS),
                        COMPLETE_STATUS_TTL_MS, "status", now=now)
            return
        if self.view_idx is not None:
            self.view_idx = None
            return
        g = self._guide()
        if g is not None:
            self.view_idx = 0
            return
        st = self.step
        if st.where is not None:
            self._flash(Screen.ask(st.where, ttl_ms=ASK_TTL_MS), ASK_TTL_MS, "ask", now=now)
        # no guide and no `where`: repeat the step cue (it is already on screen; identical frames are never re-sent)

    def _swipe_down(self, now: int, from_ask: bool) -> None:
        if self.done:
            return
        g = self._guide()
        if self.view_idx is not None and g is not None:
            self.view_idx = min(self.view_idx + 1, len(g.views) - 1)
            return
        self.view_idx = None
        st = self.step
        if st.id in self.confirmed or st.id in self.verified:
            self._after_step_done(now)  # revisited step that was already completed: just move on
            return
        if st.verify is not None:
            cue = NO_DATA if self._telemetry_state(now) == "absent" else NOT_MET
            self._flash(Screen.uncertain(cue, ttl_ms=UNCERTAIN_TTL_MS), UNCERTAIN_TTL_MS, "uncertain", now=now)
            self._event(f"step {st.id}: swipe ignored, check not met ({cue.line1})", "DETERMINISTIC", {"step": st.id})
            return
        if not from_ask and not self._step_settled(now):
            return  # accidental-input guard: no frame
        self.confirmed.append(st.id)
        self._event(f"step {st.id} confirmed by wearer", "HUMAN CONFIRMED", {"step": st.id})
        self._after_step_done(now)

    def _swipe_up(self, now: int, from_ask: bool) -> None:
        g = self._guide()
        if self.done:
            self.done = False  # a mistaken last swipe: reopen the final step; confirmations are kept
            self.index = self.count - 1
            self._flashes = []
            self._reset_hold()
            self._save()
            return
        if self.view_idx is not None and g is not None:
            self.view_idx = None if self.view_idx == 0 else self.view_idx - 1
            return
        self.view_idx = None
        if self.index > 0:
            self.index -= 1
            self._reset_hold()
            self._save()

    def _after_step_done(self, now: int) -> None:
        """The current step is complete (confirmed / verified / already was): go to the next one or finish."""
        self.view_idx = None
        self._reset_hold()
        if self.index + 1 < self.count:
            self.index += 1
        else:
            self._finish(now)
        self._save()

    def _finish(self, now: int) -> None:
        self.done = True
        steps = self.card.steps
        measured = sum(1 for s in steps if s.verify is not None)
        if measured == len(steps):
            screen = Screen.verified(Cue(line1="● PLAYBOOK VERIFIED", line2="EVERY STEP CHECKED"), ttl_ms=DONE_TTL_MS, cue_id=f"{self.card.card_id}/done", immediate=True)
            if self.last_obs is not None:
                screen = replace(screen, source=self.last_obs.source)  # driven by the last observation
        else:
            line2 = "YOU CONFIRMED EACH" if measured == 0 else "SOME CHECKED, SOME BY YOU"
            screen = Screen.intervene(Cue(line1="✓ ALL STEPS DONE", line2=line2), cue_id=f"{self.card.card_id}/done", ttl_ms=DONE_TTL_MS, immediate=True)
        self._flash(screen, DONE_TTL_MS, "done", consumes_input=True, now=now)
        self._event(f"playbook {self.card.card_id} complete", "DETERMINISTIC", {"measured_steps": measured, "steps": len(steps)})

    def _reset_hold(self) -> None:
        self._sat_since = None

    def _step_settled(self, now: int) -> bool:
        """True iff the current step frame has actually been on the glasses for at least guard_ms."""
        return self._shown_key == self._key() and now - self._shown_at >= self.guard_ms

    # ------------------------------------------------------------------ flashes
    def _flash(self, screen: Screen, ttl: int, kind: str, *, consumes_input: bool = False, now: int) -> None:
        start = now
        queued = [f for f in self._flashes if f.end > now]
        if queued and consumes_input:
            start = max(f.end for f in queued)  # results chain: verified -> completion
        self._flashes = queued + [_Flash(screen, start, start + ttl, kind, consumes_input)]

    def _active_flash(self, now: int) -> Optional[_Flash]:
        self._flashes = [f for f in self._flashes if f.end > now]
        for f in self._flashes:
            if f.start <= now < f.end:
                return f
        return None

    # ------------------------------------------------------------------ screens
    def _key(self) -> tuple:
        return (self.index, self.step.id in self.confirmed or self.step.id in self.verified)

    def _step_ref(self) -> StepRef:
        st = self.step
        return StepRef(
            index=self.index,
            count=self.count,
            step_id=st.id,
            check="measured" if st.verify is not None else "manual",
            confirmed=st.id in self.confirmed or st.id in self.verified,
        )

    def _guide(self) -> Optional[Guide]:
        gid = self.step.guide_id
        if not gid:
            return None
        for g in self.card.guides:
            if g.id == gid and g.views:
                return g
        return None

    def _compute_screen(self, now: int) -> Screen:
        fl = self._active_flash(now)
        if fl is not None:
            return fl.screen
        if self.done:
            return Screen.quiet()
        st = self.step
        cue_id = f"{self.card.card_id}/{st.id}"
        g = self._guide()
        if self.view_idx is not None and g is not None:
            idx = min(self.view_idx, len(g.views) - 1)
            view = g.views[idx]
            ref = self._image_ref(g, idx, view)
            if ref is None:
                # never a broken image: the card's own text fallback, still a step frame
                return Screen.step_screen(view.fallback, self._step_ref(), cue_id=cue_id, immediate=True)
            nxt = g.views[idx + 1].view.upper() if idx + 1 < len(g.views) else None
            cue = Cue(line1=f"{view.title}: {g.title}".upper()[:24], line2=(f"SWIPE FOR {nxt}" if nxt else "PRESS TO GO BACK")[:26])
            return Screen.visual(cue, ref, cue_id=cue_id, step=self._step_ref())
        return Screen.step_screen(st.cue, self._step_ref(), cue_id=cue_id)

    def _refresh(self, immediate: bool = False) -> None:
        now = self.clock.now_ms()
        screen = self._compute_screen(now)
        if immediate:
            screen = screen.with_immediate(True)
        if screen.source is None:
            screen = replace(screen, source="manual")  # not backed by telemetry: the wearer's own navigation
        self.hud.set_layer("engine", screen)
        self.hud.sync()

    def _on_frame(self, frame: HudFrame) -> None:
        """Hud subscriber: remember when the current step frame actually reached the glasses (for the accidental-input guard)."""
        if frame.mode == "step" and frame.step is not None and frame.step.step_id == self.step.id:
            key = (frame.step.index, frame.step.confirmed)
            if key != self._shown_key:
                self._shown_key = key
                self._shown_at = self.clock.now_ms()

    def _emitted_since(self, seq_before: int) -> Optional[HudFrame]:
        cur = self.hud.current
        return cur if cur.seq > seq_before else None

    # ------------------------------------------------------------------ pictures
    def _image_ref(self, guide: Guide, idx: int, view: GuideView) -> Optional[ImageRef]:
        path = self.asset_root / view.image
        key = str(path)
        try:
            st = path.stat()
            sig: Any = (st.st_mtime_ns, st.st_size)
        except OSError:
            sig = None
        cached = self._image_cache.get(key)
        if cached is not None and cached[0] == sig:
            meta = cached[1]
        else:
            meta = Engine._read_png(path) if sig is not None else None
            if meta is None:
                self._event(f"guide image unavailable, using text fallback: {view.image}", "DETERMINISTIC", {"image": view.image})
            self._image_cache[key] = (sig, meta)
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

    # ------------------------------------------------------------------ contextual follow-ups (/ask, voice)
    def ask(self, text: str) -> AskResult:
        """Deterministic intents over the ACTIVE step. The answer is card text only; nothing is generated."""
        now = self.clock.now_ms()
        st = self.step
        text = (text or "").strip()[:300]
        intent = intent_mod.classify_playbook(text, st.faq)
        self._event(f'ask "{text[:120]}" -> {intent}', "INFERRED", {"intent": intent, "step": st.id})
        cue: Optional[Cue] = None
        detail = ""
        label: EvidenceLabel = self.card.provenance
        body = ""
        if intent == "where":
            cue = st.where
        elif intent == "why":
            cue = st.why
        elif intent == "faq":
            i = intent_mod.faq_best(text, st.faq)
            cue = st.faq[i[0]].a if i else None
        elif intent == "troubleshoot":
            last = self.last_obs
            for chk in st.troubleshoot:
                if not chk.when or (last is not None and eval_all(chk.when, last)):
                    cue, detail = chk.action, chk.why
                    break
        elif intent == "status":
            cue = Cue(line1=f"STEP {self.index + 1} OF {self.count}" if not self.done else "TASK COMPLETE", line2=(st.title if not self.done else self.card.title).upper()[:26])
            label = "DETERMINISTIC"
        elif intent in ("next", "back", "picture"):
            return self._ask_navigate(intent, now)
        answered = cue is not None
        if cue is None:
            cue = intent_mod.NOT_IN_PLAYBOOK
            label = "DETERMINISTIC"
        body = _cue_text(cue)
        if answered:
            self._event(f"answer ({intent}): {body}" + (f" | {detail}" if detail else ""), label, {"step": st.id})
        self._flash(Screen.ask(cue, ttl_ms=ASK_TTL_MS), ASK_TTL_MS, "ask", now=now)
        self._refresh(immediate=True)
        return AskResult(intent=intent, answered=answered, cue=cue, text=body, detail=detail, label=label, step_id=st.id, card_id=self.card.card_id)

    def _ask_navigate(self, intent: str, now: int) -> AskResult:
        gesture = {"next": "swipe_down", "back": "swipe_up", "picture": "press"}[intent]
        if intent == "picture" and self.view_idx is not None:
            gesture = "swipe_down"  # already looking at one: show the next view
        before = (self.index, self.done, self.view_idx, tuple(self.confirmed))
        self.handle_input(G2Input(gesture=gesture, seq_seen=self.hud.current.seq), from_ask=True)  # type: ignore[arg-type]
        cur = self.hud.current
        cue = cur.cue or Cue(line1="OK", line2="")
        moved = before != (self.index, self.done, self.view_idx, tuple(self.confirmed))
        return AskResult(
            intent=intent, answered=moved or cur.mode in ("uncertain", "ask"), cue=cue, text=_cue_text(cue), detail="",
            label="DETERMINISTIC", step_id=self.step.id, card_id=self.card.card_id,
        )

    # ------------------------------------------------------------------ misc
    def _event(self, text: str, label: EvidenceLabel, evidence: Optional[dict] = None) -> None:
        ev = Evidence(at=self.clock.epoch_ms(), text=text, label=label, evidence=evidence or {})
        self.events.append(ev)
        if self.on_event is not None:
            try:
                self.on_event(ev)
            except Exception:
                log.exception("event sink failed")
