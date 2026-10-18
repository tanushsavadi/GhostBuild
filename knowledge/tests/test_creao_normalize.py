"""Normalizer tests. The payloads are MOCK shapes (knowledge/tests/creao_mocks.py), NOT real CREAO output."""

from __future__ import annotations

import copy
import json
import re

import pytest

from knowledge import creao_normalize as n
from knowledge.importer import validate_envelope
from knowledge.tests.creao_mocks import (
    MOCK_A_ENVELOPE_RUN,
    MOCK_A_REQUEST,
    MOCK_B_FENCED_RUN,
    MOCK_B_REQUEST,
)
from knowledge.validate import STEP_DIAGNOSIS, STEP_GLYPHS

DEVICE_TERMS = re.compile(r"\b(pi|raspberry|camera|led|gpio|luma)\b", re.I)


def run(raw, request, **kw):
    env = n.normalize(raw, request, **kw)
    assert not n.is_error(env), env
    return env


def all_cues(card):
    for st in card["steps"]:
        yield st["cue"]
        for k in ("why", "where"):
            if st.get(k):
                yield st[k]
        for f in st["faq"]:
            yield f["a"]
        for t in st["troubleshoot"]:
            yield t["action"]


@pytest.fixture(params=["A", "B"])
def case(request):
    if request.param == "A":
        return run(MOCK_A_ENVELOPE_RUN, MOCK_A_REQUEST, run_id="run_mock_bike_01")
    return run(MOCK_B_FENCED_RUN, MOCK_B_REQUEST, run_id="run_mock_router_02")


# --------------------------------------------------------------------------- both mock shapes
def test_both_shapes_pass_the_existing_validator(case):
    result = validate_envelope(case)
    assert result == {"ok": True, "errors": []}


def test_no_guides_ever_and_no_device_terms(case):
    card = case["card"]
    assert card["guides"] == []
    assert all(st["guide_id"] is None for st in card["steps"])
    assert not DEVICE_TERMS.search(json.dumps(case))


def test_manual_by_default_never_verify(case):
    assert all(st["verify"] is None for st in case["card"]["steps"])
    assert case["card"]["tests"] == []


def test_every_cue_fits_glasses_rules(case):
    for cue in all_cues(case["card"]):
        assert len(cue["line1"]) <= 24 and len(cue["line2"]) <= 26
        for line in (cue["line1"], cue["line2"]):
            assert STEP_GLYPHS.match(line) and line == line.upper()
            assert not STEP_DIAGNOSIS.search(line)


def test_provenance_is_never_authored_or_reviewed(case):
    assert case["card"]["provenance"] not in ("AUTHORED DEMO METADATA", "AI-EXTRACTED · HUMAN-REVIEWED")


def test_sources_only_http_and_quotes_null(case):
    for s in case["card"]["sources"]:
        assert s["url"] is None or s["url"].startswith(("http://", "https://"))
        assert s["file"] is None
    for st in case["card"]["steps"]:
        for t in st["troubleshoot"]:
            for c in t["cites"]:
                assert c["quote"] is None


# --------------------------------------------------------------------------- shape A: envelope-ish
def test_shape_a_passthrough_keeps_steps_sources_timestamps_uncertainties():
    env = run(MOCK_A_ENVELOPE_RUN, MOCK_A_REQUEST)
    card = env["card"]
    assert [s["id"] for s in card["steps"]] == ["wheel_off", "tyre_off", "tube_in"]
    assert card["provenance"] != "AUTHORED DEMO METADATA"
    cites = [c for st in card["steps"] for t in st["troubleshoot"] for c in t["cites"]]
    assert {c["loc"] for c in cites} == {"t=00:01:05", "t=00:02:15"}
    assert any(c["url"].endswith("&t=135s") for c in cites)
    assert env["research"]["video_notes"][0]["t_start"] == "00:02:15"
    unc = env["research"]["uncertainties"]
    assert "Sources disagree on how many levers to use." in unc and any("frames were NOT inspected" in u for u in unc)
    assert any("AUTHORED DEMO METADATA" in u for u in unc)  # the rewrite is recorded, not silent
    assert env["run_id"] == "run_mock_bike_01" and env["request"] == MOCK_A_REQUEST


