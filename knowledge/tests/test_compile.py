"""Source-to-action compiler: parsing, verbatim-quote and route validation, picture-strategy helpers, cached demo cards."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from contracts.models import Card
from knowledge.compile import GraphWire, StepWire, compile_graph, menu_path, path_diagram, validate_graph
from knowledge.sources import Block, SourceDoc, parse_html, quote_in, source_kind

ROOT = Path(__file__).resolve().parents[2]
HTML = """<html><head><title>Fix a thing | Maker</title><script>var x=1</script></head><body><nav><a>Home</a></nav>
<h1>Fix a thing</h1><p>Turn the power off before you open the cover.</p><img src="/img/cover.jpg" alt="The cover screws">
<ol><li>Remove the four cover screws with a Phillips screwdriver.</li><li>Lift the cover straight up.</li></ol>
<p>If the light still blinks, contact support.</p><img src="/logo.svg"><footer>Shop</footer></body></html>"""


def doc() -> SourceDoc:
    return parse_html("https://support.apple.com/x", HTML)


def step(id, quote, **kw):
    base = dict(id=id, kind="action", title=id, line1="DO IT", line2="", detail="", expected="", tools=[], risk="low", warnings=[],
                choices=[], next="", source=0, quote=quote, image=-1, expected_image=-1)
    base.update(kw)
    return StepWire(**base)


def test_parse_keeps_content_blocks_and_page_pictures_only():
    d = doc()
    texts = [b.text for b in d.blocks]
    assert "Turn the power off before you open the cover." in texts and not any("var x" in t or t == "Home" or t == "Shop" for t in texts)
    assert [i.src for i in d.images] == ["https://support.apple.com/img/cover.jpg"] and d.images[0].alt == "The cover screws"
    assert d.kind == "MANUFACTURER DOC" and source_kind("https://www.parktool.com/a") == "WEB TUTORIAL"


def test_quotes_must_be_verbatim_after_normalisation():
    d = doc()
    assert quote_in("Remove the four cover screws with a Phillips screwdriver", d)
    assert quote_in("remove   the four COVER screws", d)
    assert not quote_in("Remove the six cover screws", d) and not quote_in("cover", d)  # changed number / too short


def test_validator_rejects_invented_quotes_bad_routes_and_long_glasses_text():
    d = doc()
    g = GraphWire(title="Fix", task_kind="repair", goal_mode="fix", aliases=[], uncovered=[], steps=[
        step("off", "Turn the power off before you open the cover"),
        step("q", "If the light still blinks, contact support", kind="question", choices=[
            {"id": "a", "label": "BLINKS", "say": [], "next": "nowhere", "records": ""}]),
        step("open", "Unscrew the six bolts", line1="THIS CUE IS FAR TOO LONG FOR GLASSES"),
    ])
    errs = " | ".join(validate_graph(g, [d]))
    assert "route to unknown step 'nowhere'" in errs and "2-4 choices" in errs and "not verbatim" in errs and "too long" in errs


class FakeClient:
    """Stands in for the model: first a guide with one invented quote, then the repaired guide."""

    def __init__(self, replies):
        self.replies, self.calls = list(replies), []
        self.messages = self

    def parse(self, **kw):
        self.calls.append(kw)
        from types import SimpleNamespace

        return SimpleNamespace(stop_reason="end_turn", parsed_output=self.replies.pop(0), usage=SimpleNamespace(output_tokens=10))


def test_one_repair_round_then_honest_failure():
    d = doc()
    good = [step("off", "Turn the power off before you open the cover"), step("unscrew", "Remove the four cover screws"),
            step("lift", "Lift the cover straight up", kind="outcome")]
    bad = good[:1] + [step("unscrew", "Remove the six cover screws")] + good[2:]
    mk = lambda steps: GraphWire(title="Fix", task_kind="repair", goal_mode="fix", aliases=["fix a thing"], uncovered=[], steps=steps)
    client = FakeClient([mk(bad), mk(good)])
    g, stats = compile_graph("fix a thing", [d], client=client)
    assert stats["rounds"] == 2 and not stats["errors"] and "Remove the six cover screws" in client.calls[1]["messages"][0]["content"]
    # still wrong after the repair, and dropping the step would leave too little: the guide is refused, never kept
    with pytest.raises(ValueError, match="not verbatim"):
        compile_graph("fix a thing", [d], client=FakeClient([mk(bad), mk(bad)]))
    # with enough verified steps left, an unverifiable step that nothing routes to is dropped
    more = good + [step("done", "If the light still blinks, contact support", kind="stop")]
    g, stats = compile_graph("fix a thing", [d], client=FakeClient([mk(bad + more[3:]), mk(bad + more[3:])]))
    assert stats["dropped_unverified_steps"] == ["unscrew"] and [s.id for s in g.steps] == ["off", "lift", "done"]


def test_menu_path_and_its_drawing():
    assert menu_path("On your Mac, choose Apple menu > System Settings, then click Accessibility in the sidebar.") == ["Apple menu", "System Settings", "Accessibility"]
    assert menu_path("Push one bead of tire toward rim center.") == []
    png = path_diagram(["Apple menu", "System Settings", "Displays"])
    from PIL import Image
    import io

    im = Image.open(io.BytesIO(png))
    assert im.mode == "L" and im.getpixel((2, 2)) == 0  # black background: transparent on the glasses


@pytest.mark.parametrize("cid", ["mac_display_colors", "bike_flat_tire", "prusa_mk4_not_extruding"])
def test_cached_demo_cards_are_valid_cited_and_every_step_is_reachable(cid):
    path = ROOT / "knowledge" / "compiled" / cid / "card.json"
    if not path.is_file():
        pytest.skip("compiled demo not present in this checkout")
    card = Card.model_validate(json.loads(path.read_text()))
    assert card.task_kind and card.review and "not human-reviewed" in card.review
    assert all(st.cites and st.cites[0].quote and st.cites[0].url for st in card.steps)
    assert card.steps[0].kind == "question"  # every demo opens with the one question that changes the path
    ids = [s.id for s in card.steps]
    seen, todo = set(), [0]
    while todo:
        i = todo.pop()
        if i in seen:
            continue
        seen.add(i)
        st = card.steps[i]
        nxt = [c.next for c in st.choices] + ([st.next] if st.next else [])
        if st.kind == "action" and not st.next and i + 1 < len(ids):
            nxt.append(ids[i + 1])
        todo += [ids.index(n) for n in nxt]
    assert len(seen) == len(ids), f"unreachable: {set(ids) - {ids[i] for i in seen}}"
    assert any(st.kind in ("outcome", "stop") for st in card.steps)
