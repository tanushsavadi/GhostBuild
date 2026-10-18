"""Card import endpoints: schema, read, validate, token-gated webhook that stores drafts the runtime never loads."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from contracts.models import Card
from ghostbuild_core.cards import load_cards
from ghostbuild_core.clock import ManualClock
from ghostbuild_core.runtime import Runtime
from ghostbuild_core.server import create_app

REPO = Path(__file__).resolve().parents[2]
EXAMPLE = REPO / "contracts" / "examples" / "card_camera_lens.json"
SHIPPED = REPO / "knowledge" / "cards" / "camera_lens.json"
TEXT = "If the image is black,   check that the lens   cap is removed."
QUOTE = "check that the lens cap is removed"
TOKEN = "s3cret-token"


def envelope(quote=QUOTE) -> dict:
    card = json.loads(EXAMPLE.read_text())
    card["provenance"] = "WEB TUTORIAL"
    for guide in card["guides"]:
        for view in guide["views"]:
            view["fallback"] = {"line1": "CHECK LENS COVER", "line2": "SEE PICTURE"}
    card["tests"][0]["checks"][0]["cites"] = [{"source": "picam_docs", "loc": "x", "quote": quote}]
    return {
        "run_id": "r1",
        "request": "black camera",
        "card": card,
        "source_texts": {"picam_docs": TEXT},
        "research": {"sources": [], "video_notes": [], "visual_references": [], "uncertainties": []},
    }


@pytest.fixture
def rt(card, asset_root, tmp_path):
    clock = ManualClock()
    r = Runtime([card], clock=clock, log_dir=tmp_path / "logs", asset_root=asset_root)
    r.clock = clock
    return r


@pytest.fixture
def client(rt):
    app = create_app(rt, tick_interval=None, sim_interval=None, web_dir=rt.asset_root / "no-web")
    with TestClient(app) as c:
        yield c


@pytest.fixture
def token(monkeypatch):
    monkeypatch.setenv("GB_AGENT_TOKEN", TOKEN)
    return {"X-GhostBuild-Token": TOKEN}


def drafts(rt) -> list[Path]:
    base = rt.asset_root / "knowledge" / "drafts"
    return sorted(base.iterdir()) if base.exists() else []


# ---------------------------------------------------------------- schema / read
def test_schema_matches_card_model_and_validates_example(client):
    r = client.get("/cards/schema")
    assert r.status_code == 200
    assert r.json() == Card.model_json_schema()
    Card.model_validate(json.loads(EXAMPLE.read_text()))  # the schema describes cards like this one


def test_schema_matches_exported_contract_file(client):
    exported = json.loads((REPO / "contracts" / "schema" / "card.json").read_text())
    assert client.get("/cards/schema").json() == exported


def test_get_card_by_id_and_404(client, card):
    r = client.get(f"/cards/{card.card_id}")
    assert r.status_code == 200
    assert Card.model_validate(r.json()) == card
    assert client.get("/cards/nope").status_code == 404
    assert client.get("/cards/..%2Fsecret").status_code == 404
    assert client.get("/cards/Bad.Id").status_code == 404


def test_schema_route_not_shadowed_by_card_id(client):
    assert "properties" in client.get("/cards/schema").json()


# ---------------------------------------------------------------- validate
def test_validate_accepts_good_envelope(client):
    r = client.post("/cards/validate", json=envelope())
    assert r.status_code == 200 and r.json() == {"ok": True, "errors": []}


def test_validate_rejects_fabricated_quote(client):
    r = client.post("/cards/validate", json=envelope("never said"))
    assert r.status_code == 200
    assert r.json()["ok"] is False and any("not found verbatim" in e for e in r.json()["errors"])


def test_validate_rejects_bad_glyph_and_unknown_signal(client):
    env = envelope()
    env["card"]["tests"][0]["fact"]["line1"] = "LOST!"
    env["card"]["tests"][0]["fail_when"][0]["signal"] = "camera.nope"
    errors = client.post("/cards/validate", json=env).json()["errors"]
    assert any("characters not allowed" in e for e in errors) and any("camera.nope" in e for e in errors)


def test_validate_missing_source_text(client):
    env = envelope()
    env["source_texts"] = {}
    assert not client.post("/cards/validate", json=env).json()["ok"]


def test_validate_non_json_is_422(client):
    assert client.post("/cards/validate", content=b"{nope").status_code == 422


def test_validate_oversize_is_413(client):
    big = json.dumps({"x": "y" * 1_100_000})
    assert client.post("/cards/validate", content=big).status_code == 413


def test_validate_writes_nothing(client, rt):
    client.post("/cards/validate", json=envelope())
    assert drafts(rt) == []


# ---------------------------------------------------------------- webhook
def test_webhook_disabled_without_env(client, rt, monkeypatch):
    monkeypatch.delenv("GB_AGENT_TOKEN", raising=False)
    r = client.post("/agent/webhook", json=envelope(), headers={"X-GhostBuild-Token": "anything"})
    assert r.status_code == 503 and "webhook disabled" in r.text
    assert drafts(rt) == []


def test_webhook_disabled_with_empty_env(client, monkeypatch):
    monkeypatch.setenv("GB_AGENT_TOKEN", "")
    assert client.post("/agent/webhook", json=envelope()).status_code == 503


@pytest.mark.parametrize("header", [None, "", "wrong", TOKEN + "x", TOKEN[:-1]])
def test_webhook_bad_token(client, rt, token, header):
    headers = {} if header is None else {"X-GhostBuild-Token": header}
    assert client.post("/agent/webhook", json=envelope(), headers=headers).status_code == 401
    assert drafts(rt) == []


def test_webhook_non_ascii_token_header_is_401_not_500(client, token):
    r = client.post("/agent/webhook", content=json.dumps(envelope()), headers={"X-GhostBuild-Token": "tökén".encode("utf-8")})
    assert r.status_code == 401


def test_webhook_writes_draft(client, rt, token):
    r = client.post("/agent/webhook", json=envelope(), headers=token)
    assert r.status_code == 200
    draft_id = r.json()["draft_id"]
    assert draft_id.startswith("camera_lens-") and len(draft_id) == len("camera_lens-20261017T210509")
    base = rt.asset_root / "knowledge" / "drafts" / draft_id
    assert json.loads((base / "envelope.json").read_text())["run_id"] == "r1"
    assert Card.model_validate(json.loads((base / "card.json").read_text())).card_id == "camera_lens"


def test_webhook_revalidates(client, rt, token):
    r = client.post("/agent/webhook", json=envelope("fabricated"), headers=token)
    assert r.status_code == 422 and r.json()["ok"] is False
    assert drafts(rt) == []


def test_webhook_oversize_413(client, rt, token):
    big = json.dumps({"x": "y" * 1_100_000})
    assert client.post("/agent/webhook", content=big, headers=token).status_code == 413
    assert drafts(rt) == []


@pytest.mark.parametrize("bad_id", ["../../evil", "a/b", "..", "UPPER", "x y", ""])
def test_webhook_traversal_in_card_id_rejected(client, rt, token, bad_id):
    env = envelope()
    env["card"]["card_id"] = bad_id
    assert client.post("/agent/webhook", json=env, headers=token).status_code == 422
    assert drafts(rt) == []
    assert not (rt.asset_root.parent / "evil").exists()


def test_webhook_token_checked_before_body(client, token):
    assert client.post("/agent/webhook", content=b"{nope", headers={"X-GhostBuild-Token": "bad"}).status_code == 401
    assert client.post("/agent/webhook", content=b"{nope", headers=token).status_code == 422


# ---------------------------------------------------------------- drafts are never loaded
def test_drafts_never_loaded_by_card_loader_or_runtime(client, rt, token, card):
    cards_dir = rt.asset_root / "knowledge" / "cards"
    cards_dir.mkdir(parents=True)
    (cards_dir / "lens.json").write_text(card.model_dump_json())
    client.post("/agent/webhook", json=envelope(), headers=token)
    assert len(drafts(rt)) == 1

    ids = [c.card_id for c in load_cards(cards_dir)]
    assert ids == [card.card_id]
    assert [c.card_id for c in load_cards(rt.asset_root / "knowledge")] == []  # no recursion into drafts/
    assert [c.card_id for c in rt.cards] == [card.card_id]
    assert client.get("/card").json()["card_id"] == card.card_id
    draft_card_id = json.loads(next(drafts(rt)[0].glob("card.json")).read_text())["card_id"]
    assert draft_card_id == "camera_lens"
    # the example draft has a different id than the loaded card; it must still be unknown to the server
    if draft_card_id != card.card_id:
        assert client.get(f"/cards/{draft_card_id}").status_code == 404


def test_shipped_card_not_affected_by_webhook(client, rt, token):
    before = SHIPPED.read_bytes()
    client.post("/agent/webhook", json=envelope(), headers=token)
    assert SHIPPED.read_bytes() == before
