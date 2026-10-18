from pathlib import Path
import pytest
from PIL import Image
from knowledge.validate import validate_cards
from ghostbuild_core.discovery.source import load_bundle
from integrations.ikea.tools.build_manual import printed_id, cross_check
from integrations.ikea.manual import Word, Band

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "knowledge/products/ikea/80213074"


def test_cards_images_and_mapping():
    assert validate_cards(BASE / "cards", root=ROOT, check_images=True) == []
    b = load_bundle(BASE)
    assert len(b.all_cards()) == 2
    for side in ["left", "right"]:
        card = b.load_card(side)
        assert len(card.steps) == 35
        for i, st in enumerate(card.steps, 1):
            assert (
                st.id == f"s{i:02}"
                and st.guide_id == b.built_from["mapping"][side][str(i)]["guide_id"]
            )
            page = b.built_from["mapping"][side][str(i)]["page"]
            assert st.cites[0].url.endswith(f"#page={page}")
            assert st.verify is None
        assert (
            card.steps[13].parts[0].id == "103430" and card.steps[13].parts[0].qty == 8
        )
    assert b.load_card("left").steps[34].parts[0].qty == 1
    assert b.load_card("right").steps[34].parts[0].qty == 2
    assert b.built_from["mapping"]["left"]["14"]["page"] == 13
    assert b.built_from["mapping"]["right"]["14"]["page"] == 28
    for path in BASE.rglob("*.png"):
        if ".phone." in path.name:
            continue
        with Image.open(path) as im:
            assert im.size == (288, 144)
            assert all(x % 17 == 0 for x in set(im.convert("L").tobytes()))


def test_rotated_part_crosscheck_fails_on_invented_or_remote_digits():
    ws = [
        Word(10, 10, 15, 15, "10"),
        Word(18, 14, 23, 19, "93"),
        Word(26, 18, 31, 23, "38"),
    ]
    assert printed_id("109338", ws)
    assert not printed_id("109339", ws)
    ws[-1].x0 = 300
    assert not printed_id("109338", ws)
    with pytest.raises(ValueError, match="part 999999 not printed"):
        cross_check(
            [{"n": 1, "parts": [{"id": "999999", "qty": 2}]}],
            {1: ws},
            {1: [Band(1, 1, 0, 100)]},
            "left",
        )
