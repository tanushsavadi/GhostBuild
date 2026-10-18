"""CreaoClient against a MOCK server (httpx.MockTransport). Nothing here has talked to the real CREAO API."""

from __future__ import annotations

import json

import httpx
import pytest

from knowledge import creao
from knowledge.creao import CreaoClient, CreaoError, redact

KEY = "capi_TESTKEY1234567890"


def client(handler, **kw):
    sleeps: list[float] = []
    c = CreaoClient(api_key=KEY, transport=httpx.MockTransport(handler), sleep=sleeps.append, **kw)
    c.sleeps = sleeps
    return c


def test_start_run_default_body_and_auth_header():
    seen = {}

    def handler(req: httpx.Request):
        seen["req"] = req
        return httpx.Response(200, json={"id": "run_1", "status": "queued"})

    c = client(handler)
    rid = c.start_run({"goal": "replace a bike tube", "doc_urls": ["https://a.example/x"], "device": "", "follow_up": None})
    req = seen["req"]
    assert rid == "run_1" and req.method == "POST" and str(req.url) == "https://agent.creao.ai/api/v1/runs"
    assert req.headers["authorization"] == f"Bearer {KEY}"
    body = json.loads(req.content)
    assert body == {"appId": creao.DEFAULT_APP_ID, "inputs": {"goal": "replace a bike tube\n\nResearch context:\nDocumentation URLs: https://a.example/x", "intent": "build"}}


@pytest.mark.parametrize("resp,expected", [({"run_id": "r2"}, "r2"), ({"runId": "r3"}, "r3"), ({"data": {"id": "r4"}}, "r4"), ({"id": 7}, "7")])
def test_run_id_found_tolerantly(resp, expected):
    assert client(lambda r: httpx.Response(200, json=resp)).start_run({"goal": "g"}) == expected


def test_missing_run_id_names_the_shape():
    with pytest.raises(CreaoError, match="no run id"):
        client(lambda r: httpx.Response(200, json={"ok": True})).start_run({"goal": "g"})


def test_custom_body_template_and_auth_header():
    seen = {}

    def handler(req):
        seen["req"] = req
        return httpx.Response(200, json={"id": "x"})

    tpl = '{"agent": "{app_id}", "input": {"prompt": "Goal: {goal}", "urls": "{doc_urls}", "dev": "{device}"}}'
    c = client(handler, body_template=tpl, auth_header="X-API-Key", auth_scheme="")
    c.start_run({"goal": "reset router", "doc_urls": ["https://a.example", "https://b.example"]})
    assert seen["req"].headers["x-api-key"] == KEY and "authorization" not in seen["req"].headers
    assert json.loads(seen["req"].content) == {"agent": creao.DEFAULT_APP_ID, "input": {"prompt": "Goal: reset router", "urls": ["https://a.example", "https://b.example"]}}


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("CREAO_API_KEY", KEY)
    monkeypatch.setenv("CREAO_APP_ID", "app-123")
    monkeypatch.setenv("CREAO_BASE_URL", "https://example.test/")
    monkeypatch.setenv("CREAO_AUTH_HEADER", "X-Key")
    monkeypatch.setenv("CREAO_RUN_BODY", '{"a": "{app_id}", "g": "{goal}"}')
    c = CreaoClient()
    d = c.dry_run({"goal": "hi"})
    assert d["url"] == "https://example.test/api/v1/runs" and d["body"] == {"a": "app-123", "g": "hi"} and "X-Key" in d["headers"]
    assert KEY not in json.dumps(d) and KEY not in repr(c)


def test_429_then_success_is_retried_with_backoff():
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, text="slow down", headers={"retry-after": "2"})
        return httpx.Response(200, json={"id": "ok"})

    c = client(handler)
    assert c.start_run({"goal": "g"}) == "ok" and calls["n"] == 3 and c.sleeps and max(c.sleeps) <= 15


