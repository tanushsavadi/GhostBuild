"""Tolerant client + CLI for the CREAO agent API (build time only; never on the HUD/cue path, never imported by core's cue code).

STATUS: UNVERIFIED against a real response (documented contract only). The official app-scoped endpoints are
    POST https://agent.creao.ai/api/v1/apps/{appId}/runs         start a run   (docs.creao.ai/developer-api/api-paths)
    GET  https://agent.creao.ai/api/v1/apps/{appId}/runs/{id}    read a run
with a backend-only key `CREAO_API_KEY` (starts `capi_`, scoped to one agent). The start body is
`{inputs: {goal, intent}}` (the app id is in the URL) with Authorization: Bearer; poll statuses per the docs are
pending|completed|failed|cancelled and the output text is `result.text` (`result.artifacts` lists files). Only those saved form fields are sent by default;
optional context is appended to goal. Response status values and output locations remain tolerant until a real response
is available (`python -m knowledge.creao probe`).
This module has only ever talked to mock servers in tests.

The API key is read from the environment only. It is never written to disk, never logged, and every error/log string is
passed through `redact()` first.

    python -m knowledge.creao probe --goal "replace a bicycle inner tube" [--device ..] [--doc-url ..] [--video-url ..] [--dry-run]
    python -m knowledge.creao status RUN_ID
    python -m knowledge.creao normalize knowledge/requests/creao_raw/RUN_ID.json [--goal ..]
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import quote

import httpx

from knowledge.validate import REPO_ROOT

DEFAULT_APP_ID = "032b9dc5-2fc7-4b5d-af36-8efdbd2648ac"  # "GhostBuild Intelligence" (created by the project owner)
DEFAULT_BASE_URL = "https://agent.creao.ai"
DEFAULT_RUN_PATH = "/api/v1/apps/{app_id}/runs"  # docs.creao.ai/developer-api/api-paths: app-scoped capi_ key, appId in the URL
KEY_PATTERN = re.compile(r"capi_[A-Za-z0-9_\-]{4,}")
RAW_DIR = REPO_ROOT / "knowledge" / "requests" / "creao_raw"

SUCCESS_STATUSES = frozenset({"completed", "complete", "succeeded", "success", "done", "finished"})
FAILURE_STATUSES = frozenset({"failed", "error", "errored", "cancelled", "canceled", "timeout", "timed_out"})
STATUS_KEYS = ("status", "state", "run_status")
RUN_ID_KEYS = ("id", "run_id", "runId")
PLACEHOLDERS = ("app_id", "goal", "device", "model", "intent", "doc_urls", "video_urls", "follow_up")


class CreaoError(Exception):
    """A CREAO call failed. `.status` is the HTTP status (0 for transport errors); the message is already redacted."""

    def __init__(self, message: str, status: int = 0, body: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.body = body


def redact(text: Any, key: Optional[str] = None) -> str:
    """Remove the API key (and anything shaped like `capi_...`) from text before it is logged, stored or shown."""
    s = text if isinstance(text, str) else str(text)
    if key:
        s = s.replace(key, "[REDACTED]")
    return KEY_PATTERN.sub("[REDACTED]", s)


# ----------------------------------------------------------------------------- tolerant readers (pure)
def _get_path(obj: Any, *path: str) -> Any:
    for part in path:
        if not isinstance(obj, dict) or part not in obj:
            return None
        obj = obj[part]
    return obj


def find_run_id(resp: Any) -> Optional[str]:
    """`id|run_id|runId` at the top, else under `data` / `run` / `result`."""
    if not isinstance(resp, dict):
        return None
    for holder in (resp, resp.get("data"), resp.get("run"), resp.get("result")):
        if isinstance(holder, dict):
            for key in RUN_ID_KEYS:
                value = holder.get(key)
                if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value).strip():
                    return str(value).strip()
    return None


def find_share_url(resp: Any) -> Optional[str]:
    """Preserve an actual provider share URL; never construct or infer one from a run id."""
    if not isinstance(resp, dict):
        return None
    from knowledge.importer import is_http_url

    for holder in (resp, resp.get("data"), resp.get("run"), resp.get("result")):
        if isinstance(holder, dict):
            for name in ("shareUrl", "share_url", "publicUrl", "public_url"):
                value = holder.get(name)
                if is_http_url(value) and not KEY_PATTERN.search(value):
                    return value
    return None


def read_status(raw: Any) -> Optional[str]:
    """Lower-case status string from `status|state|run_status` (top level or under `data`), else None."""
    if not isinstance(raw, dict):
        return None
    for holder in (raw, raw.get("data"), raw.get("run")):
        if not isinstance(holder, dict):
            continue
        for key in STATUS_KEYS:
            value = holder.get(key)
            if isinstance(value, dict):  # {"status": {"state": "running"}} style
                for inner in ("state", "status", "name", "value"):
                    if isinstance(value.get(inner), str):
                        value = value[inner]
                        break
            if isinstance(value, str) and value.strip():
                return value.strip().lower()
    return None


def run_state(raw: Any) -> tuple[str, Optional[str]]:
    """('success'|'failed'|'running', status_string). Anything that is not a known terminal status counts as running."""
    status = read_status(raw)
    if status in SUCCESS_STATUSES:
        return "success", status
    if status in FAILURE_STATUSES:
        return "failed", status
    return "running", status


def failure_detail(raw: Any, key: Optional[str] = None, limit: int = 300) -> str:
    """Best-effort error text from a failed run (error|message|reason|detail), redacted and truncated."""
    for holder in (raw, raw.get("data") if isinstance(raw, dict) else None):
        if isinstance(holder, dict):
            for name in ("error", "error_message", "message", "reason", "detail"):
                value = holder.get(name)
                if isinstance(value, dict):
                    value = value.get("message") or json.dumps(value, ensure_ascii=False)
                if isinstance(value, str) and value.strip():
                    return redact(value.strip(), key)[:limit]
    return ""


# ----------------------------------------------------------------------------- request body
def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == []


FAST_DIRECTIVE = (
    "\n\nSPEED MODE: a person wearing smart glasses is waiting for this answer right now. Be fast and lean. "
    "Use at most 3 sources (official docs first) and at most 2 searches; do not browse extra pages. "
    "Produce ONLY the GhostBuild workflow JSON plus ONE simple labelled diagram. Do NOT write extra scripts, markdown reports or "
    "README files, and do NOT re-render or vision-verify the diagram. Keep it to 5-7 short steps. Do not ask questions: "
    "record every assumption under uncertainties and keep going."
)


def default_body(app_id: str, inputs: dict) -> dict:
    """Existing GhostBuild Intelligence form contract; extra context uses the saved goal field."""
    goal = str(inputs.get("goal") or "").strip()
    context = []
    for key, label in (("device", "Device"), ("model", "Model"), ("doc_urls", "Documentation URLs"),
                       ("video_urls", "Video URLs"), ("follow_up", "Follow-up")):
        value = inputs.get(key)
        if not _is_empty(value):
            context.append(f"{label}: {', '.join(map(str, value)) if isinstance(value, list) else value}")
    if context:
        goal += "\n\nResearch context:\n" + "\n".join(context)
    if inputs.get("audience"):
        goal += "\n\nWho this guide is for (write for them; do not assume more than this): " + str(inputs["audience"])
    if inputs.get("fast"):
        goal += FAST_DIRECTIVE
    return {"inputs": {"goal": goal, "intent": inputs.get("intent") or "build"}}  # app id travels in the URL, not the body


def render_template(template: Any, values: dict[str, Any]) -> Any:
    """Fill a JSON body template. A string that is EXACTLY a placeholder ("{goal}", "{doc_urls}") is replaced by the value
    keeping its type (list stays a list); an empty value drops that key from its object. Placeholders inside longer strings are
    substituted as text (lists joined by ", "). Unknown {words} are left alone."""
    exact = re.compile(r"^\{(" + "|".join(PLACEHOLDERS) + r")\}$")
    inline = re.compile(r"\{(" + "|".join(PLACEHOLDERS) + r")\}")
    drop = object()

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            out = {}
            for k, v in node.items():
                r = walk(v)
                if r is not drop:
                    out[k] = r
            return out
        if isinstance(node, list):
            return [r for r in (walk(v) for v in node) if r is not drop]
        if isinstance(node, str):
            m = exact.match(node)
            if m:
                value = values.get(m.group(1))
                return drop if _is_empty(value) else value

            def sub(match: re.Match) -> str:
                value = values.get(match.group(1))
                if isinstance(value, list):
                    return ", ".join(str(x) for x in value)
                return "" if value is None else str(value)

            return inline.sub(sub, node)
        return node

    return walk(template)


class CreaoClient:
    """Synchronous CREAO client (call it from a worker thread, never from the live HUD loop).

    Every setting is a constructor argument that falls back to an environment variable, then a default:
      api_key        CREAO_API_KEY    (required for any network call)
      app_id         CREAO_APP_ID     (default: the GhostBuild Intelligence app)
      base_url       CREAO_BASE_URL   (default https://agent.creao.ai)
      auth_header    CREAO_AUTH_HEADER (default Authorization)        auth_scheme  CREAO_AUTH_SCHEME (default Bearer; '' = raw key)
      body_template  CREAO_RUN_BODY   (JSON text with {app_id} {goal} {device} {model} {intent} {doc_urls} {video_urls} {follow_up})
      run_path       CREAO_RUN_PATH   (default /api/v1/apps/{app_id}/runs)
    `transport` is an httpx transport (tests inject httpx.MockTransport); `sleep` is injectable so tests do not wait.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        app_id: Optional[str] = None,
        base_url: Optional[str] = None,
        auth_header: Optional[str] = None,
        auth_scheme: Optional[str] = None,
        run_path: Optional[str] = None,
        body_template: Any = None,
        timeout: float = 20,
        transport: Optional[httpx.BaseTransport] = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        max_attempts: int = 4,
    ) -> None:
        env = os.environ
        self._api_key = api_key if api_key is not None else env.get("CREAO_API_KEY", "")
        self.app_id = app_id or env.get("CREAO_APP_ID") or DEFAULT_APP_ID
        self.base_url = (base_url or env.get("CREAO_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.auth_header = auth_header or env.get("CREAO_AUTH_HEADER") or "Authorization"
        scheme = auth_scheme if auth_scheme is not None else env.get("CREAO_AUTH_SCHEME")
        self.auth_scheme = "Bearer" if scheme is None else scheme
        raw_path = (run_path or env.get("CREAO_RUN_PATH") or DEFAULT_RUN_PATH).replace("{app_id}", quote(self.app_id, safe=""))
        self.run_path = "/" + raw_path.strip("/")
        template = body_template if body_template is not None else env.get("CREAO_RUN_BODY")
        if isinstance(template, str) and template.strip():
            try:
                template = json.loads(template)
            except ValueError as exc:
                raise CreaoError(f"CREAO_RUN_BODY is not valid JSON: {exc}") from None
        self.body_template = template if isinstance(template, (dict, list)) else None
        self.timeout = timeout
        self._transport = transport
        self._sleep = sleep
        self._clock = clock
        self.max_attempts = max(1, max_attempts)
        self.last_start_response: Any = None

    def __repr__(self) -> str:  # never include the key
        return f"CreaoClient(base_url={self.base_url!r}, app_id={self.app_id!r}, key_set={bool(self._api_key)})"

    def redact(self, text: Any) -> str:
        """Redact this client's key (and anything shaped like one) from text."""
        return redact(text, self._api_key)

    # ------------------------------------------------------------------ request building
    @property
    def has_key(self) -> bool:
        return bool(self._api_key)

    def build_body(self, inputs: dict) -> Any:
        values = {
            "app_id": self.app_id,
            "goal": inputs.get("goal"),
            "device": inputs.get("device"),
            "model": inputs.get("model"),
            "intent": inputs.get("intent"),
            "doc_urls": list(inputs.get("doc_urls") or []),
            "video_urls": list(inputs.get("video_urls") or []),
            "follow_up": inputs.get("follow_up"),
        }
        if self.body_template is not None:
            return render_template(self.body_template, values)
        return default_body(self.app_id, inputs)

    def _headers(self, placeholder_key: bool = False) -> dict[str, str]:
        key = "<CREAO_API_KEY>" if placeholder_key else self._api_key
        value = f"{self.auth_scheme} {key}".strip() if self.auth_scheme else key
        return {self.auth_header: value, "Content-Type": "application/json", "Accept": "application/json"}

    def dry_run(self, inputs: dict) -> dict:
        """The exact request that start_run would send, with the key replaced by a placeholder."""
        return {
            "method": "POST",
            "url": self.base_url + self.run_path,
            "headers": self._headers(placeholder_key=True),
            "body": self.build_body(inputs),
        }

    # ------------------------------------------------------------------ transport
    def _request(self, method: str, path: str, body: Any = None) -> Any:
        if not self._api_key:
            raise CreaoError("CREAO_API_KEY is not set; no request was made")
        url = self.base_url + path
        last = ""
        delay = 1.0
        for attempt in range(1, self.max_attempts + 1):
            try:
                with httpx.Client(transport=self._transport, timeout=self.timeout) as http:
                    resp = http.request(method, url, headers=self._headers(), json=body if body is not None else None)
            except httpx.HTTPError as exc:
                last = f"transport error: {type(exc).__name__}: {redact(exc, self._api_key)[:200]}"
                status = 0
                if method == "POST":
                    raise CreaoError(f"CREAO start outcome unknown after {last}; not retried to avoid a duplicate paid run. Check the agent run history before starting again.") from None
            else:
                status = resp.status_code
                if status < 400:
                    try:
                        return resp.json()
                    except ValueError:
                        return {"_non_json_body": redact(resp.text, self._api_key)[:2000]}
                text = redact(resp.text, self._api_key)[:500]
                if status != 429 and status < 500:
                    raise CreaoError(
                        f"CREAO answered HTTP {status} to {method} {path}; this is not retried (fix the request body/auth header; "
                        f"see CREAO_RUN_BODY / CREAO_AUTH_HEADER). Response body: {text!r}",
                        status=status,
                        body=text,
                    )
                last = f"HTTP {status}: {text!r}"
                if method == "POST" and status >= 500:
                    raise CreaoError(f"CREAO start outcome unknown ({last}); not retried to avoid a duplicate paid run. Check the agent run history before starting again.", status=status, body=text)
                retry_after = resp.headers.get("retry-after")
                if retry_after and retry_after.isdigit():
                    delay = max(delay, min(float(retry_after), 15.0))
            if attempt < self.max_attempts:
                self._sleep(min(delay, 15.0))
                delay = min(delay * 2, 15.0)
        raise CreaoError(f"CREAO {method} {path} failed after {self.max_attempts} attempts; last: {last}", status=status, body=last)

    # ------------------------------------------------------------------ API
    def start_run(self, inputs: dict) -> str:
        if not str(inputs.get("goal") or "").strip():
            raise CreaoError("goal is required")
        resp = self._request("POST", self.run_path, self.build_body(inputs))
        self.last_start_response = resp
        run_id = find_run_id(resp)
        if run_id is None:
            shape = sorted(resp.keys()) if isinstance(resp, dict) else type(resp).__name__
            raise CreaoError(f"CREAO accepted the request but the response has no run id (looked for id|run_id|runId|data.id); top-level shape: {shape}")
        return run_id

    def get_run(self, run_id: str) -> dict:
        resp = self._request("GET", f"{self.run_path}/{quote(str(run_id), safe='')}")
        return resp if isinstance(resp, dict) else {"_value": resp}

    # ------------------------------------------------------------------ artifacts
    def _download(self, url: str, max_bytes: int) -> bytes:
        """GET one run artifact. The CREAO URL needs the key; it answers 302 to a signed storage URL, which must NOT receive the key."""
        if not url.startswith(self.base_url + "/"):
            raise CreaoError("artifact URL is not on the CREAO host; not fetched")
        with httpx.Client(transport=self._transport, timeout=self.timeout, follow_redirects=False) as http:
            resp = http.get(url, headers=self._headers())
            if resp.status_code in (301, 302, 303, 307, 308):
                target = resp.headers.get("location", "")
                if not target.startswith("https://"):
                    raise CreaoError("artifact redirect is not https; not followed")
                resp = http.get(target, headers={"Accept": "*/*"})
        if resp.status_code >= 400:
            raise CreaoError(f"artifact download answered HTTP {resp.status_code}", status=resp.status_code)
        if len(resp.content) > max_bytes:
            raise CreaoError("artifact larger than the allowed size; not used")
        return resp.content

    def attach_json_artifacts(self, raw: Any, *, max_files: int = 3, max_bytes: int = 262_144) -> Any:
        """Download the run's application/json artifacts (the structured playbook lives there, `result.text` is only metadata) and
        embed each parsed value as `artifact["content"]` so the tolerant extractor can find it. Failures are recorded per artifact
        as `artifact["download_error"]` (redacted); they never raise. Downloading is not a new run."""
        result = raw.get("result") if isinstance(raw, dict) else None
        arts = result.get("artifacts") if isinstance(result, dict) else None
        if not isinstance(arts, list):
            return raw
        done = svgs = imgs = 0
        for art in arts:
            if not isinstance(art, dict) or not isinstance(art.get("url"), str):
                continue
            title = str(art.get("title", "")).lower()
            is_svg = title.endswith(".svg")
            if title.endswith((".png", ".jpg", ".jpeg")) and "image/" in str(art.get("type", "")).lower() and imgs < 2:
                imgs += 1  # a raster diagram (the agent chooses SVG or PNG per run)
                try:
                    art["image_b64"] = base64.b64encode(self._download(art["url"], 3_145_728)).decode("ascii")
                except (CreaoError, ValueError, httpx.HTTPError) as exc:
                    art["download_error"] = redact(exc, self._api_key)[:200]
                continue
            if is_svg and svgs < 2:  # the agent's diagram: kept as text so a picture for the glasses can be built from it
                svgs += 1
                try:
                    text = self._download(art["url"], 1_048_576).decode("utf-8")
                    if "<svg" in text[:2000]:
                        art["svg_text"] = text
                except (CreaoError, ValueError, httpx.HTTPError) as exc:
                    art["download_error"] = redact(exc, self._api_key)[:200]
                continue
            if done >= max_files or "json" not in str(art.get("type", "")).lower():
                continue
            done += 1
            try:
                art["content"] = json.loads(self._download(art["url"], max_bytes).decode("utf-8"))
            except (CreaoError, ValueError, httpx.HTTPError) as exc:
                art["download_error"] = redact(exc, self._api_key)[:200]
        return raw

    def poll(
        self,
        run_id: str,
        interval: float = 3,
        max_wait: float = 900,
        on_update: Optional[Callable[[Optional[str], dict], None]] = None,
        max_interval: float = 15,
    ) -> dict:
        """Poll until a terminal status; return that raw response (check `run_state(raw)`). The wait grows 1.5x per poll up to
        `max_interval`. Raises CreaoError on timeout or a non-retryable HTTP error."""
        started = self._clock()
        wait = float(interval)
        while True:
            raw = self.get_run(run_id)
            state, status = run_state(raw)
            if on_update is not None:
                on_update(status, raw)
            if state != "running":
                return raw
            if self._clock() - started + wait > max_wait:
                raise CreaoError(f"CREAO run {run_id} still {status or 'without a status'} after {max_wait:.0f} s; stopped polling (the run may still finish in CREAO)")
            self._sleep(wait)
            wait = min(wait * 1.5, max_interval)


# ----------------------------------------------------------------------------- structural summary
def describe_shape(obj: Any, *, max_depth: int = 6, max_items: int = 12, key: Optional[str] = None) -> list[str]:
    """Lines like `output.result.steps: list[7]` so the team can see the real response shape. Short strings (<= 40 chars,
    e.g. status values) are shown; longer strings only by length."""
    lines: list[str] = []

    def walk(node: Any, path: str, depth: int) -> None:
        if isinstance(node, dict):
            lines.append(f"{path or '(root)'}: object keys={sorted(node.keys())[:max_items * 2]}")
            if depth >= max_depth:
                return
            for k in list(node)[:40]:
                walk(node[k], f"{path}.{k}" if path else str(k), depth + 1)
        elif isinstance(node, list):
            kinds = sorted({type(x).__name__ for x in node})
            lines.append(f"{path}: list[{len(node)}] of {kinds}")
            if depth >= max_depth:
                return
            for i, item in enumerate(node[:3]):
                walk(item, f"{path}[{i}]", depth + 1)
        elif isinstance(node, str):
            shown = f" = {redact(node, key)!r}" if len(node) <= 40 else ""
            lines.append(f"{path}: string len={len(node)}{shown}")
        else:
            lines.append(f"{path}: {type(node).__name__}{'' if node is None else ' = ' + repr(node)}")

    walk(obj, "", 0)
    return lines


# ----------------------------------------------------------------------------- CLI
def _inputs_from_args(args: argparse.Namespace) -> dict:
    return {
        "goal": args.goal,
        "device": args.device,
        "model": args.model,
        "intent": args.intent,
        "doc_urls": args.doc_url or [],
        "video_urls": args.video_url or [],
        "follow_up": args.follow_up,
        "fast": args.fast,
    }


def _no_key() -> int:
    print("CREAO_API_KEY is not set. Export it in your shell (never put it in a file or the repo); no request was made.", file=sys.stderr)
    return 2


def save_raw(run_id: str, document: dict, directory: Optional[Path] = None, key: Optional[str] = None) -> Path:
    directory = directory or RAW_DIR
    directory.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", run_id)[:80] or "run"
    path = directory / f"{safe}.json"
    path.write_text(redact(json.dumps(document, indent=2, ensure_ascii=False), key) + "\n", encoding="utf-8")
    return path


def _print_normalized(raw: dict, request: str, run_id: str, root: Path = REPO_ROOT) -> int:
    from knowledge import creao_normalize
    from knowledge.importer import validate_envelope

    payload = creao_normalize.extract_payload(raw)
    print(f"extract_payload: {'found ' + type(payload).__name__ if payload is not None else 'NOTHING FOUND'}")
    if payload is None:
        print("The raw response contains no recognisable playbook; adjust creao_normalize.extract_payload from the shape above.")
        return 1
    envelope = creao_normalize.to_envelope(payload, request, run_id=run_id)
    if creao_normalize.is_error(envelope):
        print("normalize ERROR:", json.dumps(envelope["error"], indent=2, ensure_ascii=False))
        return 1
    result = validate_envelope(envelope, root)
    print(f"envelope: card_id={envelope['card']['card_id']} steps={len(envelope['card']['steps'])} sources={len(envelope['card']['sources'])} "
          f"uncertainties={len(envelope['research']['uncertainties'])} guides={len(envelope['card'].get('guides', []))}")
    if result["ok"]:
        print("validation: OK (not stored; use the core /research/run flow or `make card-import` to store a draft)")
        return 0
    print(f"validation: {len(result['errors'])} error(s)")
    for error in result["errors"]:
        print("  -", error)
    return 1


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m knowledge.creao", description="CREAO agent API probe (UNVERIFIED against the real API until a key is supplied).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("probe", help="start a run, poll it, save the complete raw responses, print the shape, normalize, validate")
    p.add_argument("--goal", required=True)
    p.add_argument("--device")
    p.add_argument("--model")
    p.add_argument("--intent")
    p.add_argument("--doc-url", action="append")
    p.add_argument("--video-url", action="append")
    p.add_argument("--follow-up")
    p.add_argument("--fast", action="store_true", help="append the SPEED MODE directive (fewer sources, no extra files)")
    p.add_argument("--dry-run", action="store_true", help="print the exact request (without the key) and exit; no network")
    p.add_argument("--interval", type=float, default=3)
    p.add_argument("--max-wait", type=float, default=900)
    s = sub.add_parser("status", help="GET one run and print its shape")
    s.add_argument("run_id")
    n = sub.add_parser("normalize", help="offline: normalize + validate a saved raw response")
    n.add_argument("raw_file")
    n.add_argument("--goal", default=None, help="request text for the envelope (default: the file's recorded goal, else its run id)")
    args = parser.parse_args(argv)

    if args.cmd == "normalize":
        try:
            raw = json.loads(Path(args.raw_file).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"cannot read {args.raw_file}: {exc}", file=sys.stderr)
            return 1
        final = raw.get("final") if isinstance(raw, dict) and isinstance(raw.get("final"), dict) else raw
        goal = args.goal or (raw.get("inputs", {}).get("goal") if isinstance(raw, dict) and isinstance(raw.get("inputs"), dict) else None) or Path(args.raw_file).stem
        return _print_normalized(final, goal, Path(args.raw_file).stem)

    client = CreaoClient()
    if args.cmd == "probe":
        inputs = _inputs_from_args(args)
        if args.dry_run:
            print(json.dumps(client.dry_run(inputs), indent=2, ensure_ascii=False))
            print("(dry run: nothing was sent)")
            return 0
        if not client.has_key:
            return _no_key()
        try:
            run_id = client.start_run(inputs)
            print(f"started run {run_id}; polling (this can take minutes)")
            updates: list[dict] = []

            def seen(status: Optional[str], raw: dict) -> None:
                print(f"  status={status!r}")
                updates.append(raw)

            final = client.poll(run_id, interval=args.interval, max_wait=args.max_wait, on_update=seen)
        except CreaoError as exc:
            print(f"CREAO error: {redact(exc, client._api_key)}", file=sys.stderr)
            return 1
        if run_state(final)[0] == "success":
            final = client.attach_json_artifacts(final)
        document = {"inputs": inputs, "request_body": client.dry_run(inputs)["body"], "start_response": client.last_start_response, "final": final, "poll_count": len(updates)}
        path = save_raw(run_id, document, key=client._api_key)
        print(f"complete raw responses saved to {path} (gitignored)")
        print("--- response shape ---")
        for line in describe_shape(final, key=client._api_key):
            print(line)
        state, status = run_state(final)
        print(f"--- terminal state: {state} (status {status!r}) ---")
        if state == "failed":
            print("run failed:", failure_detail(final, client._api_key) or "(no error text found; see the saved file)")
            return 1
        return _print_normalized(final, args.goal, run_id)

    if not client.has_key:
        return _no_key()
    try:
        raw = client.get_run(args.run_id)
    except CreaoError as exc:
        print(f"CREAO error: {redact(exc, client._api_key)}", file=sys.stderr)
        return 1
    for line in describe_shape(raw, key=client._api_key):
        print(line)
    print("terminal state:", run_state(raw))
    return 0


if __name__ == "__main__":
    sys.exit(main())
