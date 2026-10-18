"""Reuse completed work without crossing identity, step, profile or evidence boundaries."""

import time

import pytest
from ghostbuild_core.assistant.brain import FakeBrain
from ghostbuild_core.assistant.schemas import Profile, StepReply
from ghostbuild_core.cache import AppCache, goal_key
from ghostbuild_core.clock import ManualClock
from ghostbuild_core.runtime import Runtime
from pbhelpers import make_card

from contracts.models import G2Hello, GoalRequest


def card():
    c = make_card(
        3,
        card_id="panel",
        title="Assemble a wooden panel",
        goal_mode="build",
        aliases=["wooden panel"],
    ).model_dump(mode="json")
    c["steps"][0]["title"] = "Fit the cam locks"
    c["steps"][0]["detail"] = (
        "The cam lock engages the cam bolt. Turn it a quarter turn to secure the panels."
    )
    return type(make_card()).model_validate(c)


@pytest.fixture(autouse=True)
def providers_off(monkeypatch):
    monkeypatch.setenv("GB_ASSISTANT", "0")
    monkeypatch.setenv("GB_LIVE_RESEARCH", "0")


def boot(tmp_path, brain=None):
    rt = Runtime(
        [card()],
        asset_root=tmp_path,
        log_dir=tmp_path / "logs",
        clock=ManualClock(),
        brain=brain,
    )
    rt.hello(G2Hello(client_id="cache-test"))
    rt.clock.advance(2600)
    rt.tick()
    return rt


def request(rt, text):
    return rt.resolve_goal(
        GoalRequest(
            session_id=rt.session().id, mode="build", via="phone_text", text=text
        )
    )


def start(rt):
    rt.sessions.start_card(rt.session().id, rt.cards[0], echo=False)


def settle(rt):
    deadline = time.monotonic() + 2
    while rt.assistant.pending and time.monotonic() < deadline:
        rt.tick()
        time.sleep(0.005)
    assert not rt.assistant.pending


def reply():
    return StepReply(
        answer="The cam lock engages the cam bolt and secures the panels.",
        grounding="guide",
        cue1="CAM LOCK ENGAGES BOLT",
        cue2="TURN A QUARTER TURN",
    )


def test_courtesy_order_and_number_word_variants_keep_identity():
    assert goal_key(
        "Can you help me assemble model 80213074 with two drawers please", "build"
    ) == goal_key("assemble model 80213074 with 2 drawers", "build")
    assert goal_key("Assemble 80213074 cabinet left", "build") != goal_key(
        "Assemble 90214308 cabinet left", "build"
    )
    assert goal_key("Assemble 80213074 cabinet left", "build") != goal_key(
        "Assemble 80213074 cabinet right", "build"
    )
    assert goal_key("frame with 2 panels", "build") != goal_key(
        "frame with 3 panels", "build"
    )
    assert goal_key("frame without glue", "build") != goal_key(
        "frame with glue", "build"
    )
    assert goal_key("frame", "build") != goal_key("frame", "fix")


def test_goal_cache_keeps_quantities_and_negation_with_their_objects():
    assert goal_key("2 drawers 3 shelves", "build") != goal_key(
        "3 drawers 2 shelves", "build"
    )
    assert goal_key("desk without drawer with cabinet", "build") != goal_key(
        "desk with drawer without cabinet", "build"
    )


def test_persistence_expiry_and_invalid_file_fallback(tmp_path):
    now = [100.0]
    path = tmp_path / "cache.json"
    c = AppCache(path, now=lambda: now[0])
    c.put("answers", "key", {"answer": "a"}, ttl=5)
    other = AppCache(path, now=lambda: now[0])
    assert other.get("answers", "key") == {"answer": "a"}
    now[0] = 106
    assert other.get("answers", "key") is None
    path.write_text("{bad-json")
    assert AppCache(path).get("answers", "key") is None
    path.write_text('[{"invalid": true}]')
    assert AppCache(path).get("answers", "key") is None
    path.write_text('{"v":1,"answers":{"key":{"expires":"bad","value":"bad"}}}')
    assert AppCache(path).get("answers", "key") is None
    c = AppCache(path, enabled=False)
    c.put("answers", "key", "a")
    assert c.get("answers", "key") is None


def test_general_guide_reuse_skips_brain_across_sessions_and_restart(tmp_path):
    rt = boot(tmp_path)
    result = request(rt, "Help me assemble a wooden panel")
    assert result.status == "supported"
    brain = FakeBrain()
    rt.assistant.attach(brain)
    result = request(rt, "Please assemble the wooden panel")
    assert (
        result.status == "supported"
        and result.cue.line1 == "SAVED GUIDE READY"
        and not brain.calls
    )
    rt.close()
    restored = boot(tmp_path, FakeBrain())
    try:
        result = request(restored, "Can you help me assemble the wooden panel please")
        assert (
            result.cue.line1 == "SAVED GUIDE READY"
            and not restored.assistant.brain.calls
        )
        assert restored.live.started == 0
    finally:
        restored.close()


