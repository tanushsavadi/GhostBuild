"""Conversation traces A and B with an assistant attached: identity and the official manual come before any guide.

A FakeBrain is attached so a model WOULD be reachable; these traces assert the policy never needs it to pick a product
or a manual (orchestration only; no network, no live model)."""

from ghostbuild_core.assistant.brain import FakeBrain
from ghostbuild_core.assistant.schemas import IntakeReply

from .test_discovery_service import env, phase, say, wait  # noqa: F401  (pytest fixture)


def attach(rt):
    brain = FakeBrain(intake=[IntakeReply(action="start", say="Unbox and lay out every part.", goal="assemble a desk", context_sufficient=True)])
    rt.assistant.attach(brain)
    return brain


def test_b_vague_white_ikea_desk_shows_real_photos_then_configuration_then_the_official_manual(env):
    rt, d, src = env
    brain = attach(rt)
    say(rt, "building a white IKEA desk")
    sid = rt.session().id
    s = d.state(sid)
    assert s.phase in ("choosing", "asking") and s.candidates and rt.playbook is None  # no generic steps for an unidentified product
    assert rt.hud.current.mode == "visual" and rt.hud.current.image.guide_id == "product_matches"  # actual product photos
    assert brain.calls == []  # identification is the adapter's job, not the model's
    task = rt.assistant.tasks[sid]
    assert task.critical_unknowns and task.decisions[-1]["decision"] == "IDENTIFY_PRODUCT"
    say(rt, "It's the MICKE")
    s = d.state(sid)
    assert s.phase == "choosing" and {c.record.name for c in s.candidates} == {"MICKE"} and len(s.candidates) > 1  # two real sizes
    assert rt.playbook is None
    say(rt, "number one")
    assert phase(rt, d) == "configuring" and rt.playbook is None  # the one configuration that changes the manual
    say(rt, "Cabinet on the left")
    assert phase(rt, d) == "ready" and rt.playbook is not None and rt.playbook.index == 0 and not rt.playbook.confirmed
    card = rt.playbook.card
    sel = d.state(sid).selected
    assert sel.article == "80213074" and any(sel.manual_url == x.url for x in card.sources)
    assert "unbox" not in " ".join(st.cue.line1.lower() for st in card.steps[:2])
    assert not task.critical_unknowns and any(f.field == "product" and "80213074" in f.value for f in task.facts)
    assert brain.calls == []


def test_a_exact_article_needs_only_the_configuration(env):
    rt, d, src = env
    brain = attach(rt)
    src.live = True
    say(rt, "assemble IKEA MICKE 802.130.74")
    wait(d, lambda: phase(rt, d) == "confirming")
    say(rt, "yes")
    assert phase(rt, d) == "configuring"  # no colour/size/model interview for a confirmed article
    say(rt, "right")
    assert phase(rt, d) == "ready" and rt.playbook.card.steps and d.state(rt.session().id).config == {"cabinet_side": "right"}
    assert brain.calls == []


def test_a_generic_assistant_start_never_bypasses_identification(env):
    """Even if a model says 'start', a clarified IKEA goal goes through product identification first."""
    rt, d, _ = env
    brain = FakeBrain(intake=[IntakeReply(action="start", say="OK.", goal="assemble my white IKEA desk with a drawer", context_sufficient=True)])
    rt.assistant.attach(brain)
    say(rt, "help me put together some furniture")
    end = __import__("time").time() + 3
    while not brain.calls or rt.assistant.pending:
        rt.tick()
        if __import__("time").time() > end:
            break
    rt.tick()
    s = d.state(rt.session().id)
    assert s.phase in ("choosing", "asking") and s.candidates and rt.playbook is None
