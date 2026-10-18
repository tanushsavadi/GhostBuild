"""Playbook (Card.steps) validation: the shipped playbooks pass, deliberately broken copies fail with a readable reason."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from contracts.models import Card
from knowledge.approve import main as approve_main
from knowledge.importer import main as importer_main
from knowledge.importer import validate_envelope
from knowledge.validate import ALLOWED_VERIFY_SIGNALS, DEFAULT_CARDS_DIR, REPO_ROOT, validate_cards

PAPER = DEFAULT_CARDS_DIR / "paper_cup.json"
PI = DEFAULT_CARDS_DIR / "pi_camera_setup.json"
LED = DEFAULT_CARDS_DIR / "led_breadboard.json"
FIXTURE = REPO_ROOT / "knowledge" / "fixtures" / "envelope_paper_cup.json"
PLAYBOOKS = [PAPER, PI, LED]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def errors_for(tmp_path: Path, data: dict, name: str | None = None) -> list[str]:
    cards = tmp_path / "cards"
    cards.mkdir(exist_ok=True)
    (cards / (name or f"{data['card_id']}.json")).write_text(json.dumps(data), encoding="utf-8")
    return validate_cards(cards, root=REPO_ROOT)


def step_of(data: dict, step_id: str) -> dict:
    return next(s for s in data["steps"] if s["id"] == step_id)


# ------------------------------------------------------------------ the shipped playbooks
def test_shipped_playbooks_validate_with_images():
    assert validate_cards(DEFAULT_CARDS_DIR, root=REPO_ROOT, check_images=True) == []


@pytest.mark.parametrize("path", PLAYBOOKS, ids=lambda p: p.stem)
def test_playbook_basics(path: Path):
    card = Card.model_validate(load(path))
    assert card.provenance == "AUTHORED DEMO METADATA"
    assert card.goal_mode == "build" and card.tests == []
    assert 5 <= len(card.steps) <= 9
    assert all(a == a.lower() for a in card.aliases)
    for step in card.steps:
        assert len(step.cue.line1) <= 24 and len(step.cue.line2) <= 26
        assert all(r in {s.id for s in card.steps} for r in step.requires)
    assert sum(1 for s in card.steps if s.guide_id) <= 2


def test_paper_cup_is_sourced_manual_and_sized():
    card = Card.model_validate(load(PAPER))
    assert len(card.steps) == 8
    assert all(s.verify is None for s in card.steps)  # manual: only the wearer confirms
    assert {s.kind for s in card.sources} == {"WEB TUTORIAL"}
    assert all(s.url and s.url.startswith("https://origami.me/") for s in card.sources)
    assert {"paper cup", "origami", "fold", "cup", "paper"} <= set(card.aliases)
    quotes = [c.quote for s in card.steps for t in s.troubleshoot for c in t.cites if c.quote]
    assert len(quotes) >= 7  # every folding step cites a verbatim sentence
    assert {g.id for g in card.guides} == {"cup_fold_half", "cup_pinch"}
    for guide in card.guides:
        assert all(v.provenance == "AUTHORED DEMO METADATA" and "SCHEMATIC" in v.depicts for v in guide.views)


def test_pi_camera_setup_has_two_measured_steps_with_allowed_signals():
    card = Card.model_validate(load(PI))
    measured = [s for s in card.steps if s.verify is not None]
    assert [s.id for s in measured] == ["camera_feed", "led_test"]
    for step in measured:
        assert {p.signal for p in step.verify.when} <= ALLOWED_VERIFY_SIGNALS
    assert {p.signal for p in measured[0].verify.when} == {"camera.frame_seq", "camera.mean_luma"}
    assert {p.signal for p in measured[1].verify.when} == {"led.commanded_on"}
    assert "VERIFIED" not in json.dumps(load(PI))
    led_test = measured[1]
    assert "COMMANDED" in led_test.verify.ok.line1


def test_pi_camera_setup_never_invents_a_pin_or_connector_direction():
    text = json.dumps(load(PI)).lower()
    assert "gpio" in text  # mentioned only to say: read it from your own wiring
    for step in Card.model_validate(load(PI)).steps:
        assert not any(ch.isdigit() for ch in step.cue.line1 + step.cue.line2)  # no pin numbers on the glasses
    assert "pin 17" not in text and "gpio 17" not in text


def test_led_breadboard_never_claims_verification():
    card = Card.model_validate(load(LED))
    assert card.steps and all(s.verify is None for s in card.steps)
    assert card.tests == [] and card.functional is None
    blob = json.dumps(load(LED))
    assert "VERIFIED" not in blob and "CORRECT" not in blob.replace("correct direction", "")


def test_alias_clash_between_cards_of_one_goal_mode_rejected(tmp_path: Path):
    a, b = load(PAPER), load(LED)
    b["aliases"].append("origami")
    cards = tmp_path / "cards"
    cards.mkdir()
    (cards / "paper_cup.json").write_text(json.dumps(a), encoding="utf-8")
    (cards / "led_breadboard.json").write_text(json.dumps(b), encoding="utf-8")
    errors = validate_cards(cards, root=REPO_ROOT)
    assert any("alias 'origami'" in e and "ambiguous" in e for e in errors), errors


def test_shipped_aliases_do_not_clash():
    seen: dict[tuple[str, str], str] = {}
    for path in sorted(DEFAULT_CARDS_DIR.glob("*.json")):
        card = Card.model_validate(load(path))
        for alias in card.aliases:
            assert (card.goal_mode, alias) not in seen, (alias, path.name)
            seen[(card.goal_mode, alias)] = card.card_id


# ------------------------------------------------------------------ cue rules on step text
@pytest.mark.parametrize(
    "where,mutate,needle",
    [
        ("cue", lambda d: d["steps"][1]["cue"].update(line1="Fold bottom corner up"), "upper case"),
        ("cue", lambda d: d["steps"][1]["cue"].update(line1="FOLD 50% UP"), "'%'"),
        ("cue", lambda d: d["steps"][1]["cue"].update(line1="✓ DONE"), "folds the check mark"),
        ("cue", lambda d: d["steps"][1]["cue"].update(line1="A" * 25), "at most 24"),
        ("cue line2", lambda d: d["steps"][1]["cue"].update(line2="B" * 27), "at most 26"),
        ("why", lambda d: d["steps"][1].update(why={"line1": "NEAT TRICK?!;", "line2": ""}), "';'"),
        ("where", lambda d: d["steps"][1].update(where={"line1": "ON THE <TABLE>", "line2": ""}), "'<'"),
        ("faq a", lambda d: d["steps"][1]["faq"][0]["a"].update(line1="Which side"), "upper case"),
        ("troubleshoot", lambda d: d["steps"][1]["troubleshoot"][0]["action"].update(line1="CHECK SIDE #1"), "'#'"),
        ("diagnosis", lambda d: d["steps"][1]["troubleshoot"][0]["action"].update(line1="PAPER IS WRONG"), "diagnosis"),
        ("diagnosis wrong", lambda d: d["steps"][1]["cue"].update(line2="WRONG FOLD"), "diagnosis"),
    ],
)
def test_step_text_rules(tmp_path: Path, where: str, mutate, needle: str):
    data = load(PAPER)
    mutate(data)
    errors = errors_for(tmp_path, data)
    assert any(needle in e for e in errors), (where, errors)


def test_step_text_may_use_ascii_punctuation(tmp_path: Path):
    data = load(PAPER)
    data["steps"][1]["cue"] = {"line1": "FOLD (BOTTOM), 1: UP+", "line2": "WHAT? SEE A=B!"}
    assert errors_for(tmp_path, data) == []


def test_fault_card_glyph_rules_stay_strict(tmp_path: Path):
    camera = load(DEFAULT_CARDS_DIR / "camera_lens.json")
    camera["tests"][0]["fact"]["line2"] = "CHECK (LENS)"
    assert any("characters not allowed" in e for e in errors_for(tmp_path, camera))


def test_faq_question_must_be_lowercase(tmp_path: Path):
    data = load(PAPER)
    data["steps"][1]["faq"][0]["q"] = "Which side faces up"
    assert any("faq[0].q" in e and "lowercase" in e for e in errors_for(tmp_path, data))


# ------------------------------------------------------------------ structure
def test_duplicate_step_ids_rejected(tmp_path: Path):
    data = load(PAPER)
    data["steps"][2]["id"] = data["steps"][1]["id"]
    assert any("step ids must be unique" in e for e in errors_for(tmp_path, data))


def test_requires_must_name_an_earlier_step(tmp_path: Path):
    data = load(PAPER)
    step_of(data, "fold_half")["requires"] = ["open"]
    errors = errors_for(tmp_path, data)
    assert any("requires 'open'" in e and "LATER" in e for e in errors), errors
    data = load(PAPER)
    step_of(data, "fold_half")["requires"] = ["nope"]
    assert any("requires 'nope'" in e and "not a step" in e for e in errors_for(tmp_path, data))
    data = load(PAPER)
    step_of(data, "fold_half")["requires"] = ["fold_half"]
    assert any("requires itself" in e for e in errors_for(tmp_path, data))


def test_unknown_step_guide_id_rejected(tmp_path: Path):
    data = load(PAPER)
    step_of(data, "fold_half")["guide_id"] = "missing_guide"
    assert any("missing_guide" in e for e in errors_for(tmp_path, data))
    data = load(PAPER)
    step_of(data, "fold_half")["troubleshoot"][0]["guide_id"] = "also_missing"
    assert any("also_missing" in e for e in errors_for(tmp_path, data))


# ------------------------------------------------------------------ verify rules
def test_verify_signal_must_exist_on_observation(tmp_path: Path):
    data = load(PI)
    step_of(data, "camera_feed")["verify"]["when"][0]["signal"] = "camera.nonexistent"
    assert any("unknown signal 'camera.nonexistent'" in e for e in errors_for(tmp_path, data))


def test_verify_signal_must_be_an_allowed_telemetry_signal(tmp_path: Path):
    data = load(PI)
    step_of(data, "camera_feed")["verify"]["when"][0] = {"signal": "camera.marker_found", "op": "eq", "value": True}
    errors = errors_for(tmp_path, data)
    assert any("not an allowed telemetry signal" in e and "camera.marker_found" in e for e in errors), errors
    data = load(PI)
    step_of(data, "camera_feed")["verify"]["when"][0] = {"signal": "led", "op": "not_null", "value": None}
    assert any("not an allowed telemetry signal" in e for e in errors_for(tmp_path, data))


def test_verify_threshold_range_and_shape_checked(tmp_path: Path):
    data = load(PI)
    step_of(data, "camera_feed")["verify"]["when"][1]["value"] = 999
    assert any("outside physical range" in e for e in errors_for(tmp_path, data))
    data = load(PI)
    step_of(data, "camera_feed")["verify"]["when"][1]["value"] = None
    assert any("needs a value" in e for e in errors_for(tmp_path, data))


def test_verify_ok_cue_follows_cue_rules(tmp_path: Path):
    data = load(PI)
    step_of(data, "camera_feed")["verify"]["ok"]["line1"] = "● camera live"
    assert any("verify.ok.line1" in e and "upper case" in e for e in errors_for(tmp_path, data))


def test_troubleshoot_predicate_signals_must_exist(tmp_path: Path):
    data = load(PI)
    step_of(data, "camera_feed")["troubleshoot"][0]["when"][0]["signal"] = "camera.nope"
    assert any("troubleshoot[0].when[0]" in e and "camera.nope" in e for e in errors_for(tmp_path, data))


@pytest.mark.parametrize("field", ["cue", "why", "where"])
def test_manual_step_never_says_verified_or_correct(tmp_path: Path, field: str):
    for word in ("VERIFIED", "CORRECT"):
        data = load(PAPER)
        step_of(data, "pinch")[field] = {"line1": f"FOLD {word}", "line2": ""}
        errors = errors_for(tmp_path, data)
        assert any("manual step" in e and word in e for e in errors), (field, word, errors)


def test_manual_step_faq_and_troubleshoot_also_barred(tmp_path: Path):
    data = load(PAPER)
    step_of(data, "pinch")["faq"][0]["a"] = {"line1": "THAT IS CORRECT", "line2": ""}
    assert any("manual step" in e and "CORRECT" in e for e in errors_for(tmp_path, data))
    data = load(PAPER)
    step_of(data, "pinch")["troubleshoot"][0]["action"] = {"line1": "FOLD VERIFIED", "line2": ""}
    assert any("manual step" in e and "VERIFIED" in e for e in errors_for(tmp_path, data))


def test_measured_step_may_say_verified_but_an_led_command_may_not(tmp_path: Path):
    data = load(PI)
    step_of(data, "camera_feed")["verify"]["ok"] = {"line1": "● FEED VERIFIED", "line2": ""}
    assert errors_for(tmp_path, data) == []  # measured camera evidence: allowed
    data = load(PI)
    step_of(data, "led_test")["verify"]["ok"] = {"line1": "● LED VERIFIED", "line2": ""}
    errors = errors_for(tmp_path, data)
    assert any("COMMANDED, not measured light" in e for e in errors), errors


# ------------------------------------------------------------------ cites
def test_fabricated_step_quote_rejected(tmp_path: Path):
    data = load(PAPER)
    step_of(data, "pinch")["troubleshoot"][0]["cites"][0]["quote"] = "Always pinch twice for a perfect cup."
    assert any("not found verbatim" in e and "origami_me_cup" in e for e in errors_for(tmp_path, data))


def test_quote_is_case_sensitive_and_unknown_source_rejected(tmp_path: Path):
    data = load(PAPER)
    step_of(data, "pinch")["troubleshoot"][0]["cites"][0]["quote"] = "BUT ONLY PINCH AT THE RIGHT EDGE LEVEL."
    assert any("not found verbatim" in e for e in errors_for(tmp_path, data))
    data = load(PAPER)
    step_of(data, "pinch")["troubleshoot"][0]["cites"][0]["source"] = "nope"
    assert any("not in this card's sources" in e for e in errors_for(tmp_path, data))


def test_quote_without_a_source_file_rejected(tmp_path: Path):
    data = load(PAPER)
    data["sources"][0]["file"] = None
    assert any("has no file to check it against" in e for e in errors_for(tmp_path, data))


def test_every_shipped_quote_is_verbatim_in_its_source_file():
    for path in PLAYBOOKS:
        card = Card.model_validate(load(path))
        files = {s.id: (REPO_ROOT / s.file).read_text(encoding="utf-8") for s in card.sources if s.file}
        for step in card.steps:
            for check in step.troubleshoot:
                for cite in check.cites:
                    if cite.quote:
                        assert " ".join(cite.quote.split()) in " ".join(files[cite.source].split()), (path.stem, step.id)


# ------------------------------------------------------------------ importer + approve on a playbook envelope
def make_env() -> dict:
    return copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))


def test_fixture_is_marked_as_hand_made_not_creao():
    env = make_env()
    assert "NOT produced by CREAO" in env["request"]
    assert any("hand-made fixture, NOT produced by CREAO" in u for u in env["research"]["uncertainties"])
    assert env["run_id"].startswith("fixture-")
    assert Card.model_validate(env["card"]).provenance == "WEB TUTORIAL"  # a draft never claims review


def test_fixture_envelope_validates():
    result = validate_envelope(make_env(), REPO_ROOT)
    assert result == {"ok": True, "errors": []}


def test_importer_cli_accepts_fixture_as_draft_then_approve_dry_run_and_real(tmp_path: Path, capsys):
    assert importer_main([str(FIXTURE), "--root", str(tmp_path)]) == 0
    drafts = sorted((tmp_path / "knowledge" / "drafts").iterdir())
    assert len(drafts) == 1 and (drafts[0] / "envelope.json").is_file()
    draft_id = drafts[0].name
    assert approve_main([draft_id, "--reviewer", "tester", "--dry-run", "--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "DRY RUN: nothing written" in out and "paper_cup__origami_me_cup.md" in out
    assert not (tmp_path / "knowledge" / "cards").exists()
    assert approve_main([draft_id, "--reviewer", "tester", "--root", str(tmp_path)]) == 0
    cards = tmp_path / "knowledge" / "cards"
    approved = json.loads((cards / "paper_cup.json").read_text(encoding="utf-8"))
    assert approved["provenance"] == "AI-EXTRACTED · HUMAN-REVIEWED" and len(approved["steps"]) == 8
    assert validate_cards(cards, root=tmp_path) == []  # quotes re-checked against the stored source files


def test_approve_never_replaces_the_hand_authored_card_without_force(tmp_path: Path, capsys):
    cards = tmp_path / "knowledge" / "cards"
    cards.mkdir(parents=True)
    (cards / "paper_cup.json").write_text(PAPER.read_text(encoding="utf-8"), encoding="utf-8")
    assert importer_main([str(FIXTURE), "--root", str(tmp_path)]) == 0
    draft_id = next((tmp_path / "knowledge" / "drafts").iterdir()).name
    assert approve_main([draft_id, "--reviewer", "tester", "--dry-run", "--root", str(tmp_path)]) == 1
    assert "hand-authored" in capsys.readouterr().out
    assert json.loads((cards / "paper_cup.json").read_text(encoding="utf-8"))["provenance"] == "AUTHORED DEMO METADATA"


@pytest.mark.parametrize(
    "mutate,needle",
    [
        (lambda e: e["card"]["steps"][2]["troubleshoot"][0]["cites"][0].update(quote="A made up sentence."), "not found verbatim"),
        (lambda e: e["card"]["steps"][2]["troubleshoot"][0]["cites"][0].update(url="javascript:alert(1)"), "url must be http(s)"),
        (lambda e: e["card"]["steps"][2].update(verify={"when": [{"signal": "camera.marker_found", "op": "eq", "value": True}], "hold_ms": 0, "ok": {"line1": "● OK", "line2": ""}}), "not an allowed telemetry signal"),
        (lambda e: e["card"]["steps"][2].update(requires=["open"]), "LATER"),
        (lambda e: e["card"]["steps"][2]["cue"].update(line1="Fold it"), "upper case"),
        (lambda e: e["card"]["steps"][2]["cue"].update(line1="FOLD VERIFIED"), "manual step"),
        (lambda e: e["card"]["steps"][2].update(guide_id="none"), "not a guide"),
        (lambda e: e["source_texts"].pop("origami_me_cup"), "has no text"),
        (lambda e: e["card"].update(provenance="AI-EXTRACTED · HUMAN-REVIEWED"), "cannot claim"),
    ],
)
def test_importer_rejects_broken_playbook_envelopes(mutate, needle):
    env = make_env()
    mutate(env)
    result = validate_envelope(env, REPO_ROOT)
    assert not result["ok"]
    assert any(needle in e for e in result["errors"]), result["errors"]


def test_paper_cup_guides_are_the_built_manifest_guides_plus_reference_url():
    card = load(PAPER)
    for guide in card["guides"]:
        built = json.loads((REPO_ROOT / "knowledge" / "guides" / guide["id"] / "manifest.json").read_text(encoding="utf-8"))["guide"]
        for view in guide["views"]:
            assert view.pop("reference_url") == "https://origami.me/cup/"
        assert guide == built, f"re-paste manifest.json guide into paper_cup.json for {guide['id']} (make guides changed it)"
