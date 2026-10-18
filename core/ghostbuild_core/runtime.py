"""Runtime: wires cards, the single HUD writer, the engine, sessions and the log. The server is a thin shell on this."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Optional

from contracts.models import (
    Card,
    Cue,
    G2Hello,
    G2Input,
    GoalRequest,
    GoalResolution,
    Health,
    HudFrame,
    Observation,
    Session,
    Source,
    State,
)

from . import intent as intent_mod
from .clock import Clock, as_clock
from .cache import AppCache
from .cards import load_cards
from .engine import Engine
from .hud import Hud
from .log import EventLog
from .assistant.brain import brain_from_env
from .assistant.service import Assistant
from .live_research import LiveResearch
from .playbook import AskResult, PlaybookEngine
from .research import SAVED_DETAIL, ResearchQueue, SaveResult
from .session import SessionManager

log = logging.getLogger("ghostbuild.runtime")


class Runtime:
    def __init__(
        self,
        cards: list[Card],
        *,
        clock: Clock | Callable[[], int] | None = None,
        log_dir: Path | str | None = None,
        asset_root: Path | str | None = None,
        default_source: Source = "pi_live",
        simulate: bool = False,
        force_source: Optional[Source] = None,
        require_device_link: bool = False,
        brain: Optional[Any] = None,
    ) -> None:
        if not cards:
            raise ValueError("Runtime needs at least one valid Repair Card")
        self.clock = as_clock(clock)
        self.cache = AppCache(Path(log_dir) / "reuse-cache.json" if log_dir is not None else None)
        self.cards = list(cards)
        self.discovery = None
        self.require_device_link = require_device_link  # the real server sets it: a fault card starts only while its device reports
        self.asset_root = Path(asset_root) if asset_root is not None else Path.cwd()
        self.force_source = force_source
        self.started = self.clock.now_ms()
        self.elog = EventLog(log_dir, self.clock)
        self.hud = Hud(self.clock, source="simulated" if simulate and default_source == "pi_live" else default_source)
        self.hud.subscribe(lambda f: self.elog.write("frame", frame=f.model_dump(mode="json")))
        self.playbook: Optional[PlaybookEngine] = None  # set while the active task is a playbook (Card.steps)
        self._pb_sid: Optional[str] = None
        self.research = ResearchQueue(self.asset_root, self.clock)
        self.engine = self._make_engine(self._default_card())
        self.research_runs: Any = None  # ResearchRuns, attached by mount_research_runs when the server is built
        self.live = LiveResearch(self)
        for cached_card, review in self.cache.saved_guides():
            if all(c.card_id != cached_card.card_id for c in self.cards):
                self.cards.append(cached_card)
                if review:
                    self.live.cards[cached_card.card_id] = review
        self.assistant = Assistant(self, brain if brain is not None else brain_from_env())
        self.sim = None  # set below when simulating; startable_cards() reads it while sessions load
        self.voice = None  # optional VoiceService (voice.py), attached by its constructor; None = voice off (read while sessions load)
        sess_path = Path(log_dir) / "sessions.json" if log_dir is not None else None
        self.sessions = SessionManager(
            self.hud, self.clock, lambda: self.all_cards(), self._set_card, sess_path,
            record=lambda kind, **d: self.elog.write(kind, **d),
            refine=self._refine_unsupported,
            startable=self.startable_cards,
            voice_on=lambda: self.voice is not None,
            research_progress=lambda: self.live.progress(),
            on_convo_cancel=lambda sid: self.assistant.cancel(sid),
            recover=self.live.recover_draft,
        )
        self.sessions.restore()
        self.assistant.resume_question(self.sessions.active_id)  # an interview interrupted by a restart asks its open question again
        self.hud.session_id = self._sid()
        if simulate:
            from .simulate import SimPi

            self.sim = SimPi(self.clock)
        self._last_poll_ms: Optional[int] = None
        self.ws_clients = 0

    # ------------------------------------------------------------------ cards / engine
    def _default_card(self) -> Card:
        for c in self.cards:
            if c.goal_mode == "fix":
                return c
        return self.cards[0]

    def _make_engine(self, card: Card, passive: bool = False) -> Engine:
        return Engine(
            card, self.clock, hud=self.hud, asset_root=self.asset_root, force_source=self.force_source, passive=passive,
            on_event=lambda ev: self.elog.write("event", evidence=ev.model_dump(mode="json")),
        )

    def _set_card(self, card: Card, fresh: bool = False) -> None:
        """Activate the task on the glasses.

        A card with `steps` runs as a PLAYBOOK (PlaybookEngine). If it also has `tests`, the tests are ignored for now:
        the fault Engine stays PASSIVE (keeps link/camera bookkeeping for /health but writes no HUD screen).
        A card with only `tests` runs the original fault Engine, unchanged.
        """
        sid = self.sessions.active_id
        if hasattr(self, "assistant"):
            self.assistant.bind_card(card, sid)
        if card.steps:
            same = self.playbook is not None and self.playbook.card.card_id == card.card_id and self._pb_sid == sid
            if same and not fresh:
                return
            if self.engine.card.card_id != card.card_id or not self.engine.passive:
                self.engine = self._make_engine(card, passive=True)
            progress = None if fresh else self.sessions.get_progress(sid)
            self._pb_sid = sid
            self.playbook = PlaybookEngine(
                card, self.clock, hud=self.hud, asset_root=self.asset_root, force_source=self.force_source, progress=progress,
                on_event=lambda ev: self.elog.write("event", evidence=ev.model_dump(mode="json")),
                on_progress=lambda d, sid=sid: self.sessions.set_progress(sid, d),
            )
            self.playbook._save()
            if progress is None or not progress.get("confirmed"):
                self._answer_from_conversation(sid)
            if fresh:
                self.playbook.reveal()  # first step now, not after the HUD throttle
            return
        if self.playbook is not None:
            self.playbook.detach()
            self.playbook = None
            self._pb_sid = None
            self.engine = self._make_engine(card)
            self.engine.tick()
        elif self.engine.card.card_id != card.card_id or self.engine.passive:
            self.engine = self._make_engine(card)
            self.engine.tick()

    def reload_cards(self, directory: Path | str | None = None) -> dict:
        """Re-read the cards directory (default <asset_root>/knowledge/cards) without a restart, e.g. after `knowledge.approve`.

        Cards that exist only in memory are kept (disk wins on a card_id clash); a reload never leaves zero cards. The chooser reads
        `self.cards` each time it opens, so a new card is selectable immediately. The active session and task stay intact: if the
        active card's definition changed, a playbook keeps its position only when the ordered step ids are unchanged (otherwise it
        restarts at step 1). Returns {"loaded": n, "added": [ids], "changed": [ids], "active": "kept"|"updated"|"restarted"|"none"}.
        """
        d = Path(directory) if directory is not None else self.asset_root / "knowledge" / "cards"
        disk = load_cards(d)
        by_id = {c.card_id: c for c in disk}
        merged = disk + [c for c in self.cards if c.card_id not in by_id]
        if not merged:
            return {"loaded": len(self.cards), "added": [], "changed": [], "active": "none"}
        old = {c.card_id: c for c in self.cards}
        added = [c.card_id for c in merged if c.card_id not in old]
        changed = [c.card_id for c in merged if c.card_id in old and c.model_dump() != old[c.card_id].model_dump()]
        self.cards = merged
        active = "none"
        current = self.playbook.card if self.playbook is not None else (self.engine.card if self.sessions.active is not None and self.sessions.active.phase == "task" else None)
        if current is not None:
            new = self.card_by_id(current.card_id)
            if new is None or current.card_id not in changed:
                active = "kept"
            elif self.playbook is not None:
                same_steps = [s.id for s in new.steps] == [s.id for s in current.steps]
                self.playbook.detach()
                self.playbook = None
                self._set_card(new, fresh=not same_steps)  # progress is read back from the session unless fresh
                active = "updated" if same_steps else "restarted"
            else:
                self.engine = self._make_engine(new, passive=self.engine.passive)
                self.engine.tick()
                active = "updated"
        self.elog.write("event", text=f"cards reloaded: added={added} changed={changed} active={active}")
        log.info("cards reloaded: %d loaded, added=%s changed=%s active=%s", len(merged), added, changed, active)
        self.sessions.refresh()  # an open task list must show a card that was just approved
        return {"loaded": len(merged), "added": added, "changed": changed, "active": active}

    @property
    def active_card(self) -> Card:
        return self.playbook.card if self.playbook is not None else self.engine.card

    def _answer_from_conversation(self, sid: Optional[str]) -> None:
        """A guide that opens with a question the person already answered in conversation does not ask it again."""
        task = self.assistant.tasks.get(sid or "") if hasattr(self, "assistant") else None
        pb = self.playbook
        if task is None or pb is None:
            return
        said = [t for t in task.observations if t.strip()][-8:]
        for _ in range(3):
            if pb.step.kind != "question" or pb.done:
                return
            choice = next((c for c in (pb.match_choice(t) for t in reversed(said)) if c), None)
            if choice is None:
                return
            pb.choose(choice, via="earlier answer")

    def card_by_id(self, card_id: str) -> Optional[Card]:
        return next((c for c in self.all_cards() if c.card_id == card_id), None)

    def all_cards(self) -> list[Card]:
        return self.cards + (list(self.discovery.cards.values()) if self.discovery is not None else [])

    # ------------------------------------------------------------------ inputs
    def ingest(self, obs: Observation) -> bool:
        ok = self.engine.ingest(obs)
        if ok and self.playbook is not None:
            self.playbook.ingest(obs)  # optional telemetry: only measured steps look at it
        self.elog.write("observation", accepted=ok, obs=obs.model_dump(mode="json"))
        return ok

    def handle_input(self, gi: G2Input) -> HudFrame:
        self.elog.write("input", input=gi.model_dump(mode="json"))
        # A retry belongs to the frame the user saw. It must never act on a later
        # step after the first delivery already advanced. seq=0 is legacy tooling.
        if gi.gesture not in ("hold_start", "hold_end") and gi.seq_seen > 0 and gi.seq_seen < self.hud.current.seq:
            return self.hud.current
        if self.voice is not None and gi.gesture in ("hold_start", "hold_end"):
            self.voice.on_hold(gi.gesture)
        elif self.playbook is not None and self.playbook.done and gi.gesture in ("press", "swipe_down"):
            self.playbook.detach()  # finished: the next press / swipe-down opens the task list again (swipe-up reopens the last step)
            self.playbook, self._pb_sid = None, None
            self.sessions.return_to_menu()
        elif self.playbook is not None and self.sessions.flash_showing() and self.sessions.active is not None and self.sessions.active.phase == "task":
            self.sessions.dismiss_flash()  # the task-start cue hides the first step: a gesture only reveals it, never acts on it
            self.playbook.reveal()
        elif self.discovery is not None and self.discovery.handle_input(gi):
            pass
        elif not self.sessions.handle_input(gi):
            if self.playbook is not None:
                self.playbook.handle_input(gi)
            else:
                self.engine.handle_input(gi)
        self.hud.sync()
        return self.hud.current

    def hello(self, h: G2Hello) -> HudFrame:
        self.elog.write("input", hello=h.model_dump(mode="json"))
        self.sessions.hello(h)
        if self.discovery is not None:
            self.discovery.refresh()
        self.hud.session_id = self._sid()
        self.hud.sync()
        return self.hud.current

    def startable_cards(self) -> list[Card]:
        """Playbook cards always; a fault-mode card (checks only, no steps) only while its device is reporting (or simulated).
        Without this FIX on a bench with no device would open a card that can only say LINK LOST."""
        if not self.require_device_link:
            return list(self.cards)
        link_up = self.sim is not None or self.engine.link_status() == "up"
        return [c for c in self.cards if (c.steps or link_up) and not (
            self.discovery is not None and self.discovery.requires_identification(c))]

    def _sid(self) -> Optional[str]:
        sid = self.sessions.view().id
        return None if sid == "none" else sid

    def tick(self) -> None:
        if self.discovery is not None:
            self.discovery.pump()
        self.live.pump()
        self.assistant.pump()
        self.sessions.tick()
        self.engine.tick()
        if self.playbook is not None:
            self.playbook.tick()
        if self.voice is not None:
            self.voice.tick()

    def resolve_goal(self, req: GoalRequest) -> Optional[GoalResolution]:
        """A spoken or typed request. With an assistant it is first talked through (questions, experience); otherwise resolved directly."""
        if req.session_id == self.session().id and req.text:
            self.assistant.observe_goal(req)
        if self.discovery is not None and self.discovery.wants(req):
            return self.discovery.submit(req)
        if self.discovery is not None and self.discovery.state(req.session_id).phase != "idle":
            self.discovery.cancel(req.session_id)
        if self._reuse_goal(req):
            return self._reuse_resolution(req)
        if self.assistant.wants_goal(req):
            self.elog.write("input", goal=req.model_dump(mode="json"), via_assistant=True)
            res = self.assistant.submit_goal(req)
            self.hud.sync()
            return res
        return self.resolve_goal_direct(req)

    def resolve_goal_direct(self, req: GoalRequest) -> Optional[GoalResolution]:
        """The deterministic resolver (cards, then live research). Also the fallback whenever the assistant cannot help."""
        self.elog.write("input", goal=req.model_dump(mode="json"))
        if self._reuse_goal(req):
            return self._reuse_resolution(req)
        res = self.sessions.apply_goal(req)
        if res is not None and res.status == "supported" and res.card_id and req.text:
            card = self.card_by_id(res.card_id)
            if card is not None:
                self.cache.remember_guide(req.text, req.mode, card, self.live.cards.get(card.card_id))
        self.hud.sync()
        return res

    def _reuse_goal(self, req: GoalRequest) -> bool:
        if req.session_id != self.session().id or not req.text or req.via not in ("phone_text", "voice"):
            return False
        intake = self.assistant.intakes.get(req.session_id)
        if intake is not None and intake.active:
            return False  # the person's answer belongs to the current conversation
        saved = self.cache.guide(req.text, req.mode)
        if saved is None:
            saved = self.live.cached_guide(req.text, req.mode)
        if saved is None:
            return False
        card, review = saved
        current = next((c for c in self.cards if c.card_id == card.card_id), None)
        card = current or card
        task = self.assistant.tasks.get(req.session_id)
        if task is not None and (task.critical_unknowns or task.confirmation_pending):
            return False
        if self.discovery is not None and self.discovery.requires_identification(card):
            return False
        if not card.steps and card not in self.startable_cards():
            return False
        if current is None:
            self.cards.append(card)
            if review:
                self.live.cards[card.card_id] = review
        sess = self.sessions.active
        if sess is None:
            return False
        self.assistant.cancel(req.session_id)
        sess.phase = "menu"
        self.sessions.start_card(req.session_id, card, echo=False)
        self.cache.remember_guide(req.text, req.mode, card, review)
        self.live.last = {"cached": True, "goal": req.text, "card_id": card.card_id, "ok": True}
        self.elog.write("cache", kind_name="guide", card_id=card.card_id, hit=True)
        return True

    def _reuse_resolution(self, req: GoalRequest) -> GoalResolution:
        card = self.active_card
        return GoalResolution(session_id=req.session_id, status="supported", mode=card.goal_mode,
            card_id=card.card_id, task_title=card.title, cue=Cue(line1="SAVED GUIDE READY", line2="NO NEW RESEARCH"),
            detail=f"Using the saved guide: {card.title}. No new research was needed." +
                (" AI-researched, not human-reviewed." if card.card_id in self.live.cards else ""))

    def _refine_unsupported(self, req: GoalRequest, res: GoalResolution) -> GoalResolution:
        """Free-text goal with no card: save it for async research and say QUEUED only if it really was saved."""
        if req.via not in ("phone_text", "voice") or not (req.text or "").strip():
            return res
        if self.live.try_start(req):  # research it now, show a thinking screen, then start the guide (opt-in; see live_research.py)
            return res.model_copy(update={
                "research_queued": True,
                "cue": Cue(line1="RESEARCHING", line2="THIS TAKES A FEW MINUTES"),
                "detail": "No authored guide matches, so it is being researched live now. It starts here automatically when ready. "
                          "A live-researched guide is not reviewed by a human.",
            })
        saved = self.research.save(req.session_id, req.mode, req.text or "", req.via)
        if not saved.queued:
            return res
        self.elog.write("research", request=req.model_dump(mode="json"), status=saved.status)
        return res.model_copy(update={
            "research_queued": True,
            "cue": Cue(line1="NOT SUPPORTED YET", line2="QUEUED FOR RESEARCH"),
            "detail": res.detail + " Your request was " + SAVED_DETAIL + ".",
        })

    def request_research(self, session_id: str, mode: str, text: str) -> tuple[Optional[GoalResolution], SaveResult]:
        """POST /research/request: save an unsupported request. Never promises availability."""
        saved = self.research.save(session_id, mode, text, "phone_text")
        if not saved.queued:
            return None, saved
        self.elog.write("research", request={"session_id": session_id, "mode": mode, "text": text}, status=saved.status)
        res = GoalResolution(
            session_id=session_id,
            status="unsupported",
            mode=mode,  # type: ignore[arg-type]
            cue=Cue(line1="NOT SUPPORTED YET", line2="QUEUED FOR RESEARCH"),
            detail=SAVED_DETAIL,
            alternatives=[c.title for c in self.cards],
            research_queued=True,
        )
        return res, saved

    def ask(self, text: str) -> Optional[AskResult]:
        """Contextual follow-up for the active playbook step. None if no playbook is active."""
        if self.playbook is None:
            return None
        self.elog.write("input", ask=text[:300])
        from .assistant.adaptive import identity_correction, task_switch
        if task_switch(text) or identity_correction(text):
            sid = self.session().id
            task = self.assistant.tasks.get(sid)
            if identity_correction(text) and self.discovery is not None and self.discovery.state(sid).selected is not None:
                self.assistant.observe_goal(GoalRequest(session_id=sid, mode="build", via="phone_text", text=text))
                self.discovery.correct(sid, text)
                return AskResult(intent="goal", answered=True, cue=Cue(line1="CHECK PRODUCT AGAIN", line2="PICK THE MATCHING PHOTO"), text="Let's identify the correct product before continuing. Your earlier progress is kept.", detail="", label="DETERMINISTIC", step_id="", card_id="")
            if self.playbook is not None:
                self.playbook.detach()
                self.playbook, self._pb_sid = None, None
            sess = self.sessions.active
            sess.phase = "menu"
            self.sessions.clear_convo(sid)
            if identity_correction(text) and task:
                self.assistant.cancel(sid)
                self.assistant.intakes.pop(sid, None)
                task.phase = "intake"
                task.critical_unknowns = ["Confirm the corrected identity or applicability before continuing"]
                req_text = task.goal + ". Correction: " + text
            else:
                req_text = text
            res = self.resolve_goal(GoalRequest(session_id=sid, mode=intent_mod.infer_goal_mode(req_text), via="phone_text", text=req_text))
            return AskResult(intent="goal", answered=False, pending=bool(res and res.conversing), cue=res.cue if res else Cue(line1="WHAT DO YOU NEED?",line2=""), text=res.detail if res else "Tell me the new task.", detail="", label="DETERMINISTIC",step_id="",card_id="")
        if intent_mod.returns_to_step(text):
            self.assistant.dismiss(self.session().id, self.playbook.card.card_id, self.playbook.step.id)
        choice = self.playbook.match_choice(text)  # an answer to the current diagnostic question: deterministic, no model
        if choice is not None:
            st = self.playbook.step
            picked = next(c for c in st.choices if c.id == choice)
            self.playbook.choose(choice, via="voice/text")
            res = AskResult(intent="choice", answered=True, cue=self.hud.current.cue or Cue(line1="NOTED", line2=""),
                            text=f"Noted: {picked.records or picked.label.capitalize()}.", detail="", label="HUMAN CONFIRMED",
                            step_id=st.id, card_id=self.playbook.card.card_id)
            self.assistant.record_guide_answer(text, res)
            self.hud.sync()
            return res

        where = self.assistant.route(text, self.playbook)  # commands and the card's own FAQ stay deterministic; real questions go to the assistant
        if where == "assistant":
            res = self.assistant.submit_question(text)
        elif where == "notes":
            res = self.assistant.recall_note(text)
        else:
            res = self.playbook.ask(text)
            if res.intent not in ("next","back","goto","picture","status","repeat"):
                self.assistant.record_guide_answer(text,res)
        self.hud.sync()
        return res

    def note_poll(self) -> None:
        self._last_poll_ms = self.clock.now_ms()

    # ------------------------------------------------------------------ views
    def health(self) -> Health:
        e = self.engine
        link = e.link_status()
        cam = e.camera_status
        polled = self._last_poll_ms is not None and self.clock.now_ms() - self._last_poll_ms < 5000
        pi_ok = link == "up" and cam == "ok"
        return Health(
            ok=pi_ok if (self.playbook is None or self.playbook.current_is_measured) else True,  # manual steps need no telemetry
            uptime_s=round((self.clock.now_ms() - self.started) / 1000.0, 3),
            pi_link=link,  # type: ignore[arg-type]
            pi_last_seq=e.last_seq,
            pi_age_ms=e.link_age_ms(),
            source=e.last_obs.source if e.last_obs else None,
            camera=cam,  # type: ignore[arg-type]
            g2_clients=self.ws_clients + (1 if polled else 0),
        )

    def state(self) -> State:
        e = self.engine
        pb = self.playbook
        if pb is not None:
            events = sorted([*e.events, *pb.events], key=lambda ev: ev.at)[-50:]
            return State(
                session=self.sessions.view(),
                engine="PLAYBOOK",
                card_id=pb.card.card_id,
                test=None,
                step_id=pb.step.id,
                check=None,
                help_view=pb.help_view(),  # type: ignore[arg-type]
                source=(pb.last_obs or e.last_obs).source if (pb.last_obs or e.last_obs) else None,
                health=self.health(),
                hud=self.hud.current,
                playbook=pb.playbook_state(),
                events=events,
            )
        tr = e.current_track()
        return State(
            session=self.sessions.view(),
            engine=e.state,  # type: ignore[arg-type]
            card_id=e.card.card_id,
            test=tr.test.id if tr else None,
            step_id=e.step_id(),
            check=tr.check_idx if tr else None,
            help_view=e.help_view(),  # type: ignore[arg-type]
            source=e.last_obs.source if e.last_obs else None,
            health=self.health(),
            hud=self.hud.current,
            events=list(e.events)[-50:],
        )

    def session(self) -> Session:
        return self.sessions.view()

    def close(self) -> None:
        self.assistant.close()
        if self.discovery is not None:
            self.discovery.close()
        self.elog.close()
