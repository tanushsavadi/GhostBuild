"""The assistant orchestrator. Brain calls run on worker threads; EVERY state change and HUD write happens on the main loop in pump().

Two conversations, both per session:
  intake - before a guide exists: ask the next useful question (max 3), learn the person's experience and situation, then start a
           ready guide or hand a context-rich request to live research.
  step   - while following a guide: answer a real question about the current step, optionally keep it as a note on that step.
If no brain is configured, or one call fails, callers fall back to the deterministic path: the product never depends on the model."""

from __future__ import annotations

import itertools
import json
import logging
import queue
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from contracts.models import Cue, GoalRequest, GoalResolution

from .. import goal as goal_mod
from ..cache import ANSWER_TTL_S, digest, question_key, reusable_question
from ..playbook import AskResult
from . import prompts
from .adaptive import TaskProfile, decide, question_key as intake_question_key, correction, new_goal, task_switch
from .brain import Brain, BrainError
from .cuefmt import cue_from_reply, fit_cue
from .router import route as route_utterance
from .schemas import IntakeReply, Message, Note, Profile, StepReply

if TYPE_CHECKING:  # pragma: no cover
    from ..runtime import Runtime

log = logging.getLogger("ghostbuild.assistant")

MAX_QUESTIONS = None  # no forced start: critical context, not a turn count, decides
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
    def __init__(
        self, rt: "Runtime", brain: Optional[Brain] = None, *, workers: int = 2
    ) -> None:
        self.rt, self.brain = rt, brain
        self._pool = (
            ThreadPoolExecutor(max_workers=workers, thread_name_prefix="gb-brain")
            if brain is not None
            else None
        )
        self._inbox: "queue.Queue[_Result]" = queue.Queue()
        self._ids = itertools.count(1)
        self._latest: dict[
            str, int
        ] = {}  # sid -> newest job id (an older answer is dropped: the wearer moved on)
        self.pending: dict[str, str] = {}  # sid -> "intake" | "step"
        self.chat: dict[str, list[Message]] = {}
        self.profiles: dict[str, Profile] = {}
        self.tasks: dict[str, TaskProfile] = {}
        self.intakes: dict[str, _Intake] = {}
        self.notes: dict[str, list[Note]] = {}
        self._contexts: dict[str, dict] = {}
        self._silent_jobs: set[int] = set()
        self._message_ids = itertools.count(1)
        self._path = (
            rt.cache.path.with_name("assistant.json")
            if rt.cache.path is not None
            else None
        )
        self._restore()

    def _restore(self):
        if self._path is None or not self._path.is_file():
            return
        try:
            raw = json.loads(self._path.read_text())
            self.tasks = {sid: TaskProfile.model_validate(t) for sid,t in raw.get("tasks", {}).items()}
            for sid,t in self.tasks.items():
                if t.phase == "intake" and t.pending_question:
                    self.intakes[sid] = _Intake(active=True, asked=len(t.asked), first_text=t.goal, mode=t.mode)
            self.chat = {
                sid: [Message.model_validate(m) for m in rows[-KEEP_MESSAGES:]]
                for sid, rows in raw.get("chat", {}).items()
            }
            self.profiles = {
                sid: Profile.model_validate(p)
                for sid, p in raw.get("profiles", {}).items()
            }
            self.notes = {
                sid: [Note.model_validate(n) for n in rows]
                for sid, rows in raw.get("notes", {}).items()
            }
        except (ValueError, OSError, TypeError, AttributeError):
            log.warning("conversation state could not be restored")

    def _persist(self):
        if self._path is None:
            return
        try:
            raw = {
                "tasks": {sid:t.model_dump() for sid,t in self.tasks.items()},
                "chat": {
                    s: [m.model_dump() for m in rows] for s, rows in self.chat.items()
                },
                "profiles": {s: p.model_dump() for s, p in self.profiles.items()},
                "notes": {
                    s: [n.model_dump() for n in rows] for s, rows in self.notes.items()
                },
            }
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(raw))
            tmp.replace(self._path)
        except OSError:
            log.warning("conversation state could not be persisted")

    def attach(self, brain: Optional[Brain], workers: int = 2) -> None:
        """(Re)configure the brain at runtime (tests, or a key added later)."""
        self.brain = brain
        if self._pool is not None:
            self._pool.shutdown(wait=False, cancel_futures=True)
        self._pool = (
            ThreadPoolExecutor(max_workers=workers, thread_name_prefix="gb-brain")
            if brain is not None
            else None
        )

    # ------------------------------------------------------------------ basics
    @property
    def enabled(self) -> bool:
        return self.brain is not None

    def _now(self) -> int:
        return self.rt.clock.epoch_ms()

    def _sid(self) -> Optional[str]:
        return self.rt.sessions.active_id

    def log(
        self, sid: str, role: str, text: str, kind: str = "info", **kw: Any
    ) -> Message:
        m = Message(
            id=f"{sid}-{self._now()}-{next(self._message_ids)}",
            role=role,
            task_id=self.tasks[sid].id if sid in self.tasks else "",
            text=text,
            kind=kind,
            at=self._now(),
            **kw,
        )  # type: ignore[arg-type]
        buf = self.chat.setdefault(sid, [])
        buf.append(m)
        del buf[:-KEEP_MESSAGES]
        self.rt.elog.write("assistant", who=role, topic=kind, text=text[:400])
        self._persist()
        return m

    def _submit(self, kind: str, sid: str, fn, ctx: dict) -> int:
        jid = next(self._ids)
        self._latest[sid] = jid
        self.pending[sid] = kind
        self._contexts[sid] = dict(ctx)

        if sid in self.tasks:
            ctx = {**ctx, "task_id":self.tasks[sid].id, "revision":self.tasks[sid].revision}

        def run() -> None:
            try:
                self._inbox.put(_Result(kind, jid, sid, payload=fn(), ctx=ctx))
            except BrainError as exc:
                self._inbox.put(_Result(kind, jid, sid, error=str(exc), ctx=ctx))
            except Exception as exc:  # a worker must never die silently
                log.exception("assistant job failed")
                self._inbox.put(
                    _Result(kind, jid, sid, error=type(exc).__name__, ctx=ctx)
                )

        assert self._pool is not None
        self._pool.submit(run)
        return jid

    def observe_goal(self, req):
        sid, text = req.session_id, (req.text or "").strip()
        if not text:
            return
        old = self.tasks.get(sid)
        active = self.intakes.get(sid)
        changed = old is None or ((new_goal(text) or task_switch(text)) and text != old.goal and not correction(text))
        if changed:
            self.cancel(sid)
            self.intakes[sid] = _Intake()
            self.tasks[sid] = TaskProfile(goal=text, mode=req.mode)
        task = self.tasks[sid]
        task.observe(text)
        if task.confirmation_pending and text.lower() in ("yes", "yes that's right", "correct"):
            task.confirmation_pending = ""
        if correction(text) and active:
            task.critical_unknowns = ["Confirm the corrected product, model or configuration"]
        self._persist()

    def _ready_card(self, text, mode, library_id=""):
        from ..cache import terms
        cards = self.rt.startable_cards()
        if library_id:
            # The model named a ready guide: accept it only if it is startable and the person's words really overlap it.
            card = next((c for c in cards if c.card_id == library_id and c.steps), None)
            if card is not None:
                said = terms(text) - {"wire", "wiring"}
                covered = terms(card.title + " " + " ".join(card.aliases))
                if len(said & covered) >= 2 or (said and said <= covered):
                    return card
        other = "fix" if mode == "build" else "build"
        chosen = goal_mod.candidates(GoalRequest(session_id=self._sid() or "", mode=mode, via="phone_text", text=text), cards) or \
            goal_mod.candidates(GoalRequest(session_id=self._sid() or "", mode=other, via="phone_text", text=text), cards)
        if len(chosen) != 1 or (library_id and chosen[0].card_id != library_id):
            return None
        card = chosen[0]
        requested = terms(text) - {"wire", "wiring"}
        covered = terms(card.title + " " + " ".join(card.aliases))
        # Courtesy words are ignored, but an unfamiliar identity cannot match merely on one shared noun.
        if not requested <= covered:
            return None
        return card if card.steps else None

    def reference_notes(self, text):
        path = self.rt.asset_root / "knowledge" / "intake_references.json"
        try:
            refs = json.loads(path.read_text())
            task = self.tasks.get(self._sid())
            query = (text + " " + (task.goal if task else "")).lower()
            selected = [r for r in refs if any(k.lower() in query for k in r.get("keywords", []))]
            if task:
                for r in selected:
                    if r["url"] not in task.sources:
                        task.sources.append(r["url"])
            return json.dumps(selected)
        except (OSError, ValueError, TypeError):
            return "No trusted identification reference is loaded. Offer a model-label/manual lookup; do not invent a visual or procedure."

    def resume_question(self, sid):
        """After a restart: put a still-open interview question back on the glasses (never an answered one)."""
        task, st = self.tasks.get(sid or ""), self.intakes.get(sid or "")
        sess = self.rt.sessions.active
        if task is None or st is None or not st.active or not task.pending_question or sess is None or sess.phase != "menu":
            return
        self.rt.sessions.show_convo(sid, fit_cue(task.pending_question))

    def bind_card(self, card, sid=None):
        sid = sid or self._sid()
        if not sid:
            return
        task = self.tasks.setdefault(sid, TaskProfile(goal=card.title, mode=card.goal_mode))
        task.phase, task.pending_question = "task", ""
        task.sources = list(dict.fromkeys(task.sources + [s.url for s in card.sources if s.url]))
        task.record("START_GUIDE", "Selected sourced card " + card.card_id)
        self._persist()

    # ------------------------------------------------------------------ intake: before a guide exists
    def wants_goal(self, req: GoalRequest) -> bool:
        sess = self.rt.sessions.active
        return (
            self.enabled
            and req.via in ("voice", "phone_text")
            and bool((req.text or "").strip())
            and sess is not None
            and sess.id == req.session_id
            and sess.phase == "menu"
            and self.rt.live.active is None
        )

    def submit_goal(self, req: GoalRequest) -> GoalResolution:
        sid, text = req.session_id, (req.text or "").strip()
        if sid not in self.tasks:
            self.observe_goal(req)
        st = self.intakes.setdefault(sid, _Intake())
        if not st.active:
            st.active, st.asked, st.first_text, st.mode = True, 0, text, req.mode
        self.log(sid, "user", text, "intake")
        prof = self.profiles.setdefault(sid, Profile())
        system = (
            prompts.INTAKE_SYSTEM
            + "\n\n"
            + prompts.intake_context(self.rt.startable_cards(), prof, st.asked)
            + "\nSTRUCTURED TASK (user facts and inferences are distinct):\n" + self.tasks[sid].model_dump_json()
            + "\nTRUSTED REFERENCE NOTES:\n" + self.reference_notes(text)
        )
        messages = prompts.to_messages([m for m in self.chat[sid][:-1] if m.task_id == self.tasks[sid].id], text, kind="intake")
        self.rt.sessions.show_convo(sid, THINKING)
        self._submit(
            "intake", sid, lambda: self.brain.intake(system, messages), {"req": req}
        )  # type: ignore[union-attr]
        return GoalResolution(
            session_id=sid,
            status="unsupported",
            mode=req.mode,
            cue=THINKING,
            conversing=True,
            detail="Talking it through first so the guide fits you. Answer on the glasses or the phone.",
        )

    def _apply_intake(self, r: _Result) -> None:
        sid, req = r.sid, r.ctx["req"]
        st = self.intakes.setdefault(sid, _Intake())
        reply: Optional[IntakeReply] = r.payload
        if r.error or reply is None:
            task = self.tasks.get(sid)
            ready = self._ready_card(st.first_text, st.mode)
            st.active = False
            self.rt.sessions.clear_convo(sid)
            if ready is not None and not (task and task.critical_unknowns):
                self.rt.resolve_goal_direct(req)
            else:
                self.log(sid, "system", "The assistant is unavailable. I need the missing product or safety details before choosing a procedure. Text and ready sourced guides still work.", "intake")
                if task:
                    task.phase = "blocked"
                    task.record("ESCALATE_OR_STOP", "Assistant unavailable while critical context unresolved")
                self.rt.sessions.flash_message(sid, Cue(line1="NEED MORE CONTEXT", line2="TEXT OR PICK A GUIDE"), 6000)
            self._persist()
            return
        self.profiles[sid] = self.profiles.get(sid, Profile()).merged(reply.profile)
        task = self.tasks.setdefault(sid, TaskProfile(goal=st.first_text, mode=st.mode))
        task.phase = "intake"
        task.merge(reply.facts)
        task.critical_unknowns = list(reply.critical_unknowns)
        task.branch = reply.branch or task.branch
        task.confidence = reply.confidence
        ready = self._ready_card(st.first_text, st.mode, reply.library_id) or (
            self._ready_card(reply.goal, st.mode, reply.library_id) if reply.goal else None)
        decision = decide(reply, task, ready_exact=ready is not None)
        if task.confirmation_pending and decision in ("RESEARCH", "START_GUIDE"):
            decision = "REQUEST_CONFIRMATION"
            reply.say = "Please confirm the exact request before I choose a procedure: " + task.confirmation_pending
        task.record(decision, reply.question_reason or reply.say)
        action = "ask" if decision in ("ASK_QUESTION", "IDENTIFY_PRODUCT", "REQUEST_CONFIRMATION", "EXPLAIN", "SHOW_VISUAL") else "decline" if decision == "ESCALATE_OR_STOP" else "start"
        if decision == "ESCALATE_OR_STOP" and reply.action != "decline":
            missing = "; ".join(task.critical_unknowns) or "a reliable identification or a usable source"
            reply.say = "I still need " + missing + ". I cannot safely choose the procedure yet. You can give a model, reference link, or change tasks."
            reply.cue1, reply.cue2 = "MORE CONTEXT NEEDED", "SEE PHONE OR CHANGE TASK"
        if decision in ("EXPLAIN", "SHOW_VISUAL") and reply.identification_help:
            reply.say = reply.identification_help
        if decision == "REQUEST_CONFIRMATION":
            task.confirmation_pending = req.text or ""
        if action == "ask":
            if ready is None and decision == "ASK_QUESTION" and (reply.goal or st.first_text):
                self.rt.live.prefetch(task.id + ":" + str(task.revision), reply.goal or st.first_text)  # research while conversing
            st.asked += 1
            task.pending_question = reply.say
            key = intake_question_key(reply)
            if key not in task.asked:
                task.asked.append(key)
            self.log(
                sid,
                "assistant",
                reply.say,
                "intake",
                quick_replies=[q[:28] for q in reply.quick_replies[:4]],
                speak=True,
            )
            self.rt.sessions.show_convo(
                sid, cue_from_reply(reply.cue1, reply.cue2, reply.say)
            )
        elif action == "decline":
            st.active = False
            task.phase = "blocked"
            task.pending_question = ""
            self.log(sid, "assistant", reply.say, "intake", speak=True)
            self.rt.sessions.flash_message(
                sid,
                cue_from_reply(reply.cue1, reply.cue2, "NOT SOMETHING I CAN HELP WITH"),
                6000,
            )
        else:
            self._begin(sid, req, reply, st)
        self._persist()

    def _begin(
        self, sid: str, req: GoalRequest, reply: IntakeReply, st: _Intake
    ) -> None:
        st.active = False
        goal = (reply.goal or "").strip() or st.first_text or (req.text or "")
        if reply.say:
            self.log(sid, "assistant", reply.say, "intake", speak=True)
        card = self._ready_card(st.first_text, st.mode, reply.library_id) or (
            self._ready_card(goal, st.mode, reply.library_id) if goal != st.first_text else None)
        task = self.tasks.get(sid)
        if task:
            task.pending_question = ""
            task.phase = "task" if card is not None else "research"
        if card is not None:
            self.rt.sessions.clear_convo(sid)
            self.rt.cache.remember_guide(
                st.first_text, st.mode, card, self.rt.live.cards.get(card.card_id)
            )
            self.rt.cache.remember_guide(
                goal, st.mode, card, self.rt.live.cards.get(card.card_id)
            )
            self.rt.sessions.start_card(sid, card)
            return
        self.rt.sessions.clear_convo(sid)
        clarified = GoalRequest(session_id=sid, mode=st.mode, via="phone_text", text=goal)
        d = self.rt.discovery
        if d is not None and d.wants(clarified):
            if task:
                task.phase = "intake"
            d.submit(clarified)  # the conversation named a product source: identify the real product before any manual
            return
        self.rt.resolve_goal_direct(clarified)  # -> live research with context

    def audience_for(self, sid: Optional[str]) -> Optional[str]:
        """What a researcher should know about the person, from their own words (<= 480 chars)."""
        if not sid or sid not in self.profiles:
            return None
        said = " ".join(
            m.text
            for m in self.chat.get(sid, [])
            if m.role == "user" and m.kind == "intake"
        )
        text = self.profiles[sid].describe() + (
            f" In their own words: {said}" if said else ""
        )
        return text[:480]

    def cancel(self, sid: str) -> None:
        """The wearer left the conversation (swipe up): drop the pending answer and end the intake."""
        self._latest[sid] = next(self._ids)
        self.pending.pop(sid, None)
        self._contexts.pop(sid, None)
        if sid in self.intakes:
            self.intakes[sid].active = False

    # ------------------------------------------------------------------ step: while following a guide
    def route(self, text: str, pb) -> str:
        sid = self._sid()
        return route_utterance(
            text,
            pb,
            assistant_available=self.enabled
            or self._cached_reply(text, pb) is not None,
            has_notes=bool(sid and self._notes_for(pb)),
        )

    def _notes_for(self, pb) -> list[Note]:
        sid = self._sid()
        return [
            n
            for n in self.notes.get(sid or "", [])
            if n.card_id == pb.card.card_id and n.step_id == pb.step.id
        ]

    def _product_context(self, sid, pb):
        d = self.rt.discovery
        s = d.state(sid) if d is not None else None
        return (
            {"product": s.selected.model_dump(), "configuration": s.config}
            if s is not None and s.selected is not None and s.card_id == pb.card.card_id
            else None
        )

    def _answer_key(self, text, pb):
        if (
            not self.rt.cache.enabled
            or not reusable_question(text)
            or pb.step.verify is not None
        ):
            return None
        sid = self._sid()
        return digest(
            {
                "v": 1,
                "card": pb.card.model_dump(mode="json"),
                "step": pb.step.id,
                "question": question_key(text),
                "profile": (self.profiles.get(sid) or Profile()).model_dump(),
                "product": self._product_context(sid, pb),
                "confirmed": sorted(pb.confirmed),
                "tried": pb.tried_checks(),
                "task": self.tasks[sid].signature() if sid in self.tasks else None,
            }
        )

    def _cached_reply(self, text, pb):
        key = self._answer_key(text, pb)
        value = self.rt.cache.get("answers", key) if key else None
        try:
            return StepReply.model_validate(value) if value else None
        except ValueError:
            return None

    def record_guide_answer(self, text, result):
        sid = self._sid()
        if not sid:
            return
        ctx = {"card_id": result.card_id, "step_id": result.step_id}
        self.log(sid, "user", text, "step", **ctx)
        self.log(
            sid,
            "assistant",
            result.as_json()["text"],
            "step",
            grounding="guide" if result.answered else "unsure",
            **ctx,
        )

    def submit_question(self, text: str) -> AskResult:
        pb, sid = self.rt.playbook, self._sid()
        assert pb is not None and sid is not None
        st = pb.step
        task = self.tasks.setdefault(sid, TaskProfile(goal=pb.card.title, phase="task"))
        task.observe(text, revise=False)  # an identity correction mid-step is routed before this (Runtime.ask)
        ctx = {
            "text": text,
            "card_id": pb.card.card_id,
            "step_id": st.id,
            "cache_key": self._answer_key(text, pb),
        }
        reply = self._cached_reply(text, pb)
        if reply is not None:
            self.cancel(sid)
            self.log(
                sid,
                "user",
                text,
                "step",
                card_id=ctx["card_id"],
                step_id=ctx["step_id"],
            )
            self._apply_step(
                _Result("step", 0, sid, payload=reply, ctx={**ctx, "cached": True})
            )
            return AskResult(
                intent="assistant",
                answered=True,
                cue=cue_from_reply(reply.cue1, reply.cue2, reply.answer),
                text=reply.answer,
                detail="Saved answer from this guide and configuration.",
                label="INFERRED",
                step_id=st.id,
                card_id=pb.card.card_id,
                cached=True,
            )
        assert self.brain is not None
        system = (
            prompts.STEP_SYSTEM
            + "\n\n"
            + prompts.step_context(
                pb.card,
                pb.index,
                confirmed=pb.confirmed,
                tried=pb.tried_checks(),
                notes=[
                    n for n in self.notes.get(sid, []) if n.card_id == pb.card.card_id
                ],
                profile=self.profiles.get(sid),
                product=self._product_context(sid, pb),
                observations=[o["text"] for o in pb.observations],
            )
        )
        system += "\nSTRUCTURED TASK:\n" + task.model_dump_json()
        history = [
            m
            for m in self.chat.get(sid, [])
            if m.kind == "step"
            and m.card_id == ctx["card_id"]
            and m.step_id == ctx["step_id"]
        ]
        messages = prompts.to_messages(history, text, kind="step")
        self.log(
            sid, "user", text, "step", card_id=ctx["card_id"], step_id=ctx["step_id"]
        )
        pb.show_ask(THINKING, 25_000, pending=True)
        self._submit("step", sid, lambda: self.brain.step(system, messages), ctx)
        return AskResult(
            intent="assistant",
            answered=False,
            cue=THINKING,
            text="Thinking…",
            detail="",
            label="DETERMINISTIC",
            step_id=st.id,
            card_id=pb.card.card_id,
            pending=True,
        )

    def recall_note(self, text: str) -> AskResult:
        pb = self.rt.playbook
        assert pb is not None
        note = self._notes_for(pb)[-1]
        cue = fit_cue(note.answer)
        pb.show_answer(note.answer, cue=cue, grounding=note.grounding)
        return AskResult(
            intent="notes",
            answered=True,
            cue=cue,
            text=note.answer,
            detail=note.title,
            label="INFERRED",
            step_id=pb.step.id,
            card_id=pb.card.card_id,
        )

    def _apply_step(self, r: _Result) -> None:
        sid, ctx = r.sid, r.ctx
        pb = self.rt.playbook
        reply: Optional[StepReply] = r.payload
        here = (
            pb is not None
            and self._sid() == sid
            and pb.card.card_id == ctx["card_id"]
            and pb.step.id == ctx["step_id"]
            and r.jid not in self._silent_jobs
            and not pb.pending_dismissed
        )
        if r.error or reply is None:
            self.log(
                sid,
                "system",
                "I could not reach the assistant just now. The guide's own text is still here.",
                "step",
                card_id=ctx["card_id"],
                step_id=ctx["step_id"],
            )
            if here:
                pb.show_ask(Cue(line1="CAN'T ANSWER NOW", line2="SEE PHONE"), 4000)
            return
        task = self.tasks.get(sid)
        if task:
            task.merge(reply.facts)
            task.critical_unknowns = list(reply.critical_unknowns)
            task.branch = reply.branch or task.branch
            task.record(reply.decision, ctx["text"])
        cached = bool(ctx.get("cached"))
        self.log(
            sid,
            "assistant",
            reply.answer,
            "step",
            speak=True,
            grounding=reply.grounding,
            card_id=ctx["card_id"],
            step_id=ctx["step_id"],
            cached=cached,
            quick_replies=[q[:28] for q in reply.quick_replies[:4]]
            if reply.follow_up
            else [],
        )
        if (
            not cached
            and ctx.get("cache_key")
            and reply.grounding == "guide"
            and not reply.follow_up
        ):
            self.rt.cache.put(
                "answers", ctx["cache_key"], reply.model_dump(), ttl=ANSWER_TTL_S
            )
        if reply.add_note and not any(
            n.question == ctx["text"]
            and n.card_id == ctx["card_id"]
            and n.step_id == ctx["step_id"]
            for n in self.notes.get(sid, [])
        ):
            self.notes.setdefault(sid, []).append(
                Note(
                    card_id=ctx["card_id"],
                    step_id=ctx["step_id"],
                    title=(reply.note_title or "Extra help")[:40],
                    question=ctx["text"],
                    answer=reply.answer,
                    grounding=reply.grounding,
                    at=self._now(),
                )
            )
        if here:
            pb.show_answer(reply.answer + (" " + reply.follow_up if reply.follow_up else ""),
                cue=cue_from_reply(reply.cue1, reply.cue2, reply.answer), grounding=reply.grounding)
            pb.note_ai_answer(ctx["text"], reply.grounding)
            if reply.follow_up:
                self.log(
                    sid,
                    "assistant",
                    reply.follow_up,
                    "step",
                    speak=True,
                    card_id=ctx["card_id"],
                    step_id=ctx["step_id"],
                    quick_replies=[q[:28] for q in reply.quick_replies[:4]],
                )


        self._persist()

    # ------------------------------------------------------------------ main loop
    def pump(self) -> None:
        while True:
            try:
                r = self._inbox.get_nowait()
            except queue.Empty:
                return
            task = self.tasks.get(r.sid)
            stale_task = task is not None and r.ctx.get("task_id") and (task.id != r.ctx["task_id"] or task.revision != r.ctx.get("revision"))
            if self._latest.get(r.sid) != r.jid or stale_task:
                continue  # superseded or cancelled
            self.pending.pop(r.sid, None)
            self._contexts.pop(r.sid, None)
            (self._apply_intake if r.kind == "intake" else self._apply_step)(r)
            self._silent_jobs.discard(r.jid)

    # ------------------------------------------------------------------ view (phone)
    def state(self) -> dict:
        sid = self._sid()
        pb = self.rt.playbook if self.rt.session().phase == "task" else None
        st = self.intakes.get(sid or "")
        return {
            "enabled": self.enabled,
            "model": getattr(self.brain, "name", None),
            "session_id": sid,
            "pending": self.pending.get(sid or ""),
            "pending_step": self._contexts.get(sid or "")
            if self.pending.get(sid or "") == "step"
            else None,
            "current_step": {
                "card_id": pb.card.card_id,
                "step_id": pb.step.id,
                "index": pb.index,
                "title": pb.step.title,
            }
            if pb is not None
            else None,
            "task_profile": self.tasks[sid].model_dump() if sid in self.tasks else None,
            "metrics": self.tasks[sid].metrics() if sid in self.tasks else None,
            "cache": self.rt.cache.status(),
            "messages": [m.model_dump() for m in self.chat.get(sid or "", [])[-40:]],
            "notes": [
                n.model_dump()
                for n in self.notes.get(sid or "", [])
                if pb is not None and n.card_id == pb.card.card_id
            ],
            "profile": (self.profiles.get(sid or "") or Profile()).model_dump(),
            "intake": {
                "active": bool(st and st.active),
                "asked": st.asked if st else 0,
                "max": MAX_QUESTIONS,
            },
        }

    def dismiss(self, sid: str, card_id: str, step_id: str) -> bool:
        pb = self.rt.playbook
        if (
            sid != self._sid()
            or pb is None
            or pb.card.card_id != card_id
            or pb.step.id != step_id
        ):
            return False
        if sid in self.pending:
            self._silent_jobs.add(self._latest[sid])
        pb.dismiss_ask()
        return True

    def close(self):
        self._persist()
        if self._pool is not None:
            self._pool.shutdown(wait=False, cancel_futures=True)
