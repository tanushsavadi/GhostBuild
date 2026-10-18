"""Core HTTP + WebSocket server on :8787.

  WS  /ws?role=g2       g2_input in, hud frames out        WS /ws?role=jig   jig observations in
  WS  /ws?role=mirror   hud frames out (mirror/review)      GET /state, /health
  GET /procedures, /procedures/{id}, /procedures/schema, /jigs
  POST /procedures/validate, /agent/webhook, /procedures/{id}/approve, /session/load, /input
  POST /compile (GB_CREAO=1)   POST /sim/jig (--simulate-jig only)   GET /review
  POST /ptt {phase: start|cancel}, POST /audio (raw 16 kHz s16le mono PCM)   hold-to-talk (GB_VOICE)
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError

from contracts.models import AgentDelivery, G2Input, JigObservation, JigStatus, Procedure, State, ValidateResult

from . import store as store_mod
from . import stt
from .engine import Engine
from .hud import Hud

ROOT = Path(__file__).resolve().parents[2]
REVIEW_PAGE = ROOT / "compiler" / "review" / "index.html"
BUILD_REQUEST = re.compile(r"^(?:teach me(?: how)? to|i want to (?:build|make)|help me (?:build|make)|how do i (?:build|make))\s+(.+)$", re.I)


def flag(name: str) -> bool:
    return os.environ.get(name, "0") == "1"


def voice_on() -> bool:
    """Hold-to-talk: on by default once a speech-to-text key is configured; GB_VOICE=0 turns it off."""
    return os.environ.get("GB_VOICE", "1") == "1" and stt.available()


@dataclass
class Config:
    simulate_jig: bool = False
    jig_enabled: bool = True
    procedure: str | None = None


@dataclass
class Core:
    cfg: Config
    engine: Engine
    hud: Hud
    store: store_mod.Store
    g2: set = field(default_factory=set)
    mirrors: set = field(default_factory=set)
    sim_fields: dict | None = None
    compiles: list = field(default_factory=list)
    log_path: Path | None = None

    def log(self, kind: str, data: object) -> None:
        if self.log_path:
            with self.log_path.open("a") as f:
                f.write(json.dumps({"at": time.time(), "kind": kind, "data": data}, default=str) + "\n")

    async def push(self, force: bool = False) -> None:
        force = force or self.engine.force
        self.engine.force = False
        frame = self.hud.update(self.engine.view(), force=force)
        if frame is None:
            return
        self.log("hud", frame.model_dump())
        msg = frame.model_dump_json()
        for ws in list(self.g2 | self.mirrors):
            try:
                await ws.send_text(msg)
            except Exception:
                self.g2.discard(ws)
                self.mirrors.discard(ws)

    def state(self) -> State:
        e = self.engine
        if not e.jig_enabled:
            jig = JigStatus(link="disabled")
        else:
            age = int((e.clock() - e.jig_at) * 1000) if e.jig_at else None
            jig = JigStatus(link="up" if e.jig_fresh() else "down", source=e.jig_source, fields=e.jig_fields, age_ms=age)
        return State(
            engine=e.engine_state,
            procedure_id=e.proc.id if e.proc else None,
            procedure_title=e.proc.title if e.proc else None,
            step_index=e.idx if e.proc else None,
            step_total=len(e.proc.steps) if e.proc else None,
            completed=list(e.completed.values()),
            jig=jig,
            hud=self.hud.last,
            events=e.events[-30:],
        )


def create_app(cfg: Config | None = None) -> FastAPI:
    cfg = cfg or Config()
    profiles = store_mod.load_profiles()
    engine = Engine(profiles, jig_enabled=cfg.jig_enabled)
    core = Core(cfg, engine, Hud(source="simulated" if cfg.simulate_jig else "live"), store_mod.Store(profiles))
    logs = ROOT / "logs"
    logs.mkdir(exist_ok=True)
    core.log_path = logs / f"session-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    if cfg.procedure:
        p = core.store.get(cfg.procedure)
        if p is None:
            raise SystemExit(f"unknown procedure {cfg.procedure!r}; approved: {sorted(core.store.approved())}")
        engine.load(p)
    if cfg.simulate_jig:
        core.sim_fields = {k: v[0] for k, v in next(iter(profiles.values())).fields.items()} if profiles else {}

    async def loop() -> None:
        while True:
            await asyncio.sleep(0.1)
            if core.sim_fields is not None:
                engine.on_jig(core.sim_fields, source="simulated")
            engine.tick()
            await core.push()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.create_task(loop())
        yield
        task.cancel()

    app = FastAPI(title="GhostBuild core", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.state.core = core

    async def handle_input(inp: G2Input) -> None:
        core.log("g2_input", inp.model_dump())
        m = BUILD_REQUEST.match((inp.text or "").strip()) if inp.kind == "voice" else None
        if m and flag("GB_VOICE_COMPILE"):
            start_compile(m.group(1).rstrip(".?!"))
        else:
            engine.on_input(inp)
        await core.push()

    def start_compile(request: str) -> dict:
        from compiler import creao_client

        entry = {"request": request, "status": "starting", "at": time.time()}
        core.compiles.append(entry)
        if not creao_client.configured():
            entry["status"] = "not configured (CREAO_API_KEY, CREAO_TRIGGER_URL, GB_PUBLIC_URL)"
            engine.say("COMPILER NOT SET UP")
            return entry
        engine.say("RESEARCHING YOUR BUILD", seconds=8)

        async def run() -> None:
            try:
                entry.update(await asyncio.to_thread(creao_client.trigger, request), status="running")
            except Exception as exc:  # report, never crash the live loop
                entry["status"] = f"trigger failed: {exc}"
                engine.say("COMPILE FAILED · SEE PHONE")
            core.log("compile", entry)

        asyncio.get_running_loop().create_task(run())
        return entry

    # --- websockets ------------------------------------------------------------------------------

    @app.websocket("/ws")
    async def ws(socket: WebSocket, role: str = "g2") -> None:
        await socket.accept()
        if role in ("g2", "mirror"):
            (core.g2 if role == "g2" else core.mirrors).add(socket)
            if core.hud.last:
                await socket.send_text(core.hud.last.model_dump_json())
            else:
                await core.push(force=True)
        try:
            while True:
                raw = await socket.receive_text()
                try:
                    data = json.loads(raw)
                    if role == "jig":
                        obs = JigObservation.model_validate(data)
                        engine.on_jig(obs.fields, source="live")
                        await core.push()
                    elif role == "g2":
                        await handle_input(G2Input.model_validate(data))
                except (ValueError, ValidationError) as exc:
                    await socket.send_text(json.dumps({"type": "error", "error": str(exc)[:300]}))
        except WebSocketDisconnect:
            pass
        finally:
            core.g2.discard(socket)
            core.mirrors.discard(socket)

    # --- http ------------------------------------------------------------------------------------

    @app.get("/health")
    def health() -> dict:
        s = core.state()
        return {"ok": True, "engine": s.engine, "procedure": s.procedure_id, "jig": s.jig.link,
                "source": core.hud.source, "g2_connected": len(core.g2), "mirrors": len(core.mirrors),
                "creao": flag("GB_CREAO"), "voice": voice_on(), "voice_compile": flag("GB_VOICE_COMPILE")}

    @app.get("/state")
    def state() -> dict:
        return {**json.loads(core.state().model_dump_json()), "compiles": core.compiles[-10:]}

    @app.post("/input")
    async def post_input(inp: G2Input) -> dict:
        await handle_input(inp)
        return {"ok": True, "hud": core.hud.last.model_dump() if core.hud.last else None}

    @app.get("/procedures")
    def procedures() -> dict:
        row = lambda p: {"id": p.id, "title": p.title, "domain": p.domain, "origin": p.origin,  # noqa: E731
                         "review": p.review.status, "steps": len(p.steps), "jig_profile": p.jig_profile}
        return {"approved": [row(p) for p in core.store.approved().values()],
                "drafts": [row(p) for p in core.store.drafts().values()]}

    @app.get("/procedures/schema")
    def schema() -> dict:
        return AgentDelivery.model_json_schema(by_alias=True)

    @app.get("/procedures/{pid}")
    def procedure(pid: str) -> dict:
        p = core.store.get(pid)
        if p is None:
            raise HTTPException(404, f"no procedure {pid!r}")
        return store_mod.dump(p)

    @app.get("/jigs")
    def jigs() -> dict:
        return {k: json.loads(v.model_dump_json(by_alias=True)) for k, v in profiles.items()}

    def unwrap(body: object) -> object:
        return body.get("procedure", body) if isinstance(body, dict) else body

    @app.post("/procedures/validate")
    async def validate(request: Request) -> dict:
        body = await request.json()
        _, errors = store_mod.validate(unwrap(body), profiles)
        core.log("validate", {"ok": not errors, "errors": errors[:20]})
        return ValidateResult(ok=not errors, errors=errors).model_dump()

    @app.post("/agent/webhook")
    async def webhook(request: Request) -> JSONResponse:
        token = os.environ.get("GB_WEBHOOK_TOKEN")
        if token and request.headers.get("x-ghostbuild-token") != token:
            raise HTTPException(401, "bad token")
        body = await request.json()
        proc, errors = store_mod.validate(unwrap(body), profiles)
        if proc is None:
            return JSONResponse(ValidateResult(ok=False, errors=errors).model_dump(), status_code=422)
        draft = core.store.save_draft(proc)
        run_id = body.get("run_id") if isinstance(body, dict) else None
        for c in core.compiles:
            if c.get("compile_id") == run_id:
                c["status"], c["procedure_id"] = "delivered", draft.id
        core.log("delivery", {"run_id": run_id, "procedure_id": draft.id})
        engine.say("NEW BUILD READY · SEE PHONE")
        await core.push()
        return JSONResponse({"ok": True, "procedure_id": draft.id, "review": "draft"})

    @app.post("/procedures/{pid}/approve")
    async def approve(pid: str, body: dict | None = None) -> dict:
        reviewer = (body or {}).get("reviewer") or "reviewer"
        try:
            p = core.store.approve(pid, reviewer)
        except KeyError:
            raise HTTPException(404, f"no draft {pid!r}")
        core.log("approve", {"procedure_id": pid, "reviewer": reviewer})
        return {"ok": True, "procedure_id": p.id}

    @app.post("/session/load")
    async def load(body: dict) -> dict:
        p = core.store.approved().get(body.get("procedure_id", ""))
        if p is None:
            raise HTTPException(409, "only approved procedures can run on the glasses")
        engine.load(p)
        core.log("load", {"procedure_id": p.id})
        await core.push(force=True)
        return {"ok": True}

    @app.post("/session/stop")
    async def stop() -> dict:
        engine.unload()
        await core.push(force=True)
        return {"ok": True}

    @app.post("/ptt")
    async def ptt(body: dict) -> dict:
        phase = body.get("phase")
        if phase == "start":
            engine.say("LISTENING..." if voice_on() else "VOICE OFF · TAP INSTEAD", seconds=15)
        elif phase == "cancel":
            engine.notice = None
        core.log("ptt", {"phase": phase})
        await core.push()
        return {"ok": True, "voice": voice_on()}

    @app.post("/audio")
    async def audio(request: Request) -> dict:
        pcm = await request.body()
        if not voice_on():
            engine.say("VOICE OFF · TAP INSTEAD")
            await core.push()
            return {"ok": False, "error": "voice disabled (set ELEVENLABS_API_KEY; GB_VOICE=0 turns it off)"}
        engine.say("HEARING YOU...", seconds=15)
        await core.push()
        started = time.time()
        try:
            text = await asyncio.to_thread(stt.transcribe, pcm)
        except Exception as exc:  # never crash the live loop on a provider error
            core.log("stt", {"error": str(exc)[:300], "bytes": len(pcm)})
            engine.say("VOICE FAILED · TAP INSTEAD")
            await core.push()
            return {"ok": False, "error": str(exc)[:300]}
        engine.notice = None
        core.log("stt", {"text": text, "bytes": len(pcm), "seconds": round(len(pcm) / stt.BYTES_PER_SECOND, 2),
                         "latency_ms": int((time.time() - started) * 1000)})
        if not text:
            engine.say("DIDN'T CATCH THAT", seconds=3)
            await core.push()
            return {"ok": True, "text": ""}
        await handle_input(G2Input(kind="voice", text=text))
        return {"ok": True, "text": text}

    @app.post("/compile")
    async def compile_(body: dict) -> dict:
        if not flag("GB_CREAO"):
            raise HTTPException(403, "compile disabled (set GB_CREAO=1)")
        request = (body.get("request") or "").strip()
        if not request:
            raise HTTPException(400, "request is required")
        return start_compile(request[:500])

    @app.post("/sim/jig")
    async def sim_jig(body: dict) -> dict:
        if core.sim_fields is None:
            raise HTTPException(403, "start core with --simulate-jig")
        core.sim_fields.update(body)
        engine.on_jig(core.sim_fields, source="simulated")
        await core.push()
        return {"ok": True, "fields": core.sim_fields}

    @app.get("/review")
    def review() -> FileResponse:
        return FileResponse(REVIEW_PAGE)

    return app


def procedure_ids(app: FastAPI) -> list[str]:
    return sorted(app.state.core.store.approved())


__all__ = ["Config", "create_app", "Procedure"]
