"""Optional async research runs (feature flag GB_CREAO=1) and human approval of the resulting drafts.

Build-time tooling only: nothing here touches the HUD, the engine or any cue. A run is started by a human (phone page or API),
executed in a background thread (start -> poll -> normalize -> validate -> store a DRAFT under knowledge/drafts/), and a draft
reaches the glasses only after `POST /cards/drafts/{id}/approve` (admin token + reviewer name -> knowledge.approve) and a
card reload. The live loop never waits for any of it. The CREAO API key is read from the environment by the client, never
stored here, and every error string is redacted before it is logged or put in the run table.

UNVERIFIED against the real CREAO API: see knowledge/creao.py. The knowledge package is imported lazily so core still runs
without it.
"""

from __future__ import annotations

import contextlib
import hmac
import io
import json
import logging
import os
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

log = logging.getLogger("ghostbuild.research_runs")

FLAG_ENV = "GB_CREAO"
ADMIN_ENV = "GB_ADMIN_TOKEN"
TOKEN_HEADER = "x-ghostbuild-token"
MIN_GAP_S = 10.0
MAX_RUNS_PER_PROCESS = 20
KEEP_RUNS = 60
STATUSES = ("queued", "running", "failed", "draft_ready", "invalid")
HTTP_URL = re.compile(r"^https?://[^\s/$.?#][^\s]*$", re.IGNORECASE)
_approve_lock = threading.Lock()


