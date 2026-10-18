import hashlib

from conftest import press


def fault(feed, ms=3000):
    feed.blocked(ms)


def test_press_opens_where_with_correct_imageref(engine, feed, asset_root):
    fault(feed)
    f = engine.handle_input(press())
    assert f is not None and f.mode == "visual"
    im = f.image
    assert (im.guide_id, im.view, im.index, im.count) == ("camera_lens", "where", 0, 3)
    assert im.url == "/guides/camera_lens/where.png"
    assert (im.w, im.h) == (64, 32)
    data = (asset_root / "knowledge/guides/camera_lens/where.png").read_bytes()
    assert im.sha256 == hashlib.sha256(data).hexdigest()
    assert im.step_id == "camera_lens.where" and im.provenance == "AUTHORED DEMO METADATA"
    assert f.cue is not None  # text fallback always present
    assert engine.help_view() == "where"


def test_swipe_order_and_clamp(engine, feed):
    fault(feed)
    engine.handle_input(press())
    f = engine.handle_input(press("swipe_down"))
    assert f.image.view == "how" and f.image.index == 1
    f = engine.handle_input(press("swipe_down"))
    assert f.image.view == "correct" and f.image.index == 2
    n = len(engine.frames)
    assert engine.handle_input(press("swipe_down")) is None  # clamped, identical => no new frame
    assert len(engine.frames) == n
    f = engine.handle_input(press("swipe_up"))
    assert f.image.view == "how"
    f = engine.handle_input(press("swipe_up"))
    assert f.image.view == "where"
    f = engine.handle_input(press("swipe_up"))  # index 0 -> primary cue
    assert f.mode == "intervene" and f.cue.line2 == "CHECK CAMERA LENS"


def test_press_toggles_and_context_preserved(engine, feed):
    fault(feed)
    engine.handle_input(press())
    engine.handle_input(press("swipe_down"))
    f = engine.handle_input(press())  # press in help => back to cue
    assert f.mode == "intervene" and f.cue.line1 == "CAMERA VIEW LOST"
    f = engine.handle_input(press())  # reopen restores HOW
    assert f.mode == "visual" and f.image.view == "how"


def test_swipe_without_help_open_is_ignored(engine, feed):
    fault(feed)
    n = len(engine.frames)
    assert engine.handle_input(press("swipe_down")) is None
    assert engine.handle_input(press("swipe_up")) is None
    assert len(engine.frames) == n


def test_press_never_changes_fault_state(engine, feed):
    fault(feed)
    for g in ("press", "swipe_down", "press", "press", "press"):
        engine.handle_input(press(g))
    assert engine.state == "FAULT"
    assert "verified" not in [f.mode for f in engine.frames]


def test_missing_image_text_fallback(card, clock, tmp_path):
    from conftest import Feeder
    from ghostbuild_core.engine import Engine

    e = Engine(card, clock, asset_root=tmp_path / "nothing_here")
    f = Feeder(e, clock)
    f.blocked(3000)
    out = e.handle_input(press())
    assert out.mode == "intervene" and out.image is None
    assert (out.cue.line1, out.cue.line2) == ("FALLBACK WHERE", "TEXT ONLY")
    out = e.handle_input(press("swipe_down"))
    assert out.cue.line1 == "FALLBACK HOW" and out.image is None


def test_unreadable_image_text_fallback(card, clock, asset_root):
    from conftest import Feeder
    from ghostbuild_core.engine import Engine

    (asset_root / "knowledge/guides/camera_lens/where.png").write_bytes(b"not a png")
    e = Engine(card, clock, asset_root=asset_root)
    f = Feeder(e, clock)
    f.blocked(3000)
    out = e.handle_input(press())
    assert out.mode == "intervene" and out.image is None


def test_oversize_image_falls_back(card, clock, asset_root):
    from PIL import Image

    from conftest import Feeder
    from ghostbuild_core.engine import Engine

    Image.new("L", (400, 300)).save(asset_root / "knowledge/guides/camera_lens/where.png")
    e = Engine(card, clock, asset_root=asset_root)
    Feeder(e, clock).blocked(3000)
    assert e.handle_input(press()).image is None


def test_press_when_healthy_status_then_quiet(engine, feed):
    feed.healthy(2000)
    f = engine.handle_input(press())
    assert f.cue.line1 == "ALL TESTS PASSING" and f.cue.line2 == "LIVE" and f.ttl_ms == 3000
    n = len(engine.frames)
    assert engine.handle_input(press()) is None  # identical => no new frame
    feed.healthy(3500)
    assert engine.frames[-1].mode == "quiet"
    assert len(engine.frames) == n + 1


def test_press_status_simulated_label(engine, feed):
    feed.healthy(2000, source="simulated")
    f = engine.handle_input(press())
    assert f.cue.line2 == "SIMULATED" and f.source == "simulated"


def test_press_with_no_data_shows_nothing_success(engine, feed):
    assert engine.handle_input(press()) is None
    assert engine.frames == []


def test_press_during_link_loss_keeps_error(engine, feed):
    feed.healthy(1000)
    feed.idle(6000)
    n = len(engine.frames)
    assert engine.handle_input(press()) is None
    assert engine.frames[-1].mode == "error" and len(engine.frames) == n


def test_hold_gestures_ignored(engine, feed):
    fault(feed)
    n = len(engine.frames)
    assert engine.handle_input(press("hold_start")) is None
    assert engine.handle_input(press("hold_end")) is None
    assert len(engine.frames) == n


def test_input_response_is_not_throttled(engine, feed):
    fault(feed, 1800)  # fault frame at ~1.6 s
    f = engine.handle_input(press())  # < 2 s later: direct response, immediate
    assert f is not None and f.mode == "visual"


def test_throttle_defers_non_input_cues(engine, feed):
    # fault frame ~1.6 s, recovery measured ~3.1 s: deferred until 2 s after the first cue
    feed.blocked(1800)
    assert len(engine.frames) == 1
    feed.healthy(1200)
    assert [f.mode for f in engine.frames] == ["intervene"]
    feed.healthy(600)
    assert [f.mode for f in engine.frames][:2] == ["intervene", "verified"]


def test_help_closed_on_recovery(engine, feed):
    fault(feed)
    engine.handle_input(press())
    feed.healthy(5000)
    assert engine.help_view() is None
    assert engine.state in ("HEALTHY", "AWAIT_FUNC")
    assert engine.frames[-1].mode != "visual"


def test_new_episode_resets_help_index_and_offer(engine, feed):
    fault(feed, 3000)
    engine.handle_input(press())
    engine.handle_input(press("swipe_down"))
    feed.healthy(8000)
    feed.blocked(3000)
    f = engine.handle_input(press())
    assert f.image.view == "where"
