"""The assistant orchestrator. Brain calls run on worker threads; EVERY state change and HUD write happens on the main loop in pump().

Two conversations, both per session:
  intake - before a guide exists: ask the next useful question (max 3), learn the person's experience and situation, then start a
           ready guide or hand a context-rich request to live research.
  step   - while following a guide: answer a real question about the current step, optionally keep it as a note on that step.
If no brain is configured, or one call fails, callers fall back to the deterministic path: the product never depends on the model."""

from __future__ import annotations

import itertools
import logging
import queue
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from contracts.models import Cue, GoalRequest, GoalResolution

from .. import goal as goal_mod
from ..playbook import AskResult
from . import prompts
from .brain import Brain, BrainError
from .cuefmt import cue_from_reply, fit_cue
from .router import route as route_utterance
from .schemas import IntakeReply, Message, Note, Profile, StepReply

if TYPE_CHECKING:  # pragma: no cover
    from ..runtime import Runtime

log = logging.getLogger("ghostbuild.assistant")

MAX_QUESTIONS = 3
KEEP_MESSAGES = 60
THINKING = Cue(line1="THINKING", line2="")


@dataclass
class _Intake:
    active: bool = False
    asked: int = 0
    first_text: str = ""
    mode: str = "build"


@dataclass
class _Result:
    kind: str
    jid: int
    sid: str
    payload: Any = None
    error: Optional[str] = None
    ctx: dict = field(default_factory=dict)


