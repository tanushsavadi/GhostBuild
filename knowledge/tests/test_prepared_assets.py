"""Prepared cards must survive a clean clone without an operator's ignored image cache."""

from pathlib import Path

from fastapi.testclient import TestClient

from contracts.models import Card
from ghostbuild_core.clock import ManualClock
from ghostbuild_core.runtime import Runtime
from ghostbuild_core.server import create_app

ROOT = Path(__file__).resolve().parents[2]


def prepared_cards():
    return [Card.model_validate_json(path.read_text())
            for path in sorted((ROOT / "knowledge/compiled").glob("*/card.json"))]


def test_prepared_views_bundle_originals_and_keep_external_caches_optional():
    """A local cached file must not hide a missing release asset or a false fallback promise."""
    views = [view for card in prepared_cards() for guide in card.guides for view in guide.views]
    assert views
    for view in views:
        path = Path(view.image)
        assert not path.is_absolute() and ".." not in path.parts
        if path.is_relative_to("knowledge/live"):
            # Third-party source images may be absent; do not redistribute them to make tests green.
            assert view.provenance not in ("DETERMINISTIC", "AUTHORED DEMO METADATA", "AUTHORED PROJECT SPEC")
            assert view.reference_url and view.reference_url.startswith("https://")
            assert "SOURCE LINK" in view.fallback.line2
            assert "PICTURE ON" not in view.fallback.line2
        else:
            assert path.is_relative_to("knowledge/guides")
            assert (ROOT / path).is_file(), f"prepared image absent from release: {path}"
            assert view.phone_image and (ROOT / view.phone_image).is_file()


def test_prepared_original_images_are_served_without_a_live_cache(tmp_path, monkeypatch):
    """Exercise the public URLs used by the phone and glasses against the checkout's bundled assets."""
    monkeypatch.setenv("GB_ASSISTANT", "0")
    monkeypatch.setenv("GB_CREAO", "0")
    monkeypatch.setenv("GB_LIVE_RESEARCH", "0")
    cards = prepared_cards()
    runtime = Runtime(cards, clock=ManualClock(), asset_root=ROOT, log_dir=tmp_path)
    app = create_app(runtime, tick_interval=None, sim_interval=None)
    with TestClient(app) as client:
        checked = 0
        for card in cards:
            for guide in card.guides:
                for view in guide.views:
                    if Path(view.image).is_relative_to("knowledge/live"):
                        continue
                    for suffix in ("png", "phone.png"):
                        response = client.get(f"/guides/{guide.id}/{view.view}.{suffix}")
                        assert response.status_code == 200, response.text
                        assert response.headers["content-type"] == "image/png"
                        assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
                        checked += 1
        assert checked, "no original prepared reference images were tested"
