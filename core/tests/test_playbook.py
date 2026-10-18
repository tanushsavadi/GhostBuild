"""PlaybookEngine: manual walk with ZERO observations, guard, pictures, measured steps, completion wording."""

from __future__ import annotations

import hashlib

import pytest

from pbhelpers import Rig, example_card, guide_dict, make_card, verify_led, verify_luma, write_pngs


# ------------------------------------------------------------------ manual walks, no telemetry at all
def test_example_card_first_frame_is_step_zero():
    r = Rig(example_card())
    f = r.cur
    assert f.mode == "step" and f.cue.line1 == "GATHER LED + RESISTOR"  # clipped to 24 by the HUD
    assert (f.step.index, f.step.count, f.step.step_id, f.step.check, f.step.confirmed) == (0, 3, "parts", "manual", False)
    assert f.ttl_ms is None  # stays on screen


def test_manual_walk_eight_steps_with_zero_observations():
    r = Rig(make_card(8))
    for i in range(8):
        assert r.cur.mode == "step" and r.cur.step.index == i and r.cur.step.check == "manual"
        assert r.cur.cue.line1 == f"DO THING {i}"
        f = r.confirm()
        assert f is not None
    assert r.cur.mode == "intervene" and (r.cur.cue.line1, r.cur.cue.line2) == ("✓ ALL STEPS DONE", "YOU CONFIRMED EACH") and r.cur.ttl_ms == 4000
    r.wait(4100)
    assert r.cur.mode == "quiet"
    st = r.pb.playbook_state()
    assert st.confirmed == [f"s{i}" for i in range(8)] and st.verified == []
    ev = [e for e in r.pb.events if e.label == "HUMAN CONFIRMED"]
    assert [e.text for e in ev] == [f"step s{i} confirmed by wearer" for i in range(8)]
    assert not [x for x in r.frames if x.mode == "verified" or (x.cue and "●" in x.cue.line1)]
    assert not [x for x in r.frames if x.mode == "error"]


def test_after_completion_press_says_task_complete_then_quiet():
    r = Rig(make_card(2, title="Build a thing"))
    r.confirm(), r.confirm()
    r.wait(4100)
    f = r.send("press")
    assert f.mode == "ask" and (f.cue.line1, f.cue.line2) == ("TASK COMPLETE", "Build a thing") and f.ttl_ms == 3000
    r.wait(3100)
    assert r.cur.mode == "quiet"


def test_swipe_up_goes_back_clamped_and_keeps_confirmations():
    r = Rig(make_card(4))
    r.send("swipe_up")  # clamped at 0: nothing
    n = len(r.frames)
    assert r.cur.step.index == 0 and len(r.frames) == n
    r.confirm(), r.confirm()
    assert r.cur.step.index == 2
    f = r.send("swipe_up")
    assert f.step.index == 1 and f.step.confirmed is True
    f = r.send("swipe_up")
    assert f.step.index == 0 and f.step.confirmed is True
    assert r.pb.playbook_state().confirmed == ["s0", "s1"]
    f = r.send("swipe_down")  # already confirmed: just moves on, no duplicate evidence
    assert f.step.index == 1 and f.step.confirmed
    assert len([e for e in r.pb.events if e.label == "HUMAN CONFIRMED"]) == 2


def test_swipe_up_after_completion_reopens_last_step():
    r = Rig(make_card(2))
    r.confirm(), r.confirm()
    r.wait(4100)
    f = r.send("swipe_up")
    assert f.mode == "step" and f.step.index == 1 and f.step.confirmed


# ------------------------------------------------------------------ accidental-input guard
def test_swipe_down_within_1500ms_of_step_frame_is_ignored():
    r = Rig(make_card(3))
    r.wait(1000)
    n = len(r.frames)
    assert r.send("swipe_down") is None
    assert len(r.frames) == n and r.cur.step.index == 0 and r.pb.playbook_state().confirmed == []
    r.wait(600)  # 1600 ms after the frame was shown
    assert r.send("swipe_down").step.index == 1
    assert r.send("swipe_down") is None  # the next step frame is brand new: guarded again
    assert r.cur.step.index == 1


