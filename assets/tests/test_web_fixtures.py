"""Phone page (web/): fixtures must be valid contract messages and the page must stay offline-capable."""
import json
import re
from pathlib import Path

import pytest

from contracts.models import Card, GoalResolution, State

WEB = Path(__file__).resolve().parents[2] / "web"
FX = WEB / "fixtures"


@pytest.mark.parametrize("p", sorted(FX.glob("state_*.json")), ids=lambda p: p.name)
def test_state_fixtures_valid(p):
    st = State.model_validate_json(p.read_text())
    if st.hud and st.hud.image:
        assert st.hud.image.url.startswith("/guides/")


def test_card_and_goal_fixtures_valid():
    card = Card.model_validate_json((FX / "card_camera_lens.json").read_text())
    assert card.guides and len(card.guides[0].views) == 3
    for p in FX.glob("goal_resolution_*.json"):
        GoalResolution.model_validate_json(p.read_text())


def test_fixture_set_covers_honesty_cases():
    names = {p.stem for p in FX.glob("state_*.json")}
    assert {"state_simulated", "state_pi_down", "state_healthy", "state_visual", "state_fault"} <= names
    assert json.loads((FX / "state_simulated.json").read_text())["source"] == "simulated"


def test_no_external_requests_in_page():
    for f in ("index.html", "dev.html", "style.css", "app.js"):
        txt = (WEB / f).read_text()
        urls = re.findall(r"""(?:src|href)=["']https?://|url\(["']?https?://|@import\s+["']?https?://""", txt)
        assert not urls, (f, urls)
        assert "cdn." not in txt and "googleapis" not in txt