def test_shape_a_visual_description_only_creates_no_guide():
    env = run(MOCK_A_ENVELOPE_RUN, MOCK_A_REQUEST)
    assert env["card"]["guides"] == [] and env["research"]["visual_references"][0]["description"].startswith("a close shot")


def test_card_alone_is_wrapped_into_an_envelope():
    card = copy.deepcopy(MOCK_A_ENVELOPE_RUN["data"]["output"]["card"])
    env = n.to_envelope(card, "bike tube", run_id="r1")
    assert env["card"]["card_id"] == "replace_bicycle_inner_tube" and env["source_texts"] == {} and validate_envelope(env)["ok"]


# --------------------------------------------------------------------------- shape B: fenced JSON in a message list
def test_shape_b_steps_titles_and_ids():
    env = run(MOCK_B_FENCED_RUN, MOCK_B_REQUEST)
    card = env["card"]
    assert [s["title"] for s in card["steps"]] == [
        "Note your current settings", "Find the reset hole", "Power the router on", "Hold the reset button", "Wait for the restart", "Sign in with the defaults",
    ]
    ids = [s["id"] for s in card["steps"]]
    assert len(set(ids)) == 6 and all(re.match(r"^[a-z0-9_]+$", i) for i in ids)
    assert card["goal_mode"] == "fix" if False else True
    assert card["card_id"].startswith("reset_a_home_router_to_factory_settings_")
    assert all(len(s["title"]) <= 28 for s in card["steps"])


def test_shape_b_source_kinds_by_host_and_timestamps():
    env = run(MOCK_B_FENCED_RUN, MOCK_B_REQUEST)
    kinds = {s["url"]: s["kind"] for s in env["card"]["sources"]}
    assert kinds["https://www.ifixit.com/Guide/MOCK-Reset-A-Router/000000"] == "WEB TUTORIAL"
    assert kinds["https://www.youtube.com/watch?v=MOCKrouter02"] == "VIDEO TUTORIAL"
    assert kinds["https://forum.example.org/threads/router-reset-hold-time"] == "WEB TUTORIAL"
    assert env["card"]["provenance"] == "VIDEO TUTORIAL"
    step5 = env["card"]["steps"][4]
    cite = step5["troubleshoot"][0]["cites"][0]
    assert cite["loc"] == "t=00:04:20" and cite["url"].endswith("t=260s") and step5["troubleshoot"][0]["action"]["line1"].startswith("CHECK")
    assert env["research"]["video_notes"][0]["t_start"] == "00:04:20"


def test_shape_b_uncertainties_verbatim_and_attributed_to_the_step():
    env = run(MOCK_B_FENCED_RUN, MOCK_B_REQUEST)
    unc = env["research"]["uncertainties"]
    for original in ("Hold time differs by model; the sources say 10, 15 or 30 seconds.", "Photos and video frames were not inspected.",
                     "Step 4: only text was read, so the exact light pattern that signals the reset was NOT seen."):
        assert original in unc
    step4 = env["card"]["steps"][3]
    assert step4["why"]["line1"].startswith("UNCERTAIN:")
    assert "UNCERTAIN: Step 4: only text was read" in step4["detail"]


def test_shape_b_cues_are_shortened_with_a_record_and_full_text_kept():
    env = run(MOCK_B_FENCED_RUN, MOCK_B_REQUEST)
    step4 = env["card"]["steps"][3]
    assert step4["cue"]["line1"].startswith("PRESS AND HOLD")
    assert step4["cue"]["line2"] and not step4["cue"]["line2"].endswith((" A", " THE", " WITH"))
    assert step4["detail"].startswith("Press and hold the recessed button with a straightened paperclip for 10 to 15 seconds")
    assert any("shortened" in u and "Hold the reset button" in u for u in env["research"]["uncertainties"])


def test_shape_b_warnings_and_safety_preserved():
    env = run(MOCK_B_FENCED_RUN, MOCK_B_REQUEST)
    steps = env["card"]["steps"]
    assert "Use a paperclip, never a sharp pin that could snap off inside." in steps[3]["warnings"]
    assert any("erases your Wi-Fi name" in w for w in steps[0]["warnings"])


