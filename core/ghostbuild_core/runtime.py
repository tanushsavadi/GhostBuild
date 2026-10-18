"""Runtime: wires cards, the single HUD writer, the engine, sessions and the log. The server is a thin shell on this."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

from contracts.models import (
    Card,
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
from .engine import Engine
from .hud import Hud
from .log import EventLog
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
        self.engine = self._make_engine(self._default_card())
        sess_path = Path(log_dir) / "sessions.json" if log_dir is not None else None
        self.sessions = SessionManager(
            self.hud, self.clock, lambda: self.cards, self._set_card, sess_path,
            record=lambda kind, **d: self.elog.write(kind, **d),
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

    def _make_engine(self, card: Card) -> Engine:
        return Engine(
            card, self.clock, hud=self.hud, asset_root=self.asset_root, force_source=self.force_source,
            on_event=lambda ev: self.elog.write("event", evidence=ev.model_dump(mode="json")),
        )

    def _set_card(self, card: Card) -> None:
        if self.engine.card.card_id != card.card_id:
            self.engine = self._make_engine(card)
            self.engine.tick()

    def card_by_id(self, card_id: str) -> Optional[Card]:
        return next((c for c in self.cards if c.card_id == card_id), None)

    # ------------------------------------------------------------------ inputs
    def ingest(self, obs: Observation) -> bool:
        ok = self.engine.ingest(obs)
        self.elog.write("observation", accepted=ok, obs=obs.model_dump(mode="json"))
        return ok

    def handle_input(self, gi: G2Input) -> HudFrame:
        self.elog.write("input", input=gi.model_dump(mode="json"))
        if self.voice is not None and gi.gesture in ("hold_start", "hold_end"):
            self.voice.on_hold(gi.gesture)
        elif not self.sessions.handle_input(gi):
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
        if self.voice is not None:
            self.voice.tick()

    def resolve_goal(self, req: GoalRequest) -> Optional[GoalResolution]:
        self.elog.write("input", goal=req.model_dump(mode="json"))
        res = self.sessions.apply_goal(req)
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
        return Health(
            ok=link == "up" and cam == "ok",
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
