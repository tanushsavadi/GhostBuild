import json

import pytest
from fastapi.testclient import TestClient

from ghostbuild_core.clock import ManualClock
from ghostbuild_core.runtime import Runtime
from ghostbuild_core.server import create_app

from conftest import Feeder

HELLO = {"type": "g2_hello", "v": 2, "client_id": "g2-b1", "session_id": None, "surface": "g2"}


def inp(g):
    return {"type": "g2_input", "v": 2, "gesture": g, "seq_seen": 0, "surface": "g2"}


@pytest.fixture
def rt(card, asset_root, tmp_path):
    clock = ManualClock()
    r = Runtime([card], clock=clock, log_dir=tmp_path / "logs", asset_root=asset_root)
    r.clock = clock
    return r


@pytest.fixture
def client(rt):
    app = create_app(rt, tick_interval=None, sim_interval=None, web_dir=rt.asset_root / "no-web")
    with TestClient(app) as c:
        yield c


def post_obs(client, rt, feeder, ms=100, **kw):
    rt.clock.advance(ms)
    o = feeder.obs(**kw)
    r = client.post("/observation", content=o.model_dump_json())
    assert r.status_code == 204
    rt.tick()
    return r


def test_health_state_card_session_before_anything(client):
    h = client.get("/health").json()
    assert h["pi_link"] == "down" and h["camera"] == "unknown" and h["g2_clients"] == 0
    st = client.get("/state").json()
    assert st["engine"] in ("HEALTHY", "NO_LINK") and st["card_id"] == "camera_lens" and st["session"]["welcome_shown"] is False
    assert client.get("/card").json()["card_id"] == "camera_lens"
    assert client.get("/session").json()["id"] == "none"
    assert client.get("/phone").status_code == 404  # no web dir: 404, not a crash


def test_cors_allow_all(client):
    r = client.get("/health", headers={"Origin": "http://x.example"})
    assert r.headers["access-control-allow-origin"] == "*"
    r = client.options("/observation", headers={"Origin": "http://x.example", "Access-Control-Request-Method": "POST"})
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] in ("*", "http://x.example")


def test_observation_validation_and_dup_seq(client, rt):
    assert client.post("/observation", content=b'{"nope": 1}').status_code == 422
    f = Feeder(rt.engine, rt.clock)
    o = f.obs()
    assert client.post("/observation", content=o.model_dump_json()).status_code == 204
    r = client.post("/observation", content=o.model_dump_json())
    assert r.status_code == 204 and r.headers.get("x-ghostbuild-dropped") == "stale_seq"
    assert client.get("/health").json()["pi_last_seq"] == o.seq


def test_observation_to_ws_frame_end_to_end(client, rt):
    f = Feeder(rt.engine, rt.clock)
    with client.websocket_connect("/ws?role=g2") as ws:
        ws.send_text(json.dumps(HELLO))
        first = ws.receive_json()
        assert first["type"] == "hud" and first["mode"] == "welcome"  # new session
        assert client.get("/health").json()["g2_clients"] == 1
        for _ in range(8):
            post_obs(client, rt, f)  # keep the link up while the welcome plays
        rt.clock.advance(2600)
        rt.tick()
        p = ws.receive_json()
        assert p["mode"] == "intervene" and p["cue"]["line1"] == "WHAT DO YOU NEED?" and p["menu"] is None  # conversation front screen
        ws.send_text(json.dumps(inp("press")))  # failsafe: a tap lists what can start
        m = ws.receive_json()
        assert m["mode"] == "menu" and m["menu"]["prompt"] == "PICK A TASK" and m["menu"]["options"][0] == "PI CAMERA VIEW"
        ws.send_text(json.dumps(inp("press")))
        t = ws.receive_json()
        assert t["mode"] == "intervene" and t["cue"]["line1"].startswith("FIX:")
        rt.clock.advance(2600)
        post_obs(client, rt, f)
        assert ws.receive_json()["mode"] == "quiet"
        for _ in range(20):
            post_obs(client, rt, f, luma=6.0, std=1.0)
        fault = ws.receive_json()
        assert fault["mode"] == "intervene" and fault["cue"]["line1"] == "CAMERA VIEW LOST" and fault["source"] == "pi_live"
        ws.send_text(json.dumps(inp("press")))
        vis = ws.receive_json()
        assert vis["mode"] == "visual" and vis["image"]["url"] == "/guides/camera_lens/where.png"
        img = client.get(vis["image"]["url"])
        assert img.status_code == 200 and img.headers["content-type"] == "image/png" and img.content[:4] == b"\x89PNG"
    assert client.get("/health").json()["g2_clients"] == 0