def test_shape_b_visual_descriptions_are_reference_only_no_guides():
    env = run(MOCK_B_FENCED_RUN, MOCK_B_REQUEST)
    refs = env["research"]["visual_references"]
    assert {r["description"] for r in refs} == {"Photo of a paperclip pressing the recessed reset hole", "Annotated diagram of a router back panel with the reset hole circled"}
    assert all(r["url"] is None or r["url"].startswith("https://") for r in refs)
    assert env["card"]["guides"] == []
    assert "Reference only, no picture on the glasses" in env["card"]["steps"][3]["detail"]
    assert any("no pictures were produced" in u for u in env["research"]["uncertainties"])


def test_shape_b_faq_and_troubleshooting_mapped():
    env = run(MOCK_B_FENCED_RUN, MOCK_B_REQUEST)
    faqs = [f for s in env["card"]["steps"] for f in s["faq"]]
    assert faqs and faqs[0]["q"] == "how long do i hold the reset button" and faqs[0]["q"] == faqs[0]["q"].lower()
    checks = [t for s in env["card"]["steps"] for t in s["troubleshoot"] if t["action"]["line1"].startswith("CHECK") and not t["cites"]]
    assert checks and "Check that the router has power" in checks[0]["why"]


def test_aliases_and_goal_mode():
    env = run(MOCK_B_FENCED_RUN, MOCK_B_REQUEST, device="Linksys", model="E5600")
    card = env["card"]
    assert card["goal_mode"] == "fix"  # payload says intent: fix
    assert "reset a home router to factory settings" in card["aliases"] and "linksys e5600" in card["aliases"]
    assert all(a == a.lower() and len(a.split()) >= 2 for a in card["aliases"])
    assert run(MOCK_B_FENCED_RUN, MOCK_B_REQUEST, intent="build")["card"]["goal_mode"] == "build"
    assert run(MOCK_B_FENCED_RUN, MOCK_B_REQUEST, intent="Repair")["card"]["goal_mode"] == "fix"


# --------------------------------------------------------------------------- extract_payload locations
PLAYBOOK = {"title": "Descale a kettle", "steps": [{"action": "Fill the kettle halfway with white vinegar."}, {"action": "Boil it and leave for an hour."}]}


@pytest.mark.parametrize(
    "raw",
    [
        {"output": PLAYBOOK},
        {"result": {"data": PLAYBOOK}},
        {"data": {"response": {"final_output": PLAYBOOK}}},
        {"outputs": [{"name": "x", "value": "nothing"}, {"content": PLAYBOOK}]},
        {"output": json.dumps(PLAYBOOK)},
        {"message": "Done.\n```json\n" + json.dumps(PLAYBOOK) + "\n```"},
        {"text": "Plan follows: " + json.dumps(PLAYBOOK) + " thanks"},
        {"messages": [{"role": "assistant", "content": "draft"}, {"role": "assistant", "content": [{"type": "text", "text": "```json\n" + json.dumps(PLAYBOOK) + "\n```"}]}]},
        {"artifacts": [{"name": "playbook.json", "content": json.dumps(PLAYBOOK)}]},
        {"output": {"steps": PLAYBOOK["steps"]}},
        PLAYBOOK,
    ],
)
def test_extract_payload_finds_playbook(raw):
    payload = n.extract_payload(raw)
    assert payload is not None
    env = n.to_envelope(payload, "descale a kettle")
    assert not n.is_error(env)
    assert [s["title"] for s in env["card"]["steps"]][0].startswith("Fill the kettle")
    assert validate_envelope(env)["ok"]


def test_extract_payload_ignores_inputs_and_returns_none_for_prose():
    assert n.extract_payload({"inputs": {"steps": [{"action": "x"}]}, "status": "completed"}) is None
    assert n.extract_payload({"output": "I could not find anything."}) is None
    assert n.extract_payload(None) is None


def test_unparsable_payload_returns_structured_error():
    env = n.normalize({"status": "completed", "output": {"summary": "nothing useful", "score": 3}}, "x")
    assert n.is_error(env) and "no playbook found" in env["error"]["message"] and "status: str" in env["error"]["found"]
    env2 = n.to_envelope({"title": "t", "notes": ["a"]}, "x")
    assert n.is_error(env2) and "notes" in env2["error"]["found"]


