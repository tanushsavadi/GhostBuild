import json

import pytest

from contracts.models import Observation
from ghostbuild_core.cards import load_cards
from ghostbuild_core.clock import ManualClock
from ghostbuild_core.engine import Engine
from ghostbuild_core.replay import main as replay_main
from ghostbuild_core.replay import replay
from ghostbuild_core.runtime import Runtime
from ghostbuild_core.simulate import SimPi

from conftest import CARD_PATH, REPO, Feeder


def run_sim(sim, clock, eng, seconds):
    for _ in range(seconds * 10):
        clock.advance(100)
        eng.ingest(sim.observe())
        eng.tick()


def test_sim_script_produces_labelled_simulated_frames(card, asset_root):
    clock = ManualClock()
    eng = Engine(card, clock, asset_root=asset_root)
    sim = SimPi(clock)
    run_sim(sim, clock, eng, 100)
    assert all(f.source == "simulated" for f in eng.frames)
    assert all(e.label == "SIMULATED" for e in eng.events if e.label not in ("DETERMINISTIC", "COMMANDED"))
    seq = [(f.mode, f.cue.line1 if f.cue else None) for f in eng.frames]
    assert ("intervene", "CAMERA VIEW LOST") in seq
    assert ("verified", "● CAMERA VIEW BACK") in seq
    assert ("verified", "● LED COMMANDED") in seq
    assert seq.index(("intervene", "CAMERA VIEW LOST")) < seq.index(("verified", "● CAMERA VIEW BACK")) < seq.index(("verified", "● LED COMMANDED"))


@pytest.mark.parametrize("name,expect", [
    ("blocked", "CAMERA VIEW LOST"),
    ("null_camera", "CAMERA FEED LOST"),
    ("freeze", "CAMERA FEED FROZEN"),
])
def test_sim_scenarios(card, asset_root, name, expect):
    clock = ManualClock()
    eng = Engine(card, clock, asset_root=asset_root)
    sim = SimPi(clock)
    run_sim(sim, clock, eng, 3)
    sim.set_scenario(name)
    run_sim(sim, clock, eng, 6)
    assert eng.frames[-1].cue.line1 == expect and eng.frames[-1].source == "simulated"


def test_sim_healthy_is_silent(card, asset_root):
    clock = ManualClock()
    eng = Engine(card, clock, asset_root=asset_root)
    sim = SimPi(clock)
    sim.set_scenario("healthy")
    run_sim(sim, clock, eng, 60)
    assert eng.frames == []


def test_sim_bad_scenario():
    with pytest.raises(ValueError):
        SimPi(ManualClock()).set_scenario("nope")


def test_runtime_simulate_labels_initial_source(card, asset_root):
    r = Runtime([card], clock=ManualClock(), asset_root=asset_root, simulate=True)
    assert r.hud.current.source == "simulated" and r.state().hud.source == "simulated"


def test_load_cards_skips_invalid(tmp_path, caplog):
    (tmp_path / "good.json").write_text(CARD_PATH.read_text())
    (tmp_path / "bad.json").write_text(json.dumps({"card_id": "x", "tests": []}))
    (tmp_path / "junk.json").write_text("{ not json")
    (tmp_path / "other.json").write_text(json.dumps({"hello": 1}))
    with caplog.at_level("WARNING"):
        cards = load_cards(tmp_path)
    assert sorted(c.card_id for c in cards) == ["camera_lens", "led_breadboard"]
    assert "skipping invalid card" in caplog.text and "unreadable JSON" in caplog.text
    assert load_cards(tmp_path / "nope") == []


def test_load_examples_dir_loads_the_fixture_card():
    cards = load_cards(REPO / "contracts" / "examples")
    assert sorted(c.card_id for c in cards) == ["camera_lens", "led_breadboard"]


def make_log(path, card, asset_root):
    clock = ManualClock()
    rt = Runtime([card], clock=clock, log_dir=path, asset_root=asset_root)
    f = Feeder(rt.engine, clock)
    for ms, kw in [(2000, {}), (3000, dict(luma=6.0, std=1.0)), (2000, {}), (4000, {})]:
        for _ in range(ms // 100):
            clock.advance(100)
            rt.ingest(f.obs(**kw))
            rt.tick()
    live = [(x.mode, x.cue.line1 if x.cue else None) for x in rt.hud.frames]
    rt.close()
    return rt.elog.path, live


def test_replay_matches_live_sequence_and_forces_replay_source(card, asset_root, tmp_path):
    p, live = make_log(tmp_path / "logs", card, asset_root)
    frames = replay(p, card, asset_root=asset_root)
    got = [(x.mode, x.cue.line1 if x.cue else None) for x in frames]
    assert got[:2] == live[:2] == [("intervene", "CAMERA VIEW LOST"), ("verified", "● CAMERA VIEW BACK")]
    assert all(x.source == "replay" for x in frames)


def test_replay_cli_prints_replay_banner(card, asset_root, tmp_path, capsys):
    p, _ = make_log(tmp_path / "logs", card, asset_root)
    assert replay_main([str(p), "--card", str(CARD_PATH), "--root", str(asset_root)]) == 0
    out = capsys.readouterr().out
    assert "REPLAY (not live)" in out and "CAMERA VIEW LOST" in out and "src=replay" in out


def test_replay_accepts_bare_observation_lines(card, asset_root):
    clock = ManualClock()
    f = Feeder(Engine(card, clock), clock)
    lines = []
    for i in range(40):
        clock.advance(100)
        lines.append(f.obs(luma=6.0, std=1.0).model_dump_json())
    frames = replay(lines, card, asset_root=asset_root)
    assert frames and frames[0].cue.line1 == "CAMERA VIEW LOST" and frames[0].source == "replay"


def test_replay_is_fast_and_deterministic(card, asset_root, tmp_path):
    p, _ = make_log(tmp_path / "logs", card, asset_root)
    a = [x.model_dump() for x in replay(p, card, asset_root=asset_root)]
    b = [x.model_dump() for x in replay(p, card, asset_root=asset_root)]
    assert a == b