def test_saved_research_survives_restart_with_providers_off(tmp_path):
    rt = boot(tmp_path)
    saved = card().model_copy(
        update={"card_id": "researched_panel", "title": "Saved panel guide"}
    )
    rt.cache.remember_guide(
        "Build an oak panel model 77",
        "build",
        saved,
        {
            "run_id": "saved-run",
            "draft_id": "saved-draft",
            "goal": "Build an oak panel model 77",
        },
    )
    rt.close()
    restored = boot(tmp_path)
    try:
        result = request(restored, "Please build the oak panel model 77")
        assert (
            result.status == "supported"
            and restored.active_card.card_id == "researched_panel"
        )
        assert "not human-reviewed" in result.detail and restored.live.started == 0
        assert restored.cache.guide("oak panel model 78", "build") is None
    finally:
        restored.close()


def test_grounded_answer_reused_without_thinking_and_persists(tmp_path):
    brain = FakeBrain(step=[reply()])
    rt = boot(tmp_path, brain)
    start(rt)
    text = "What does a cam lock engage with?"
    first = rt.ask(text)
    assert first.pending
    settle(rt)
    second = rt.ask("Please, what does the cam lock engage with?")
    assert second.cached and not second.pending and len(brain.calls) == 1
    assert rt.playbook.index == 0 and not rt.playbook.confirmed
    sid = rt.session().id
    rt.close()
    restored = Runtime(
        [card()],
        asset_root=tmp_path,
        log_dir=tmp_path / "logs",
        clock=ManualClock(),
        brain=None,
    )
    try:
        restored.hello(G2Hello(client_id="return", session_id=sid))
        result = restored.ask(text)
        assert result.cached and restored.playbook.index == 0
        assert any(m["cached"] for m in restored.assistant.state()["messages"])
    finally:
        restored.close()


def test_answer_cache_invalidates_changed_profile_source_or_step(tmp_path):
    brain = FakeBrain(step=[reply(), reply(), reply()])
    rt = boot(tmp_path, brain)
    start(rt)
    text = "What does a cam lock engage with?"
    rt.ask(text)
    settle(rt)
    rt.assistant.profiles[rt.session().id] = Profile(experience="first_time")
    assert rt.ask(text).pending
    settle(rt)
    rt.playbook.card.steps[0].detail += " Source correction."
    assert rt.ask(text).pending
    settle(rt)
    rt.ask("next")
    assert rt.assistant._cached_reply(text, rt.playbook) is None
    assert len(brain.calls) == 3
    rt.close()


def test_general_answers_and_followups_are_not_saved_as_guide_facts(tmp_path):
    general = reply().model_copy(update={"grounding": "general"})
    brain = FakeBrain(step=[general, general])
    rt = boot(tmp_path, brain)
    start(rt)
    text = "What does a cam lock engage with?"
    rt.ask(text)
    settle(rt)
    assert rt.ask(text).pending
    settle(rt)
    assert len(brain.calls) == 2 and rt.cache.status()["entries"]["answers"] == 0
    assert rt.assistant._answer_key("Can I use that instead?", rt.playbook) is None
    rt.close()


def test_late_answer_remains_on_its_original_step(tmp_path):
    brain = FakeBrain(step=[reply()], delay_s=0.08)
    rt = boot(tmp_path, brain)
    start(rt)
    text = "What does a cam lock engage with?"
    rt.ask(text)
    assert rt.hud.current.cue.line1 == "THINKING"
    rt.ask("next")
    assert rt.playbook.index == 1
    settle(rt)
    assert rt.hud.current.mode == "step" and rt.hud.current.step.index == 1
    answer = [m for m in rt.assistant.state()["messages"] if m["role"] == "assistant"][
        -1
    ]
    assert (
        answer["step_id"] == "s0"
        and rt.assistant.state()["current_step"]["step_id"] == "s1"
    )
    rt.ask("back")
    assert rt.playbook.index == 0 and rt.playbook.confirmed == ["s0"]
    rt.close()


def test_return_to_step_dismisses_overlay_without_advancing(tmp_path):
    brain = FakeBrain(step=[reply()], delay_s=0.08)
    rt = boot(tmp_path, brain)
    start(rt)
    rt.ask("What does a cam lock engage with?")
    assert rt.assistant.dismiss(rt.session().id, "panel", "s0")
    assert rt.hud.current.mode == "step"
    settle(rt)
    assert (
        rt.hud.current.mode == "step"
        and rt.playbook.index == 0
        and not rt.playbook.confirmed
    )
    assert not rt.assistant.dismiss(rt.session().id, "panel", "s1")
    rt.close()
