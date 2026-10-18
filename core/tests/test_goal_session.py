import json

import pytest

from contracts.models import Card, G2Hello, G2Input, GoalRequest
from ghostbuild_core import goal
from ghostbuild_core.clock import ManualClock
from ghostbuild_core.runtime import Runtime

from conftest import Feeder, make_card_dict


def gi(g):
    return G2Input(gesture=g, seq_seen=0)


def hello(sid=None, client="g2-b1", surface="g2"):
    return G2Hello(client_id=client, session_id=sid, surface=surface)


@pytest.fixture
def rt(card, asset_root, tmp_path):
    clock = ManualClock()
    r = Runtime([card], clock=clock, log_dir=tmp_path / "logs", asset_root=asset_root)
    r.clock = clock
    return r


def live(rt, ms=1000, **kw):
    f = getattr(rt, "_feeder", None) or Feeder(rt.engine, rt.clock)
    rt._feeder = f
    for _ in range(ms // 100):
        rt.clock.advance(100)
        rt.ingest(f.obs(**kw))
        rt.tick()


def cues(rt):
    return [(f.mode, f.cue.line1 if f.cue else None) for f in rt.hud.frames]


# ------------------------------------------------------------------ resolver
def test_resolver_menu_single_card(card):
    r = goal.resolve(GoalRequest(session_id="s", mode="fix", via="g2_menu", text=None), [card])
    assert r.status == "supported" and r.card_id == "camera_lens"
    assert r.cue.line1 == "FIX: PI CAMERA VIEW" and len(r.cue.line1) <= 24 and len(r.cue.line2) <= 26


def test_resolver_text_alias_and_title(card):
    for t in ("my camera view is black", "check the inspection station", "Camera"):
        r = goal.resolve(GoalRequest(session_id="s", mode="fix", via="phone_text", text=t), [card])
        assert r.status == "supported", t


def test_resolver_unsupported_is_honest(card):
    r = goal.resolve(GoalRequest(session_id="s", mode="fix", via="phone_text", text="my espresso machine leaks"), [card])
    assert r.status == "unsupported" and r.card_id is None and r.task_title is None
    assert r.cue.line1 == "NOT SUPPORTED YET" and r.cue.line2.startswith("TRY: ")
    assert len(r.cue.line2) <= 26
    assert "Pi camera view" in r.detail and r.alternatives == [card.title]
    assert "diagnos" in r.detail.lower() and "guess" in r.detail.lower()


def test_resolver_build_has_no_card_is_unsupported(card):
    r = goal.resolve(GoalRequest(session_id="s", mode="build", via="g2_menu", text=None), [card])
    assert r.status == "unsupported"


def test_resolver_ambiguous_menu(card_dict, card):
    d = make_card_dict()
    d["card_id"], d["title"] = "camera_two", "Second camera"
    other = Card.model_validate(d)
    r = goal.resolve(GoalRequest(session_id="s", mode="fix", via="g2_menu", text=None), [card, other])
    assert r.status == "ambiguous" and len(r.alternatives) == 2


# ------------------------------------------------------------------ session / onboarding
def test_welcome_once_then_menu(rt):
    f = rt.hello(hello())
    assert f.mode == "welcome" and (f.cue.line1, f.cue.line2) == ("GHOSTBUILD", "WHAT DO YOU NEED?") and f.ttl_ms == 2500
    rt.clock.advance(2600)
    rt.tick()
    m = rt.hud.current
    assert m.mode == "menu" and m.menu.prompt == "WHAT DO YOU NEED?" and m.menu.selected == 0 and "PI CAMERA VIEW" in m.menu.options
    assert [x for x in cues(rt) if x[0] == "welcome"] == [("welcome", "GHOSTBUILD")]


def test_menu_navigation_clamped_and_fix_selects_card(rt):
    rt.hello(hello())
    rt.clock.advance(2600)
    rt.tick()
    live(rt, 100)
    assert rt.handle_input(gi("swipe_up")).menu.selected == 0  # clamped
    assert rt.handle_input(gi("swipe_down")).menu.selected == 1
    assert rt.handle_input(gi("swipe_down")).menu.selected == 1  # clamped
    assert rt.handle_input(gi("swipe_up")).menu.selected == 0
    f = rt.handle_input(gi("press"))
    assert f.mode == "intervene" and f.cue.line1 == "FIX: PI CAMERA VIEW" and f.ttl_ms == 2500
    s = rt.session()
    assert (s.phase, s.goal, s.card_id) == ("task", "fix", "camera_lens")
    assert rt.state().session.card_id == "camera_lens"
    live(rt, 2600)
    assert rt.hud.current.mode == "quiet"  # healthy => blank


def test_menu_build_unsupported_returns_to_menu(rt):
    rt.hello(hello())
    rt.clock.advance(2600)
    rt.tick()
    rt.handle_input(gi("swipe_down"))  # the second row is the phone: nothing is started
    f = rt.handle_input(gi("press"))
    assert f.mode == "uncertain" and f.cue.line1 == "USE THE PHONE"
    assert rt.session().phase == "menu"
    rt.clock.advance(2600)
    rt.tick()
    assert rt.hud.current.mode == "menu"


def test_reconnect_with_known_id_never_rewelcomes(rt):
    rt.hello(hello())
    sid = rt.session().id
    rt.clock.advance(2600)
    rt.tick()
    n = len(rt.hud.frames)
    f = rt.hello(hello(sid))
    assert f.mode == "menu" and len(rt.hud.frames) == n  # current frame, no welcome, no new frame
    rt.handle_input(gi("press"))
    live(rt, 3000)
    f = rt.hello(hello(sid))
    assert f.mode == "quiet"
    assert sum(1 for x in rt.hud.frames if x.mode == "welcome") == 1


def test_frames_carry_session_id_so_plugin_can_resume(rt):
    first = rt.hello(hello())
    assert first.session_id == rt.session().id != "none"
    rt.clock.advance(2600)
    rt.tick()
    assert rt.hud.current.session_id == first.session_id
    assert rt.hello(hello(first.session_id)).session_id == first.session_id


def test_unknown_id_creates_new_session_with_welcome(rt):
    rt.hello(hello())
    first = rt.session().id
    rt.clock.advance(20_000)
    rt.tick()
    f = rt.hello(hello("s-unknown", client="g2-b2"))
    assert f.mode == "welcome" and rt.session().id not in (first, "s-unknown")


def test_second_surface_joins_fresh_session_without_second_welcome(rt):
    rt.hello(hello(client="g2-b1"))
    sid = rt.session().id
    rt.clock.advance(500)
    rt.hello(hello(client="sim-1", surface="simulator"))
    assert rt.session().id == sid
    assert sum(1 for x in rt.hud.frames if x.mode == "welcome") == 1


def test_any_gesture_in_welcome_skips_it_to_the_menu(rt):
    rt.hello(hello())
    assert rt.hud.current.mode == "welcome"
    rt.handle_input(gi("press"))
    assert rt.session().phase == "menu" and rt.hud.current.mode == "menu"  # nobody waits for a banner; nothing was chosen
    assert rt.session().card_id is None


def test_restart_persistence(card, asset_root, tmp_path):
    logs = tmp_path / "logs"
    c1 = ManualClock()
    r1 = Runtime([card], clock=c1, log_dir=logs, asset_root=asset_root)
    r1.hello(hello())
    sid = r1.session().id
    c1.advance(2600)
    r1.tick()
    r1.handle_input(gi("press"))
    r1.close()
    assert json.loads((logs / "sessions.json").read_text())["active"] == sid

    c2 = ManualClock()
    r2 = Runtime([card], clock=c2, log_dir=logs, asset_root=asset_root)
    assert r2.session().id == sid and r2.session().phase == "task"
    f = r2.hello(hello(sid))
    assert f.mode != "welcome"
    assert r2.engine.card.card_id == "camera_lens"
    assert [x for x in r2.hud.frames if x.mode == "welcome"] == []


def test_restart_during_menu_resumes_menu(card, asset_root, tmp_path):
    c1 = ManualClock()
    r1 = Runtime([card], clock=c1, log_dir=tmp_path, asset_root=asset_root)
    r1.hello(hello())
    sid = r1.session().id
    r1.close()
    r2 = Runtime([card], clock=ManualClock(), log_dir=tmp_path, asset_root=asset_root)
    f = r2.hello(hello(sid))
    assert f.mode == "menu"


def test_phone_goal_unsupported_and_supported(rt):
    rt.hello(hello())
    sid = rt.session().id
    r = rt.resolve_goal(GoalRequest(session_id=sid, mode="fix", via="phone_text", text="fix my toaster"))
    assert r.status == "unsupported" and rt.session().phase != "task"
    r = rt.resolve_goal(GoalRequest(session_id=sid, mode="fix", via="phone_text", text="my camera view is black"))
    assert r.status == "supported" and rt.session().phase == "task"
    assert rt.resolve_goal(GoalRequest(session_id="nope", mode="fix", via="phone_text", text="x")) is None


def test_task_engine_runs_after_start_and_fault_cue_returns(rt):
    rt.hello(hello())
    rt.clock.advance(2600)
    rt.tick()
    rt.handle_input(gi("press"))
    f = Feeder(rt.engine, rt.clock)
    for _ in range(40):
        rt.clock.advance(100)
        rt.ingest(f.obs(luma=6.0, std=1.0))
        rt.tick()
    assert rt.hud.current.mode == "intervene" and rt.hud.current.cue.line1 == "CAMERA VIEW LOST"
    assert rt.state().engine == "FAULT"
    # press in task phase goes to the engine (opens help), not the menu
    assert rt.handle_input(gi("press")).mode == "visual"


def test_input_dismisses_task_start_flash_and_reaches_engine(rt):
    rt.hello(hello())
    rt.clock.advance(2600)
    rt.tick()
    rt.handle_input(gi("press"))
    assert rt.hud.current.cue.line1.startswith("FIX:")
    rt.handle_input(gi("press"))  # engine press, healthy w/o data => nothing; the flash is dismissed
    assert rt.hud.current.mode == "quiet"


def test_state_events_endpoint_shape(rt):
    f = Feeder(rt.engine, rt.clock)
    for _ in range(40):
        rt.clock.advance(100)
        rt.ingest(f.obs(luma=6.0, std=1.0))
    st = rt.state()
    assert 1 <= len(st.events) <= 50 and {e.label for e in st.events} >= {"MEASURED LIVE", "INFERRED"}
