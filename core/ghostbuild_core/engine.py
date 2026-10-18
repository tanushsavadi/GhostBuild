"""Step engine: the explicit state machine that runs any procedure and decides what the glasses show.

Only measured jig checks (VERIFIED) or the user (GUIDED, "done"/tap) complete a step. No model decides physical
state, unknown or stale jig data never verifies anything, and nothing here knows what is being built: all build
facts come from the Procedure and its JigProfile. The engine produces a View; hud.py turns Views into frames.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Callable, Literal

from contracts.models import Completion, Event, G2Input, JigProfile, Predicate, Procedure, Step

from . import answer

JIG_STALE_S = 2.0  # no jig reading for this long -> link down, nothing verifies
FAULT_HOLD_S = 1.0  # a fault must persist this long before the glasses show it
CHECK_TIMEOUT_S = 2.5  # "done" on a jig step with no pass in this window -> troubleshoot
ACK_S = 1.5  # how long VERIFIED / DONE shows before the next step
TRANSIENT_S = 6.0  # answers, help lines, notices
COMPLETE_S = 8.0  # final screen, then dark

VERIFIED_MARK = "● VERIFIED"
CONFIRMED_MARK = "DONE (YOU CONFIRMED)"
ASK_MENTOR = "ASK A MENTOR"

Kind = Literal[
    "idle", "step", "checking", "verified", "confirmed", "fault", "answer",
    "troubleshoot", "complete", "clear", "status", "offline",
]

COMMANDS = {
    "next": {"next", "next step", "continue", "go on", "skip"},
    "back": {"back", "go back", "previous", "previous step", "last step"},
    "repeat": {"repeat", "again", "say again", "repeat that", "what was that"},
    "done": {"done", "finished", "im done", "i am done", "did it", "i did it", "got it", "complete", "placed"},
    "help": {"help", "help me", "stuck", "im stuck", "i am stuck", "its not working", "not working"},
}
FILLER = {"ok", "okay", "um", "uh", "please", "ghostbuild", "hey", "so", "now", "alright"}


def normalize(text: str) -> str:
    words = re.sub(r"[^a-z0-9 ]+", "", text.lower().replace("'", "")).split()
    return " ".join(w for w in words if w not in FILLER)


def command_of(text: str) -> str | None:
    t = normalize(text)
    for cmd, phrases in COMMANDS.items():
        if t in phrases:
            return cmd
    return None


def matches(preds: list[Predicate], fields: dict) -> bool:
    for p in preds:
        if p.field not in fields:
            return False
        v = fields[p.field]
        if p.eq is not None and v != p.eq:
            return False
        if p.in_ is not None and v not in p.in_:
            return False
    return True


@dataclass
class View:
    kind: Kind
    lines_hint: dict = field(default_factory=dict)  # header/action/status for hud.py
    ttl_ms: int | None = None
    procedure_id: str | None = None
    step_index: int | None = None
    step_total: int | None = None
    mode: Literal["VERIFIED", "GUIDED"] | None = None
    progress: tuple[int, int] | None = None


@dataclass
class Transient:
    kind: Kind
    text: str
    until: float
    advance: bool = False  # an ack: move to the next step when it expires


class Engine:
    def __init__(
        self,
        profiles: dict[str, JigProfile] | None = None,
        clock: Callable[[], float] = time.time,
        jig_enabled: bool = True,
    ) -> None:
        self.profiles = profiles or {}
        self.clock = clock
        self.jig_enabled = jig_enabled
        self.proc: Procedure | None = None
        self.idx = 0
        self.completed: dict[str, Completion] = {}
        self.events: list[Event] = []
        self.jig_fields: dict = {}
        self.jig_source: str | None = None
        self.jig_at: float | None = None
        self.notice: Transient | None = None  # shown while idle (e.g. compile progress)
        self._reset_step()
        self.complete_until: float | None = None
        self.force = False  # next view must be re-sent even if unchanged ("repeat")

    # --- lifecycle ---------------------------------------------------------------------------------

    def load(self, proc: Procedure) -> None:
        self.proc = proc
        self.idx = 0
        self.completed = {}
        self.complete_until = None
        self.notice = None
        self._reset_step()
        self._event(f"loaded {proc.id} ({len(proc.steps)} steps)", "DETERMINISTIC")
        self.evaluate()

    def unload(self) -> None:
        self.proc = None
        self.complete_until = None
        self._reset_step()

    def _reset_step(self) -> None:
        self.transient: Transient | None = None
        self.checking_since: float | None = None
        self.trouble_i = 0
        self.fault_id: str | None = None
        self.fault_since: float | None = None
        self.seen_fail = False  # for edge checks

    @property
    def engine_state(self) -> Literal["IDLE", "STEP", "COMPLETE"]:
        if not self.proc:
            return "IDLE"
        return "COMPLETE" if self.idx >= len(self.proc.steps) else "STEP"

    @property
    def step(self) -> Step | None:
        if self.proc and self.idx < len(self.proc.steps):
            return self.proc.steps[self.idx]
        return None

    # --- jig ---------------------------------------------------------------------------------------

    @property
    def profile(self) -> JigProfile | None:
        if not (self.proc and self.proc.jig_profile and self.jig_enabled):
            return None
        return self.profiles.get(self.proc.jig_profile)

    def jig_fresh(self) -> bool:
        return self.jig_at is not None and self.clock() - self.jig_at <= JIG_STALE_S

    def on_jig(self, fields: dict, source: str = "live") -> None:
        if fields != self.jig_fields:
            self._event(f"jig {fields}", "SIMULATED" if source == "simulated" else "MEASURED LIVE")
        self.jig_fields = dict(fields)
        self.jig_source = source
        self.jig_at = self.clock()
        self.evaluate()

    def mode_of(self, step: Step) -> Literal["VERIFIED", "GUIDED"]:
        p = self.profile
        if step.check.type == "jig" and p and step.check.jig_check in p.checks:
            return "VERIFIED"
        return "GUIDED"

    def _raw_fault(self, step: Step) -> str | None:
        p = self.profile
        if not (p and self.jig_fresh()):
            return None
        for fid in step.check.faults:
            if fid in p.faults and matches(p.faults[fid], self.jig_fields):
                return fid
        return None

    def _check_passes(self, step: Step) -> bool | None:
        """True/False from fresh jig data; None when unknown (no profile, stale or missing link)."""
        p = self.profile
        if not (p and self.jig_fresh() and step.check.jig_check in p.checks):
            return None
        return matches(p.checks[step.check.jig_check], self.jig_fields)

    # --- the state machine -------------------------------------------------------------------------

    def tick(self) -> None:
        self.evaluate()

    def evaluate(self) -> None:
        now = self.clock()
        if self.notice and now >= self.notice.until:
            self.notice = None
        step = self.step
        if step is None:
            return
        if self.transient and now >= self.transient.until:
            t, self.transient = self.transient, None
            if t.advance:
                self._advance()
                return self.evaluate()

        # Faults are watched on the active step only, and shown only after they persist.
        fid = self._raw_fault(step)
        if fid != self.fault_id:
            self.fault_id, self.fault_since = fid, (now if fid else None)
            if fid:
                self._event(f"fault {fid} on {step.id}", "MEASURED LIVE")
        if self.transient and self.transient.advance:
            return
        if step.id in self.completed or self.mode_of(step) != "VERIFIED":
            return

        passes = self._check_passes(step)
        p = self.profile
        edge = p is not None and step.check.jig_check in p.edge_checks
        if passes is False:
            self.seen_fail = True
        if passes and not self._fault_active(now) and (self.seen_fail or not edge):
            self._complete(step, "verified")
            return
        if self.checking_since is not None and now - self.checking_since >= CHECK_TIMEOUT_S:
            self.checking_since = None
            if passes is None:
                self._show("offline", "JIG OFFLINE · " + ASK_MENTOR)
            else:
                self._show_help()

    def _fault_active(self, now: float) -> bool:
        return self.fault_id is not None and self.fault_since is not None and now - self.fault_since >= FAULT_HOLD_S

    def _complete(self, step: Step, how: Literal["verified", "confirmed"]) -> None:
        now = self.clock()
        self.completed[step.id] = Completion(step_id=step.id, how=how, at=now)
        label = "MEASURED LIVE" if how == "verified" else "USER CONFIRMED"
        if how == "verified" and self.jig_source == "simulated":
            label = "SIMULATED"
        self._event(f"{step.id} {how}", label)
        self.checking_since = None
        mark = VERIFIED_MARK if how == "verified" else CONFIRMED_MARK
        self.transient = Transient("verified" if how == "verified" else "confirmed", mark, now + ACK_S, advance=True)

    def _advance(self) -> None:
        assert self.proc
        self.idx += 1
        self._reset_step()
        if self.idx >= len(self.proc.steps):
            self.complete_until = self.clock() + COMPLETE_S
            self._event("procedure complete", "DETERMINISTIC")
        else:
            self.evaluate()

    def _show(self, kind: Kind, text: str, seconds: float = TRANSIENT_S) -> None:
        self.transient = Transient(kind, text, self.clock() + seconds)

    def _show_help(self) -> None:
        step = self.step
        checks = [c for t in step.troubleshoot for c in t.checks] if step else []
        if not checks:
            self._show("troubleshoot", ASK_MENTOR)
            return
        self._show("troubleshoot", checks[self.trouble_i % len(checks)])
        self.trouble_i += 1

    # --- inputs ------------------------------------------------------------------------------------

    def on_input(self, inp: G2Input) -> None:
        if inp.kind == "voice":
            text = inp.text or ""
            cmd = command_of(text)
            if cmd:
                self.command(cmd)
            elif text.strip():
                self.ask(text)
        elif inp.kind == "tap":
            self.command("done")
        elif inp.kind == "menu":
            self.menu(inp.text or "")
        elif inp.kind == "swipe_down":
            self.command("next")
        elif inp.kind == "swipe_up":
            self.command("back")
        self.evaluate()

    def command(self, cmd: str) -> None:
        if cmd == "repeat":
            self.force = True
            return
        step = self.step
        if step is None:
            return
        if self.transient and self.transient.advance:
            if cmd in ("done", "next"):  # skip the ack, already complete
                self.transient = None
                self._advance()
            return
        if cmd == "back":
            if self.idx > 0:
                self.idx -= 1
                self._reset_step()
            return
        if cmd == "help":
            self._show_help()
            return
        # done / next
        if step.id in self.completed:
            self._advance()
            return
        if self._raw_fault(step):
            self.transient = None  # the fault line is the answer: fix it first
            self.fault_since = min(self.fault_since or self.clock(), self.clock() - FAULT_HOLD_S)
            return
        if self.mode_of(step) == "GUIDED":
            self._complete(step, "confirmed")
        else:
            self.transient = None
            self.checking_since = self.clock()

    def ask(self, text: str) -> None:
        if not self.proc or self.step is None:
            self._show("answer", ASK_MENTOR)
            return
        hit = answer.answer(text, self.proc, self.idx)
        self._event(f"Q: {text!r} -> {hit or ASK_MENTOR}", "DETERMINISTIC")
        self._show("answer", hit or ASK_MENTOR)

    def menu(self, item: str) -> None:
        step = self.step
        if not (self.proc and step):
            return
        key = normalize(item)
        if key.startswith("why"):
            self._show("answer", step.why or ASK_MENTOR)
        elif key.startswith("where"):
            self._show("answer", step.where or ASK_MENTOR)
        elif key.startswith("whats done") or key.startswith("what is done"):
            v = sum(1 for c in self.completed.values() if c.how == "verified")
            self._show("status", f"{len(self.completed)}/{len(self.proc.steps)} DONE · {v} VERIFIED")
        elif key.startswith("what next"):
            nxt = self.proc.steps[self.idx + 1].hud if self.idx + 1 < len(self.proc.steps) else "THIS IS THE LAST STEP"
            self._show("answer", nxt)
        else:
            self.ask(item)

    def say(self, text: str, seconds: float = TRANSIENT_S) -> None:
        """A notice from outside the step loop (e.g. compile progress). Text must already be HUD-safe."""
        self.notice = Transient("status", text, self.clock() + seconds)

    # --- output ------------------------------------------------------------------------------------

    def view(self) -> View:
        now = self.clock()
        proc, step = self.proc, self.step
        if proc is None:
            if self.notice:
                return View("status", {"action": "GHOSTBUILD", "status": self.notice.text})
            return View("idle", {"action": "GHOSTBUILD", "status": "LOAD A BUILD ON THE PHONE"})
        total = len(proc.steps)
        base = dict(procedure_id=proc.id, step_total=total)
        if step is None:
            if self.complete_until is not None and now >= self.complete_until:
                return View("clear", {}, **base)
            v = sum(1 for c in self.completed.values() if c.how == "verified")
            status = f"{total}/{total} DONE · {v} VERIFIED" if v else f"{total}/{total} DONE"
            ttl = int(max(0.0, (self.complete_until or now) - now) * 1000)
            return View("complete", {"action": "BUILD COMPLETE", "status": status}, ttl_ms=ttl,
                        progress=(total, total), **base)

        mode = self.mode_of(step)
        hint = {"header": f"STEP {self.idx + 1}/{total} · {mode} MODE", "action": step.hud}
        kind: Kind = "step"
        ttl: int | None = None
        if self.transient:
            kind, hint["status"] = self.transient.kind, self.transient.text
            ttl = int(max(0.0, self.transient.until - now) * 1000)
        elif self._fault_active(now) and self.fault_id:
            kind, hint["status"] = "fault", step.check.faults[self.fault_id]
        elif self.checking_since is not None:
            kind, hint["status"] = "checking", "CHECKING..."
        elif step.id in self.completed:
            done = self.completed[step.id]
            hint["status"] = VERIFIED_MARK if done.how == "verified" else CONFIRMED_MARK
        elif step.warnings:
            hint["status"] = step.warnings[0]
        if self.notice and kind == "step":
            hint["status"] = self.notice.text
        done_n = len(self.completed)
        return View(kind, hint, ttl_ms=ttl, step_index=self.idx, mode=mode, progress=(done_n, total), **base)

    def _event(self, text: str, label: str) -> None:
        self.events.append(Event(at=self.clock(), text=text, label=label))  # type: ignore[arg-type]
        del self.events[:-100]
