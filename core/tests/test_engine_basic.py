from conftest import press


def modes(e):
    return [f.mode for f in e.frames]


def test_flicker_produces_no_frames(engine, feed):
    feed.healthy(2000)
    feed.blocked(1000)  # < fail_after_ms (1500)
    feed.healthy(3000)
    assert engine.frames == []
    assert engine.state == "HEALTHY"


def test_sustained_failure_one_intervene_frame(engine, feed):
    feed.healthy(1000)
    feed.blocked(5000)
    assert len(engine.frames) == 1
    f = engine.frames[0]
    assert f.mode == "intervene" and f.cue.line1 == "CAMERA VIEW LOST" and f.cue.line2 == "CHECK CAMERA LENS"
    assert f.source == "pi_live" and f.seq == 1
    assert engine.state == "FAULT"


def test_identical_frames_never_reemitted(engine, feed):
    feed.healthy(500)
    feed.blocked(6000)
    n = len(engine.frames)
    feed.blocked(5000)  # offer already emitted at 8 s; nothing new until recovery
    assert len(engine.frames) <= n + 0 or all(a.seq + 1 == b.seq for a, b in zip(engine.frames, engine.frames[1:]))
    keys = [(f.mode, f.cue.line1 if f.cue else None, f.cue.line2 if f.cue else None) for f in engine.frames]
    assert all(a != b for a, b in zip(keys, keys[1:]))


def test_healthy_60s_zero_frames(engine, feed):
    feed.healthy(60_000)
    assert engine.frames == []
    assert engine.hud.current.mode == "quiet" and engine.hud.current.seq == 0


def test_recovery_needs_measured_pass_window(engine, feed):
    feed.blocked(2000)
    assert modes(engine) == ["intervene"]
    feed.healthy(800)  # < pass_after_ms (1000)
    assert modes(engine) == ["intervene"]
    feed.blocked(500)  # relapse resets the pass window
    feed.healthy(800)
    assert modes(engine) == ["intervene"]
    feed.healthy(500)
    assert modes(engine)[-1] == "verified"
    v = engine.frames[-1]
    assert v.cue.line1 == "● CAMERA VIEW BACK" and v.ttl_ms == 3000
    # a quiet or the functional prompt follows at ttl expiry
    feed.healthy(3500)
    assert engine.frames[-1].mode in ("quiet", "intervene")


def test_verified_then_quiet_without_functional(card_dict, clock, asset_root):
    from contracts.models import Card
    from ghostbuild_core.engine import Engine
    from conftest import Feeder

    d = dict(card_dict)
    d["functional"] = None
    e = Engine(Card.model_validate(d), clock, asset_root=asset_root)
    f = Feeder(e, clock)
    f.blocked(5000)
    f.healthy(1500)
    assert e.frames[-1].mode == "verified"
    f.healthy(3500)
    assert e.frames[-1].mode == "quiet"
    assert modes(e) == ["intervene", "verified", "quiet"]


def test_null_camera_never_recovers(engine, feed):
    feed.blocked(2000)
    n = len(engine.frames)
    feed.run(5000, camera=False, error="camera_open_failed")
    assert engine.frames[-1].mode == "error"
    assert engine.frames[-1].cue.line1 == "CAMERA FEED LOST" and engine.frames[-1].cue.line2 == "CHECK CAMERA CABLE"
    assert "verified" not in modes(engine)
    assert engine.state == "FAULT"


def test_null_camera_when_healthy_is_error_not_success(engine, feed):
    feed.healthy(2000)
    feed.run(3000, camera=False)
    assert modes(engine) == ["error"]
    assert "verified" not in modes(engine)


def test_frozen_feed_error(engine, feed):
    feed.healthy(1000)
    feed.run(3000, frame=False)  # frame_seq stuck, observations keep coming
    e = engine.frames[-1]
    assert e.mode == "error" and e.cue.line1 == "CAMERA FEED FROZEN" and e.cue.line2 == "RESTART CAMERA"
    assert e.stale is True
    feed.healthy(500)  # new frames flow again
    assert engine.frames[-1].mode == "quiet"


def test_link_loss_error_then_recovery(engine, feed):
    feed.healthy(2000)
    feed.idle(5200)
    assert engine.frames[-1].mode == "error"
    assert engine.frames[-1].cue.line1 == "PI LINK LOST" and engine.frames[-1].cue.line2 == "CHECK PI POWER"
    assert engine.state == "NO_LINK"
    feed.healthy(500)
    assert engine.frames[-1].mode == "quiet"
    assert engine.state == "HEALTHY"
    assert "verified" not in modes(engine)


def test_never_connected_is_link_lost_after_grace(engine, feed):
    feed.idle(4800)
    assert engine.frames == []
    feed.idle(500)
    assert engine.frames[-1].cue.line1 == "PI LINK LOST"


def test_link_loss_during_fault_then_still_failing_stays_fault(engine, feed):
    feed.blocked(2000)
    feed.idle(6000)
    assert engine.frames[-1].mode == "error"
    feed.blocked(300)
    assert engine.frames[-1].mode == "intervene"
    assert "verified" not in modes(engine)


def test_offer_help_once(engine, feed):
    feed.blocked(7000)
    assert [f.cue.line2 for f in engine.frames] == ["CHECK CAMERA LENS"]
    feed.blocked(3000)
    assert [f.cue.line2 for f in engine.frames] == ["CHECK CAMERA LENS", "PRESS FOR PICTURE"]
    assert engine.frames[-1].cue.line1 == "CAMERA VIEW LOST" and engine.frames[-1].mode == "intervene"
    feed.blocked(30_000)
    assert len(engine.frames) == 2


def test_offer_not_repeated_after_help_used(engine, feed):
    feed.blocked(10_000)
    assert engine.frames[-1].cue.line2 == "PRESS FOR PICTURE"
    engine.handle_input(press())
    engine.handle_input(press())  # back to cue
    feed.blocked(20_000)
    assert engine.frames[-1].cue.line2 == "CHECK CAMERA LENS"
    assert sum(1 for f in engine.frames if f.cue and f.cue.line2 == "PRESS FOR PICTURE") == 1


def test_seq_drop_and_reboot_heuristic(engine, feed):
    o = feed.obs()
    assert engine.ingest(o) is True
    assert engine.ingest(o) is False  # duplicate
    feed.seq = 1000
    assert engine.ingest(feed.obs()) is True
    feed.seq = 990
    assert engine.ingest(feed.obs()) is False  # reordered within 50
    feed.seq = 10  # < last-50 => new boot
    assert engine.ingest(feed.obs()) is True


def test_evidence_labels(engine, feed):
    feed.blocked(2000)
    labels = [(e.label) for e in engine.events]
    assert "MEASURED LIVE" in labels and "INFERRED" in labels


def test_evidence_labels_simulated(engine, feed):
    feed.blocked(2000, source="simulated")
    assert all(e.label in ("SIMULATED",) for e in engine.events)
    assert engine.frames[-1].source == "simulated"
