"""FastAPI shell over Runtime. All frames come from hud.py via Runtime; this file only moves JSON."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from contracts.models import G2Hello, G2Input, GoalMode, GoalRequest, HudFrame, Observation

from .cards_api import mount_cards_api
from .research_runs import mount_research_runs
from .runtime import Runtime

log = logging.getLogger("ghostbuild.server")


class ResearchRequestBody(BaseModel):
    """POST /research/request body (core-local; not a cross-lane contract)."""

    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(min_length=1, max_length=64)
    mode: GoalMode
    text: str = Field(min_length=1, max_length=300)


class AskBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(default="", max_length=64)
    text: str = Field(min_length=1, max_length=300)


class PhoneAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(min_length=1, max_length=64)
    action: str = Field(pattern="^(press|previous|confirm|next_view|answer_next|answer_previous|choose)$")
    seq_seen: int = Field(ge=0)
    choice: Optional[str] = Field(default=None, max_length=40, description="for choose: the answer id of the current question step")


class StepHelpBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(min_length=1,max_length=64)
    card_id: str = Field(min_length=1,max_length=120)
    step_id: str = Field(min_length=1,max_length=120)


class SpeakBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=500)
    consent: bool = False


def _json(model, status: int = 200) -> Response:
    return Response(content=model.model_dump_json(), media_type="application/json", status_code=status)


def create_app(
    runtime: Runtime,
    *,
    tick_interval: Optional[float] = 0.2,
    sim_interval: Optional[float] = 0.1,
    web_dir: Path | str | None = None,
    research_runs=None,
) -> FastAPI:
    clients: list[asyncio.Queue] = []

    def broadcast(frame: HudFrame) -> None:
        for q in list(clients):
            try:
                q.put_nowait(frame)
            except Exception:  # pragma: no cover
                log.exception("broadcast failed")

    runtime.hud.subscribe(broadcast)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        tasks: list[asyncio.Task] = []

        async def ticker() -> None:
            while True:
                try:
                    runtime.tick()
                except Exception:
                    log.exception("tick failed")
                await asyncio.sleep(tick_interval or 0.2)

        async def simulator() -> None:
            while True:
                try:
                    if runtime.sim is not None:
                        runtime.ingest(runtime.sim.observe())
                except Exception:
                    log.exception("simulator step failed")
                await asyncio.sleep(sim_interval or 0.1)

        if tick_interval:
            tasks.append(asyncio.create_task(ticker()))
        if runtime.sim is not None and sim_interval:
            tasks.append(asyncio.create_task(simulator()))
        try:
            yield
        finally:
            for t in tasks:
                t.cancel()
            runtime.close()

    app = FastAPI(title="GhostBuild core", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.state.runtime = runtime
    from .discovery.api import mount_discovery
    mount_discovery(app, runtime)

    @app.get("/cache/status")
    async def cache_status():
        return runtime.cache.status()

    @app.post("/assistant/dismiss")
    async def dismiss_answer(body: StepHelpBody):
        if not runtime.assistant.dismiss(body.session_id, body.card_id, body.step_id):
            raise HTTPException(409,"The step changed; refresh before returning.")
        return _json(runtime.hud.current)

    # ------------------------------------------------------------------ Pi -> core
    @app.post("/observation", status_code=204)
    async def post_observation(request: Request) -> Response:
        try:
            obs = Observation.model_validate(json.loads(await request.body()))
        except (ValidationError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)[:500])
        accepted = runtime.ingest(obs)
        # A stale/duplicate seq is dropped but acknowledged (a retrying Pi must not error-loop); the header says so.
        return Response(status_code=204, headers={} if accepted else {"x-ghostbuild-dropped": "stale_seq"})

    # ------------------------------------------------------------------ G2
    def parse(model, data):
        try:
            return model.model_validate(data)
        except ValidationError:
            return None

    @app.websocket("/ws")
    async def ws(websocket: WebSocket, role: str = "g2") -> None:
        await websocket.accept()
        q: asyncio.Queue = asyncio.Queue()
        counted = role == "g2"
        registered = False
        pump: Optional[asyncio.Task] = None

        async def pump_frames() -> None:
            while True:
                frame = await q.get()
                await websocket.send_json(frame.model_dump(mode="json"))

        def register() -> None:
            nonlocal registered
            if not registered:
                clients.append(q)
                registered = True
                if counted:
                    runtime.ws_clients += 1

        try:
            while True:
                text = await websocket.receive_text()
                try:
                    data = json.loads(text)
                except ValueError:
                    continue  # ignore garbage, keep the socket
                kind = data.get("type") if isinstance(data, dict) else None
                if kind == "g2_hello":
                    h = parse(G2Hello, data)
                    if h is None:
                        continue
                    frame = runtime.hello(h)  # may emit welcome/menu frames to the OTHER clients
                    q.put_nowait(frame)
                    register()  # no await between hello and register: nothing can be missed
                    if pump is None:
                        pump = asyncio.create_task(pump_frames())
                elif kind == "g2_input":
                    gi = parse(G2Input, data)
                    if gi is None:
                        continue
                    if not registered:  # input before hello: serve the current frame, keep listening
                        q.put_nowait(runtime.hud.current)
                        register()
                        pump = pump or asyncio.create_task(pump_frames())
                    runtime.handle_input(gi)
        except WebSocketDisconnect:
            pass
        except Exception:
            log.exception("ws handler failed")
        finally:
            if pump is not None:
                pump.cancel()
            if registered:
                if q in clients:
                    clients.remove(q)
                if counted:
                    runtime.ws_clients = max(0, runtime.ws_clients - 1)

    @app.get("/hud")
    async def get_hud(after: int = Query(-1)) -> Response:
        runtime.note_poll()
        cur = runtime.hud.current
        if cur.seq > after:
            return _json(cur)
        return Response(status_code=204)

    @app.post("/input")
    async def post_input(request: Request) -> Response:
        try:
            gi = G2Input.model_validate(json.loads(await request.body()))
        except (ValidationError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)[:500])
        runtime.note_poll()
        return _json(runtime.handle_input(gi))

    @app.post("/hello")
    async def post_hello(request: Request) -> Response:
        try:
            h = G2Hello.model_validate(json.loads(await request.body()))
        except (ValidationError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)[:500])
        runtime.note_poll()
        frame = runtime.hello(h)
        s = runtime.session()
        return Response(content=frame.model_dump_json(), media_type="application/json", headers={"x-ghostbuild-session": s.id})

    # ------------------------------------------------------------------ phone / tools
    @app.get("/state")
    async def get_state() -> Response:
        return _json(runtime.state())

    @app.get("/health")
    async def get_health() -> Response:
        d = runtime.health().model_dump(mode="json")
        d["voice"] = "on" if runtime.voice is not None else "off"  # additive; not part of the Health contract model
        return JSONResponse(d)

    @app.get("/card")
    async def get_card() -> Response:
        return _json(runtime.active_card)

    @app.get("/session")
    async def get_session() -> Response:
        return _json(runtime.session())

    @app.post("/session/connect")
    async def connect_phone() -> Response:
        """Join the current task; phone-only launch works without impersonating a G2 connection."""
        current = runtime.session()
        if current.id == "none":
            runtime.hello(G2Hello(client_id="phone-companion"))
        return _json(runtime.session())

    @app.get("/catalog")
    async def get_catalog() -> Response:
        return JSONResponse({"tasks": [{"card_id": c.card_id, "title": c.title, "mode": c.goal_mode,
                                      "steps": len(c.steps), "provenance": c.provenance}
                                     for c in runtime.startable_cards()]})

    @app.get("/engine/summary")
    async def engine_summary() -> Response:
        """What the one runtime is playing right now: every loaded guide, its sources and its shape (read-only, for the phone)."""
        from urllib.parse import urlparse

        def shape(c):
            kinds = [s.kind for s in c.steps]
            return {"card_id": c.card_id, "title": c.title, "task_kind": c.task_kind or ("assembly" if c.goal_mode == "build" else "diagnosis" if c.tests else None),
                    "provenance": c.provenance, "review": c.review, "steps": len(c.steps), "questions": kinds.count("question"),
                    "quoted": sum(1 for s in c.steps if any(ct.quote for ct in s.cites)),
                    "endings": kinds.count("outcome") + kinds.count("stop"), "hazards": sum(1 for s in c.steps if s.risk == "hazard"),
                    "pictures": sum(len(g.views) for g in c.guides), "measured": sum(1 for s in c.steps if s.verify is not None),
                    "sources": sorted({urlparse(x.url).netloc.removeprefix("www.") for x in c.sources if x.url}),
                    "ai_compiled": c.card_id in runtime.live.cards or bool(c.review and "AI-compiled" in c.review)}
        cards = runtime.all_cards()
        return JSONResponse({"guides": [shape(c) for c in cards if c.steps], "engine": runtime.live.engine,
                             "live": runtime.live.view(), "active": runtime.active_card.card_id})

    @app.post("/session/action")
    async def phone_action(body: PhoneAction) -> Response:
        if body.session_id != runtime.session().id:
            raise HTTPException(409, "task session changed; refresh before acting")
        if body.seq_seen != runtime.hud.current.seq:
            raise HTTPException(409, "display changed; review the current step before acting")
        pb = runtime.playbook
        if body.action == "choose":
            if pb is None or not body.choice or not pb.choose(body.choice, via="phone"):
                raise HTTPException(409, "that answer is not available on the current step")
            runtime.hud.sync()
            return _json(runtime.hud.current)
        if body.action == "confirm":
            if pb is None or pb.done or pb.view_idx is not None or pb.step.verify is not None:
                raise HTTPException(409, "only a visible manual step can be confirmed")
            if runtime.hud.current.mode not in ("step", "visual"):
                raise HTTPException(409, "return to the step before confirming")
            if not pb._step_settled(runtime.clock.now_ms()):
                raise HTTPException(409, "read the current step before confirming")
            gesture = "swipe_down"
        elif body.action in ("answer_next", "answer_previous"):
            if pb is None or pb.answer_data is None:
                raise HTTPException(409, "No answer page open")
            gesture = "swipe_down" if body.action == "answer_next" else "swipe_up"
        elif body.action == "next_view":
            if pb is None or pb.view_idx is None:
                raise HTTPException(409, "open a picture first")
            gesture = "press"  # press is the picture button on the glasses too: it cycles WHERE -> HOW -> CORRECT
        else:
            gesture = "press" if body.action == "press" else "swipe_up"
        return _json(runtime.handle_input(G2Input(gesture=gesture, seq_seen=body.seq_seen)))

    @app.post("/session/goal")
    async def post_goal(request: Request) -> Response:
        try:
            req = GoalRequest.model_validate(json.loads(await request.body()))
        except (ValidationError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)[:500])
        res = runtime.resolve_goal(req)
        if res is None:
            raise HTTPException(status_code=404, detail="unknown session_id; GET /session for the current one")
        return _json(res)

    @app.post("/research/request")
    async def post_research(request: Request) -> Response:
        """Save an unsupported request for async research. It is NOT available now and nothing is promised."""
        try:
            body = ResearchRequestBody.model_validate(json.loads(await request.body()))
        except (ValidationError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)[:500])
        res, saved = runtime.request_research(body.session_id, body.mode, body.text.strip())
        if res is None:
            if saved.status == "rate_limited":
                raise HTTPException(status_code=429, detail="one research request per 2 s per session")
            raise HTTPException(status_code=500, detail="could not save the request")
        return _json(res)

    @app.post("/ask")
    async def post_ask(request: Request) -> Response:
        """Contextual follow-up for the active playbook step (phone page, tests, voice). Answers are card text only."""
        try:
            body = AskBody.model_validate(json.loads(await request.body()))
        except (ValidationError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)[:500])
        if body.session_id and body.session_id != runtime.session().id:
            raise HTTPException(409, "task session changed; ask again in the current session")
        if not body.text.strip():
            raise HTTPException(422, "enter a question")
        res = runtime.ask(body.text.strip())
        if res is None:
            raise HTTPException(status_code=409, detail="no active playbook; start a task with steps first")
        return JSONResponse(res.as_json())

    @app.get("/guides/{guide_id}/{view}.png")
    async def get_guide(guide_id: str, view: str) -> Response:
        if view.endswith(".phone"):
            return await get_phone_guide(guide_id, view[:-6])
        for card in runtime.all_cards():
            for g in card.guides:
                if g.id != guide_id:
                    continue
                for v in g.views:
                    if v.view == view:
                        root = runtime.asset_root.resolve()
                        path = (root / v.image).resolve()
                        if root not in path.parents or not path.is_file():
                            raise HTTPException(status_code=404, detail="guide image missing")
                        return FileResponse(path, media_type="image/png")
        raise HTTPException(status_code=404, detail="no such guide view")

    @app.get("/guides/{guide_id}/{view}.phone.png")
    async def get_phone_guide(guide_id: str, view: str) -> Response:
        for card in runtime.all_cards():
            for guide in card.guides:
                if guide.id == guide_id:
                    for item in guide.views:
                        if item.view == view and item.phone_image:
                            root = runtime.asset_root.resolve()
                            path = (root / item.phone_image).resolve()
                            if root in path.parents and path.is_file():
                                return FileResponse(path, media_type="image/png")
        # A missing rich image has a supported, useful small-image fallback.
        return await get_guide(guide_id, view)

    @app.get("/guides/{guide_id}/manifest.json")
    async def get_manifest(guide_id: str) -> Response:
        guide = next((g for c in runtime.all_cards() for g in c.guides if g.id == guide_id), None)
        if guide is None:
            raise HTTPException(404, "no such guide")
        root = runtime.asset_root.resolve()
        path = (root / "knowledge" / "guides" / guide_id / "manifest.json").resolve()
        if root in path.parents and path.is_file():
            return FileResponse(path, media_type="application/json")
        return JSONResponse({"guide_id": guide.id, "views": [v.model_dump(mode="json") for v in guide.views]})

    @app.get("/voice/status")
    async def voice_status() -> Response:
        return JSONResponse({"stt": runtime.voice is not None and bool(os.environ.get("ELEVENLABS_API_KEY")),
                             "tts": os.environ.get("GB_TTS") == "1" and bool(os.environ.get("ELEVENLABS_API_KEY")) and bool(os.environ.get("ELEVENLABS_VOICE_ID")),
                             "provider": "ElevenLabs", "conversation": False,
                             "notice": "Audio is sent to ElevenLabs for processing. Recordings are not retained by GhostBuild."})

    speech_lock = asyncio.Lock()
    last_speech_at = -float("inf")

    @app.post("/voice/speak")
    async def speak(body: SpeakBody, request: Request) -> Response:
        nonlocal last_speech_at
        if not body.consent:
            raise HTTPException(422, "enable spoken replies with consent first")
        if os.environ.get("GB_TTS") != "1":
            raise HTTPException(503, "spoken replies are disabled; text remains available")
        if speech_lock.locked() or time.monotonic() - last_speech_at < 2:
            raise HTTPException(429, "a spoken reply is already in progress; try again shortly")
        async with speech_lock:
            last_speech_at = time.monotonic()
            from integrations.elevenlabs.client import synthesize, VoiceProviderError
            generation = asyncio.create_task(synthesize(body.text.strip(), consent=True))

            async def disconnected():
                # FastAPI has consumed the JSON body. Await the next ASGI
                # disconnect directly; polling is_disconnected uses a cancel
                # scope that can swallow cancellation during task cleanup.
                while True:
                    message = await request.receive()
                    if message["type"] == "http.disconnect":
                        return

            disconnect = asyncio.create_task(disconnected())
            try:
                done, _ = await asyncio.wait((generation, disconnect), return_when=asyncio.FIRST_COMPLETED)
                if disconnect in done:
                    raise HTTPException(499, "spoken reply cancelled")
                audio = generation.result()
            except VoiceProviderError:
                raise HTTPException(503, "spoken reply unavailable; use the displayed text")
            finally:
                for task in (generation, disconnect):
                    if not task.done():
                        task.cancel()
                await asyncio.gather(generation, disconnect, return_exceptions=True)
            return Response(audio, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})

    mount_cards_api(app, runtime)  # card import endpoints (build-time tooling; see cards_api.py)
    mount_research_runs(app, runtime, research_runs)  # optional CREAO runs + draft approval (GB_CREAO=1; research_runs.py)

    # ------------------------------------------------------------------ optional voice lane (only when --voice / GB_VOICE=1)
    if runtime.voice is not None:

        @app.websocket("/ws/voice")
        async def ws_voice(websocket: WebSocket, session_id: str = "") -> None:
            if session_id and session_id != runtime.session().id:
                await websocket.close(code=1008)
                return
            await runtime.voice.serve(websocket)

    # ------------------------------------------------------------------ simulator (only when --simulate)
    if runtime.sim is not None:

        @app.post("/sim/scenario")
        async def post_scenario(name: str = Query(...)) -> Response:
            try:
                runtime.sim.set_scenario(name)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc))
            return JSONResponse({"scenario": name, "source": "simulated"})

    # ------------------------------------------------------------------ static phone page (web/), optional
    wd = Path(web_dir) if web_dir is not None else runtime.asset_root / "web"
    if wd.is_dir():
        app.mount("/phone", StaticFiles(directory=str(wd), html=True), name="phone")

    return app