def test_guard_starts_when_step_frame_is_actually_shown_not_before():
    r = Rig(make_card(3))
    r.confirm()
    r.wait(1400)
    assert r.send("swipe_down") is None
    r.wait(100)
    assert r.send("swipe_down").step.index == 2


# ------------------------------------------------------------------ pictures
def pic_card(measured=None):
    return make_card(3, guides=[guide_dict("gd", 3)], guide_steps={1: "gd"}, measured=measured)


def test_picture_open_next_prev_back(tmp_path):
    write_pngs(tmp_path)
    r = Rig(pic_card(), tmp_path)
    r.confirm()  # now on step 1 with a guide
    assert r.cur.step.index == 1
    f = r.send("press")
    assert f.mode == "visual" and f.image.view == "where" and f.image.index == 0 and f.image.count == 3
    assert f.step is not None and f.step.step_id == "s1"
    png = (tmp_path / "knowledge/guides/gd/where.png").read_bytes()
    assert f.image.sha256 == hashlib.sha256(png).hexdigest() and (f.image.w, f.image.h) == (64, 32)
    assert f.image.url == "/guides/gd/where.png"
    assert r.send("swipe_down").image.view == "how"
    assert r.send("swipe_down").image.view == "correct"
    assert r.send("swipe_down") is None  # clamped at the last view
    assert r.send("swipe_up").image.view == "how"
    assert r.send("swipe_up").image.view == "where"
    f = r.send("swipe_up")  # from view 0 back to the step
    assert f.mode == "step" and f.step.index == 1
    assert r.send("press").mode == "visual"
    f = r.send("press")  # press while a picture is open => back to the step
    assert f.mode == "step"
    # swipe_down while a picture is open must NEVER advance the step
    r.send("press")
    r.send("swipe_down")
    assert r.pb.playbook_state().step_index == 1 and r.pb.playbook_state().confirmed == ["s0"]


def test_missing_png_falls_back_to_step_frame_with_fallback_cue(tmp_path):
    r = Rig(pic_card(), tmp_path)  # no files written
    r.confirm()
    f = r.send("press")
    assert f.mode == "step" and f.image is None
    assert (f.cue.line1, f.cue.line2) == ("FALLBACK WHERE", "TEXT ONLY") and f.step.step_id == "s1"
    assert any("text fallback" in e.text for e in r.pb.events)
    f = r.send("swipe_down")  # next view is also missing -> its own fallback, still never a broken image
    assert f.mode == "step" and f.cue.line1 == "FALLBACK HOW"
    f = r.send("press")
    assert f.mode == "step" and f.cue.line1 == "DO THING 1"


def test_unreadable_or_oversized_png_is_a_fallback(tmp_path):
    from PIL import Image

    d = tmp_path / "knowledge/guides/gd"
    d.mkdir(parents=True)
    (d / "where.png").write_bytes(b"not a png")
    Image.new("L", (400, 200)).save(d / "how.png")  # wider than the G2 limit
    r = Rig(pic_card(), tmp_path)
    r.confirm()
    assert r.send("press").mode == "step"
    assert r.send("swipe_down").mode == "step"


def test_press_without_guide_shows_where_else_repeats_cue():
    r = Rig(make_card(3))  # steps have `where`, no guide
    f = r.send("press")
    assert f.mode == "ask" and f.cue.line1 == "WHERE 0 IS" and f.ttl_ms == 4000
    r.wait(4100)
    assert r.cur.mode == "step"
    d = make_card(1).model_dump(mode="json")
    d["steps"][0]["where"] = None
    from contracts.models import Card

    r2 = Rig(Card.model_validate(d))
    n = len(r2.frames)
    assert r2.send("press") is None and len(r2.frames) == n  # the cue is already on screen
    assert r2.cur.cue.line1 == "DO THING 0"