def test_two_clients_get_same_frames_and_known_hello_gets_current(client, rt):
    f = Feeder(rt.engine, rt.clock)
    with client.websocket_connect("/ws?role=g2") as a, client.websocket_connect("/ws?role=g2") as b:
        a.send_text(json.dumps(HELLO))
        assert a.receive_json()["mode"] == "welcome"
        sid = client.get("/session").json()["id"]
        b.send_text(json.dumps({**HELLO, "client_id": "sim", "session_id": sid, "surface": "simulator"}))
        assert b.receive_json()["mode"] == "welcome"  # current frame (not a new welcome): same seq
        rt.clock.advance(2600)
        post_obs(client, rt, f)
        ma, mb = a.receive_json(), b.receive_json()
        assert ma == mb and ma["cue"]["line1"] == "WHAT DO YOU NEED?"
        assert client.get("/health").json()["g2_clients"] == 2
        # reconnect with known id: current frame, not welcome
        with client.websocket_connect("/ws?role=g2") as c:
            c.send_text(json.dumps({**HELLO, "session_id": sid}))
            assert c.receive_json()["cue"]["line1"] == "WHAT DO YOU NEED?"


def test_ws_ignores_garbage_and_input_before_hello(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_text("not json")
        ws.send_text(json.dumps({"type": "who"}))
        ws.send_text(json.dumps(inp("press")))
        assert ws.receive_json()["type"] == "hud"


def test_polling_fallback(client, rt):
    f = Feeder(rt.engine, rt.clock)
    r = client.post("/hello", json=HELLO)
    assert r.status_code == 200 and r.json()["mode"] == "welcome" and r.headers["x-ghostbuild-session"].startswith("s-")
    seq = r.json()["seq"]
    assert client.get(f"/hud?after={seq}").status_code == 204
    assert client.get(f"/hud?after={seq - 1}").json()["seq"] == seq
    for _ in range(8):
        post_obs(client, rt, f)
    rt.clock.advance(2600)
    rt.tick()
    assert client.get(f"/hud?after={seq}").json()["cue"]["line1"] == "WHAT DO YOU NEED?"
    assert client.post("/input", json=inp("press")).json()["mode"] == "menu"  # failsafe list
    r = client.post("/input", json=inp("press"))
    assert r.status_code == 200 and r.json()["cue"]["line1"].startswith("FIX:")
    assert client.get("/health").json()["g2_clients"] == 1
    assert client.post("/input", json={"type": "g2_input"}).status_code == 422


def test_goal_endpoint(client, rt):
    client.post("/hello", json=HELLO)
    sid = client.get("/session").json()["id"]
    r = client.post("/session/goal", json={"v": 2, "session_id": sid, "mode": "fix", "via": "phone_text", "text": "fix my toaster"})
    assert r.status_code == 200 and r.json()["status"] == "unsupported" and r.json()["cue"]["line1"] == "NOT SUPPORTED YET"
    r = client.post("/session/goal", json={"v": 2, "session_id": sid, "mode": "fix", "via": "phone_text", "text": "my camera view is black"})
    assert r.json()["status"] == "supported" and client.get("/session").json()["phase"] == "task"
    assert client.post("/session/goal", json={"v": 2, "session_id": "zzz", "mode": "fix", "via": "phone_text"}).status_code == 404


def test_state_and_events_after_fault(client, rt):
    f = Feeder(rt.engine, rt.clock)
    for _ in range(25):
        post_obs(client, rt, f, luma=6.0, std=1.0)
    st = client.get("/state").json()
    assert st["engine"] == "FAULT" and st["test"] == "camera_view" and st["hud"]["mode"] == "intervene"
    assert st["source"] == "pi_live" and st["health"]["pi_link"] == "up" and st["health"]["camera"] == "ok"
    assert {e["label"] for e in st["events"]} >= {"MEASURED LIVE", "INFERRED"}
    assert len(st["events"]) <= 50


def test_guide_route_404s(client):
    assert client.get("/guides/camera_lens/nope.png").status_code == 404
    assert client.get("/guides/other/where.png").status_code == 404


def test_guide_missing_file_404(card, tmp_path):
    r = Runtime([card], clock=ManualClock(), asset_root=tmp_path / "empty")
    with TestClient(create_app(r, tick_interval=None, sim_interval=None)) as c:
        assert c.get("/guides/camera_lens/where.png").status_code == 404


def test_phone_static_served_when_web_exists(card, asset_root):
    (asset_root / "web").mkdir()
    (asset_root / "web" / "index.html").write_text("<h1>phone</h1>")
    r = Runtime([card], clock=ManualClock(), asset_root=asset_root)
    with TestClient(create_app(r, tick_interval=None, sim_interval=None)) as c:
        assert c.get("/phone/").status_code == 200 and "phone" in c.get("/phone/").text


def test_sim_scenario_only_when_simulating(client, card, asset_root):
    assert client.post("/sim/scenario?name=blocked").status_code in (404, 405)
    r = Runtime([card], clock=ManualClock(), asset_root=asset_root, simulate=True)
    with TestClient(create_app(r, tick_interval=None, sim_interval=None)) as c:
        assert c.post("/sim/scenario?name=blocked").json()["source"] == "simulated"
        assert c.post("/sim/scenario?name=bogus").status_code == 422


def test_session_log_written(rt, client, tmp_path):
    f = Feeder(rt.engine, rt.clock)
    for _ in range(20):
        post_obs(client, rt, f, luma=6.0, std=1.0)
    rt.elog.close()
    recs = [json.loads(line) for line in rt.elog.path.read_text().splitlines()]
    kinds = {r["kind"] for r in recs}
    assert {"observation", "event", "frame"} <= kinds
