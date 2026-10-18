"""A corrected product must be identified before any old manual can be shown."""

import pytest

from ghostbuild_core.discovery.attrs import extract, search_query
from .test_discovery_service import env, say  # noqa: F401


def start_micke(rt):
    say(rt, "assemble a white IKEA MICKE desk")
    say(rt, "number one")
    say(rt, "cabinet on the left")
    assert rt.playbook is not None
    rt.ask("show me step 14")


@pytest.mark.parametrize("text", [
    "It's a MALM desk, not MICKE.",
    "Actually I checked the box, it's MALM not MICKE.",
])
def test_different_product_line_drops_old_steps_and_does_not_offer_unrelated_products(env, text):
    rt, discovery, source = env
    start_micke(rt)
    sid = rt.session().id
    result = rt.ask(text)
    state = discovery.state(sid)
    assert result.intent == "goal" and rt.playbook is None
    assert state.selected is None and state.attrs.name_hint == "MALM"
    assert "MICKE" in state.attrs.excluded_names
    assert all(c.record.name == "MALM" for c in state.candidates)
    assert rt.hud.current.step is None
    assert rt.hud.current.image is None or rt.hud.current.image.guide_id == "product_matches"
    assert source.searches == []  # fake source is offline; no invented product/manual


def test_a_negated_different_name_does_not_replace_current_product(env):
    rt, discovery, _ = env
    start_micke(rt)
    sid = rt.session().id
    assert not discovery.names_other_product(sid, "Actually it is MICKE, not MALM")


def test_excluded_product_names_are_not_sent_as_search_keywords():
    attrs = extract("It's a MALM desk, not MICKE", ("MICKE", "MALM"))
    assert attrs.name_hint == "MALM" and attrs.excluded_names == ["MICKE"]
    query = search_query(attrs).lower()
    assert "malm" in query and "micke" not in query