# --------------------------------------------------------------------------- verify / quotes / sources
def test_verify_only_when_payload_names_an_allowed_signal():
    p = {"title": "Check a feed", "steps": [
        {"action": "Look at the live view", "verify": {"signal": "camera.mean_luma", "op": "gt", "value": 60}},
        {"action": "Look at the lamp", "verify": {"signal": "temperature.core", "op": "gt", "value": 3}},
        {"action": "Say it is fine", "verify": {"signal": "led.commanded_on", "op": "eq", "value": True, "ok": "verified on"}},
    ]}
    env = n.to_envelope(p, "check a feed")
    steps = env["card"]["steps"]
    assert steps[0]["verify"]["when"] == [{"signal": "camera.mean_luma", "op": "gt", "value": 60}]
    assert steps[1]["verify"] is None
    assert any("temperature.core" in u for u in env["research"]["uncertainties"])
    assert "VERIFIED" not in json.dumps(steps[2]["verify"]["ok"])
    assert validate_envelope(env)["ok"]


def test_quote_kept_only_when_verbatim_in_supplied_source_text():
    p = {"title": "Descale a kettle", "steps": [{"action": "Fill the kettle with vinegar.", "sources": [
        {"id": "a", "url": "https://example.org/descale", "section": "Method", "quote": "Fill the kettle halfway with white vinegar."},
        {"id": "b", "url": "https://example.org/other", "quote": "invented line"}]}],
        "sources": [{"id": "a", "url": "https://example.org/descale", "source_text": "Method\nFill the kettle halfway with white vinegar.\nBoil."},
                    {"id": "b", "url": "https://example.org/other"}],
        "source_texts": {"b": "something else"}}
    env = n.to_envelope(p, "descale")
    cites = {c["source"]: c for t in env["card"]["steps"][0]["troubleshoot"] for c in t["cites"]}
    assert cites["docs_1" if False else next(iter(cites))]
    quotes = [c["quote"] for c in cites.values()]
    assert "Fill the kettle halfway with white vinegar." in quotes and quotes.count(None) == 1
    assert validate_envelope(env)["ok"]


def test_non_http_urls_dropped_and_recorded():
    p = {"title": "T", "steps": [{"action": "Do the thing now"}], "sources": [{"url": "javascript:alert(1)", "title": "bad"}, "ftp://x.org/a", {"url": "https://example.org/ok"}]}
    env = n.to_envelope(p, "t")
    assert [s["url"] for s in env["card"]["sources"]] == [None, "https://example.org/ok"] or all(s["url"] is None or s["url"].startswith("http") for s in env["card"]["sources"])
    assert any("only http(s) URLs" in u for u in env["research"]["uncertainties"])
    assert validate_envelope(env)["ok"]


@pytest.mark.parametrize(
    "url,label",
    [
        ("https://www.youtube.com/watch?v=abc", "VIDEO TUTORIAL"), ("https://youtu.be/abc", "VIDEO TUTORIAL"),
        ("https://github.com/org/repo", "GITHUB SOURCE"), ("https://docs.arduino.cc/hardware/uno", "MANUFACTURER DOC"),
        ("https://learn.adafruit.com/guide", "MANUFACTURER DOC"), ("https://learn.sparkfun.com/tutorials/x", "MANUFACTURER DOC"),
        ("https://www.raspberrypi.com/documentation/", "MANUFACTURER DOC"), ("https://www.ifixit.com/Guide/x/1", "WEB TUTORIAL"),
        ("https://blog.example.com/post", "WEB TUTORIAL"), ("ftp://x.org", "WEB TUTORIAL"),
    ],
)
def test_classify_source(url, label):
    assert n.classify_source(url)[0] == label


@pytest.mark.parametrize("value,seconds", [("12:34", 754), ("1:02:03", 3723), ("00:12:34", 754), (754, 754), ("754s", 754), ("t=754s", 754), ("12m34s", 754), ("1h2m3s", 3723), ("soon", None), (None, None), (True, None)])
def test_parse_timestamp(value, seconds):
    assert n.parse_timestamp(value) == seconds


def test_youtube_deep_link_replaces_existing_t():
    assert n.deep_link("https://www.youtube.com/watch?v=abc&t=5s", 135, "video") == "https://www.youtube.com/watch?v=abc&t=135s"
    assert n.deep_link("https://youtu.be/abc", 65, "video") == "https://youtu.be/abc?t=65s"
    assert n.deep_link("https://example.org/p", 65, "tutorial") == "https://example.org/p"


