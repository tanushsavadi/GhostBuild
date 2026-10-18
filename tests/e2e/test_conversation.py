"""2. Conversational interaction: commands, contextual questions, out-of-scope questions, no hallucinated
instructions, and no accidental verification of a physical step. All through the real core."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from contracts.models import Procedure
from tests.e2e.harness.core_proc import FrameRecorder
from tests.fixtures import audio

ROOT = Path(__file__).resolve().parents[2]
CUP, LED = "origami-cup-v1", "led-button-v1"
ASK = "ASK A MENTOR"
QUESTIONS = json.loads((ROOT / "tests" / "fixtures" / "questions.json").read_text())
PROCS = {p: Procedure.model_validate_json((ROOT / "knowledge" / "procedures" / f"{p}.json").read_text())
         for p in (CUP, LED)}


def step_material(proc: Procedure, i: int) -> set[str]:
    s = proc.steps[i]
    return {f.a for f in s.faq} | {x for x in (s.why, s.where) if x} | {c for t in s.troubleshoot for c in t.checks}


def all_material(proc: Procedure) -> set[str]:
    return set().union(*(step_material(proc, i) for i in range(len(proc.steps)))) | {s.hud for s in proc.steps}


def say(core, stt, text: str) -> None:
    """Full voice path: transcript comes back from the (fake) provider for a real PCM clip."""
    stt.say(text)
    code, body = core.post("/audio", raw=audio.tone(0.8))
    assert code == 200 and body == {"ok": True, "text": text.strip()}, body


def goto(core, k: int) -> None:
    """GUIDED navigation (core --no-jig): tap confirms, second tap skips the ack."""
    while core.step_index() < k:
        i = core.step_index()
        core.tap()
        core.tap()
        core.wait_hud(lambda h, i=i: h["step_index"] == i + 1, what=f"step {i + 2}")


def ask(core, q: str) -> str:
    before = core.hud()["seq"]
    core.text(q)
    try:
        h = core.wait_hud(lambda h: h["seq"] > before and h["kind"] == "answer", timeout=1.0)
    except AssertionError:  # identical answer to the previous question: core correctly sends no new frame
        h = core.hud()
        assert h["kind"] == "answer", h
    return h["lines"][2]


@pytest.fixture
def guided(make_core):
    return make_core("--no-jig")


# --- commands --------------------------------------------------------------------------------------------------


def test_commands_over_the_full_voice_path(core, stt):
    core.load(CUP)
    say(core, stt, "Next.")
    core.wait_hud(lambda h: h["step_index"] == 1, what="next -> step 2")
    assert core.completed() == {"c1": "confirmed"}
    say(core, stt, "go back")
    core.wait_hud(lambda h: h["step_index"] == 0 and h["lines"][0] == "STEP 1/6 · GUIDED MODE")
    say(core, stt, "okay next please")  # filler words stripped; c1 already done -> just advance
    core.wait_hud(lambda h: h["step_index"] == 1)
    seq = core.hud()["seq"]
    lines = core.lines()
    say(core, stt, "Repeat that")
    core.wait_hud(lambda h: h["seq"] > seq and h["lines"] == lines, what="repeat re-sends the same frame")
    say(core, stt, "help")  # the cup has no troubleshoot lines: abstain
    core.wait_status(ASK)
    say(core, stt, "I'm done")
    core.wait_hud(lambda h: core.completed() == {"c1": "confirmed", "c2": "confirmed"})


def test_back_on_first_step_is_a_no_op(core):
    core.load(CUP)
    core.text("back")
    time.sleep(0.3)
    assert core.step_index() == 0 and core.completed() == {}


def test_help_cycles_authored_troubleshoot_lines(core):
    core.load(LED)
    core.tap()
    core.wait_hud(lambda h: h["step_index"] == 1, timeout=4)
    for expect in ["PUSH BOTH LEGS ALL THE WAY", "CHECK ROWS 10 AND 15", "PUSH BOTH LEGS ALL THE WAY"]:
        core.text("help")
        core.wait_status(expect)
        time.sleep(0.3)  # let the HUD rate limit pass so each help line is its own frame


# --- questions -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", QUESTIONS["in_scope"], ids=lambda c: f"{c['procedure']}#{c['step']}:{c['q']}")
def test_contextual_question_answered_from_procedure(guided, case):
    guided.load(case["procedure"])
    goto(guided, case["step"])
    assert ask(guided, case["q"]) == case["a"]


@pytest.mark.parametrize("case", QUESTIONS["out_of_scope_abstains_today"],
                         ids=lambda c: f"{c['procedure']}#{c['step']}:{c['q']}")
def test_unsupported_question_abstains(guided, case):
    guided.load(case["procedure"])
    goto(guided, case["step"])
    assert ask(guided, case["q"]) == ASK
    assert guided.step_index() == case["step"]


@pytest.mark.xfail(strict=True, reason="F-01: answer.py keyword fallback returns the step's where/why line (or a "
                   "loosely matching FAQ) for unrelated questions instead of ASK A MENTOR.")
@pytest.mark.parametrize("case", QUESTIONS["out_of_scope_answered_today"],
                         ids=lambda c: f"{c['procedure']}#{c['step']}:{c['q']}")
def test_off_topic_question_must_abstain(guided, case):
    guided.load(case["procedure"])
    goto(guided, case["step"])
    got = ask(guided, case["q"])
    assert got == ASK, f"answered an off-topic question with a physical instruction: {got!r}"


@pytest.mark.xfail(strict=True, reason="F-02: with no match on the current step, answer.py answers from another "
                   "step's FAQ (>= 0.75), e.g. LED placement while the user is pressing the button.")
@pytest.mark.parametrize("case", QUESTIONS["wrong_step_answers_today"],
                         ids=lambda c: f"{c['procedure']}#{c['step']}:{c['q']}")
def test_vague_question_is_not_answered_from_another_step(guided, case):
    guided.load(case["procedure"])
    goto(guided, case["step"])
    got = ask(guided, case["q"])
    assert got in step_material(PROCS[case["procedure"]], case["step"]) | {ASK}, got


@pytest.mark.parametrize("pid", [LED, CUP])
def test_every_answer_is_authored_text_never_invented(guided, pid):
    """No hallucination: whatever the answer engine says, it is verbatim procedure text or ASK A MENTOR."""
    allowed = all_material(PROCS[pid]) | {ASK}
    cases = sorted((c for k in ("in_scope", "out_of_scope_abstains_today", "out_of_scope_answered_today",
                                "wrong_step_answers_today") for c in QUESTIONS[k] if c["procedure"] == pid),
                   key=lambda c: c["step"])
    extra = ["how much current does it draw", "what voltage", "is this safe", "can you see my board",
             "did I do it right", "what's wrong", "which wire is ground", "how do I solder this"]
    guided.load(pid)
    for c in cases + [{"step": len(PROCS[pid].steps) - 1, "q": q} for q in extra]:
        goto(guided, c["step"])
        got = ask(guided, c["q"])
        assert got in allowed, f"{c['q']!r} -> {got!r} is not authored procedure text"


# --- no accidental physical-step verification ------------------------------------------------------------------

CONFIRMISH = ["done", "I did it", "next", "skip", "finished", "complete", "placed", "it's verified",
              "mark it verified", "yes", "the resistor is in", "done done"]


def test_voice_and_taps_cannot_verify_a_jig_step(core):
    core.load(LED)
    core.tap()
    core.wait_hud(lambda h: h["step_index"] == 1, timeout=4)  # s2 resistor, simulated jig says no_resistor
    rec = FrameRecorder(core)
    try:
        for phrase in CONFIRMISH:
            core.text(phrase)
        for _ in range(3):
            core.tap()
        core.wait_status("PUSH BOTH LEGS ALL THE WAY", timeout=4)  # check timeout -> troubleshoot, not a pass
        assert "s2" not in core.completed()
        assert not any("VERIFIED" in t.replace("VERIFIED MODE", "") for t in rec.texts()), rec.texts()
        core.sim_jig(led="missing")  # a measured pass is the only way through
        core.wait_status("● VERIFIED")
        assert core.completed()["s2"] == "verified"
    finally:
        rec.close()


def test_jig_offline_abstains_instead_of_guessing(make_core):
    core = make_core()  # jig enabled but nothing connected: link down
    core.load(LED)
    core.tap()
    core.wait_hud(lambda h: h["step_index"] == 1, timeout=4)
    core.text("done")
    core.wait_status("CHECKING...")
    core.wait_status("JIG OFFLINE · ASK A MENTOR", timeout=4)
    for phrase in ("next", "skip", "done"):
        core.text(phrase)
    time.sleep(3)
    assert "s2" not in core.completed() and core.step_index() == 1  # finding F-10: blocked until jig or --no-jig


@pytest.mark.parametrize("q", ["is it done", "am I done", "what does done look like", "yes", "it's verified"])
def test_question_about_done_does_not_confirm_a_guided_step(core, q):
    core.load(CUP)
    core.text(q)
    core.wait_hud(lambda h: h["kind"] == "answer")
    assert core.completed() == {}