def test_5xx_exhausts_attempts():
    c = client(lambda r: httpx.Response(503, text="down"), max_attempts=3)
    with pytest.raises(CreaoError, match="after 3 attempts"):
        c.get_run("existing")
    assert len(c.sleeps) == 2


def test_4xx_fails_fast_with_redacted_truncated_body():
    calls = {"n": 0}
    body = f"bad field app_id; token {KEY} echoed; " + "x" * 2000

    def handler(req):
        calls["n"] += 1
        return httpx.Response(422, text=body)

    c = client(handler)
    with pytest.raises(CreaoError) as ei:
        c.start_run({"goal": "g"})
    msg = str(ei.value)
    assert calls["n"] == 1 and "HTTP 422" in msg and "CREAO_RUN_BODY" in msg
    assert KEY not in msg and "[REDACTED]" in msg and len(msg) < 1200 and ei.value.status == 422


def test_poll_running_then_completed_with_tolerant_status():
    statuses = iter([{"status": "QUEUED"}, {"state": "Running"}, {"data": {"status": "Completed"}, "output": {"x": 1}}])
    seen = []

    def handler(req):
        assert req.method == "GET" and req.url.raw_path == b"/api/v1/runs/run%2F1"
        return httpx.Response(200, json=next(statuses))

    c = client(handler)
    raw = c.poll("run/1", interval=3, on_update=lambda s, r: seen.append(s))
    assert raw["output"] == {"x": 1} and seen == ["queued", "running", "completed"]
    assert c.sleeps == [3, 4.5] and creao.run_state(raw) == ("success", "completed")


def test_poll_backoff_is_capped_and_timeout_raises():
    c = client(lambda r: httpx.Response(200, json={"status": "working"}))
    t = {"now": 0.0}
    c._clock = lambda: t["now"]
    c._sleep = lambda s: t.__setitem__("now", t["now"] + s)
    with pytest.raises(CreaoError, match="stopped polling"):
        c.poll("r", interval=3, max_wait=100)
    assert t["now"] <= 100


def test_poll_returns_failed_terminal_and_detail():
    c = client(lambda r: httpx.Response(200, json={"status": "FAILED", "error": {"message": f"boom {KEY}"}}))
    raw = c.poll("r")
    assert creao.run_state(raw) == ("failed", "failed")
    detail = creao.failure_detail(raw, KEY)
    assert "boom" in detail and KEY not in detail


@pytest.mark.parametrize("word", ["cancelled", "canceled", "timeout", "timed_out", "error", "errored"])
def test_failure_statuses(word):
    assert creao.run_state({"status": word})[0] == "failed"


@pytest.mark.parametrize("word", ["completed", "complete", "succeeded", "success", "done", "finished"])
def test_success_statuses(word):
    assert creao.run_state({"state": word.upper()})[0] == "success"


def test_unknown_status_counts_as_running():
    assert creao.run_state({"status": "thinking"}) == ("running", "thinking")
    assert creao.run_state({}) == ("running", None)


def test_missing_key_makes_no_request():
    called = []
    c = CreaoClient(api_key="", transport=httpx.MockTransport(lambda r: called.append(r) or httpx.Response(200, json={})))
    with pytest.raises(CreaoError, match="CREAO_API_KEY is not set"):
        c.start_run({"goal": "g"})
    assert called == []


def test_goal_required():
    with pytest.raises(CreaoError, match="goal is required"):
        client(lambda r: httpx.Response(200, json={"id": "x"})).start_run({"goal": "  "})


def test_redact_removes_key_and_capi_pattern():
    assert KEY not in redact(f"x {KEY} y", KEY)
    assert "capi_OTHERKEY99" not in redact("auth capi_OTHERKEY99 here")


def test_describe_shape_shows_structure_not_long_text():
    lines = creao.describe_shape({"status": "done", "output": {"text": "z" * 500, "steps": [{"a": 1}]}})
    joined = "\n".join(lines)
    assert "status: string len=4 = 'done'" in joined and "output.text: string len=500" in joined and "zzzz" not in joined and "output.steps: list[1]" in joined


