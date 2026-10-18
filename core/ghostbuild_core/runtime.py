"""Runtime: wires cards, the single HUD writer, the engine, sessions and the log. The server is a thin shell on this."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

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

from .clock import Clock, as_clock
from .cards import load_cards
from .engine import Engine
from .hud import Hud
from .log import EventLog
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
    ) -> None:
        if not cards:
            raise ValueError("Runtime needs at least one valid Repair Card")
        self.clock = as_clock(clock)
        self.cards = cards
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
        sess_path = Path(log_dir) / "sessions.json" if log_dir is not None else None
        self.sessions = SessionManager(
            self.hud, self.clock, lambda: self.cards, self._set_card, sess_path,
            record=lambda kind, **d: self.elog.write(kind, **d),
            refine=self._refine_unsupported,
        )
        self.sessions.restore()
        self.hud.session_id = self._sid()
        self.sim = None
        if simulate:
            from .simulate import SimPi

            self.sim = SimPi(self.clock)
        self._last_poll_ms: Optional[int] = None
        self.ws_clients = 0
        self.voice = None  # optional VoiceService (voice.py), attached by its constructor; None = voice off

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
        return {"loaded": len(merged), "added": added, "changed": changed, "active": active}

    @property
    def active_card(self) -> Card:
        return self.playbook.card if self.playbook is not None else self.engine.card

    def card_by_id(self, card_id: str) -> Optional[Card]:
        return next((c for c in self.cards if c.card_id == card_id), None)

    # ------------------------------------------------------------------ inputs
    def ingest(self, obs: Observation) -> bool:
        ok = self.engine.ingest(obs)
        if ok and self.playbook is not None:
            self.playbook.ingest(obs)  # optional telemetry: only measured steps look at it
        self.elog.write("observation", accepted=ok, obs=obs.model_dump(mode="json"))
        return ok

    def handle_input(self, gi: G2Input) -> HudFrame:
        self.elog.write("input", input=gi.model_dump(mode="json"))
        if self.voice is not None and gi.gesture in ("hold_start", "hold_end"):
            self.voice.on_hold(gi.gesture)
        elif self.playbook is not None and self.sessions.flash_showing() and self.sessions.active is not None and self.sessions.active.phase == "task":
            self.sessions.dismiss_flash()  # the task-start cue hides the first step: a gesture only reveals it, never acts on it
            self.playbook.reveal()
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
        self.hud.session_id = self._sid()
        self.hud.sync()
        return self.hud.current

    def _sid(self) -> Optional[str]:
        sid = self.sessions.view().id
        return None if sid == "none" else sid

    def tick(self) -> None:
        self.sessions.tick()
        self.engine.tick()
        if self.playbook is not None:
            self.playbook.tick()
        if self.voice is not None:
            self.voice.tick()

    def resolve_goal(self, req: GoalRequest) -> Optional[GoalResolution]:
        self.elog.write("input", goal=req.model_dump(mode="json"))
        res = self.sessions.apply_goal(req)
        self.hud.sync()
        return res

    def _refine_unsupported(self, req: GoalRequest, res: GoalResolution) -> GoalResolution:
        """Free-text goal with no card: save it for async research and say QUEUED only if it really was saved."""
        if req.via not in ("phone_text", "voice") or not (req.text or "").strip():
            return res
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
        res = self.playbook.ask(text)
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
        self.elog.close()