# ------------------------------------------------------------------ measured steps
def measured_card(hold=500):
    return make_card(3, measured={1: verify_led(hold)})


def test_measured_step_never_advances_on_a_gesture_no_data():
    r = Rig(measured_card())
    r.confirm()
    assert r.cur.step.index == 1 and r.cur.step.check == "measured"
    r.wait(1600)
    f = r.send("swipe_down")
    assert f.mode == "uncertain" and (f.cue.line1, f.cue.line2) == ("NO PI DATA", "CHECK THE STATION") and f.ttl_ms == 2000
    r.wait(2100)
    assert r.cur.mode == "step" and r.cur.step.index == 1
    for _ in range(5):
        r.send("swipe_down")
        r.wait(2100)
    assert r.pb.playbook_state().step_index == 1 and r.pb.playbook_state().verified == []


def test_measured_step_not_met_with_fresh_data():
    r = Rig(measured_card())
    r.confirm()
    r.feed(1000, led=False)
    f = r.send("swipe_down")
    assert f.mode == "uncertain" and (f.cue.line1, f.cue.line2) == ("NOT MET YET", "WAITING FOR CHECK")
    r.wait(2000)
    assert r.cur.mode == "step" and r.cur.step.index == 1


def test_measured_step_advances_on_held_evidence_and_labels_it():
    r = Rig(measured_card(hold=500))
    r.confirm()
    r.feed(300, led=True)  # not held long enough yet
    assert r.cur.step.index == 1
    r.feed(300, led=True)
    v = [x for x in r.frames if x.mode == "verified"]
    assert len(v) == 1 and v[0].cue.line1 == "● CHECK PASSED" and v[0].ttl_ms == 2000
    assert r.pb.playbook_state().step_index == 2 and r.pb.playbook_state().verified == ["s1"]
    labels = {e.label for e in r.pb.events}
    assert "COMMANDED" in labels and "INFERRED" in labels and "MEASURED LIVE" not in labels  # led.* is commanded, never "measured light"
    r.feed(2500, led=True)  # emitted exactly once, then the next step shows
    assert len([x for x in r.frames if x.mode == "verified"]) == 1
    assert r.cur.mode == "step" and r.cur.step.index == 2


def test_hold_resets_when_evidence_flickers():
    r = Rig(measured_card(hold=500))
    r.confirm()
    r.feed(300, led=True)
    r.feed(100, led=False)
    r.feed(300, led=True)
    assert r.cur.step.index == 1  # 300 ms each side of the gap: never 500 ms continuous
    r.feed(300, led=True)
    assert r.pb.playbook_state().step_index == 2


def test_source_labels_follow_the_observation_source():
    for src, want in (("simulated", "SIMULATED"), ("replay", "REPLAY")):
        r = Rig(measured_card(hold=0))
        r.confirm()
        r.feed(200, led=True, source=src)
        assert r.pb.playbook_state().step_index == 2
        assert want in {e.label for e in r.pb.events} and "MEASURED LIVE" not in {e.label for e in r.pb.events}


def test_camera_predicates_use_measured_live():
    r = Rig(make_card(2, measured={0: verify_luma(200)}))
    r.feed(500, luma=118.0)
    assert r.pb.playbook_state().verified == ["s0"]
    assert "MEASURED LIVE" in {e.label for e in r.pb.events}


def test_null_camera_and_frozen_feed_are_never_evidence():
    r = Rig(make_card(2, measured={0: verify_luma(0)}))
    r.feed(1000, camera=False, led=False)  # camera: null
    assert r.pb.playbook_state().verified == []
    r2 = Rig(make_card(2, measured={0: verify_luma(10_000)}))
    r2.feed(3000, luma=118.0, new_frame=True)
    assert r2.pb.playbook_state().verified == []  # hold not reached
    r3 = Rig(make_card(2, measured={0: verify_luma(0)}))
    r3.feed(100, luma=10.0)  # dark first
    r3.feed(2500, luma=10.0, new_frame=False)  # frame_seq stuck for > 2 s
    r3.feed(300, luma=118.0, new_frame=False)  # frozen feed that "recovers": never evidence
    assert r3.pb.playbook_state().verified == []


