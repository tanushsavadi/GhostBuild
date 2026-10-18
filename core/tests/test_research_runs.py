"""CREAO runs + approval through the FastAPI app, with a MOCK CREAO server (httpx.MockTransport). Nothing here talks to CREAO."""

from __future__ import annotations

import json
import shutil
import threading
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from contracts.models import G2Hello, G2Input
from ghostbuild_core.cards import load_cards
from ghostbuild_core.clock import ManualClock
from ghostbuild_core.research_runs import ResearchRuns
from ghostbuild_core.runtime import Runtime
from ghostbuild_core.server import create_app
from knowledge.creao import CreaoClient
from knowledge.tests.creao_mocks import MOCK_A_ENVELOPE_RUN, MOCK_A_REQUEST, MOCK_B_FENCED_RUN, MOCK_B_REQUEST

REPO = Path(__file__).resolve().parents[2]
KEY = "capi_E2EKEY_1234567890"
TOKEN = "admin-secret-xyz"
H = {"X-GhostBuild-Token": TOKEN}

# only picture-description visuals, no URLs: the run must produce NO guide
VISUAL_ONLY = {"id": "run_mock_visual", "status": "done", "output": {
    "title": "Tighten a loose cabinet hinge", "steps": [
        {"title": "Open the door", "action": "Open the cabinet door fully", "visual": "Photo of the hinge plate with two screws circled"},
        {"title": "Tighten the screws", "action": "Tighten both hinge screws a quarter turn", "images": ["Diagram of the screw order"]}],
    "sources": [{"url": "https://www.ifixit.com/Guide/MOCK-hinge/1", "title": "MOCK hinge guide"}]}}


def gi(g):
    return G2Input(gesture=g, seq_seen=0)


class MockCreao:
    """Mock server: POST /api/v1/apps/{appId}/runs picks a canned run by goal; GET walks queued -> running -> completed."""

    def __init__(self, hold: threading.Event | None = None):
        self.canned = {MOCK_A_REQUEST: MOCK_A_ENVELOPE_RUN, MOCK_B_REQUEST: MOCK_B_FENCED_RUN, "tighten a loose cabinet hinge": VISUAL_ONLY}
        self.runs: dict[str, dict] = {}
        self.polls: dict[str, int] = {}
        self.posts: list[dict] = []
        self.auth_seen: list[str] = []
        self.hold = hold
        self.fail_status: int | None = None

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.auth_seen.append(req.headers.get("authorization", ""))
        if self.fail_status:
            return httpx.Response(self.fail_status, text=f"denied for {req.headers.get('authorization')}")
        if req.method == "POST":
            body = json.loads(req.content)
            self.posts.append(body)
            assert req.url.path == "/api/v1/apps/032b9dc5-2fc7-4b5d-af36-8efdbd2648ac/runs" and "appId" not in body
            assert set(body["inputs"]) == {"goal", "intent"}
            goal = body["inputs"]["goal"].split("\n\nResearch context:")[0].split("\n\nWho this guide is for")[0].split("\n\nSPEED MODE")[0]
            rid = f"mock_{len(self.posts)}"
            self.runs[rid] = self.canned[goal]
            return httpx.Response(200, json={"id": rid, "status": "queued"})
        rid = req.url.path.rsplit("/", 1)[1]
        n = self.polls[rid] = self.polls.get(rid, 0) + 1
        if self.hold is not None:
            self.hold.wait(5)
        if n == 1:
            return httpx.Response(200, json={"id": rid, "status": "running"})
        return httpx.Response(200, json={**self.runs[rid], "id": rid})


