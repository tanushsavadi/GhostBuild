"""Card import endpoints: schema, read one loaded card, validate a research-agent envelope, store a draft.

Build-time tooling only. Nothing here touches the HUD or the engine, and drafts written by the webhook live under
knowledge/drafts/, which no loader reads. A human approves a draft with `python -m knowledge.approve`.
The envelope rules live in knowledge/importer.py (imported lazily; the endpoints answer 503 if it is unavailable).
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import re
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from contracts.models import Card

log = logging.getLogger("ghostbuild.cards_api")

MAX_BODY_BYTES = 1_000_000  # 1 MB
TOKEN_ENV = "GB_AGENT_TOKEN"
TOKEN_HEADER = "x-ghostbuild-token"
CARD_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def _importer():
    try:
        from knowledge import importer
    except Exception as exc:  # pragma: no cover - only when run outside the repo checkout
        log.warning("knowledge.importer unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="card import unavailable (knowledge package not importable)")
    return importer


async def _read_envelope(request: Request) -> Any:
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="body larger than 1 MB")
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="body larger than 1 MB")
    try:
        return json.loads(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"not JSON: {str(exc)[:200]}")


def mount_cards_api(app: FastAPI, runtime) -> None:
    @app.get("/cards/schema")
    async def get_card_schema() -> Response:
        return JSONResponse(Card.model_json_schema())

    @app.get("/cards/{card_id}")
    async def get_card_by_id(card_id: str) -> Response:
        if not CARD_ID.match(card_id):
            raise HTTPException(status_code=404, detail="unknown card")
        card = next((c for c in runtime.cards if c.card_id == card_id), None)
        if card is None:
            raise HTTPException(status_code=404, detail="unknown card")
        return Response(content=card.model_dump_json(), media_type="application/json")

    @app.post("/cards/validate")
    async def post_validate(request: Request) -> Response:
        envelope = await _read_envelope(request)
        return JSONResponse(_importer().validate_envelope(envelope, runtime.asset_root))

    @app.post("/agent/webhook")
    async def post_webhook(request: Request) -> Response:
        expected = os.environ.get(TOKEN_ENV, "")
        if not expected:
            raise HTTPException(status_code=503, detail="webhook disabled")
        supplied = request.headers.get(TOKEN_HEADER, "")
        if not hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
            raise HTTPException(status_code=401, detail="bad token")
        envelope = await _read_envelope(request)
        importer = _importer()
        result = importer.validate_envelope(envelope, runtime.asset_root)
        if not result["ok"]:
            return JSONResponse({"ok": False, "errors": result["errors"]}, status_code=422)
        draft_id = importer.write_draft(envelope, runtime.asset_root)
        log.info("agent draft stored: %s", draft_id)
        return JSONResponse({"draft_id": draft_id})