class Assistant:
    def __init__(self, rt: "Runtime", brain: Optional[Brain] = None, *, workers: int = 2) -> None:
        self.rt, self.brain = rt, brain
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="gb-brain") if brain is not None else None
        self._inbox: "queue.Queue[_Result]" = queue.Queue()
        self._ids = itertools.count(1)
        self._latest: dict[str, int] = {}        # sid -> newest job id (an older answer is dropped: the wearer moved on)
        self.pending: dict[str, str] = {}        # sid -> "intake" | "step"
        self.chat: dict[str, list[Message]] = {}
        self.profiles: dict[str, Profile] = {}
        self.intakes: dict[str, _Intake] = {}
        self.notes: dict[str, list[Note]] = {}

    def attach(self, brain: Optional[Brain], workers: int = 2) -> None:
        """(Re)configure the brain at runtime (tests, or a key added later)."""
        self.brain = brain
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="gb-brain") if brain is not None else None

    # ------------------------------------------------------------------ basics
    @property
    def enabled(self) -> bool:
        return self.brain is not None

    def _now(self) -> int:
        return self.rt.clock.epoch_ms()

    def _sid(self) -> Optional[str]:
        return self.rt.sessions.active_id

    def log(self, sid: str, role: str, text: str, kind: str = "info", **kw: Any) -> Message:
        m = Message(role=role, text=text, kind=kind, at=self._now(), **kw)  # type: ignore[arg-type]
        buf = self.chat.setdefault(sid, [])
        buf.append(m)
        del buf[:-KEEP_MESSAGES]
        self.rt.elog.write("assistant", who=role, topic=kind, text=text[:400])
        return m

    def _submit(self, kind: str, sid: str, fn, ctx: dict) -> int:
        jid = next(self._ids)
        self._latest[sid] = jid
        self.pending[sid] = kind

        def run() -> None:
            try:
                self._inbox.put(_Result(kind, jid, sid, payload=fn(), ctx=ctx))
            except BrainError as exc:
                self._inbox.put(_Result(kind, jid, sid, error=str(exc), ctx=ctx))
            except Exception as exc:  # a worker must never die silently
                log.exception("assistant job failed")
                self._inbox.put(_Result(kind, jid, sid, error=type(exc).__name__, ctx=ctx))

        assert self._pool is not None
        self._pool.submit(run)
        return jid

    # ------------------------------------------------------------------ intake: before a guide exists
    def wants_goal(self, req: GoalRequest) -> bool:
        sess = self.rt.sessions.active
        return (self.enabled and req.via in ("voice", "phone_text") and bool((req.text or "").strip())
                and sess is not None and sess.id == req.session_id and sess.phase == "menu" and self.rt.live.active is None)

    def submit_goal(self, req: GoalRequest) -> GoalResolution:
        sid, text = req.session_id, (req.text or "").strip()
        st = self.intakes.setdefault(sid, _Intake())
        if not st.active:
            st.active, st.asked, st.first_text, st.mode = True, 0, text, req.mode
        self.log(sid, "user", text, "intake")
        prof = self.profiles.setdefault(sid, Profile())
        system = prompts.INTAKE_SYSTEM + "\n\n" + prompts.intake_context(self.rt.cards, prof, st.asked)
        messages = prompts.to_messages(self.chat[sid][:-1], text, kind="intake")
        self.rt.sessions.show_convo(sid, THINKING)
        self._submit("intake", sid, lambda: self.brain.intake(system, messages), {"req": req})  # type: ignore[union-attr]
        return GoalResolution(session_id=sid, status="unsupported", mode=req.mode, cue=THINKING, conversing=True,
                              detail="Talking it through first so the guide fits you. Answer on the glasses or the phone.")

    def _apply_intake(self, r: _Result) -> None:
        sid, req = r.sid, r.ctx["req"]
        st = self.intakes.setdefault(sid, _Intake())
        reply: Optional[IntakeReply] = r.payload
        if r.error or reply is None:
            self.log(sid, "system", "I could not think just now, so I will go ahead without questions.")
            st.active = False
            self.rt.sessions.clear_convo(sid)
            self.rt.resolve_goal_direct(req)
            return
        self.profiles[sid] = self.profiles.get(sid, Profile()).merged(reply.profile)
        action = reply.action
        if action == "ask" and st.asked >= MAX_QUESTIONS:
            action = "start"
        if action == "ask":
            st.asked += 1
            self.log(sid, "assistant", reply.say, "intake", quick_replies=[q[:28] for q in reply.quick_replies[:4]], speak=True)
            self.rt.sessions.show_convo(sid, cue_from_reply(reply.cue1, reply.cue2, reply.say))
        elif action == "decline":
            st.active = False
            self.log(sid, "assistant", reply.say, "intake", speak=True)
            self.rt.sessions.flash_message(sid, cue_from_reply(reply.cue1, reply.cue2, "NOT SOMETHING I CAN HELP WITH"), 6000)
        else:
            self._begin(sid, req, reply, st)

    def _begin(self, sid: str, req: GoalRequest, reply: IntakeReply, st: _Intake) -> None:
        st.active = False
        goal = (reply.goal or "").strip() or st.first_text or (req.text or "")
        if reply.say:
            self.log(sid, "assistant", reply.say, "intake", speak=True)
        card = next((c for c in self.rt.startable_cards() if c.card_id == reply.library_id and c.steps), None)
        if card is None:  # no explicit match: let the deterministic matcher try the clarified goal before paying for research
            for mode in dict.fromkeys((st.mode, "fix" if st.mode == "build" else "build")):
                cands = goal_mod.candidates(GoalRequest(session_id=sid, mode=mode, via="phone_text", text=goal), self.rt.startable_cards())
                if cands and cands[0].steps:
                    card = cands[0]
                    break
        if card is not None:
            self.rt.sessions.clear_convo(sid)
            self.rt.sessions.start_card(sid, card)
            return
        self.rt.sessions.clear_convo(sid)
        self.rt.resolve_goal_direct(GoalRequest(session_id=sid, mode=st.mode, via="phone_text", text=goal))  # -> live research with context

    def audience_for(self, sid: Optional[str]) -> Optional[str]:
        """What a researcher should know about the person, from their own words (<= 480 chars)."""
        if not sid or sid not in self.profiles:
            return None
        said = " ".join(m.text for m in self.chat.get(sid, []) if m.role == "user" and m.kind == "intake")
        text = self.profiles[sid].describe() + (f" In their own words: {said}" if said else "")
        return text[:480]

    def cancel(self, sid: str) -> None:
        """The wearer left the conversation (swipe up): drop the pending answer and end the intake."""
        self._latest[sid] = next(self._ids)
        self.pending.pop(sid, None)
        if sid in self.intakes:
            self.intakes[sid].active = False

    # ------------------------------------------------------------------ step: while following a guide
    def route(self, text: str, pb) -> str:
        sid = self._sid()
        return route_utterance(text, pb, assistant_available=self.enabled, has_notes=bool(sid and self._notes_for(pb)))

    def _notes_for(self, pb) -> list[Note]:
        sid = self._sid()
        return [n for n in self.notes.get(sid or "", []) if n.card_id == pb.card.card_id and n.step_id == pb.step.id]

    def submit_question(self, text: str) -> AskResult:
        pb, sid = self.rt.playbook, self._sid()
        assert pb is not None and sid is not None and self.brain is not None
        st = pb.step
        system = prompts.STEP_SYSTEM + "\n\n" + prompts.step_context(
            pb.card, pb.index, confirmed=pb.confirmed, tried=pb.tried_checks(),
            notes=[n for n in self.notes.get(sid, []) if n.card_id == pb.card.card_id], profile=self.profiles.get(sid))
        messages = prompts.to_messages(self.chat.get(sid, []), text, kind="step")
        self.log(sid, "user", text, "step")
        pb.show_ask(THINKING, 25_000)
        self._submit("step", sid, lambda: self.brain.step(system, messages),  # type: ignore[union-attr]
                     {"text": text, "card_id": pb.card.card_id, "step_id": st.id})
        return AskResult(intent="assistant", answered=False, cue=THINKING, text="Thinking…", detail="", label="DETERMINISTIC",
                         step_id=st.id, card_id=pb.card.card_id, pending=True)

    def recall_note(self, text: str) -> AskResult:
        pb = self.rt.playbook
        assert pb is not None
        note = self._notes_for(pb)[-1]
        cue = fit_cue(note.answer)
        pb.show_ask(cue, 7000)
        return AskResult(intent="notes", answered=True, cue=cue, text=note.answer, detail=note.title, label="INFERRED",
                         step_id=pb.step.id, card_id=pb.card.card_id)

    def _apply_step(self, r: _Result) -> None:
        sid, ctx = r.sid, r.ctx
        pb = self.rt.playbook
        reply: Optional[StepReply] = r.payload
        here = pb is not None and pb.card.card_id == ctx["card_id"]
        if r.error or reply is None:
            self.log(sid, "system", "I could not reach the assistant just now. The guide's own text is still here.", "step")
            if here:
                pb.show_ask(Cue(line1="CAN'T ANSWER NOW", line2="SEE PHONE"), 4000)
            return
        self.log(sid, "assistant", reply.answer, "step", speak=True, grounding=reply.grounding,
                 quick_replies=[q[:28] for q in reply.quick_replies[:4]] if reply.follow_up else [])
        if reply.add_note:
            self.notes.setdefault(sid, []).append(Note(card_id=ctx["card_id"], step_id=ctx["step_id"], title=(reply.note_title or "Extra help")[:40],
                                                      question=ctx["text"], answer=reply.answer, grounding=reply.grounding, at=self._now()))
        if here:
            pb.show_ask(cue_from_reply(reply.cue1, reply.cue2, reply.answer), 6500 if not reply.follow_up else 5000)
            pb.note_ai_answer(ctx["text"], reply.grounding)
            if reply.follow_up:
                self.log(sid, "assistant", reply.follow_up, "step", speak=True, quick_replies=[q[:28] for q in reply.quick_replies[:4]])
                pb.show_ask(fit_cue(reply.follow_up), 9000, after_previous=True)

    # ------------------------------------------------------------------ main loop
    def pump(self) -> None:
        while True:
            try:
                r = self._inbox.get_nowait()
            except queue.Empty:
                return
            if self._latest.get(r.sid) != r.jid:
                continue  # superseded or cancelled
            self.pending.pop(r.sid, None)
            (self._apply_intake if r.kind == "intake" else self._apply_step)(r)

    # ------------------------------------------------------------------ view (phone)
    def state(self) -> dict:
        sid = self._sid()
        pb = self.rt.playbook
        st = self.intakes.get(sid or "")
        return {
            "enabled": self.enabled, "model": getattr(self.brain, "name", None), "session_id": sid,
            "pending": self.pending.get(sid or ""),
            "messages": [m.model_dump() for m in self.chat.get(sid or "", [])[-40:]],
            "notes": [n.model_dump() for n in self.notes.get(sid or "", []) if pb is not None and n.card_id == pb.card.card_id],
            "profile": (self.profiles.get(sid or "") or Profile()).model_dump(),
            "intake": {"active": bool(st and st.active), "asked": st.asked if st else 0, "max": MAX_QUESTIONS},
        }
