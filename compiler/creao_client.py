"""Creao API Trigger client (A). Starts one compile run and returns at once; the agent reports back by
calling POST {GB_PUBLIC_URL}/procedures/validate until it passes, then POST {GB_PUBLIC_URL}/agent/webhook.

Creao's trigger format is shown in the agent's API Trigger panel on agent.creao.ai (not publicly documented).
Configure it from that snippet, server-side only:
  CREAO_API_KEY        capi_... key (sent as a Bearer token unless CREAO_AUTH_HEADER says otherwise)
  CREAO_TRIGGER_URL    the trigger endpoint from the panel
  CREAO_AUTH_HEADER    optional, e.g. "X-API-Key" (default: "Authorization" with "Bearer <key>")
  CREAO_BODY_TEMPLATE  optional JSON with a "{message}" placeholder (default: {"input": "{message}"})
  GB_PUBLIC_URL        where Creao's cloud can reach this backend (Tailscale Funnel / tunnel URL)
"""

from __future__ import annotations

import json
import os
import urllib.request
import uuid

BRIEF = """Build request: {request}

Compile this into a GhostBuild procedure, following your instructions exactly.
compile_id: {compile_id}
Schema: GET {base}/procedures/schema   Jig profiles: GET {base}/jigs   Example: GET {base}/procedures/led-button-v1
Validate: POST {base}/procedures/validate  (body: {{"run_id": "{compile_id}", "request": ..., "procedure": ...}})
Deliver:  POST {base}/agent/webhook        (same body, only after validate returns ok: true)
"""


def configured() -> bool:
    return bool(os.environ.get("CREAO_API_KEY") and os.environ.get("CREAO_TRIGGER_URL") and os.environ.get("GB_PUBLIC_URL"))


def message(request: str, compile_id: str) -> str:
    base = os.environ.get("GB_PUBLIC_URL", "http://localhost:8787").rstrip("/")
    return BRIEF.format(request=request, compile_id=compile_id, base=base)


def trigger(request: str, timeout: float = 20.0) -> dict:
    """Start a run. Blocking HTTP call: call it from a worker thread, never from the live loop."""
    compile_id = f"cmp_{uuid.uuid4().hex[:10]}"
    key = os.environ["CREAO_API_KEY"]
    template = os.environ.get("CREAO_BODY_TEMPLATE", '{"input": "{message}"}')
    msg = json.dumps(message(request, compile_id))[1:-1]  # JSON-escaped, placed inside the template's quotes
    body = template.replace("{message}", msg).encode()
    header = os.environ.get("CREAO_AUTH_HEADER", "Authorization")
    value = f"Bearer {key}" if header == "Authorization" else key
    req = urllib.request.Request(
        os.environ["CREAO_TRIGGER_URL"], data=body, method="POST",
        headers={"Content-Type": "application/json", header: value},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode() or "{}"
    try:
        reply = json.loads(raw)
    except json.JSONDecodeError:
        reply = {"raw": raw[:500]}
    return {"compile_id": compile_id, "request": request, "reply": reply}