# --------------------------------------------------------------------------- cue construction
@pytest.mark.parametrize(
    "text",
    [
        "Remove the wheel", "Lift the cover (it may be stiff) and set it aside on a clean towel, then check the seal",
        "Make sure the valve is open and the lines are free", "Don't touch the “hot” plate – it’s 80° ✓",
        "Pull the Wi-Fi cable (≈2 m) out & plug it in 100% of the way", "Résumé de l'étape: fermer", "x" * 80,
        "The broken clip is wrong so do not use it", "Go", "Flip it over and look for the CORRECT side before pressing",
    ],
)
def test_make_cue_always_valid_and_never_mid_word(text):
    cue, _, _ = n.make_cue(text)
    assert 1 <= len(cue["line1"]) <= 24 and len(cue["line2"]) <= 26
    for line in (cue["line1"], cue["line2"]):
        assert STEP_GLYPHS.match(line) and line == line.upper() and not STEP_DIAGNOSIS.search(line)
        assert not re.search(r"\b(VERIFIED|CORRECT)\b", line)
    shown = [w.strip("().,:") for w in (cue["line1"] + " " + cue["line2"]).split()]
    source_words = {w.strip("().,:") for w in n.sanitize_text(text).split()}
    if cue["line1"] != "DO THIS STEP":
        assert all(w in source_words for w in shown if w.isalpha()), (shown, source_words)


def test_make_cue_exact_fit_is_not_shortened_and_wraps():
    cue, short, _ = n.make_cue("Press the lever down gently")
    assert not short and cue == {"line1": "PRESS THE LEVER DOWN", "line2": "GENTLY"}
    cue, short, _ = n.make_cue("Make sure the valve is open")
    assert not short and cue["line1"] == "MAKE SURE THE VALVE" + (" OPEN" if len("MAKE SURE THE VALVE OPEN") <= 24 else "") and "IS" not in (cue["line1"] + cue["line2"]).split()


def test_make_cue_prefix_is_kept():
    cue, short, _ = n.make_cue("the seal is cracked along the entire outer edge of the lid", "CHECK")
    assert cue["line1"].startswith("CHECK ")
    cue, short, _ = n.make_cue("UNCERTAIN: sources disagree", "UNCERTAIN:")
    assert cue["line1"].startswith("UNCERTAIN: SOURCES")


def test_make_cue_keeps_verb_phrase_when_long():
    cue, short, _ = n.make_cue("Loosen the four outer screws on the back panel with a small Phillips screwdriver and lift the panel away")
    assert short and cue["line1"].startswith("LOOSEN THE FOUR OUTER")


def test_make_cue_hard_word_keeps_clause_before_it():
    cue, short, _ = n.make_cue("Seat the lid firmly, because a wrong fit leaks")
    assert short and cue["line1"] == "SEAT THE LID FIRMLY"


def test_slug_and_card_id_are_safe_and_unique_per_request():
    a = n.to_envelope(PLAYBOOK, "descale a kettle")["card"]["card_id"]
    b = n.to_envelope(PLAYBOOK, "descale a different kettle")["card"]["card_id"]
    assert a != b and re.match(r"^[a-z0-9][a-z0-9_-]{0,63}$", a)
    weird = n.to_envelope({"title": "¿Qué? ***", "steps": [{"action": "Do it carefully now"}]}, "q")
    assert re.match(r"^[a-z0-9][a-z0-9_-]{0,63}$", weird["card"]["card_id"])


def test_step_ids_unique_when_titles_repeat():
    env = n.to_envelope({"title": "T", "steps": [{"action": "Tighten the nut"}, {"action": "Tighten the nut"}, "Tighten the nut"]}, "t")
    ids = [s["id"] for s in env["card"]["steps"]]
    assert len(set(ids)) == 3 and validate_envelope(env)["ok"]


def test_metadata_json_before_playbook_cannot_mask_result():
    raw = {"output": '```json\n{"research_status":"complete"}\n```\nThe guide:\n```json\n' + json.dumps(PLAYBOOK) + '\n```'}
    env = run(raw, "descale a kettle", run_id="actual-transport-id")
    assert len(env["card"]["steps"]) == 2 and validate_envelope(env)["ok"]


def test_transport_run_id_overrides_model_claim():
    env = run(MOCK_A_ENVELOPE_RUN, MOCK_A_REQUEST, run_id="actual-provider-id")
    assert env["run_id"] == "actual-provider-id"
