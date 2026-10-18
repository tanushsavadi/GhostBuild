"""Live research: a request no authored card covers is researched now (CREAO), shown as a thinking screen, then started as a task.

Opt-in (GB_LIVE_RESEARCH=1 plus a working CREAO setup). The result is NOT human-reviewed. It passes the same validator as every card
(`write_draft`), is labelled AI-RESEARCHED / NOT REVIEWED on the glasses start card and on the phone, stays a draft on disk for later
human approval, and is kept in memory only (a restart forgets it unless a human approves the draft). Credits are protected: one run at
a time, a per-process cap (GB_LIVE_RESEARCH_MAX, default 3), requests of fewer than two words are never sent. The worker thread only
queues the finished run id; every HUD/session change happens on the main loop inside `pump()`.
"""

from __future__ import annotations

import json
import logging
import math
import os
import queue
import time
from typing import TYPE_CHECKING, Any, Optional

from contracts.models import Card, Cue, GoalRequest

from . import goal as goal_mod

if TYPE_CHECKING:  # pragma: no cover
    from .runtime import Runtime

log = logging.getLogger("ghostbuild.live_research")

FLAG_ENV = "GB_LIVE_RESEARCH"
MAX_ENV = "GB_LIVE_RESEARCH_MAX"
FAST_ENV = "GB_LIVE_RESEARCH_FAST"  # default on: ask the agent for a lean, quick answer
EXPECTED_ENV = "GB_LIVE_RESEARCH_EXPECTED_S"  # typical fast-mode run length until real runs teach us better (measured: 105 s)
STAGES = ("Searching sources", "Reading and cross-checking", "Writing your steps", "Drawing a diagram", "Final checks")
UNREVIEWED_NOTE = "AI-researched live; not reviewed by a human. Check the sources before relying on it."


def estimate(elapsed_s: float, expected_s: float) -> dict:
    """An ESTIMATE of progress for the wait screen (CREAO reports no percentage). It eases toward ~90% at the expected duration, never
    reaches 100% until the run actually finishes, and says so when the run is taking longer than usual. Stages are a rough guide only."""
    expected = max(30.0, float(expected_s))
    frac = min(0.95, 1 - math.exp(-2.2 * max(0.0, elapsed_s) / expected))
    remaining = max(0.0, expected - elapsed_s)
    return {
        "estimate": True, "fraction": round(frac, 3), "stage": min(len(STAGES) - 1, int(frac * len(STAGES))), "stages": list(STAGES),
        "remaining_s": int(round(remaining / 5.0) * 5), "expected_s": int(expected), "over": elapsed_s > expected * 1.15,
    }


