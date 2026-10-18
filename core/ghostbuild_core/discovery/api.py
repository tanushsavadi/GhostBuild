"""Thin validated discovery endpoints. No network retrieval on the event loop."""

from fastapi import HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, ConfigDict
from .images import photo


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(min_length=1, max_length=64)
    article: str = Field(default="", max_length=32)
    text: str = Field(default="", max_length=300)
    option: str = Field(default="", max_length=64)


def mount_discovery(app, rt):
    def service(sid=None, mutate=False):
        d = rt.discovery
        if d is None:
            raise HTTPException(503, "Product discovery is disabled.")
        sid = sid or rt.session().id
        if sid not in rt.sessions.sessions:
            raise HTTPException(404, "Unknown session.")
        if mutate and (sid != rt.session().id or rt.session().phase == "task"):
            raise HTTPException(409, "Session changed; refresh before acting.")
        return d, sid

    @app.get("/discovery/state")
    async def state(session_id: str = ""):
        if rt.discovery is None:
            return {"enabled": False, "phase": "idle"}
        if not session_id and rt.session().id == "none":
            return {"enabled": True, "phase": "idle"}
        d, sid = service(session_id)
        return {"enabled": True, **d.state(sid).model_dump(mode="json")}

    @app.post("/discovery/{action}")
    async def command(action: str, body: Action):
        d, sid = service(body.session_id, True)
        if not d.active(sid):
            raise HTTPException(409, "No active product discovery.")
        try:
            if action == "select":
                d.select(sid, body.article)
            elif action in ("refine", "lookup"):
                if not body.text.strip():
                    raise ValueError("Enter a description, number or link.")
                d.utterance(sid, body.text)
            elif action == "none":
                d.none(sid)
            elif action == "refresh":
                d.refresh_search(sid)
            elif action == "more":
                d.more(sid)
            elif action == "config":
                d.configure(sid, body.option)
            elif action == "cancel":
                d.cancel(sid)
            else:
                raise HTTPException(404, "Unknown discovery action.")
        except ValueError as e:
            raise HTTPException(409, str(e))
        return d.state(sid).model_dump(mode="json")

    @app.get("/discovery/shortlist/{digest}.png")
    async def shortlist_image(digest: str):
        data = rt.discovery.sheet_images.get(digest) if rt.discovery else None
        if data is None:
            raise HTTPException(404, "Shortlist changed; refresh the display.")
        return Response(data, media_type="image/png")

    @app.get("/discovery/img/{source}/{filename}")
    async def image(source: str, filename: str):
        d = rt.discovery
        if d is None or source not in d.sources:
            raise HTTPException(404)
        mono = filename.endswith(".g2.png")
        suffix = ".g2.png" if mono else ".png"
        if not filename.endswith(suffix):
            raise HTTPException(404)
        article = filename[: -len(suffix)]
        rec = d.sources[source].record_for(article)
        data = photo(rt.asset_root, rec, mono) if rec else None
        if data is None:
            raise HTTPException(404, "No cached product photo.")
        return Response(data, media_type="image/png")

    @app.get("/discovery/assets/{source}/{article}/{filename}")
    async def asset(source: str, article: str, filename: str):
        d = rt.discovery
        if d is None or source not in d.sources:
            raise HTTPException(404)
        rec = d.sources[source].record_for(article)
        b = d.sources[source].bundle(rec) if rec else None
        if b is None:
            raise HTTPException(404)
        root = b.root.resolve()
        p = (root / filename).resolve()
        if root not in p.parents or not p.is_file() or p.suffix != ".png":
            raise HTTPException(404)
        return FileResponse(p, media_type="image/png")
