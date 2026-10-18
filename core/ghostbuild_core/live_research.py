"""Live research: a request no authored card covers is researched now (CREAO), shown as a thinking screen, then started as a task.

Opt-in (GB_LIVE_RESEARCH=1 plus a working CREAO setup). The result is NOT human-reviewed. It passes the same validator as every card
(`write_draft`), is labelled AI-RESEARCHED / NOT REVIEWED on the glasses start card and on the phone, stays a draft on disk for later
human approval, and is persisted as a labelled unreviewed snapshot for later reuse. Credits are protected: one run at
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
from .cache import goal_key

if TYPE_CHECKING:  # pragma: no cover
    from .runtime import Runtime

log = logging.getLogger("ghostbuild.live_research")

FLAG_ENV = "GB_LIVE_RESEARCH"
MAX_ENV = "GB_LIVE_RESEARCH_MAX"
FAST_ENV = "GB_LIVE_RESEARCH_FAST"  # default on: ask the agent for a lean, quick answer
ENGINE_ENV = "GB_RESEARCH_ENGINE"  # compile (default: official sources -> verified compiler) | creao (the CREAO agent)
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
        self.durations: list[float] = []
        self._prefetched: dict[str, dict] = {}  # task id -> {goal, urls}: sources found while the person was still answering  # how long finished live runs really took (seconds): the wait estimate learns from them

    def _now(self) -> float:
        return self.rt.clock.now_ms() / 1000.0  # the runtime clock: the glasses screen and the phone estimate always agree

    # ------------------------------------------------------------------ wiring
    def attach(self, runs: Any) -> None:
        self.runs = runs
        runs.on_done = self._done.put  # worker thread: queue only

    @property
    def engine(self) -> str:
        return "creao" if os.environ.get(ENGINE_ENV, "compile").lower() == "creao" else "compile"

    @property
    def enabled(self) -> bool:
        if os.environ.get(FLAG_ENV, "") != "1":
            return False
        if self.engine == "compile":
            return bool(os.environ.get("ANTHROPIC_API_KEY"))
        return self.runs is not None and self.runs.enabled

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
    def try_start(self, req: GoalRequest, *, doc_urls: Optional[list[str]] = None) -> bool:
        """True iff research was started for this unmatched request (the caller then answers RESEARCHING)."""
        text = (req.text or "").strip()
        task = self.rt.assistant.tasks.get(req.session_id)
        # doc_urls come from an explicitly confirmed product: its identity is settled, whatever an earlier chat left open.
        if not doc_urls and task and (task.critical_unknowns or task.confirmation_pending):
            return False
        if not self.enabled or self.active is not None or len(text.split()) < 2:
            return False
        sess = self.rt.sessions.active
        if sess is None or sess.id != req.session_id or sess.phase != "menu":
            return False
        if self.engine == "compile":
            return self._start_compile(req, text, urls=doc_urls)
        if self.runs is None:
            return False
        from .research_runs import RunBody, RunRejected

        cached_id = self._cached_run(text, req.mode)
        if cached_id is None and self.started >= self._max():
            return False
        try:
            run_id = cached_id or self.runs.start(RunBody(session_id=req.session_id, goal=text[:300], intent=req.mode, fast=os.environ.get(FAST_ENV, "1") != "0",
                                       audience=self.rt.assistant.audience_for(req.session_id), doc_urls=doc_urls or []))
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

    def prefetch(self, task_id: str, goal: str) -> None:
        """Research while conversing: find and fetch the official sources for an uncached goal while the person answers.
        Keyed by the task id, so a correction or a new goal (new id / revision) never reuses mismatched sources."""
        if not (self.enabled and self.engine == "compile") or task_id in self._prefetched or len(goal.split()) < 2:
            return
        import threading

        self._prefetched[task_id] = {"goal": goal, "urls": None}
        root = self.rt.asset_root

        def work() -> None:
            try:
                from knowledge.find_sources import find_sources
                from knowledge.sources import fetch

                urls, _ = find_sources(goal)
                for u in urls:
                    try:
                        fetch(u, root)  # warms the page cache the compiler reads
                    except Exception:
                        log.info("prefetch could not read %s", u)
                if task_id in self._prefetched:
                    self._prefetched[task_id]["urls"] = urls
            except Exception as exc:
                log.info("prefetch failed: %s", type(exc).__name__)

        threading.Thread(target=work, name="gb-prefetch", daemon=True).start()

    def _start_compile(self, req: GoalRequest, text: str, urls: Optional[list[str]] = None) -> bool:
        """Official-source compiler as the research engine: search -> fetch -> compile -> verify, on a worker thread."""
        if self.started >= self._max():
            return False
        import threading
        import uuid

        run_id = "c-" + uuid.uuid4().hex[:8]
        audience = self.rt.assistant.audience_for(req.session_id) or ""
        task = self.rt.assistant.tasks.get(req.session_id)
        pre = self._prefetched.get(task.research_key()) if task else None  # same task, revision and identity only
        pre_urls = list(pre["urls"]) if pre and pre.get("urls") else None
        given = list(urls) if urls else None  # the confirmed product's own official documents: no web search
        self.started += 1
        self.active = {"run_id": run_id, "session_id": req.session_id, "goal": text[:300], "mode": req.mode, "started": self._now(),
                       "engine": "compile", "stage": "finding official sources"}
        self.rt.sessions.begin_research(req.session_id, text)
        self.rt.elog.write("live_research", event="started", run_id=run_id, goal=text[:300], engine="compile")
        root = self.rt.asset_root

        def work() -> None:
            out: dict = {"run_id": run_id}
            try:
                from knowledge.compile import compile_task
                from knowledge.find_sources import find_sources

                if given:
                    urls, search = given, {"given": True, "picked": given}
                elif pre_urls:
                    urls, search = pre_urls, {"prefetched": True, "picked": pre_urls}
                else:
                    urls, search = find_sources(text)
                out["search"] = search
                if not urls:
                    raise ValueError("no official or specialist source found")
                if self.active and self.active.get("run_id") == run_id:
                    self.active["stage"] = "reading and compiling " + ", ".join(u.split("/")[2] for u in urls)
                card, stats = compile_task(text, urls, root=root, context=audience,
                                           vision=os.environ.get("GB_COMPILE_VISION_LIVE", "0") == "1")
                folder = root / "knowledge" / "live" / "compiled_cards" / card["card_id"]
                folder.mkdir(parents=True, exist_ok=True)
                (folder / "card.json").write_text(json.dumps(card, indent=2, ensure_ascii=False))
                (folder / "compile.json").write_text(json.dumps({**stats, "search": search}, indent=2, ensure_ascii=False))
                out.update(card=card, stats=stats)
            except Exception as exc:  # an honest failure, never a made-up guide
                log.warning("live compile failed: %s", exc)
                out["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
            self._done.put(out)

        threading.Thread(target=work, name="gb-compile", daemon=True).start()
        return True

    def _finish_compile(self, out: dict, act: dict, took: float) -> None:
        if out.get("error") or not out.get("card"):
            self.last = {"run_id": act["run_id"], "goal": act["goal"], "ok": False, "status": "failed", "error": out.get("error"),
                         "engine": "compile", "took_s": round(took, 1), "at": time.time()}
            if self.rt.discovery is not None:
                self.rt.discovery.research_finished(act["session_id"], None)  # first: its redraw would clear the flash below
            self.rt.sessions.fail_research(Cue(line1="NO RELIABLE GUIDE", line2="NO VERIFIED SOURCE FOUND"))
            self.rt.elog.write("live_research", event="failed", run_id=act["run_id"], engine="compile", error=out.get("error"),
                               picked=(out.get("search") or {}).get("picked"))
            return
        card = Card.model_validate(out["card"])
        self.durations.append(took)
        if all(c.card_id != card.card_id for c in self.rt.cards):
            self.rt.cards = [*self.rt.cards, card]
        self.cards[card.card_id] = {"run_id": act["run_id"], "draft_id": "compiled:" + card.card_id, "goal": act["goal"]}
        self.rt.cache.remember_guide(act["goal"], act["mode"], card, self.cards[card.card_id])
        self.last = {"run_id": act["run_id"], "goal": act["goal"], "ok": True, "status": "compiled", "engine": "compile", "card_id": card.card_id,
                     "took_s": round(took, 1), "sources": [s.url for s in card.sources], "stats": {k: out["stats"].get(k) for k in ("compile_s", "fetch_s", "rounds")},
                     "at": time.time()}
        cue = goal_mod.task_cue(card, card.goal_mode)
        if self.rt.discovery is not None:
            self.rt.discovery.research_finished(act["session_id"], card)  # before the start: the overlay steps aside
        started = self.rt.sessions.finish_research(act["session_id"], card, Cue(line1=cue.line1, line2="COMPILED FROM SOURCES"))
        self.rt.elog.write("live_research", event="ready", run_id=act["run_id"], card_id=card.card_id, started=started, engine="compile", took_s=round(took, 1))

    def _cached_run(self, text: str, mode: str = "build") -> Optional[str]:
        """A finished, still-loadable draft for the same request (any session, any earlier start): reuse it instead of paying again."""
        from knowledge.importer import drafts_dir

        if not self.rt.cache.enabled or self.runs is None:
            return None
        key = goal_key(text, mode)
        for rec in self.runs.list():
            if rec.get("status") == "draft_ready" and rec.get("draft_id") and goal_key(str(rec.get("goal", "")), rec.get("intent") or "build") == key:
                if (drafts_dir(self.rt.asset_root) / rec["draft_id"] / "envelope.json").is_file():
                    return rec["run_id"]
        return None

    def recover_draft(self, card_id: str) -> Optional[Card]:
        """After a restart: reload the newest on-disk draft a persisted session was following (still AI-researched, unreviewed)."""
        from knowledge.importer import drafts_dir

        try:
            compiled = self.rt.asset_root / "knowledge" / "live" / "compiled_cards" / card_id / "card.json"
            dirs = sorted((d for d in drafts_dir(self.rt.asset_root).glob(card_id + "-*") if (d / "envelope.json").is_file()), reverse=True)
            if compiled.is_file():
                card, dirs = Card.model_validate(json.loads(compiled.read_text())), [compiled.parent]
            elif not dirs:
                return None
            else:
                card = Card.model_validate(json.loads((dirs[0] / "envelope.json").read_text())["card"])
        except (ValueError, OSError, KeyError, TypeError):
            return None
        if card.card_id != card_id:
            return None
        if all(c.card_id != card_id for c in self.rt.cards):
            self.rt.cards.append(card)
        self.cards.setdefault(card_id, {"run_id": "", "draft_id": dirs[0].name, "goal": card.title})
        return card

    def cached_guide(self, text: str, mode: str):
        """Reuse a finished on-disk draft even while providers/paid research are off."""
        run_id = self._cached_run(text, mode)
        if run_id is None:
            return None
        from knowledge.importer import drafts_dir
        rec = self.runs.get(run_id) or {}
        try:
            env = json.loads((drafts_dir(self.rt.asset_root) / rec["draft_id"] / "envelope.json").read_text())
            card = Card.model_validate(env["card"])
        except (ValueError, OSError, KeyError):
            return None
        review = {"run_id":run_id,"draft_id":rec["draft_id"],"goal":rec.get("goal",text)}
        self.rt.cache.remember_guide(text,mode,card,review)
        return card, review

    # ------------------------------------------------------------------ finish (main loop, from tick)
    def pump(self) -> None:
        while True:
            try:
                run_id = self._done.get_nowait()
            except queue.Empty:
                return
            act = self.active
            if isinstance(run_id, dict):  # a compile-engine result
                if act is None or act["run_id"] != run_id.get("run_id"):
                    continue
                self.active = None
                self._finish_compile(run_id, act, self._now() - act["started"])
                continue
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
        self.rt.cache.remember_guide(act["goal"], act["mode"], card, self.cards[card.card_id])
        cue = goal_mod.task_cue(card, card.goal_mode)
        cue = Cue(line1=cue.line1, line2="AI RESEARCHED, UNREVIEWED")
        started = self.rt.sessions.finish_research(act["session_id"], card, cue)
        self.rt.elog.write("live_research", event="ready", run_id=rec["run_id"], card_id=card.card_id, started=started)
        return True

    # ------------------------------------------------------------------ view (phone)
    def view(self) -> dict:
        act = self.active
        rec = (self.runs.get(act["run_id"]) if (act and self.runs and act.get("engine") != "compile") else None) or {}
        return {
            "enabled": self.enabled,
            "active": None if act is None else {
                "run_id": act["run_id"], "goal": act["goal"], "elapsed_s": int(self._now() - act["started"]),
                "status": rec.get("status") or act.get("stage"), "creao_status": rec.get("creao_status"), "engine": act.get("engine", "creao"),
                "progress": estimate(self._now() - act["started"], self.expected_s()),
            },
            "last": self.last,
            "unreviewed_cards": sorted(self.cards),
            "note": UNREVIEWED_NOTE,
            "started": self.started, "max": self._max(),
        }
