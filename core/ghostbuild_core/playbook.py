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
import os
from collections import deque
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Optional

from contracts.models import (
    AnswerPage,
    Card,
    Cue,
    Evidence,
    EvidenceLabel,
    G2Input,
    Guide,
    GuideView,
    HudFrame,
    ImageRef,
    Menu,
    Observation,
    PlaybookState,
    Source,
    Step,
    StepRef,
)

from . import intent as intent_mod
from .clock import Clock, as_clock
from .presentation import instruction
from .engine import Engine, _describe, eval_all, measured_label, resolve_path
from .hud import Hud, Screen

log = logging.getLogger("ghostbuild.playbook")

GUARD_MS = 600  # a swipe-down this soon after a step frame appears is a bounce, not a confirmation (long enough to have seen it)
VERIFIED_TTL_MS = 2000
UNCERTAIN_TTL_MS = 2000
HAZARD_CONFIRM_MS = 5000  # a hazard step's second swipe must follow within this window
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
    pending: bool = False  # THINKING: a press here means "never mind", so the late answer stays on the phone only


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
    cached: bool = False
    pending: bool = False  # an assistant answer is on its way (shown on the glasses and the phone when it arrives)

    def as_json(self) -> dict[str, Any]:
        """POST /ask response (matches the phone page): answer = the Cue shown on the glasses, or null when the playbook has no answer;
        text = the full card text for the phone (a troubleshoot answer carries its `why`)."""
        return {
            "answer": {"line1": self.cue.line1, "line2": self.cue.line2} if self.answered else None,
            "text": self.text if not self.detail else f"{self.text}. {self.detail}",
            "intent": self.intent,
            "label": self.label,
            "card_id": self.card_id,
            "step_id": self.step_id,
            "pending": self.pending,
            "cached": self.cached,
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
        self.answer_data: Optional[dict] = None
        self.answer_index = 0
        self.pending_dismissed = False  # the wearer pressed past THINKING; the assistant must not pop its answer up
        # branching guides: the route actually taken (for "back"), what the person reported at question steps, the highlighted answer
        self.path: list[int] = []
        self.observations: list[dict] = []
        self.choice_idx = 0
        self._hazard_armed: Optional[tuple[str, int]] = None
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
        self._tried: list[tuple[str, int]] = []  # (step id, check index) already suggested for 'that didn't work'; cleared when a step is confirmed

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
            observations=[o["text"] for o in self.observations],
        )

    def progress(self) -> dict:
        return {
            "card_id": self.card.card_id,
            "step_index": self.index,
            "confirmed": list(self.confirmed),
            "verified": list(self.verified),
            "done": self.done,
            "answer": self.answer_data,
            "answer_index": self.answer_index,
            "path": list(self.path),
            "observations": list(self.observations),
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
        self.path = [i for i in progress.get("path", []) if isinstance(i, int) and 0 <= i < self.count][-200:]
        self.observations = [o for o in progress.get("observations", []) if isinstance(o, dict) and o.get("step") in ids][-60:]
        saved = progress.get("answer")
        if isinstance(saved, dict) and saved.get("step_id") == self.step.id and isinstance(saved.get("text"), str):
            self.answer_data = saved
            self.answer_index = max(0, int(progress.get("answer_index", 0)))

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
        if self.answer_data is not None and not self._answer_owned():
            self.answer_data = None  # an answer for another step (evidence moved on) never traps gestures
            self._save()
        if self.answer_data is not None:
            if gi.gesture == "press":
                self.dismiss_ask()
            else:
                from .answer import pages
                count = len(pages(self.answer_data["text"]))
                self.answer_index = max(0, min(count - 1, self.answer_index + (1 if gi.gesture == "swipe_down" else -1)))
                self._save()
                self._refresh(immediate=True)
            return self._emitted_since(before)
        if (self.step.kind == "question" and not self.done and self.view_idx is None and not from_ask
                and self._active_flash(now) is None):
            self._question_input(gi.gesture, now)
            self._refresh(immediate=True)
            return self._emitted_since(before)
        fl = self._active_flash(now)
        if fl is not None and fl.pending and gi.gesture == "press" and not from_ask:
            self._flashes.remove(fl)
            self.pending_dismissed = True
            self._refresh(immediate=True)
            return self._emitted_since(before)
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
            self._flash(Screen.ask(Cue(line1="TASK COMPLETE", line2=self.card.title.upper()[:26]), ttl_ms=COMPLETE_STATUS_TTL_MS),
                        COMPLETE_STATUS_TTL_MS, "status", now=now)
            return
        g = self._guide()
        if self.view_idx is not None:
            # press = the picture button: WHERE -> HOW -> CORRECT -> back to the step (swipes never cycle pictures)
            self.view_idx = self.view_idx + 1 if g is not None and self.view_idx + 1 < len(g.views) else None
            return
        if g is not None:
            automatic = self._default_view(g)
            self.view_idx = min(automatic + 1, len(g.views) - 1) if automatic is not None else 0
            return
        st = self.step
        if st.where is not None:
            self._flash(Screen.ask(st.where, ttl_ms=ASK_TTL_MS), ASK_TTL_MS, "ask", now=now)
        # no guide and no `where`: repeat the step cue (it is already on screen; identical frames are never re-sent)

    def _swipe_down(self, now: int, from_ask: bool) -> None:
        if self.done:
            return
        was_picture = self.view_idx is not None  # the wearer has been looking at this step: no settle guard on this swipe
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
        if not from_ask and not was_picture and not self._step_settled(now):
            return  # accidental-input guard: no frame
        armed = self._hazard_armed is not None and self._hazard_armed[0] == st.id and now - self._hazard_armed[1] <= HAZARD_CONFIRM_MS
        if st.risk == "hazard" and not armed:
            # a consequential step needs a second, deliberate confirmation
            self._hazard_armed = (st.id, now)
            cue = Cue(line1="SAFETY STEP: DONE IT?", line2="SWIPE AGAIN TO CONFIRM")
            self._flash(Screen.uncertain(cue, ttl_ms=HAZARD_CONFIRM_MS), HAZARD_CONFIRM_MS, "uncertain", now=now)
            self._event(f"step {st.id}: hazard step needs a second confirmation", "DETERMINISTIC", {"step": st.id})
            return
        self._hazard_armed = None
        self.confirmed.append(st.id)
        self._tried.clear()
        self._event(f"step {st.id} confirmed by wearer", "HUMAN CONFIRMED", {"step": st.id})
        self._after_step_done(now)

    def _swipe_up(self, now: int, from_ask: bool) -> None:
        g = self._guide()
        if self.done:
            self.done = False  # a mistaken last swipe: reopen the final step; confirmations are kept
            self._flashes = []
            self._reset_hold()
            self._save()
            return
        if self.view_idx is not None:
            self.view_idx = None  # swipe up from a picture = back to the step it belongs to
            return
        if self.path:
            self.index = self.path.pop()  # back along the route actually taken (branching guides)
            self.choice_idx = 0
            self._reset_hold()
            self._save()
        elif self.index > 0:
            self.index -= 1
            self._reset_hold()
            self._save()

    def _answer_owned(self) -> bool:
        return self.answer_data is not None and not self.done and self.answer_data.get("step_id") == self.step.id

    def _after_step_done(self, now: int) -> None:
        """The current step is complete (confirmed / verified / already was): go to the next one or finish."""
        self.answer_data = None  # the answer belonged to the finished step; the phone conversation keeps it
        self.view_idx = None
        self._reset_hold()
        st = self.step
        if st.kind in ("outcome", "stop"):
            self._finish(now)
        elif st.next:
            self._go(self._index_of(st.next))
        elif self.index + 1 < self.count:
            self._go(self.index + 1)
        else:
            self._finish(now)
        self._save()

    # ------------------------------------------------------------------ branching guides
    def _index_of(self, step_id: str) -> int:
        return next(i for i, s in enumerate(self.card.steps) if s.id == step_id)

    def _go(self, index: int) -> None:
        if index != self.index:
            self.path.append(self.index)
            self.path = self.path[-200:]
        self.index = index
        self.choice_idx = 0
        self.view_idx = None

    def _question_input(self, gesture: str, now: int) -> None:
        """A question step is a small menu: swipe moves the highlight, press answers. Swipe up at the top goes back."""
        n = len(self.step.choices)
        if gesture == "press":
            self.choose(self.step.choices[min(self.choice_idx, n - 1)].id, via="g2")
        elif gesture == "swipe_down":
            self.choice_idx = (self.choice_idx + 1) % n
        elif self.choice_idx > 0:
            self.choice_idx -= 1
        else:
            self._swipe_up(now, False)

    def choose(self, choice_id: str, via: str = "phone") -> bool:
        """Answer the current question step. Records what the person reported (HUMAN CONFIRMED, never measured) and follows it."""
        st = self.step
        choice = next((c for c in st.choices if c.id == choice_id), None) if st.kind == "question" and not self.done else None
        if choice is None:
            return False
        text = choice.records or choice.label.capitalize()
        self.observations = [o for o in self.observations if o["step"] != st.id] + [{"step": st.id, "choice": choice.id, "text": text}]
        if st.id not in self.confirmed:
            self.confirmed.append(st.id)
        self._tried.clear()
        self._event(f"step {st.id}: person reported \"{text}\" ({via})", "HUMAN CONFIRMED", {"step": st.id, "choice": choice.id})
        self.answer_data = None
        self._go(self._index_of(choice.next))
        self._save()
        self._refresh(immediate=True)
        return True

    def match_choice(self, text: str) -> Optional[str]:
        """Deterministic: which answer of the current question step does this utterance give? None when unclear."""
        st = self.step
        if st.kind != "question" or self.done:
            return None
        t = " " + " ".join(intent_mod.normalize(text).split()) + " "
        from .discovery.attrs import pick_ordinal

        def hits_in(t: str) -> list[str]:
            out = []
            for c in st.choices:
                phrases = [p.lower() for p in c.say] + [c.label.lower()]
                if any(" " + " ".join(intent_mod.normalize(p).split()) + " " in t for p in phrases if p.strip()):
                    out.append(c.id)
            return out

        hits = hits_in(t)
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            # "only the external monitor, the laptop screen looks fine": a clause that rules something out does not answer
            import re

            clauses = [intent_mod.normalize(c) for c in re.split(r"[,;.]|\bbut\b|\band\b|\bwhile\b|\bthough\b", text.lower())]
            keep = [c for c in clauses if not re.search(r"\b(fine|ok|okay|works?|working|normal|good|right|not|isn t|isnt|no problem)\b", c)]
            narrowed = hits_in(" " + " ".join(" ".join(keep).split()) + " ")
            if len(narrowed) == 1:
                return narrowed[0]
            # naming several things together is the "both / all of them" answer, when the question offers one
            combined = [c.id for c in st.choices if c.id in hits and re.search(r"\b(both|all)\b", " ".join(c.say + [c.label]).lower())
                        and re.search(r"\b(both|all)\b", t)]
            if len(combined) == 1:
                return combined[0]
        ordinal = pick_ordinal(text, len(st.choices)) if not hits and len(t.split()) <= 4 else None  # "the second one"
        return st.choices[ordinal].id if ordinal is not None else None

    def _finish(self, now: int) -> None:
        self.done = True
        steps = self.card.steps
        measured = sum(1 for s in steps if s.verify is not None)
        if measured == len(steps):
            screen = Screen.verified(Cue(line1="● PLAYBOOK VERIFIED", line2="EVERY STEP CHECKED"), ttl_ms=DONE_TTL_MS, cue_id=f"{self.card.card_id}/done", immediate=True)
            if self.last_obs is not None:
                screen = replace(screen, source=self.last_obs.source)  # driven by the last observation
        elif self.step.kind == "stop":
            screen = Screen.intervene(Cue(line1="STOPPED SAFELY HERE", line2="NEXT STEPS ON YOUR PHONE"), cue_id=f"{self.card.card_id}/done", ttl_ms=DONE_TTL_MS, immediate=True)
        else:
            line2 = "YOU CONFIRMED EACH" if measured == 0 else "SOME CHECKED, SOME BY YOU"
            line1 = "✓ GUIDE FINISHED" if self.step.kind == "outcome" else "✓ ALL STEPS DONE"
            screen = Screen.intervene(Cue(line1=line1, line2=line2), cue_id=f"{self.card.card_id}/done", ttl_ms=DONE_TTL_MS, immediate=True)
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

    def _default_view(self, guide):
        if os.getenv("GB_STEP_IMAGES","1")=="0" or not self.card.step_image:
            return None
        return next((i for i,v in enumerate(guide.views) if v.view==self.card.step_image),None)

    def _compute_screen(self, now: int) -> Screen:
        fl = self._active_flash(now)
        if fl is not None:
            return fl.screen
        if self.answer_data is not None and self._answer_owned():
            from .answer import pages
            data = self.answer_data
            chunks = pages(data["text"])
            self.answer_index = min(self.answer_index, len(chunks) - 1)
            page = AnswerPage(text=chunks[self.answer_index], index=self.answer_index, count=len(chunks),
                              grounding=data["grounding"], label=data["label"])
            return Screen(mode="ask", cue=Cue.model_validate(data["cue"]), answer=page, step=self._step_ref(), immediate=True)
        if self.done:
            return Screen.quiet()
        st = self.step
        cue_id = f"{self.card.card_id}/{st.id}"
        if st.kind == "question" and self.view_idx is None:
            q = instruction(st)
            self.choice_idx = min(self.choice_idx, len(st.choices) - 1)
            return Screen(mode="menu", cue=Cue(line1=q.line1, line2=q.line2 or "SWIPE · PRESS TO ANSWER"),
                          menu=Menu(prompt=q.line1[:24], options=[c.label[:26] for c in st.choices], selected=self.choice_idx),
                          step=self._step_ref(), cue_id=cue_id, immediate=True)
        g = self._guide()
        if self.view_idx is not None and g is not None:
            idx = min(self.view_idx, len(g.views) - 1)
            view = g.views[idx]
            ref = self._image_ref(g, idx, view)
            if ref is None:
                # never a broken image: the card's own text fallback, still a step frame
                return Screen.step_screen(view.fallback, self._step_ref(), cue_id=cue_id, immediate=True)
            nxt = g.views[idx + 1].view.upper() if idx + 1 < len(g.views) else None
            cue = Cue(line1=f"{view.title}: {g.title}".upper()[:24], line2=(f"PRESS FOR {nxt}" if nxt else "PRESS TO GO BACK")[:26])
            return Screen.visual(cue, ref, cue_id=cue_id, step=self._step_ref())
        automatic = self._default_view(g) if g is not None else None
        if automatic is not None:
            ref=self._image_ref(g,automatic,g.views[automatic])
            if ref is not None:
                return Screen.visual(instruction(st),ref,cue_id=cue_id,step=self._step_ref())
        return Screen.step_screen(instruction(st), self._step_ref(), cue_id=cue_id)

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
        if (frame.mode == "step" or (frame.mode=="visual" and self.view_idx is None)) and frame.step is not None and frame.step.step_id == self.step.id:
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
        if intent in ("where", "why", "how", "correct") and not self._question_matches_step(text):
            intent = "unknown"
        if intent_mod.returns_to_step(text):
            self.dismiss_ask()
            return AskResult(intent="return", answered=True, cue=self.step.cue, text="Back to the same step.", detail="", label="DETERMINISTIC", step_id=self.step.id, card_id=self.card.card_id)
        # A deliberate voice command can leave the answer page; a page swipe never can.
        self.answer_data = None
        self._event(f'ask "{text[:120]}" -> {intent}', "INFERRED", {"intent": intent, "step": st.id})
        # Visual requests reveal reviewed card assets, never advance progress.
        if intent in ("where", "how", "correct"):
            guide = self._guide()
            target = next((i for i, v in enumerate(guide.views) if v.view == intent), None) if guide else None
            if target is not None:
                self.view_idx = target
                self._flashes = []
                self._refresh(immediate=True)
                view = guide.views[target]
                cue = view.fallback
                return AskResult(intent=intent, answered=True, cue=cue, text=_cue_text(cue), detail=view.depicts,
                                 label=view.provenance, step_id=st.id, card_id=self.card.card_id)
        if intent == "picture" and any(w in text.lower() for w in ("closer", "zoom", "bigger", "enlarge")):
            guide = self._guide()
            target = next((i for i, v in enumerate(guide.views) if v.view == "how"), 0) if guide else None
            if target is not None:
                self.view_idx = target
                self._flashes = []
                self._refresh(immediate=True)
                view = guide.views[target]
                return AskResult(intent="picture", answered=True, cue=view.fallback, text=_cue_text(view.fallback), detail=view.depicts,
                                 label=view.provenance, step_id=st.id, card_id=self.card.card_id)
        if intent == "goto":
            return self._ask_goto(text, now)
        if intent == "parts":
            return self._ask_parts(now)
        cue: Optional[Cue] = None
        detail = ""
        label: EvidenceLabel = self.card.provenance
        body = ""
        if intent == "where":
            cue = st.where
        elif intent in ("how", "repeat"):
            cue, detail = st.cue, st.detail
        elif intent == "why":
            cue = st.why
        elif intent == "correct":
            # no picture of the finished state: the source's own words for it, or an honest "not described"
            if st.expected:
                cue, detail = Cue(line1="WHEN IT'S RIGHT", line2="FROM THE SOURCE"), st.expected
            else:
                cue = Cue(line1="NOT DESCRIBED IN GUIDE", line2="SOURCE LINK ON PHONE")
                detail, label = "The source does not describe the finished result for this step. Check the cited page on your phone.", "DETERMINISTIC"
        elif intent == "faq":
            i = intent_mod.faq_best(text, st.faq)
            cue = st.faq[i[0]].a if i else None
        elif intent == "troubleshoot":
            cue, detail, label = self._next_check(label)
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
        self.show_answer(body + (". " + detail if detail else ""), cue=cue, grounding="guide" if answered else "unsure", label=label)
        return AskResult(intent=intent, answered=answered, cue=cue, text=body, detail=detail, label=label, step_id=st.id, card_id=self.card.card_id)

    def _ask_goto(self, text: str, now: int) -> AskResult:
        """'show me step 14': jump to that step. Navigation only: nothing is confirmed, earlier confirmations are kept."""
        n = intent_mod.goto_number(text) or 0
        if not 1 <= n <= self.count:
            cue = Cue(line1=f"ONLY {self.count} STEPS", line2="TRY A STEP NUMBER")
            self._flash(Screen.ask(cue, ttl_ms=ASK_TTL_MS), ASK_TTL_MS, "ask", now=now)
            self._refresh(immediate=True)
            return AskResult(intent="goto", answered=False, cue=cue, text=f"This guide has {self.count} steps; there is no step {n}.", detail="",
                             label="DETERMINISTIC", step_id=self.step.id, card_id=self.card.card_id)
        self.done = False
        self.index = n - 1
        self.view_idx = None
        self._flashes = []
        self._tried.clear()
        self._reset_hold()
        self._save()
        self._event(f"jumped to step {n} of {self.count} at the wearer's request (nothing confirmed)", "DETERMINISTIC", {"step": self.step.id})
        self._refresh(immediate=True)
        st = self.step
        cue = Cue(line1=f"STEP {n} OF {self.count}", line2=st.title.upper()[:26])
        return AskResult(intent="goto", answered=True, cue=cue, text=f"Step {n} of {self.count}: {st.title}", detail=st.detail, label="DETERMINISTIC",
                         step_id=st.id, card_id=self.card.card_id)

    def _ask_parts(self, now: int) -> AskResult:
        """'which fastener do I use': the parts the source prints for this step, plus the parts closeup when the guide has one."""
        st = self.step
        use = [p for p in st.parts if not p.avoid]
        avoid = [p for p in st.parts if p.avoid]
        if not st.parts:
            cue = Cue(line1="NO PARTS LISTED", line2="SEE THE PICTURE" if self._guide() is not None else "SEE PHONE")
            self._event("parts asked: this step prints no parts", "DETERMINISTIC", {"step": st.id})
            self._flash(Screen.ask(cue, ttl_ms=ASK_TTL_MS), ASK_TTL_MS, "ask", now=now)
            self._refresh(immediate=True)
            return AskResult(intent="parts", answered=False, cue=cue, text="The manual prints no parts or fasteners for this step.", detail="",
                             label="DETERMINISTIC", step_id=st.id, card_id=self.card.card_id)

        def one(p) -> str:
            core = f"{p.qty}x {p.name} {p.id}".replace("  ", " ").strip() if p.qty else f"{p.name} {p.id}".strip()
            return core

        text = "Use " + "; ".join(one(p) for p in use) if use else "No fasteners to add in this step"
        if avoid:
            text += ". Do not use " + "; ".join(f"{p.name} {p.id}".strip() for p in avoid) + " here (the manual crosses it out)"
        detail = " ".join(p.note for p in st.parts if p.note)
        short = ", ".join((f"{p.qty}X " if p.qty else "") + p.id for p in use)
        cue = intent_mod.wrap_two_lines("USE " + short) if use else None
        if cue is None:
            cue = Cue(line1=(f"USE {use[0].id}" if use else "NO NEW PARTS")[:24], line2="SEE PHONE LIST" if len(use) > 1 else "")
        guide = self._guide()
        target = next((i for i, v in enumerate(guide.views) if v.view == "how"), 0) if guide else None
        self._event(f"parts: {text}", self.card.provenance, {"step": st.id, "parts": ",".join(p.id for p in st.parts)})
        if guide is not None and target is not None:
            self.view_idx = target  # the closeup of the parts and fasteners, from the manual
            self._flashes = []
        else:
            self._flash(Screen.ask(cue, ttl_ms=ASK_TTL_MS), ASK_TTL_MS, "ask", now=now)
        self._refresh(immediate=True)
        return AskResult(intent="parts", answered=True, cue=cue, text=text, detail=detail, label=self.card.provenance, step_id=st.id, card_id=self.card.card_id)

    def _next_check(self, label: EvidenceLabel) -> tuple[Optional[Cue], str, EvidenceLabel]:
        """The next untried CHECK for 'that did not work'. Order: the current step's checks (card order = most likely first), then the
        checks of steps the wearer already confirmed, most recent first (a finished step can be the cause). Steps not reached yet are never
        consulted. A check with a telemetry predicate is offered only while measured data satisfies it. Source-link entries are not checks."""
        last = self.last_obs
        earlier = [s for s in reversed(self.card.steps[: self.index]) if s.id in self.confirmed or s.id in self.verified]
        for st in [self.step, *earlier]:
            for i, chk in enumerate(st.troubleshoot):
                if (st.id, i) in self._tried or chk.action.line1.startswith("CHECK SOURCE"):
                    continue
                if chk.when and not (last is not None and eval_all(chk.when, last)):
                    continue
                self._tried.append((st.id, i))
                detail = chk.why
                if st.id != self.step.id:
                    detail += f" (From step {self.card.steps.index(st) + 1}, which you already confirmed: {_cue_text(st.cue).capitalize()}.)"
                self._event(f"problem reported; suggested check {len(self._tried)}: {_cue_text(chk.action)}", "INFERRED",
                            {"step": self.step.id, "from_step": st.id, "tried": len(self._tried)})
                return chk.action, detail, label
        if self._tried:
            n = len(self._tried)
            self._event(f"problem reported; all {n} checks in this card were already suggested", "DETERMINISTIC", {"step": self.step.id, "tried": n})
            return (Cue(line1="NO MORE CHECKS HERE", line2="SEE PHONE"),
                    f"You have already tried {n} check{'s' if n != 1 else ''} from this guide. The card has no further suggestions for this problem.",
                    "DETERMINISTIC")
        return None, "", label

    # ------------------------------------------------------------------ assistant hooks (router.py, assistant/service.py)
    def specific_terms(self, text: str) -> set[str]:
        """Content words of an utterance that name a subject (not 'where', 'how', 'this'...). Empty = a plain command."""
        from .assistant.router import specific_terms

        return specific_terms(text)

    def checks_remaining(self) -> int:
        """How many documented checks the next 'that did not work' could still offer (current step, then confirmed earlier steps)."""
        earlier = [s for s in reversed(self.card.steps[: self.index]) if s.id in self.confirmed or s.id in self.verified]
        last = self.last_obs
        n = 0
        for st in [self.step, *earlier]:
            for i, chk in enumerate(st.troubleshoot):
                if (st.id, i) in self._tried or chk.action.line1.startswith("CHECK SOURCE"):
                    continue
                if chk.when and not (last is not None and eval_all(chk.when, last)):
                    continue
                n += 1
        return n

    def tried_checks(self) -> list[str]:
        out = []
        for sid, i in self._tried:
            st = next((x for x in self.card.steps if x.id == sid), None)
            if st is not None and i < len(st.troubleshoot):
                out.append(_cue_text(st.troubleshoot[i].action))
        return out

    def show_ask(self, cue: Cue, ttl_ms: int = ASK_TTL_MS, *, after_previous: bool = False, pending: bool = False) -> None:
        """Show a short status on the glasses for a while, then return to the step. A new status replaces an older answer page."""
        now = self.clock.now_ms()
        if not after_previous:
            self._flashes = [f for f in self._flashes if f.consumes_input]
        if self.answer_data is not None:
            self.answer_data = None
            self._save()
        if pending:
            self.pending_dismissed = False
        start = max([now] + [f.end for f in self._flashes if f.kind == "ask"]) if after_previous else now
        self._flashes.append(_Flash(Screen.ask(cue, ttl_ms=ttl_ms), start, start + ttl_ms, "ask", pending=pending))
        self._refresh(immediate=True)

    def show_answer(self, text: str, *, cue: Cue, grounding="guide", label="INFERRED") -> None:
        """A full answer, paged on the glasses, open until the wearer returns. GB_ANSWER_PAGES=0 restores the short timed cue."""
        if os.getenv("GB_ANSWER_PAGES", "1") == "0":
            self.show_ask(cue)
            return
        self._flashes = [f for f in self._flashes if f.kind != "ask"]
        self.answer_data = {"text": text, "cue": cue.model_dump(), "grounding": grounding,
                            "label": label, "step_id": self.step.id}
        self.answer_index = 0
        self._save()
        self._refresh(immediate=True)

    def dismiss_ask(self) -> None:
        """Dismiss only the transient answer, keeping the same step and diagram."""
        self._flashes = [f for f in self._flashes if f.kind != "ask"]
        self.answer_data = None
        self._save()
        self._refresh(immediate=True)

    def note_ai_answer(self, question: str, grounding: str) -> None:
        """Evidence log: an assistant answer was shown. It is model-written (from the guide and/or general knowledge), never a measurement."""
        self._event(f'AI answer ({grounding}) to "{question[:100]}"', "INFERRED", {"step": self.step.id, "grounding": grounding})

    def _ask_navigate(self, intent: str, now: int) -> AskResult:
        gesture = {"next": "swipe_down", "back": "swipe_up", "picture": "press"}[intent]  # press shows / cycles pictures
        before = (self.index, self.done, self.view_idx, tuple(self.confirmed))
        self.handle_input(G2Input(gesture=gesture, seq_seen=self.hud.current.seq), from_ask=True)  # type: ignore[arg-type]
        cur = self.hud.current
        cue = cur.cue or Cue(line1="OK", line2="")
        moved = before != (self.index, self.done, self.view_idx, tuple(self.confirmed))
        return AskResult(
            intent=intent, answered=moved or cur.mode in ("uncertain", "ask"), cue=cue, text=_cue_text(cue), detail="",
            label="DETERMINISTIC", step_id=self.step.id, card_id=self.card.card_id,
        )

    def _question_matches_step(self, text: str) -> bool:
        """Deictic questions refer to this step; named subjects need card support.

        This conservative lexical check abstains on unrelated topics rather than
        presenting the current step's explanation as an answer about anything.
        It never fabricates knowledge or uses a provider on the cue path.
        """
        conversational = {"where", "why", "how", "there", "here", "that", "this", "these", "those", "it", "does",
                          "should", "would", "could", "please", "tell", "explain", "show", "look", "like", "correct",
                          "matter", "important", "reason", "part", "thing", "go", "connect", "do", "step", "done",
                          "finish", "when", "more", "simply", "again", "exactly", "really", "need", "suppos",
                          "wait", "hold", "hey", "okay", "well", "actually", "sorry", "um", "umm", "uh", "er", "hmm", "ok", "just", "now", "right",
                          "confused", "lost", "sure", "can", "you", "mean", "closer", "bigger", "picture", "photo", "image",
                          "finished", "result", "end", "know", "worked", "work", "working", "tell", "state", "looks", "supposed"}
        terms = {t.strip("'") for t in intent_mod._content(text)} - conversational - {"", "it", "s"}
        if not terms:
            return True
        st = self.step
        context = " ".join([self.card.title, st.title, st.detail, _cue_text(st.cue),
                            _cue_text(st.where) if st.where else "", _cue_text(st.why) if st.why else ""])
        return bool(terms & intent_mod._content(context))

    # ------------------------------------------------------------------ misc
    def _event(self, text: str, label: EvidenceLabel, evidence: Optional[dict] = None) -> None:
        ev = Evidence(at=self.clock.epoch_ms(), text=text, label=label, evidence=evidence or {})
        self.events.append(ev)
        if self.on_event is not None:
            try:
                self.on_event(ev)
            except Exception:
                log.exception("event sink failed")
