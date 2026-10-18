"""Live research: an unmatched request is researched now (MOCK CREAO), shown as a thinking screen, then started as a task."""

from __future__ import annotations

import time

import pytest

from contracts.models import G2Hello, G2Input, GoalRequest
from knowledge.tests.creao_mocks import MOCK_A_REQUEST

from test_research_runs import MockCreao, gi, world, wait_status  # noqa: F401  (fixtures)


@pytest.fixture
def live(world, monkeypatch):
    monkeypatch.setenv("GB_LIVE_RESEARCH", "1")
    rt = world.rt
    rt.hello(G2Hello(client_id="g2-1", session_id=None))
    rt.clock.advance(2600)
    rt.tick()
    return world


def ask(c, text, via="voice", mode="build"):
    return c.rt.resolve_goal(GoalRequest(session_id=c.rt.session().id, mode=mode, via=via, text=text))


def settle_live(c, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        c.rt.tick()
        if c.rt.live.active is None:
            return
        time.sleep(0.02)
    raise AssertionError("live research did not finish")


def test_flag_off_keeps_the_queued_message_and_never_calls_creao(world):
    rt = world.rt
    rt.hello(G2Hello(client_id="g2-1", session_id=None))
    rt.clock.advance(2600)
    rt.tick()
    res = ask(world, MOCK_A_REQUEST)
    assert res.cue.line2 == "QUEUED FOR RESEARCH" and world.mock.posts == []


def test_unmatched_request_shows_a_thinking_screen_then_starts_the_researched_guide(live):
    c, rt = live, live.rt
    res = ask(c, MOCK_A_REQUEST)
    assert res.status == "unsupported" and res.research_queued and res.cue.line1 == "RESEARCHING"
    assert rt.live.active is not None and rt.live.active["goal"] == MOCK_A_REQUEST
    rt.clock.advance(3000)  # the short acknowledgement flash passes; the thinking screen stays
    rt.tick()
    f = rt.hud.current
    assert f.mode == "intervene" and f.cue.line1.startswith("RESEARCHING ") and "●" in f.cue.line2 + "○"  # elapsed + a progress bar
    settle_live(c)  # the mock run completes; pump() starts the guide
    f = rt.hud.current
    assert rt.session().phase == "task" and f.mode == "intervene" and f.cue.line1.startswith("BUILD: ") and f.cue.line2 == "AI RESEARCHED, UNREVIEWED"
    rt.handle_input(gi("swipe_down"))  # a gesture only reveals step 1
    assert rt.hud.current.mode == "step" and rt.hud.current.step.index == 0
    view = c.get("/research/live").json()
    assert view["unreviewed_cards"] == [rt.playbook.card.card_id] and view["active"] is None and view["last"]["ok"] is True
    assert "not reviewed" in view["note"]
    assert any(p["inputs"]["intent"] == "build" for p in c.mock.posts) and len(c.mock.posts) == 1


def test_swipe_up_stops_waiting_but_the_run_still_leaves_a_draft(live):
    c, rt = live, live.rt
    ask(c, MOCK_A_REQUEST)
    rt.clock.advance(3000)
    rt.tick()
    assert rt.handle_input(gi("swipe_up")).cue.line1 == "WHAT DO YOU NEED?"
    settle_live(c)
    assert rt.session().phase == "menu"  # the wearer had moved on: no surprise task start
    assert any(r["status"] == "draft_ready" for r in c.runs.list())


def test_a_failed_run_says_so_and_returns_to_the_prompt(live):
    c, rt = live, live.rt
    c.mock.fail_status = 401
    ask(c, MOCK_A_REQUEST)
    settle_live(c)
    f = rt.hud.current
    assert f.mode == "uncertain" and f.cue.line1 == "NO GUIDE BUILT"
    rt.clock.advance(6000)
    rt.tick()
    assert rt.hud.current.cue.line1 == "WHAT DO YOU NEED?" and rt.session().phase == "menu"
    assert c.get("/research/live").json()["last"]["ok"] is False


def test_credit_guards_one_at_a_time_two_word_minimum_and_a_cap(live, monkeypatch):
    c, rt = live, live.rt
    notsent = lambda r: r.cue.line1 != "RESEARCHING"  # noqa: E731  (the old queue-only path answers NOT SUPPORTED / TRY ...)
    assert notsent(ask(c, "bicycle")) and c.mock.posts == []  # one word: never sent
    monkeypatch.setenv("GB_LIVE_RESEARCH_MAX", "0")
    assert notsent(ask(c, MOCK_A_REQUEST)) and c.mock.posts == []
    monkeypatch.setenv("GB_LIVE_RESEARCH_MAX", "1")
    assert not notsent(ask(c, MOCK_A_REQUEST))
    assert len(c.mock.posts) == 1
    assert notsent(ask(c, "tighten a loose cabinet hinge")) and len(c.mock.posts) == 1  # one at a time (and over the cap)
    settle_live(c)


def test_phone_typed_request_uses_the_same_path(live):
    c = live
    sid = c.rt.session().id
    r = c.post("/session/goal", json={"v": 2, "session_id": sid, "mode": "build", "via": "phone_text", "text": MOCK_A_REQUEST})
    assert r.status_code == 200 and r.json()["research_queued"] is True and r.json()["cue"]["line1"] == "RESEARCHING"
    settle_live(c)
    assert c.rt.session().phase == "task"


def test_the_same_request_again_needs_no_new_run_in_memory_or_after_a_restart(live):
    c, rt = live, live.rt
    ask(c, MOCK_A_REQUEST)
    settle_live(c)
    assert len(c.mock.posts) == 1 and rt.session().phase == "task"
    # a new wearer session asks for the very same thing: the researched card is already loaded, so it simply starts
    rt.clock.advance(60_000)
    rt.hello(G2Hello(client_id="g2-2", session_id=None))
    rt.clock.advance(2600)
    rt.tick()
    res = ask(c, MOCK_A_REQUEST.upper())
    assert res.status == "supported" and len(c.mock.posts) == 1
    # after a restart the card is gone from memory but the finished draft is on disk: loaded instantly, no credits
    rt.cards = [x for x in rt.cards if x.card_id not in rt.live.cards]
    rt.clock.advance(60_000)
    rt.hello(G2Hello(client_id="g2-3", session_id=None))
    rt.clock.advance(2600)
    rt.tick()
    res = ask(c, MOCK_A_REQUEST)
    assert res.cue.line1 == "RESEARCHING"
    settle_live(c)
    assert len(c.mock.posts) == 1 and rt.session().phase == "task" and rt.live.started == 1


def test_researched_card_gets_a_readable_title(live):
    c, rt = live, live.rt
    ask(c, MOCK_A_REQUEST)
    settle_live(c)
    assert rt.playbook.card.title[:1].isupper()


def test_progress_is_an_honest_estimate_that_never_claims_done():
    from ghostbuild_core.live_research import estimate

    start, mid, late, way_late = estimate(0, 110), estimate(55, 110), estimate(110, 110), estimate(400, 110)
    assert start["fraction"] == 0 and start["estimate"] is True and start["stage"] == 0
    assert 0.5 < mid["fraction"] < 0.8 and late["fraction"] < 0.95 and way_late["fraction"] == 0.95  # never 100% before it finishes
    assert not late["over"] and way_late["over"] and way_late["remaining_s"] == 0
    assert [start["stage"], mid["stage"], way_late["stage"]] == sorted([start["stage"], mid["stage"], way_late["stage"]])


def test_glasses_wait_screen_has_a_bar_and_a_time_left_and_the_phone_view_carries_the_same_estimate(live):
    c, rt = live, live.rt
    ask(c, MOCK_A_REQUEST)
    rt.clock.advance(3000)
    rt.tick()
    f = rt.hud.current
    assert f.cue.line1.startswith("RESEARCHING ") and "●" in f.cue.line2 + "○" and f.cue.line2.count("●") + f.cue.line2.count("○") == 10
    assert "ABOUT" in f.cue.line2 or "ALMOST" in f.cue.line2 or "LONGER" in f.cue.line2
    prog = c.get("/research/live").json()["active"]["progress"]
    assert prog["estimate"] is True and 0 <= prog["fraction"] <= 0.95 and len(prog["stages"]) == 5
    settle_live(c)


def test_the_estimate_learns_from_real_run_durations(live):
    c, rt = live, live.rt
    assert rt.live.expected_s() == 110
    rt.live.durations.extend([60.0, 80.0, 70.0])
    assert rt.live.expected_s() == 70.0


def test_the_wait_screen_rests_after_a_few_seconds_a_gesture_peeks_and_completion_wakes_it(live):
    c, rt = live, live.rt
    ask(c, MOCK_A_REQUEST)
    rt.clock.advance(3000)
    rt.tick()
    assert rt.hud.current.cue.line1.startswith("RESEARCHING ")  # shown at first so the wearer knows it is working
    rt.clock.advance(9000)
    rt.tick()
    assert rt.hud.current.mode == "quiet"  # then it rests: eyes free, the surroundings stay in view
    rt.handle_input(gi("press"))  # a gesture only peeks at the progress
    assert rt.hud.current.cue.line1.startswith("RESEARCHING ") and rt.live.active is not None
    rt.clock.advance(11_000)
    rt.tick()
    assert rt.hud.current.mode == "quiet"
    settle_live(c)  # the guide is ready: that always wakes the display
    assert rt.hud.current.mode == "intervene" and rt.hud.current.cue.line2 == "AI RESEARCHED, UNREVIEWED"