def test_link_loss_never_produces_an_error_frame_on_manual_or_measured_steps():
    r = Rig(measured_card())
    r.feed(500, led=False)
    r.wait(20_000)  # the Pi goes silent
    assert not [x for x in r.frames if x.mode == "error" or x.stale]
    assert r.cur.mode == "step" and r.cur.step.index == 0
    r.confirm()
    r.wait(20_000)
    assert r.cur.mode == "step" and r.cur.step.index == 1  # measured step keeps its frame
    assert not [x for x in r.frames if x.mode == "error" or x.stale]


def test_stale_data_after_silence_does_not_complete_a_hold():
    r = Rig(measured_card(hold=1000))
    r.confirm()
    r.feed(500, led=True)
    r.wait(5000)  # silence: hold must not carry across it
    r.feed(100, led=True)
    assert r.pb.playbook_state().step_index == 1
    r.feed(1000, led=True)
    assert r.pb.playbook_state().step_index == 2


def test_revisiting_a_verified_step_lets_swipe_pass():
    r = Rig(measured_card(hold=0))
    r.confirm()
    r.feed(300, led=True)
    r.wait(2100)
    assert r.cur.step.index == 2
    f = r.send("swipe_up")
    assert f.step.index == 1 and f.step.confirmed and f.step.check == "measured"
    assert r.send("swipe_down").step.index == 2


# ------------------------------------------------------------------ completion wording
def test_completion_all_measured_is_the_only_bullet():
    r = Rig(make_card(2, measured={0: verify_led(0, "● FIRST OK"), 1: verify_led(0, "● SECOND OK")}))
    r.feed(300, led=True)
    r.feed(6500, led=True)
    assert [x.cue.line1 for x in r.frames if x.mode == "verified"] == ["● FIRST OK", "● SECOND OK", "● PLAYBOOK VERIFIED"]
    r.wait(4100)
    assert r.cur.mode == "quiet"


def test_completion_mixed_wording_never_claims_verified_for_manual():
    r = Rig(make_card(2, measured={1: verify_led(0)}))
    r.confirm()
    r.feed(300, led=True)
    r.wait(2100)
    done = [x for x in r.frames if x.cue and x.cue.line1 == "✓ ALL STEPS DONE"]
    assert len(done) == 1 and done[0].mode == "intervene" and done[0].cue.line2 == "SOME CHECKED, SOME BY YOU" and done[0].ttl_ms == 4000
    assert [x.cue.line1 for x in r.frames if x.mode == "verified"] == ["● CHECK PASSED"]  # only the measured step


def test_last_step_manual_after_measured_has_no_bullet():
    r = Rig(make_card(2, measured={0: verify_led(0)}))
    r.feed(300, led=True)
    r.wait(2100)
    r.confirm()
    f = r.cur
    assert f.mode == "intervene" and f.cue.line1 == "✓ ALL STEPS DONE"


# ------------------------------------------------------------------ hold gestures belong to the voice lane
def test_hold_gestures_are_ignored():
    r = Rig(make_card(2))
    n = len(r.frames)
    assert r.send("hold_start") is None and r.send("hold_end") is None and len(r.frames) == n


# ------------------------------------------------------------------ throttle / overlays
def test_overlay_returns_to_the_step_exactly_after_its_ttl():
    r = Rig(measured_card())
    r.confirm()
    r.wait(1600)
    assert r.send("swipe_down").mode == "uncertain"
    r.wait(1900)
    assert r.cur.mode == "uncertain"
    r.wait(100)
    assert r.cur.mode == "step" and r.cur.step.index == 1
    f = r.pb.ask("where")
    assert r.cur.mode == "ask" and r.cur.ttl_ms == 4000
    r.wait(3900)
    assert r.cur.mode == "ask"
    r.wait(100)
    assert r.cur.mode == "step"
