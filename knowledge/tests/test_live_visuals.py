"""The research agent's diagram becomes a G2 picture (<=288x144, 16 greys) plus a phone picture. Offline; no network."""

from __future__ import annotations

import io

import httpx
from PIL import Image

from knowledge import live_visuals
from knowledge.creao import CreaoClient

SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 600"><rect width="880" height="600" fill="#fff"/>'
       '<circle cx="300" cy="300" r="80" fill="none" stroke="#000" stroke-width="6"/><text x="40" y="60" font-size="30">demo</text></svg>')


def test_svg_renders_and_builds_a_valid_g2_and_phone_picture(tmp_path):
    guide = live_visuals.build_live_guide(tmp_path, "run-abc-123", SVG, "MANUFACTURER DOC")
    assert guide is not None and guide["id"].startswith("live_") and [v["view"] for v in guide["views"]] == ["correct"]
    v = guide["views"][0]
    assert v["image"].startswith("knowledge/live/guides/") and "diagram" in v["depicts"].lower() and "not a photo" in v["depicts"].lower()
    g2 = Image.open(tmp_path / v["image"])
    assert g2.width <= 288 and g2.height <= 144 and g2.mode == "L" and all(px % 17 == 0 for px in set(g2.getdata()))
    assert (tmp_path / v["phone_image"]).is_file()
    assert not (tmp_path / "assets").exists()  # never written into the committed asset pipeline


def test_bad_svg_returns_none_and_never_raises(tmp_path):
    assert live_visuals.build_live_guide(tmp_path, "r", "<svg", "MANUFACTURER DOC") is None


def test_which_steps_get_the_picture():
    card = [{"title": "Gather parts", "detail": ""}, {"title": "Wire the LED", "detail": ""}, {"title": "Test", "detail": ""}]
    mentioned = [{"visuals": {}}, {"visuals": {"WHERE": {"source": "generated schematic files/x.svg"}}}, {"visuals": {}}]
    assert live_visuals.step_indexes_for_diagram(mentioned, card) == [1]
    assert live_visuals.step_indexes_for_diagram([], card) == [1]  # no per-step hint: the first step that wires/places something
    assert live_visuals.step_indexes_for_diagram([], [{"title": "Rest", "detail": ""}]) == [0]


def test_client_keeps_the_svg_text_for_svg_artifacts_only():
    art = {"result": {"artifacts": [
        {"id": "a", "title": "diagram.svg", "type": "image/png", "url": "https://agent.creao.ai/x"},
        {"id": "b", "title": "evil.svg", "type": "image/png", "url": "https://evil.example/x"}]}}

    def handler(req: httpx.Request):
        return httpx.Response(200, text=SVG)

    c = CreaoClient(api_key="capi_TESTKEY1234567890", transport=httpx.MockTransport(handler), sleep=lambda s: None)
    out = c.attach_json_artifacts(art)
    assert out["result"]["artifacts"][0]["svg_text"].startswith("<svg") and "svg_text" not in out["result"]["artifacts"][1]
    assert "download_error" in out["result"]["artifacts"][1]  # other hosts are refused
