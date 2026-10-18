"""Sessions and G2 onboarding: welcome (once per session) -> BUILD/FIX menu -> goal -> task.

All HUD output goes through hud.py (layer "ui"). Selection is a goal, never a repair commit.
"""

from __future__ import annotations

import json
import logging
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from contracts.models import Card, Cue, G2Hello, G2Input, GoalRequest, GoalResolution, Session

from . import goal as goal_mod
from .clock import Clock
from .hud import Hud, Screen

log = logging.getLogger("ghostbuild.session")

WELCOME_MS = 2500
FLASH_MS = 2500
JOIN_WINDOW_MS = 15000  # a second surface (simulator) that says hello right after the first joins that session
MENU_OPTIONS = ["FIX", "BUILD"]


@dataclass
class _Choice:
    """A chooser menu on the glasses: the cards offered, the mode they were asked for, the selected option."""

    mode: str
    cards: list[Card]
    labels: list[str]
    more: bool
    selected: int = 0


class SessionManager:
    def __init__(
        self,
        hud: Hud,
        clock: Clock,
        cards: Callable[[], list[Card]],
        on_task: Callable[..., None],
        path: Path | None = None,
        record: Optional[Callable[..., None]] = None,
        refine: Optional[Callable[[GoalRequest, GoalResolution], GoalResolution]] = None,
        startable: Optional[Callable[[], list[Card]]] = None,
        voice_on: Optional[Callable[[], bool]] = None,
    ) -> None:
        self.hud = hud
        self.clock = clock
        self._cards = cards
        self._voice_on = voice_on or (lambda: False)  # when spoken goals are available the first screen says so
        self._startable = startable or cards  # cards that can START a task now (a fault card needs its device reporting); _cards resolves running ones
        self._on_task = on_task
        self._path = path
        self._record = record or (lambda *a, **k: None)
        self._refine = refine  # lets the runtime adjust an unsupported resolution (e.g. once the request was really saved)
        self.sessions: dict[str, Session] = {}
        self._created: dict[str, int] = {}
        self._creator: dict[str, str] = {}
        self.active_id: Optional[str] = None
        self._welcome_until = 0
        self._menu_selected = self._default_menu()
        self._flash: Optional[tuple[Screen, int]] = None
        self._choice: Optional[_Choice] = None
        self._progress: dict[str, dict] = {}  # playbook progress per session id (internal; not part of the Session contract)
        self._load()

    def _default_menu(self) -> int:
        return 0

    def _root_choice(self) -> Optional[_Choice]:
        """The first screen after the welcome: every task that can start now, whatever its mode. Mode (build/fix) is a property of the
        card and is inferred from what the person says; nobody is asked to pick it."""
        pool = sorted(self._startable(), key=lambda c: (goal_mod.short_title(c.title, 40), c.card_id))
        if not pool:
            return None
        shown, labels, more = goal_mod.chooser_options(pool)
        if len(labels) < 2:  # a menu needs two rows; the phone row is the always-available non-glasses path
            labels, more = [*labels, goal_mod.MORE_ON_PHONE], True
        return _Choice(mode="any", cards=shown, labels=labels, more=more, selected=min(self._menu_selected, len(labels) - 1))

    # ------------------------------------------------------------------ persistence
    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text())
            for sid, d in raw.get("sessions", {}).items():
                s = Session.model_validate({k: d[k] for k in ("id", "phase", "goal", "card_id", "welcome_shown")})
                if s.phase == "welcome":  # restarted mid-welcome: never show the welcome again
                    s.phase = "menu"
                self.sessions[sid] = s
                self._created[sid] = -10**9  # restored sessions are never "just created"
                self._creator[sid] = d.get("creator", "")
            self._progress = {k: v for k, v in (raw.get("progress") or {}).items() if k in self.sessions and isinstance(v, dict)}
            act = raw.get("active")
            self.active_id = act if act in self.sessions else None
        except Exception:
            log.exception("could not restore sessions from %s", self._path)

    def _save(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "active": self.active_id,
                "progress": self._progress,
                "sessions": {
                    sid: {**s.model_dump(), "creator": self._creator.get(sid, "")} for sid, s in self.sessions.items()
                },
            }
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2))
            tmp.replace(self._path)
        except Exception:
            log.exception("could not persist sessions")

    def restore(self) -> None:
        """After a backend restart: put the active session's UI/engine card back."""
        s = self.active
        if s is not None and s.phase == "task" and s.card_id:
            card = self._card(s.card_id)
            if card is not None:
                self._on_task(card)
        self._render()

    # ------------------------------------------------------------------ views
    @property
    def active(self) -> Optional[Session]:
        return self.sessions.get(self.active_id) if self.active_id else None

    def view(self) -> Session:
        return self.active or Session(id="none", phase="welcome", welcome_shown=False)

    def _card(self, card_id: str) -> Optional[Card]:
        for c in self._cards():
            if c.card_id == card_id:
                return c
        return None

    # ------------------------------------------------------------------ playbook progress (resume after reconnect / restart)
    def get_progress(self, sid: Optional[str]) -> Optional[dict]:
        return self._progress.get(sid) if sid else None

    def set_progress(self, sid: Optional[str], data: dict) -> None:
        if sid and sid in self.sessions:
            self._progress[sid] = data
            self._save()

    def flash_showing(self) -> bool:
        return self._flash is not None and self.clock.now_ms() < self._flash[1]

    def dismiss_flash(self) -> None:
        if self._flash is not None:
            self._flash = None
            self._render()

    # ------------------------------------------------------------------ hello
    def hello(self, h: G2Hello) -> Session:
        now = self.clock.now_ms()
        sess = self.sessions.get(h.session_id) if h.session_id else None
        if sess is None:
            act = self.active
            if h.session_id is None and act is not None and self._creator.get(act.id) == "phone-companion":
                sess = act  # a later physical launch joins the task prepared on its companion
            elif (
                h.session_id is None
                and act is not None
                and act.phase in ("welcome", "menu")
                and now - self._created.get(act.id, -10**9) <= JOIN_WINDOW_MS
                and self._creator.get(act.id) != h.client_id
            ):
                sess = act  # concurrent second surface joins the session that was just created
            else:
                sess = self._new_session(h.client_id, now)
        elif sess.phase == "welcome" and (sess.id != self.active_id or now >= self._welcome_until):
            sess.phase = "menu"
        if self.active_id != sess.id:
            self.active_id = sess.id
            self._menu_selected = self._default_menu()
            self._choice = None
            self._save()
        if sess.phase == "task" and sess.card_id:
            card = self._card(sess.card_id)
            if card is not None:
                self._on_task(card)
        self._render()
        return sess

    def _new_session(self, client_id: str, now: int) -> Session:
        sid = "s-" + secrets.token_hex(4)
        s = Session(id=sid, phase="welcome", goal=None, card_id=None, welcome_shown=True)
        self.sessions[sid] = s
        self._created[sid] = now
        self._creator[sid] = client_id
        self.active_id = sid
        self._welcome_until = now + WELCOME_MS
        self._menu_selected = self._default_menu()
        self._flash = None
        self._choice = None
        self._save()
        self._record("event", text=f"new session {sid} for client {client_id}")
        return s

    # ------------------------------------------------------------------ input
    def handle_input(self, gi: G2Input) -> bool:
        """True if the session UI consumed the gesture (welcome/menu/chooser)."""
        s = self.active
        if s is None or s.phase == "task":
            if self._flash is not None:
                self._flash = None
                self._render()
            return False
        if s.phase == "welcome":
            s.phase = "menu"  # a gesture skips the welcome: nobody should wait for a banner
            self._menu_selected = self._default_menu()
            self._save()
            self._render()
            return True
        if self._flash is not None:
            self._flash = None  # the wearer is interacting: show the menu underneath
        ch = self._choice or self._root_choice()
        if ch is not None:
            return self._chooser_input(s, ch, gi)
        self._render()
        return True

    def _chooser_input(self, s: Session, ch: _Choice, gi: G2Input) -> bool:
        if gi.gesture == "swipe_down":
            ch.selected = min(ch.selected + 1, len(ch.labels) - 1)
        elif gi.gesture == "swipe_up":
            ch.selected = max(ch.selected - 1, 0)
        if ch.mode == "any":
            self._menu_selected = ch.selected  # the root list is rebuilt on every render; remember where the wearer is
        if gi.gesture == "press":
            if ch.more and ch.selected == len(ch.labels) - 1:
                # MORE ON PHONE does nothing but point at the phone text box (a non-voice path always exists)
                self._flash = (Screen.uncertain(Cue(line1="USE THE PHONE", line2="TYPE YOUR TASK"), ttl_ms=FLASH_MS), self.clock.now_ms() + FLASH_MS)
            else:
                card = ch.cards[ch.selected]
                self._record("event", text=f"chooser picked {card.card_id}")
                self._start(s, card, card.goal_mode)
                return True
        self._render()
        return True

    # ------------------------------------------------------------------ goal
    def apply_goal(self, req: GoalRequest) -> Optional[GoalResolution]:
        sess = self.sessions.get(req.session_id)
        if sess is None:
            return None
        cards = self._startable()
        res = goal_mod.resolve(req, cards)
        if res.status == "unsupported" and (req.text or "").strip():
            other = req.model_copy(update={"mode": "build" if req.mode == "fix" else "fix"})
            alt = goal_mod.resolve(other, cards)
            if alt.status in ("supported", "ambiguous"):
                req, res = other, alt  # "fix my LED" / "build" are hints; the words decide
        if res.status == "unsupported" and self._refine is not None:
            res = self._refine(req, res)
        self._record("event", text=f"goal via {req.via}: {res.status} {res.card_id or ''}")
        now = self.clock.now_ms()
        self._choice = None
        if res.status == "supported" and res.card_id:
            card = self._card(res.card_id)
            if card is not None:
                self._start(sess, card, req.mode, res.cue)
        elif res.status == "ambiguous" and sess.phase == "menu" and sess.id == self.active_id:
            shown, labels, more = goal_mod.chooser_options(goal_mod.candidates(req, cards))
            self._choice = _Choice(mode=req.mode, cards=shown, labels=labels, more=more)
            self._flash = None
        else:
            self._flash = (Screen.uncertain(res.cue, ttl_ms=FLASH_MS), now + FLASH_MS)
        if sess.id == self.active_id:
            self._render()
        return res

    def _start(self, sess: Session, card: Card, mode: str, cue: Optional[Cue] = None) -> None:
        """Begin a task on `card` for this session (fresh playbook progress)."""
        now = self.clock.now_ms()
        cue = cue or goal_mod.task_cue(card, mode)
        self._choice = None
        sess.phase = "task"
        sess.goal = mode  # type: ignore[assignment]
        sess.card_id = card.card_id
        sess.welcome_shown = True
        self._progress.pop(sess.id, None)
        self._save()
        if sess.id == self.active_id:
            if card.steps:
                self.hud.set_layer("ui", None)  # clear the menu first so the first step can be emitted at once
            self._on_task(card, True)
            # a playbook goes straight to its first step (a title card would swallow the first swipe); a fault card keeps its cue
            self._flash = None if card.steps else (Screen.intervene(cue, cue_id="task_start", ttl_ms=FLASH_MS, immediate=True), now + FLASH_MS)
            self._render()

    # ------------------------------------------------------------------ time
    def tick(self) -> None:
        now = self.clock.now_ms()
        changed = False
        s = self.active
        if s is not None and s.phase == "welcome" and now >= self._welcome_until:
            s.phase = "menu"
            self._menu_selected = self._default_menu()
            self._save()
            changed = True
        if self._flash is not None and now >= self._flash[1]:
            self._flash = None
            changed = True
        if changed:
            self._render()

    def return_to_menu(self) -> None:
        """Task finished: back to the task list (the next gesture after the completion message)."""
        s = self.active
        if s is None:
            return
        self._progress.pop(s.id, None)
        s.phase, s.goal, s.card_id = "menu", None, None
        self._choice = None
        self._flash = None
        self._menu_selected = self._default_menu()
        self._save()
        self._render()

    def refresh(self) -> None:
        """Re-render the active session's screen (the task list is derived from the loaded cards on every render)."""
        self._render()

    def _render(self) -> None:
        s = self.active
        now = self.clock.now_ms()
        screen: Optional[Screen] = None
        if self._flash is not None and now < self._flash[1]:
            screen = self._flash[0]
        elif s is not None and s.phase == "welcome":
            screen = Screen.welcome(Cue(line1="GHOSTBUILD", line2="WHAT DO YOU NEED?"), WELCOME_MS)
        elif s is not None and s.phase == "menu":
            ch = self._choice or self._root_choice()
            if ch is None:
                screen = Screen.uncertain(Cue(line1="NOTHING LOADED YET", line2="SEE PHONE"), ttl_ms=FLASH_MS)
            else:
                prompt = ("HOLD TO SPEAK OR PICK" if self._voice_on() else "WHAT DO YOU NEED?") if ch.mode == "any" else "PICK A TASK"
                screen = Screen.make_menu(prompt, ch.labels, ch.selected)
        self.hud.set_layer("ui", screen)
        self.hud.sync()
