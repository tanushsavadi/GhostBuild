"""Guide Studio API: read-only guide inventory + exact HUD preview frames from a private engine."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from contracts.models import Card
from ghostbuild_core.clock import ManualClock
from ghostbuild_core.runtime import Runtime
from ghostbuild_core.server import create_app
from ghostbuild_core.studio import build_record, preview

REPO = Path(__file__).resolve().parents[2]
BIKE = REPO / "knowledge" / "compiled" / "bike_flat_tire" / "card.json"


def client_for(cards, root, tmp_path):
    rt = Runtime(cards, clock=ManualClock(), log_dir=tmp_path / "logs", asset_root=root)
    app = create_app(rt, tick_interval=None, sim_interval=None, web_dir=root / "no-web")
    return rt, TestClient(app)


@pytest.fixture
def card(card_dict) -> Card:
    """The fixture card as a 2-step playbook whose first step shows the three-view guide."""
    card_dict["steps"] = [
        {"id": "look", "title": "Look at the lens", "cue": {"line1": "CHECK THE LENS", "line2": ""}, "guide_id": card_dict["guides"][0]["id"]},
        {"id": "done", "title": "Done", "kind": "outcome", "cue": {"line1": "ALL DONE", "line2": ""}},
    ]
    return Card.model_validate(card_dict)


@pytest.fixture
def bike() -> Card:
    return Card.model_validate(json.loads(BIKE.read_text()))


def test_guides_lists_loaded_cards_with_provenance(card, asset_root, tmp_path):
    _, c = client_for([card], asset_root, tmp_path)
    with c:
        d = c.get("/studio/guides").json()
    row = next(g for g in d["guides"] if g["card_id"] == card.card_id)
    assert row["steps"] == len(card.steps)
    assert row["pictures"] == sum(len(g.views) for g in card.guides)
    assert row["provenance"] == card.provenance
    assert row["compiled"] is False and row["ai_compiled"] is False
    assert d["active"] == card.card_id and "enabled" in d["live"]


def test_preview_is_exact_hud_frames_and_leaves_live_runtime_alone(card, asset_root, tmp_path):
    rt, c = client_for([card], asset_root, tmp_path)
    with c:
        before = rt.hud.current.model_dump()
        d = c.get(f"/studio/preview/{card.card_id}").json()
        assert rt.hud.current.model_dump() == before
    assert [s["step_id"] for s in d["steps"]] == [s.id for s in card.steps]
    assert "not a capture from the glasses" in d["note"]
    for i, s in enumerate(d["steps"]):
        assert s["frame"]["step"]["index"] == i and s["frame"]["step"]["count"] == len(card.steps)
        assert s["frame"]["source"] == "manual"
    pics = [p for s in d["steps"] for p in s["pictures"]]
    assert pics, "fixture card has a guide with three views"
    assert [p["frame"]["image"]["index"] for p in pics[:3]] == [0, 1, 2]
    assert all(p["frame"]["mode"] == "visual" and p["available"] for p in pics[:3])
    assert pics[0]["g2_url"].startswith("/guides/")


def test_missing_picture_is_reported_not_substituted(card, asset_root, tmp_path):
    (asset_root / "knowledge" / "guides" / "camera_lens" / "how.png").unlink()
    steps = preview(card, asset_root)
    pics = {p["view"]: p for s in steps for p in s["pictures"]}
    assert pics["how"]["available"] is False and pics["where"]["available"] is True


def test_unknown_or_unsafe_ids_are_404(card, asset_root, tmp_path):
    _, c = client_for([card], asset_root, tmp_path)
    with c:
        assert c.get("/studio/preview/nope").status_code == 404
        assert c.get("/studio/preview/..%2Fcards").status_code == 404
        assert c.get("/studio/preview/ABC").status_code == 404
    assert build_record(REPO, "../x") is None


def test_compiled_guide_has_quotes_branches_and_build_record(bike, tmp_path):
    _, c = client_for([bike], REPO, tmp_path)
    with c:
        row = next(g for g in c.get("/studio/guides").json()["guides"] if g["card_id"] == "bike_flat_tire")
        d = c.get("/studio/preview/bike_flat_tire").json()
    assert row["compiled"] is True and row["quoted"] == len(bike.steps)
    assert row["questions"] == sum(1 for s in bike.steps if s.kind == "question")
    assert set(d["build"]) <= {"compile_s", "fetch_s", "images_s", "total_s", "rounds", "errors", "model", "notes", "sources"}
    q = next(i for i, s in enumerate(bike.steps) if s.kind == "question")
    assert d["steps"][q]["frame"]["mode"] == "menu"
    assert d["steps"][q]["frame"]["menu"]["options"]