class LiveResearch:
    def __init__(self, rt: "Runtime") -> None:
        self.rt = rt
        self.runs: Any = None
        self._done: "queue.Queue[str]" = queue.Queue()
        self.active: Optional[dict] = None
        self.last: Optional[dict] = None
        self.cards: dict[str, dict] = {}  # card_id -> {run_id, draft_id, goal}: loaded live, never human-reviewed
        self.started = 0
        self.durations: list[float] = []  # how long finished live runs really took (seconds): the wait estimate learns from them

    def _now(self) -> float:
        return self.rt.clock.now_ms() / 1000.0  # the runtime clock: the glasses screen and the phone estimate always agree

    # ------------------------------------------------------------------ wiring
    def attach(self, runs: Any) -> None:
        self.runs = runs
        runs.on_done = self._done.put  # worker thread: queue only

    @property
    def enabled(self) -> bool:
        return os.environ.get(FLAG_ENV, "") == "1" and self.runs is not None and self.runs.enabled

    def _max(self) -> int:
        try:
            return max(0, int(os.environ.get(MAX_ENV, "3")))
        except ValueError:
            return 3

    def expected_s(self) -> float:
        base = float(os.environ.get(EXPECTED_ENV, "110") or 110)
        if self.durations:
            recent = sorted(self.durations[-3:])
            return recent[len(recent) // 2]  # median of the last few real runs
        return base

    def progress(self) -> Optional[dict]:
        act = self.active
        return None if act is None else estimate(self._now() - act["started"], self.expected_s())

    # ------------------------------------------------------------------ start (main loop)
    def try_start(self, req: GoalRequest) -> bool:
        """True iff research was started for this unmatched request (the caller then answers RESEARCHING)."""
        text = (req.text or "").strip()
        if not self.enabled or self.active is not None or len(text.split()) < 2:
            return False
        sess = self.rt.sessions.active
        if sess is None or sess.id != req.session_id or sess.phase != "menu":
            return False
        from .research_runs import RunBody, RunRejected

        cached_id = self._cached_run(text)
        if cached_id is None and self.started >= self._max():
            return False
        try:
            run_id = cached_id or self.runs.start(RunBody(session_id=req.session_id, goal=text[:300], intent=req.mode, fast=os.environ.get(FAST_ENV, "1") != "0",
                                       audience=self.rt.assistant.audience_for(req.session_id)))
        except RunRejected as exc:
            log.info("live research not started: %s", exc.detail)
            return False
        self.started += 0 if cached_id else 1  # a cached run costs no credits and does not count against the cap
        self.active = {"run_id": run_id, "session_id": req.session_id, "goal": text[:300], "mode": req.mode, "started": self._now()}
        self.rt.sessions.begin_research(req.session_id, text)
        self.rt.elog.write("live_research", event="started", run_id=run_id, goal=text[:300])
        if (self.runs.get(run_id) or {}).get("status") == "draft_ready":  # an identical cached draft: no new run, load it now
            self._done.put(run_id)
        return True

    def _cached_run(self, text: str) -> Optional[str]:
        """A finished, still-loadable draft for the same request (any session, any earlier start): reuse it instead of paying again."""
        from knowledge.importer import drafts_dir

        norm = " ".join(text.lower().split())
        for rec in self.runs.list():
            if rec.get("status") == "draft_ready" and rec.get("draft_id") and " ".join(str(rec.get("goal", "")).lower().split()) == norm:
                if (drafts_dir(self.rt.asset_root) / rec["draft_id"] / "envelope.json").is_file():
                    return rec["run_id"]
        return None

    # ------------------------------------------------------------------ finish (main loop, from tick)
    def pump(self) -> None:
        while True:
            try:
                run_id = self._done.get_nowait()
            except queue.Empty:
                return
            act = self.active
            if act is None or act["run_id"] != run_id:
                continue
            self.active = None
            took = self._now() - act["started"]
            rec = self.runs.get(run_id) or {}
            if rec.get("status") == "draft_ready" and took > 20:  # a cached load is instant and teaches nothing
                self.durations.append(took)
            ok = rec.get("status") == "draft_ready" and self._load(rec, act)
            self.last = {"run_id": run_id, "goal": act["goal"], "ok": bool(ok), "status": rec.get("status"), "at": time.time()}
            if not ok:
                self.rt.sessions.fail_research(Cue(line1="NO GUIDE BUILT", line2="TRY ANOTHER REQUEST"))
                self.rt.elog.write("live_research", event="failed", run_id=run_id, status=rec.get("status"))

    def _load(self, rec: dict, act: dict) -> bool:
        from knowledge.importer import drafts_dir

        try:
            env = json.loads((drafts_dir(self.rt.asset_root) / rec["draft_id"] / "envelope.json").read_text(encoding="utf-8"))
            card = Card.model_validate(env["card"])
        except Exception:
            log.exception("could not load the researched draft")
            return False
        if card.title == card.title.lower():  # the request text is the title when the agent gave none: make it readable
            card = card.model_copy(update={"title": (card.title[:1].upper() + card.title[1:])[:120]})
        if all(c.card_id != card.card_id for c in self.rt.cards):
            self.rt.cards = [*self.rt.cards, card]
        else:
            card = next(c for c in self.rt.cards if c.card_id == card.card_id)
        self.cards[card.card_id] = {"run_id": rec["run_id"], "draft_id": rec["draft_id"], "goal": act["goal"]}
        cue = goal_mod.task_cue(card, card.goal_mode)
        cue = Cue(line1=cue.line1, line2="AI RESEARCHED, UNREVIEWED")
        started = self.rt.sessions.finish_research(act["session_id"], card, cue)
        self.rt.elog.write("live_research", event="ready", run_id=rec["run_id"], card_id=card.card_id, started=started)
        return True

    # ------------------------------------------------------------------ view (phone)
    def view(self) -> dict:
        act = self.active
        rec = (self.runs.get(act["run_id"]) if (act and self.runs) else None) or {}
        return {
            "enabled": self.enabled,
            "active": None if act is None else {
                "run_id": act["run_id"], "goal": act["goal"], "elapsed_s": int(self._now() - act["started"]),
                "status": rec.get("status"), "creao_status": rec.get("creao_status"),
                "progress": estimate(self._now() - act["started"], self.expected_s()),
            },
            "last": self.last,
            "unreviewed_cards": sorted(self.cards),
            "note": UNREVIEWED_NOTE,
            "started": self.started, "max": self._max(),
        }
