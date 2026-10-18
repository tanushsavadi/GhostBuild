"""FastAPI shell over Runtime. All frames come from hud.py via Runtime; this file only moves JSON."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from contracts.models import G2Hello, G2Input, GoalRequest, HudFrame, Observation

from .cards_api import mount_cards_api
from .runtime import Runtime

log = logging.getLogger("ghostbuild.server")


def _json(model, status: int = 200) -> Response:
    return Response(content=model.model_dump_json(), media_type="application/json", status_code=status)


def create_app(
    runtime: Runtime,
    *,
    tick_interval: Optional[float] = 0.2,
    sim_interval: Optional[float] = 0.1,
    web_dir: Path | str | None = None,
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
        return _json(runtime.engine.card)

    @app.get("/session")
    async def get_session() -> Response:
        return _json(runtime.session())

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

    @app.get("/guides/{guide_id}/{view}.png")
    async def get_guide(guide_id: str, view: str) -> Response:
        for card in runtime.cards:
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

    mount_cards_api(app, runtime)  # card import endpoints (build-time tooling; see cards_api.py)

    # ------------------------------------------------------------------ optional voice lane (only when --voice / GB_VOICE=1)
    if runtime.voice is not None:

        @app.websocket("/ws/voice")
        async def ws_voice(websocket: WebSocket, session_id: str = "") -> None:
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