class RunBody(BaseModel):
    """POST /research/run body (core-local; not a cross-lane contract)."""

    model_config = ConfigDict(extra="forbid")
    session_id: Optional[str] = Field(default=None, max_length=64)
    goal: str = Field(min_length=1, max_length=300)
    device: Optional[str] = Field(default=None, max_length=120)
    model: Optional[str] = Field(default=None, max_length=120)
    intent: Optional[str] = Field(default=None, max_length=40)
    doc_urls: list[str] = Field(default_factory=list, max_length=5)
    video_urls: list[str] = Field(default_factory=list, max_length=5)
    follow_up: Optional[str] = Field(default=None, max_length=500)

    @field_validator("doc_urls", "video_urls")
    @classmethod
    def _http_only(cls, urls: list[str]) -> list[str]:
        for u in urls:
            if not HTTP_URL.match(u.strip()):
                raise ValueError(f"only http(s) URLs are accepted: {u[:80]!r}")
        return [u.strip() for u in urls]

    @field_validator("goal")
    @classmethod
    def _goal(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("goal must not be blank")
        return v.strip()


class ApproveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reviewer: str = Field(min_length=1, max_length=80)


class RunRejected(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def creao_requested() -> bool:
    return os.environ.get(FLAG_ENV, "") == "1"


class ResearchRuns:
    """Run table + background worker. `client_factory` (tests) returns a knowledge.creao.CreaoClient; by default one is built from env."""

    def __init__(
        self,
        asset_root: Path | str,
        *,
        enabled: Optional[bool] = None,
        client_factory: Optional[Callable[[], Any]] = None,
        poll_interval: float = 3.0,
        max_wait: float = 900.0,
        min_gap_s: float = MIN_GAP_S,
        max_runs: int = MAX_RUNS_PER_PROCESS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.root = Path(asset_root)
        self.dir = self.root / "knowledge" / "requests"
        self.path = self.dir / "creao_runs.json"
        self._factory = client_factory
        self.poll_interval = poll_interval
        self.max_wait = max_wait
        self.min_gap_s = min_gap_s
        self.max_runs = max_runs
        self._clock = clock
        self._lock = threading.RLock()
        self._runs: dict[str, dict] = {}
        self._started = 0
        self._last_start: Optional[float] = None
        self._flag = creao_requested() if enabled is None else enabled
        self._load()

    # ------------------------------------------------------------------ enable / status
    def _has_key(self) -> bool:
        return self._factory is not None or bool(os.environ.get("CREAO_API_KEY"))

    @property
    def enabled(self) -> bool:
        return self._flag and self._has_key()

    def status(self) -> dict:
        reason = None
        if not self._flag:
            reason = f"{FLAG_ENV} is not 1"
        elif not self._has_key():
            reason = "CREAO_API_KEY is not set"
        return {
            "enabled": self.enabled,
            "reason": reason,
            "approval": bool(os.environ.get(ADMIN_ENV)),
            "limits": {"max_runs_per_process": self.max_runs, "min_seconds_between_runs": self.min_gap_s, "active_runs": 1},
            "started_this_process": self._started,
        }

    # ------------------------------------------------------------------ persistence
    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for rec in raw.get("runs", [])[-KEEP_RUNS:]:
                if isinstance(rec, dict) and isinstance(rec.get("run_id"), str):
                    if rec.get("status") in ("queued", "running"):
                        rec["status"] = "failed"
                        rec["error"] = "interrupted by a core restart; the CREAO run may still have finished in CREAO"
                    self._runs[rec["run_id"]] = rec
        except FileNotFoundError:
            pass
        except Exception:
            log.exception("could not read %s", self.path)

    def _save(self) -> None:
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"runs": list(self._runs.values())[-KEEP_RUNS:]}, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)
        except Exception:
            log.exception("could not persist the run table")

    def _update(self, run_id: str, **fields: Any) -> None:
        with self._lock:
            rec = self._runs.get(run_id)
            if rec is None:
                return
            rec.update(fields)
            rec["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._save()

    # ------------------------------------------------------------------ views
    def list(self) -> list[dict]:
        with self._lock:
            return [dict(r) for r in reversed(list(self._runs.values()))]

    def get(self, run_id: str) -> Optional[dict]:
        with self._lock:
            rec = self._runs.get(run_id)
            return dict(rec) if rec else None

    # ------------------------------------------------------------------ start
    def start(self, body: RunBody) -> str:
        if not self.enabled:
            raise RunRejected(503, "creao disabled")
        with self._lock:
            # A lost phone response or double submit must not spend another run. Reuse this session's
            # identical in-flight/cached draft; a changed goal/context or a new session starts new research.
            if body.session_id:
                request_fields = body.model_dump()
                for rec in reversed(list(self._runs.values())):
                    if rec.get("status") in ("queued", "running", "draft_ready") and all(rec.get(k) == v for k, v in request_fields.items()):
                        if rec["status"] != "draft_ready" or self.draft_preview(rec.get("draft_id") or "") is not None:
                            return rec["run_id"]
            if any(r["status"] in ("queued", "running") for r in self._runs.values()):
                raise RunRejected(429, "a research run is already active; wait for it to finish")
            if self._started >= self.max_runs:
                raise RunRejected(429, f"run cap reached ({self.max_runs} per process) to protect credits; restart core to reset it")
            now = self._clock()
            if self._last_start is not None and now - self._last_start < self.min_gap_s:
                raise RunRejected(429, f"one new run per {self.min_gap_s:.0f} s; try again shortly")
            run_id = "r-" + secrets.token_hex(4)
            stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._runs[run_id] = {
                "run_id": run_id, "creao_run_id": None, "share_url": None, "status": "queued", "creao_status": None, "error": None, "draft_id": None,
                "goal": body.goal, "device": body.device, "model": body.model, "intent": body.intent, "session_id": body.session_id,
                "doc_urls": body.doc_urls, "video_urls": body.video_urls, "follow_up": body.follow_up,
                "created_at": stamp, "updated_at": stamp, "validation_errors": [], "approved_by": None,
            }
            self._started += 1
            self._last_start = now
            self._save()
        threading.Thread(target=self._work, args=(run_id, body), name=f"creao-{run_id}", daemon=True).start()
        return run_id

    # ------------------------------------------------------------------ worker (never the live loop)
    def _make_client(self) -> Any:
        if self._factory is not None:
            return self._factory()
        from knowledge.creao import CreaoClient

        return CreaoClient()

    def _work(self, run_id: str, body: RunBody) -> None:
        client = None
        try:
            from knowledge import creao, creao_normalize
            from knowledge.importer import validate_envelope, write_draft

            client = self._make_client()
            inputs = {"goal": body.goal, "device": body.device, "model": body.model, "intent": body.intent,
                      "doc_urls": body.doc_urls, "video_urls": body.video_urls, "follow_up": body.follow_up}
            creao_id = client.start_run(inputs)
            self._update(run_id, creao_run_id=creao_id, status="running", share_url=creao.find_share_url(client.last_start_response))
            raw = client.poll(creao_id, interval=self.poll_interval, max_wait=self.max_wait,
                              on_update=lambda status, _raw: self._update(run_id, creao_status=status))
            if creao.run_state(raw)[0] == "success" and hasattr(client, "attach_json_artifacts"):
                raw = client.attach_json_artifacts(raw)  # the structured playbook is a JSON artifact, not inline text
            try:
                creao.save_raw(creao_id, {"inputs": inputs, "start_response": client.last_start_response, "final": raw},
                               self.dir / "creao_raw", key=getattr(client, "_api_key", None))
            except Exception:
                log.exception("could not save the raw CREAO response")
            state, status = creao.run_state(raw)
            share_url = creao.find_share_url(raw) or creao.find_share_url(client.last_start_response)
            self._update(run_id, creao_status=status, share_url=share_url)
            if state == "failed":
                detail = creao.failure_detail(raw, getattr(client, "_api_key", None))
                self._update(run_id, status="failed", creao_status=status, error=f"CREAO run ended {status}" + (f": {detail}" if detail else ""))
                return
            envelope = creao_normalize.normalize(raw, body.goal, run_id=creao_id, device=body.device or "", model=body.model or "", intent=body.intent or "")
            if creao_normalize.is_error(envelope):
                err = envelope["error"]
                self._update(run_id, status="invalid", error=err["message"], validation_errors=[f"{err['message']} (found: {', '.join(map(str, err['found'][:12]))})"])
                return
            result = validate_envelope(envelope, self.root)
            if not result["ok"]:
                self._save_envelope(creao_id, envelope)
                self._update(run_id, status="invalid", error=f"{len(result['errors'])} validation error(s)", validation_errors=result["errors"][:40])
                return
            envelope["provider"] = {"name": "CREAO", "app_id": getattr(client, "app_id", creao.DEFAULT_APP_ID),
                                    "run_id": creao_id, "share_url": share_url, "live_api_verified": self._factory is None}
            draft_id = write_draft(envelope, self.root)
            self._update(run_id, status="draft_ready", draft_id=draft_id, error=None, validation_errors=[])
        except Exception as exc:  # the worker must never raise into the void
            msg = client.redact(exc) if client is not None and hasattr(client, "redact") else _scrub(str(exc))
            log.warning("research run %s failed: %s", run_id, msg[:300])
            self._update(run_id, status="failed", error=msg[:600])

    def _save_envelope(self, creao_id: str, envelope: dict) -> None:
        try:
            d = self.dir / "creao_raw"
            d.mkdir(parents=True, exist_ok=True)
            safe = re.sub(r"[^A-Za-z0-9_.-]", "_", creao_id)[:80]
            (d / f"{safe}.envelope.json").write_text(json.dumps(envelope, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            log.exception("could not save the invalid envelope")

    # ------------------------------------------------------------------ draft preview
    def draft_preview(self, draft_id: str) -> Optional[dict]:
        from knowledge.importer import DRAFT_ID, drafts_dir, validate_envelope

        if not DRAFT_ID.match(draft_id):
            return None
        try:
            env = json.loads((drafts_dir(self.root) / draft_id / "envelope.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        card = env.get("card", {})
        research = env.get("research", {})
        result = validate_envelope(env, self.root)
        guides = card.get("guides") or []
        return {
            "draft_id": draft_id,
            "card_id": card.get("card_id"),
            "title": card.get("title"),
            "goal_mode": card.get("goal_mode"),
            "provenance": card.get("provenance"),
            "provider": env.get("provider"),
            "provenance_note": "DRAFT: not reviewed by a human; it cannot reach the glasses until approved",
            "aliases": card.get("aliases", []),
            "steps": [
                {"id": s["id"], "title": s["title"], "cue": s["cue"], "detail": s.get("detail", ""), "warnings": s.get("warnings", []),
                 "why": s.get("why"), "check": "measured" if s.get("verify") else "manual",
                 "cites": [c for t in s.get("troubleshoot", []) for c in t.get("cites", [])]}
                for s in card.get("steps", [])
            ],
            "sources": [{"id": s["id"], "kind": s["kind"], "title": s["title"], "url": s.get("url")} for s in card.get("sources", [])],
            "video_notes": research.get("video_notes", []),
            "uncertainties": research.get("uncertainties", []),
            "visual_references": [{**v, "reference_only": True} for v in research.get("visual_references", [])],
            "reference_only_note": "reference only — no picture on glasses",
            "guides": len(guides),
            "pictures_on_glasses": bool(guides),
            "validation": result,
        }


def _scrub(text: str) -> str:
    from knowledge.creao import redact

    return redact(text)


# ----------------------------------------------------------------------------- HTTP
def _admin_check(request: Request) -> None:
    expected = os.environ.get(ADMIN_ENV, "")
    if not expected:
        raise HTTPException(status_code=503, detail="approval disabled (GB_ADMIN_TOKEN is not set)")
    supplied = request.headers.get(TOKEN_HEADER, "")
    if not hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=401, detail="bad token")


def approve_draft(runtime, runs: ResearchRuns, draft_id: str, reviewer: str) -> dict:
    """Run knowledge.approve for one draft and reload the cards. Raises HTTPException with a readable reason on refusal."""
    from knowledge import approve as approve_mod
    from knowledge.importer import DRAFT_ID, drafts_dir

    if not DRAFT_ID.match(draft_id):
        raise HTTPException(status_code=404, detail="unknown draft")
    envelope_path = drafts_dir(runtime.asset_root) / draft_id / "envelope.json"
    try:
        envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise HTTPException(status_code=404, detail="unknown draft")
    card = envelope.get("card", {})
    clash = [
        (alias, c.card_id)
        for alias in {a.strip().lower() for a in card.get("aliases", []) if isinstance(a, str)}
        for c in runtime.cards
        if c.card_id != card.get("card_id") and c.goal_mode == card.get("goal_mode") and alias in {x.strip().lower() for x in c.aliases}
    ]
    if clash:
        raise HTTPException(status_code=409, detail=f"alias clash with a loaded card (the goal resolver would be ambiguous): {clash[0][0]!r} is also an alias of {clash[0][1]!r}; edit the draft aliases first")
    out = io.StringIO()
    with _approve_lock, contextlib.redirect_stdout(out):
        rc = approve_mod.main([draft_id, "--reviewer", reviewer.strip(), "--root", str(runtime.asset_root)])
    if rc != 0:
        lines = [ln for ln in out.getvalue().splitlines() if ln.startswith(("ERROR", "REFUSED"))]
        raise HTTPException(status_code=409, detail="; ".join(lines[-4:]) or "approval refused")
    reload = runtime.reload_cards()
    with runs._lock:
        for rec in runs._runs.values():
            if rec.get("draft_id") == draft_id:
                rec["approved_by"] = reviewer.strip()
        runs._save()
    return {"approved": True, "draft_id": draft_id, "card_id": card.get("card_id"), "reviewer": reviewer.strip(), "reload": reload}


def mount_research_runs(app: FastAPI, runtime, runs: Optional[ResearchRuns] = None) -> ResearchRuns:
    runs = runs or ResearchRuns(runtime.asset_root)
    app.state.research_runs = runs

    @app.get("/research/status")
    async def get_status() -> Response:
        return JSONResponse(runs.status())

    @app.post("/research/run", status_code=202)
    async def post_run(request: Request) -> Response:
        if not runs.enabled:
            raise HTTPException(status_code=503, detail="creao disabled")
        try:
            body = RunBody.model_validate(json.loads(await request.body()))
        except (ValidationError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)[:500])
        try:
            run_id = runs.start(body)
        except RunRejected as exc:
            raise HTTPException(status_code=exc.status, detail=exc.detail)
        return JSONResponse({"run_id": run_id, "status": runs.get(run_id)["status"]}, status_code=202)

    @app.get("/research/runs")
    async def get_runs() -> Response:
        return JSONResponse({"runs": runs.list()})

    @app.get("/research/runs/{run_id}")
    async def get_run(run_id: str) -> Response:
        rec = runs.get(run_id)
        if rec is None:
            raise HTTPException(status_code=404, detail="unknown run")
        if rec.get("draft_id"):
            rec["draft"] = runs.draft_preview(rec["draft_id"])
        return JSONResponse(rec)

    @app.post("/cards/drafts/{draft_id}/approve")
    async def post_approve(draft_id: str, request: Request) -> Response:
        _admin_check(request)
        try:
            body = ApproveBody.model_validate(json.loads(await request.body()))
        except (ValidationError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="reviewer (non-empty name) is required")
        if not body.reviewer.strip():
            raise HTTPException(status_code=422, detail="reviewer (non-empty name) is required")
        return JSONResponse(approve_draft(runtime, runs, draft_id, body.reviewer))

    return runs