# --------------------------------------------------------------------------- CLI
def test_cli_without_key_exits_2_and_no_network(monkeypatch, capsys):
    monkeypatch.delenv("CREAO_API_KEY", raising=False)
    assert creao.main(["probe", "--goal", "x"]) == 2
    assert "CREAO_API_KEY is not set" in capsys.readouterr().err
    assert creao.main(["status", "r1"]) == 2


def test_cli_dry_run_prints_request_without_key(monkeypatch, capsys):
    monkeypatch.setenv("CREAO_API_KEY", KEY)
    assert creao.main(["probe", "--goal", "replace a tube", "--doc-url", "https://a.example", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "api/v1/runs" in out and "replace a tube" in out and KEY not in out and "<CREAO_API_KEY>" in out


def test_cli_probe_end_to_end_with_mock(monkeypatch, tmp_path, capsys):
    from knowledge.tests.creao_mocks import MOCK_B_FENCED_RUN, MOCK_B_REQUEST

    monkeypatch.setenv("CREAO_API_KEY", KEY)
    monkeypatch.setattr(creao, "RAW_DIR", tmp_path / "raw")
    polls = iter([{"status": "running"}, MOCK_B_FENCED_RUN])

    def handler(req):
        if req.method == "POST":
            return httpx.Response(200, json={"id": "run_mock_router_02"})
        return httpx.Response(200, json=next(polls))

    real = creao.CreaoClient
    monkeypatch.setattr(creao, "CreaoClient", lambda: real(transport=httpx.MockTransport(handler), sleep=lambda s: None))
    rc = creao.main(["probe", "--goal", MOCK_B_REQUEST])
    out = capsys.readouterr().out
    saved = tmp_path / "raw" / "run_mock_router_02.json"
    assert rc == 0 and saved.is_file() and "validation: OK" in out and "--- response shape ---" in out
    assert KEY not in saved.read_text() and KEY not in out
    doc = json.loads(saved.read_text())
    assert doc["final"]["run_id"] == "run_mock_router_02" and doc["start_response"] == {"id": "run_mock_router_02"}
    assert creao.main(["normalize", str(saved)]) == 0  # offline path on the saved file


@pytest.mark.parametrize("failure", ["transport", "server"])
def test_start_outcome_unknown_never_retries_a_possibly_paid_run(failure):
    seen = []
    def handler(req):
        seen.append(req)
        if failure == "transport":
            raise httpx.ReadTimeout("response lost", request=req)
        return httpx.Response(503, text="upstream lost")
    c = client(handler)
    with pytest.raises(CreaoError, match="not retried.*duplicate paid run"):
        c.start_run({"goal": "g"})
    assert len(seen) == 1 and c.sleeps == []


def test_owner_confirmed_saved_form_contract():
    assert creao.default_body(creao.DEFAULT_APP_ID, {"goal": "build a box", "intent": "build"}) == {
        "appId": creao.DEFAULT_APP_ID, "inputs": {"goal": "build a box", "intent": "build"}}
    body = creao.default_body("app", {"goal": "fix a lid", "intent": "fix", "device": "a jar", "model": "small", "video_urls": ["https://example.org/video"], "follow_up": "no tools"})
    assert set(body["inputs"]) == {"goal", "intent"}
    assert "Model: small" in body["inputs"]["goal"] and "Follow-up: no tools" in body["inputs"]["goal"]


def test_share_url_preserves_actual_link_and_never_guesses():
    assert creao.find_share_url({"id": "r1"}) is None
    assert creao.find_share_url({"data": {"shareUrl": "https://agent.creao.ai/shared/run-123"}}) == "https://agent.creao.ai/shared/run-123"
    assert creao.find_share_url({"share_url": "javascript:alert(1)"}) is None
    assert creao.find_share_url({"share_url": "https://example.org/?token=" + KEY}) is None