def wait_status(client, run_id, want=("draft_ready", "failed", "invalid"), timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        rec = client.get(f"/research/runs/{run_id}").json()
        if rec["status"] in want:
            return rec
        time.sleep(0.02)
    raise AssertionError(f"run did not settle: {rec}")


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("GB_ADMIN_TOKEN", TOKEN)
    root = tmp_path / "root"
    cards = root / "knowledge" / "cards"
    cards.mkdir(parents=True)
    for name in ("paper_cup", "camera_lens"):
        shutil.copy(REPO / "knowledge" / "cards" / f"{name}.json", cards / f"{name}.json")
    clock = ManualClock()
    rt = Runtime(load_cards(cards), clock=clock, log_dir=tmp_path / "logs", asset_root=root)
    rt.clock = clock
    mock = MockCreao()
    runs = ResearchRuns(root, enabled=True, poll_interval=0, min_gap_s=0,
                        client_factory=lambda: CreaoClient(api_key=KEY, transport=httpx.MockTransport(mock), sleep=lambda s: None))
    app = create_app(rt, tick_interval=None, sim_interval=None, web_dir=root / "no-web", research_runs=runs)
    with TestClient(app) as c:
        c.rt, c.mock, c.runs, c.root = rt, mock, runs, root
        yield c


def start(c, goal, **kw):
    r = c.post("/research/run", json={"goal": goal, **kw})
    assert r.status_code == 202, r.text
    return r.json()["run_id"]


def to_menu(rt):
    rt.hello(G2Hello(client_id="g2-1", session_id=None))
    rt.clock.advance(2600)
    rt.tick()
    assert rt.hud.current.cue.line1 == "WHAT DO YOU NEED?" and rt.hud.current.menu is None  # the front screen is a conversation prompt
    rt.handle_input(G2Input(gesture="press", seq_seen=0))  # failsafe: a tap shows the task list
    assert rt.hud.current.mode == "menu"


def settle(rt, ms=2700):
    for _ in range(ms // 100):
        rt.clock.advance(100)
        rt.tick()


def build_chooser(rt):
    return rt.hud.current  # the first screen after the welcome already lists every task (no BUILD/FIX question)


# --------------------------------------------------------------------------- the end-to-end story
def test_end_to_end_two_different_tasks_neither_is_hardcoded(world, caplog):
    c, rt = world, world.rt
    caplog.set_level("DEBUG")
    to_menu(rt)

    # task 1: a bicycle inner tube (envelope-ish MOCK shape)
    rid1 = start(c, MOCK_A_REQUEST, intent="build", device="road bike")
    rec1 = wait_status(c, rid1)
    assert rec1["status"] == "draft_ready" and rec1["creao_run_id"] == "mock_1" and rec1["draft"]["card_id"] == "replace_bicycle_inner_tube"
    assert c.mock.posts[0]["inputs"]["goal"].startswith(MOCK_A_REQUEST) and c.mock.posts[0]["inputs"]["intent"] == "build"
    assert "Device: road bike" in c.mock.posts[0]["inputs"]["goal"]
    assert c.mock.auth_seen[0] == f"Bearer {KEY}"
    draft1 = rec1["draft_id"]
    assert (c.root / "knowledge" / "drafts" / draft1 / "envelope.json").is_file()

    # an unapproved draft is never selectable
    assert "replace_bicycle_inner_tube" not in [x.card_id for x in rt.cards]
    assert c.get("/cards/replace_bicycle_inner_tube").status_code == 404
    assert not (c.root / "knowledge" / "cards" / "replace_bicycle_inner_tube.json").exists()

    # approval needs the admin token and a reviewer
    assert c.post(f"/cards/drafts/{draft1}/approve", json={"reviewer": "Ada"}).status_code == 401
    assert c.post(f"/cards/drafts/{draft1}/approve", json={"reviewer": "Ada"}, headers={"X-GhostBuild-Token": "wrong"}).status_code == 401
    assert c.post(f"/cards/drafts/{draft1}/approve", json={}, headers=H).status_code == 422
    assert c.post(f"/cards/drafts/{draft1}/approve", json={"reviewer": "   "}, headers=H).status_code == 422
    assert c.post("/cards/drafts/nope/approve", json={"reviewer": "Ada"}, headers=H).status_code == 404
    assert "replace_bicycle_inner_tube" not in [x.card_id for x in rt.cards]

    r = c.post(f"/cards/drafts/{draft1}/approve", json={"reviewer": "Ada"}, headers=H)
    assert r.status_code == 200, r.text
    assert r.json()["reload"]["added"] == ["replace_bicycle_inner_tube"] and r.json()["reviewer"] == "Ada"
    saved = json.loads((c.root / "knowledge" / "cards" / "replace_bicycle_inner_tube.json").read_text())
    assert saved["provenance"] == "AI-EXTRACTED · HUMAN-REVIEWED"
    assert json.loads((c.root / "knowledge" / "drafts" / draft1 / "review.json").read_text())["reviewer"] == "Ada"
    assert c.get("/cards/replace_bicycle_inner_tube").status_code == 200

    # BUILD chooser (no restart): the new card is an option, and its first step renders as a step frame
    f = build_chooser(rt)
    assert f.mode == "menu" and f.menu.prompt == "PICK A TASK"
    label = next(o for o in f.menu.options if o.startswith("REPLACE A BICYCLE"))
    idx = f.menu.options.index(label)
    for _ in range(idx):
        rt.handle_input(gi("swipe_down"))
    f = rt.handle_input(gi("press"))
    assert f.mode == "step"
    settle(rt)
    cur = rt.hud.current
    assert cur.mode == "step" and cur.step.step_id == "wheel_off" and cur.cue.line1 == "REMOVE THE WHEEL" and cur.step.check == "manual"
    assert rt.session().card_id == "replace_bicycle_inner_tube"

    # task 2 (a router, fenced-JSON MOCK shape) approved while task 1 is active: the active task stays intact
    rec2 = wait_status(c, start(c, MOCK_B_REQUEST, intent="build"))
    assert rec2["status"] == "draft_ready" and rec2["draft"]["card_id"].startswith("reset_a_home_router")
    rt.handle_input(gi("swipe_down"))  # confirm step 1 (manual, HUMAN CONFIRMED)
    rt.clock.advance(1600)
    rt.tick()
    before = rt.state().playbook
    assert c.post(f"/cards/drafts/{rec2['draft_id']}/approve", json={"reviewer": "Ada"}, headers=H).status_code == 200
    after = rt.state().playbook
    assert rt.playbook.card.card_id == "replace_bicycle_inner_tube" and (after.step_id, after.confirmed) == (before.step_id, before.confirmed)
    ids = [x.card_id for x in rt.cards]
    assert len(ids) == 4 and any(i.startswith("reset_a_home_router") for i in ids)

    # a fresh session lists every task (3 build cards + the fault card), router included, and its first step renders
    rt.clock.advance(20_000)
    rt.hello(G2Hello(client_id="g2-2", session_id=None))
    rt.clock.advance(2600)
    rt.tick()
    rt.handle_input(gi("press"))  # failsafe list
    f = build_chooser(rt)
    assert f.menu is not None and len(f.menu.options) == 4 and "MORE ON PHONE" not in f.menu.options
    router_idx = next(i for i, o in enumerate(f.menu.options) if o.startswith("RESET A HOME ROUTER"))
    for _ in range(router_idx):
        rt.handle_input(gi("swipe_down"))
    rt.handle_input(gi("press"))
    settle(rt)
    cur = rt.hud.current
    assert cur.mode == "step" and cur.step.count == 6 and cur.step.check == "manual"
    assert cur.cue.line1 == "WRITE DOWN THE WI-FI"

    # the key appears nowhere: not in logs, not in the run table, not in any response
    blob = caplog.text + (c.root / "knowledge" / "requests" / "creao_runs.json").read_text() + json.dumps(c.get("/research/runs").json())
    assert KEY not in blob
    raw_dir = c.root / "knowledge" / "requests" / "creao_raw"
    assert raw_dir.is_dir() and all(KEY not in p.read_text() for p in raw_dir.iterdir())


def test_visual_descriptions_only_yield_no_guide_and_reference_only_flag(world):
    c = world
    rec = wait_status(c, start(c, "tighten a loose cabinet hinge"))
    d = rec["draft"]
    assert rec["status"] == "draft_ready" and d["guides"] == 0 and d["pictures_on_glasses"] is False
    assert d["visual_references"] and all(v["reference_only"] is True for v in d["visual_references"])
    assert d["reference_only_note"] == "reference only — no picture on glasses"
    env = json.loads((c.root / "knowledge" / "drafts" / rec["draft_id"] / "envelope.json").read_text())
    assert env["card"]["guides"] == [] and all(s["guide_id"] is None and s["verify"] is None for s in env["card"]["steps"])
    assert d["validation"]["ok"] is True and d["provenance"] not in ("AI-EXTRACTED · HUMAN-REVIEWED", "AUTHORED DEMO METADATA")


def test_hand_authored_card_is_not_overwritten_by_approval(world):
    c = world
    rec = wait_status(c, start(c, MOCK_A_REQUEST, intent="build"))
    env_path = c.root / "knowledge" / "drafts" / rec["draft_id"] / "envelope.json"
    env = json.loads(env_path.read_text())
    (c.root / "knowledge" / "cards" / "replace_bicycle_inner_tube.json").write_text(json.dumps({**env["card"], "provenance": "AUTHORED DEMO METADATA"}))
    r = c.post(f"/cards/drafts/{rec['draft_id']}/approve", json={"reviewer": "Ada"}, headers=H)
    assert r.status_code == 409 and "hand-authored" in r.text


def test_alias_clash_with_a_loaded_card_is_refused(world):
    c = world
    rec = wait_status(c, start(c, MOCK_A_REQUEST, intent="build"))
    env_path = c.root / "knowledge" / "drafts" / rec["draft_id"] / "envelope.json"
    env = json.loads(env_path.read_text())
    env["card"]["aliases"].append("paper cup")
    env_path.write_text(json.dumps(env))
    r = c.post(f"/cards/drafts/{rec['draft_id']}/approve", json={"reviewer": "Ada"}, headers=H)
    assert r.status_code == 409 and "alias clash" in r.text


def test_admin_token_unset_means_approval_disabled(world, monkeypatch):
    monkeypatch.delenv("GB_ADMIN_TOKEN")
    r = world.post("/cards/drafts/anything-20260101T000000/approve", json={"reviewer": "Ada"}, headers=H)
    assert r.status_code == 503


# --------------------------------------------------------------------------- failure paths, flag, limits
def test_disabled_by_default(tmp_path, monkeypatch, card):
    monkeypatch.delenv("GB_CREAO", raising=False)
    monkeypatch.setenv("CREAO_API_KEY", KEY)
    rt = Runtime([card], log_dir=tmp_path / "l", asset_root=tmp_path / "r")
    with TestClient(create_app(rt, tick_interval=None, sim_interval=None, web_dir=tmp_path / "x")) as c:
        assert c.get("/research/status").json()["enabled"] is False
        r = c.post("/research/run", json={"goal": "x"})
        assert r.status_code == 503 and "creao disabled" in r.text
        assert c.get("/health").status_code == 200 and "creao" not in json.dumps(c.get("/health").json()).lower()
        assert c.get("/research/runs").json() == {"runs": []}


def test_flag_without_key_is_disabled(tmp_path, monkeypatch, card):
    monkeypatch.setenv("GB_CREAO", "1")
    monkeypatch.delenv("CREAO_API_KEY", raising=False)
    rt = Runtime([card], log_dir=tmp_path / "l", asset_root=tmp_path / "r")
    with TestClient(create_app(rt, tick_interval=None, sim_interval=None, web_dir=tmp_path / "x")) as c:
        s = c.get("/research/status").json()
        assert s["enabled"] is False and "CREAO_API_KEY" in s["reason"]
        assert c.post("/research/run", json={"goal": "x"}).status_code == 503


def test_flag_and_key_enable(tmp_path, monkeypatch, card):
    monkeypatch.setenv("GB_CREAO", "1")
    monkeypatch.setenv("CREAO_API_KEY", KEY)
    rt = Runtime([card], log_dir=tmp_path / "l", asset_root=tmp_path / "r")
    with TestClient(create_app(rt, tick_interval=None, sim_interval=None, web_dir=tmp_path / "x")) as c:
        s = c.get("/research/status").json()
        assert s["enabled"] is True and KEY not in json.dumps(s)


def test_body_validation(world):
    c = world
    assert c.post("/research/run", json={}).status_code == 422
    assert c.post("/research/run", json={"goal": "  "}).status_code == 422
    assert c.post("/research/run", json={"goal": "x", "doc_urls": ["javascript:alert(1)"]}).status_code == 422
    assert c.post("/research/run", json={"goal": "x", "surprise": 1}).status_code == 422
    assert c.mock.posts == []


def test_creao_4xx_marks_run_failed_with_redacted_error(world, caplog):
    c = world
    c.mock.fail_status = 401
    caplog.set_level("DEBUG")
    rec = wait_status(c, start(c, MOCK_A_REQUEST))
    assert rec["status"] == "failed" and "HTTP 401" in rec["error"] and KEY not in rec["error"] and "[REDACTED]" in rec["error"]
    assert KEY not in caplog.text and KEY not in (c.root / "knowledge" / "requests" / "creao_runs.json").read_text()


def test_creao_terminal_failure_and_unparsable_output(world):
    c = world
    c.mock.canned["boom"] = {"status": "failed", "error": f"agent crashed {KEY}"}
    c.mock.canned["nothing"] = {"status": "completed", "output": {"summary": "no playbook here"}}
    rec = wait_status(c, start(c, "boom"))
    assert rec["status"] == "failed" and "agent crashed" in rec["error"] and KEY not in rec["error"]
    rec = wait_status(c, start(c, "nothing"))
    assert rec["status"] == "invalid" and "no playbook found" in rec["error"] and rec["draft_id"] is None


def test_validation_errors_make_run_invalid_and_list_them(world):
    c = world
    bad = json.loads(json.dumps(MOCK_A_ENVELOPE_RUN))
    bad["data"]["output"]["card"]["steps"][0]["cue"] = {"line1": "THIS CUE IS WAY TOO LONG FOR G2", "line2": ""}
    c.mock.canned["bad"] = bad
    rec = wait_status(c, start(c, "bad"))
    assert rec["status"] == "invalid" and any("line1" in e or "String should have at most" in e or "cue" in e for e in rec["validation_errors"])
    assert not (c.root / "knowledge" / "drafts").exists() or not list((c.root / "knowledge" / "drafts").iterdir())


def test_one_active_run_at_a_time_and_cap_and_gap(tmp_path, monkeypatch):
    monkeypatch.setenv("GB_ADMIN_TOKEN", TOKEN)
    root = tmp_path / "root"
    (root / "knowledge" / "cards").mkdir(parents=True)
    shutil.copy(REPO / "knowledge" / "cards" / "paper_cup.json", root / "knowledge" / "cards" / "paper_cup.json")
    hold = threading.Event()
    mock = MockCreao(hold)
    t = {"now": 100.0}
    runs = ResearchRuns(root, enabled=True, poll_interval=0, min_gap_s=10, max_runs=2, clock=lambda: t["now"],
                        client_factory=lambda: CreaoClient(api_key=KEY, transport=httpx.MockTransport(mock), sleep=lambda s: None))
    rt = Runtime(load_cards(root / "knowledge" / "cards"), log_dir=tmp_path / "l", asset_root=root)
    with TestClient(create_app(rt, tick_interval=None, sim_interval=None, web_dir=tmp_path / "x", research_runs=runs)) as c:
        rid = start(c, MOCK_A_REQUEST)
        r = c.post("/research/run", json={"goal": MOCK_B_REQUEST})
        assert r.status_code == 429 and "already active" in r.text
        hold.set()
        wait_status(c, rid)
        r = c.post("/research/run", json={"goal": MOCK_B_REQUEST})
        assert r.status_code == 429 and "one new run per 10 s" in r.text
        t["now"] += 11
        rid2 = start(c, MOCK_B_REQUEST)
        wait_status(c, rid2)
        t["now"] += 11
        r = c.post("/research/run", json={"goal": MOCK_A_REQUEST})
        assert r.status_code == 429 and "run cap reached" in r.text
        assert len(mock.posts) == 2


def test_run_table_persists_and_interrupted_runs_are_marked_failed(world):
    c = world
    rec = wait_status(c, start(c, MOCK_A_REQUEST))
    path = c.root / "knowledge" / "requests" / "creao_runs.json"
    data = json.loads(path.read_text())
    data["runs"].append({**data["runs"][0], "run_id": "r-stuck", "status": "running"})
    path.write_text(json.dumps(data))
    again = ResearchRuns(c.root, enabled=True)
    assert again.get(rec["run_id"])["status"] == "draft_ready"
    assert again.get("r-stuck")["status"] == "failed" and "restart" in again.get("r-stuck")["error"]


def test_get_unknown_run_404(world):
    assert world.get("/research/runs/r-nope").status_code == 404


# --------------------------------------------------------------------------- Runtime.reload_cards
def test_reload_keeps_position_when_step_ids_match_and_restarts_when_not(tmp_path, card):
    from pbhelpers import make_card

    root = tmp_path / "root"
    cards_dir = root / "knowledge" / "cards"
    cards_dir.mkdir(parents=True)
    base = make_card(4, card_id="demo_task", title="Demo task", aliases=["demo task"])
    (cards_dir / "demo_task.json").write_text(base.model_dump_json())
    clock = ManualClock()
    rt = Runtime(load_cards(cards_dir) + [card], clock=clock, log_dir=tmp_path / "l", asset_root=root)
    rt.clock = clock
    rt.hello(G2Hello(client_id="g1", session_id=None))
    clock.advance(2600)
    rt.tick()
    rt.handle_input(gi("press"))  # failsafe list
    ch = rt.sessions._root_choice()
    for _ in range(next(i for i, c in enumerate(ch.cards) if c.card_id == "demo_task")):
        rt.handle_input(gi("swipe_down"))
    rt.handle_input(gi("press"))  # pick the demo task from the first screen
    settle(rt)
    for _ in range(2):  # confirm two manual steps
        clock.advance(1600)
        rt.tick()
        rt.handle_input(gi("swipe_down"))
    assert rt.state().playbook.step_index == 2

    edited = base.model_copy(update={"title": "Demo task v2"})
    (cards_dir / "demo_task.json").write_text(edited.model_dump_json())
    res = rt.reload_cards()
    assert res["changed"] == ["demo_task"] and res["active"] == "updated"
    assert rt.playbook.card.title == "Demo task v2" and rt.state().playbook.step_index == 2 and len(rt.state().playbook.confirmed) == 2
    assert [c.card_id for c in rt.cards].count("camera_lens") == 1  # in-memory-only card survives a reload

    changed_steps = make_card(3, card_id="demo_task", title="Demo task v3", aliases=["demo task"])
    changed_steps.steps[0].id = "renamed"
    (cards_dir / "demo_task.json").write_text(changed_steps.model_dump_json())
    res = rt.reload_cards()
    assert res["active"] == "restarted" and rt.state().playbook.step_index == 0 and rt.state().playbook.step_count == 3
    assert rt.reload_cards()["active"] == "kept"  # nothing changed


def test_reload_with_empty_directory_never_drops_all_cards(tmp_path, card):
    rt = Runtime([card], log_dir=tmp_path / "l", asset_root=tmp_path / "empty")
    res = rt.reload_cards()
    assert [c.card_id for c in rt.cards] == [card.card_id] and res["loaded"] == 1


def test_actual_transport_run_id_and_share_link_survive_approval_and_restart(world):
    c = world
    c.mock.canned[MOCK_A_REQUEST] = {**MOCK_A_ENVELOPE_RUN, "shareUrl": "https://agent.creao.ai/shared/real-id"}
    rec = wait_status(c, start(c, MOCK_A_REQUEST))
    assert rec["share_url"] == "https://agent.creao.ai/shared/real-id"
    provider = rec["draft"]["provider"]
    assert provider["run_id"] == rec["creao_run_id"] == "mock_1"
    assert provider["live_api_verified"] is False
    env_path = c.root / "knowledge" / "drafts" / rec["draft_id"] / "envelope.json"
    env = json.loads(env_path.read_text())
    assert env["run_id"] == "mock_1"  # never model-authored run_mock_bike_01
    assert c.post(f"/cards/drafts/{rec['draft_id']}/approve", json={"reviewer": "Ada"}, headers=H).status_code == 200
    review = json.loads((env_path.parent / "review.json").read_text())
    assert review["run_id"] == "mock_1" and review["provider"] == provider
    restarted = ResearchRuns(c.root, enabled=True)
    assert restarted.get(rec["run_id"])["share_url"] == rec["share_url"]
    assert restarted.get(rec["run_id"])["approved_by"] == "Ada"


def test_repeated_phone_request_reuses_cached_draft_and_survives_restart(world):
    c = world
    rid = start(c, MOCK_A_REQUEST, session_id="phone-session", intent="build")
    rec = wait_status(c, rid)
    assert rec["status"] == "draft_ready"
    assert start(c, MOCK_A_REQUEST, session_id="phone-session", intent="build") == rid
    again = ResearchRuns(c.root, enabled=True, min_gap_s=0, client_factory=lambda: None)
    from ghostbuild_core.research_runs import RunBody
    assert again.start(RunBody(goal=MOCK_A_REQUEST, session_id="phone-session", intent="build")) == rid
    assert again.status()["started_this_process"] == 0
    assert len(c.mock.posts) == 1
