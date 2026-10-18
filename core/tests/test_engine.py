from __future__ import annotations

import json

import pytest

from contracts.models import G2Input, Procedure
from ghostbuild_core import store
from ghostbuild_core.engine import ASK_MENTOR, CONFIRMED_MARK, VERIFIED_MARK, Engine
from ghostbuild_core.hud import Hud, render

PROFILES = store.load_profiles()
LED = Procedure.model_validate_json((store.APPROVED_DIR / "led-button-v1.json").read_text())
CUP = Procedure.model_validate_json((store.APPROVED_DIR / "origami-cup-v1.json").read_text())


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, s: float, engine: Engine | None = None, jig: dict | None = None) -> None:
        """Advance in 100 ms ticks, feeding the jig like the 5-10 Hz adapter would."""
        for _ in range(round(s * 10)):
            self.t += 0.1
            if engine is not None:
                if jig is not None:
                    engine.on_jig(jig)
                engine.tick()


def voice(text: str) -> G2Input:
    return G2Input(kind="voice", text=text)


def make(proc: Procedure, **kw) -> tuple[Engine, Clock]:
    clock = Clock()
    e = Engine(PROFILES, clock=clock, **kw)
    e.load(proc)
    return e, clock


def status(e: Engine) -> str | None:
    return e.view().lines_hint.get("status")


def test_guided_done_confirms_then_advances():
    e, c = make(CUP)
    assert e.view().mode == "GUIDED"
    e.on_input(voice("done"))
    assert status(e) == CONFIRMED_MARK and e.view().kind == "confirmed"
    c.advance(2, e)
    assert e.idx == 1 and e.completed["c1"].how == "confirmed"


def test_guided_never_says_verified():
    e, c = make(CUP)
    for _ in CUP.steps:
        e.on_input(G2Input(kind="tap"))
        assert status(e) != VERIFIED_MARK
        c.advance(2, e)
    assert e.engine_state == "COMPLETE"
    assert "VERIFIED" not in e.view().lines_hint["status"]


def to_step(e: Engine, c: Clock, idx: int, jig: dict) -> None:
    while e.idx < idx:
        e.on_input(voice("done"))
        c.advance(2, e, jig)


def test_jig_step_verifies_only_on_measurement():
    e, c = make(LED)
    jig = {"led": "no_resistor", "button": "released"}
    to_step(e, c, 1, jig)
    assert e.view().mode == "VERIFIED"
    e.on_input(voice("done"))
    c.advance(1, e, jig)
    assert "s2" not in e.completed and e.view().kind == "checking"
    c.advance(2, e, jig)  # timeout -> first troubleshoot line, still not verified
    assert status(e) == "PUSH BOTH LEGS ALL THE WAY" and "s2" not in e.completed
    jig = {"led": "missing", "button": "released"}
    c.advance(0.2, e, jig)
    assert e.completed["s2"].how == "verified" and status(e) == VERIFIED_MARK


def test_backwards_led_shows_fault_after_hold_then_verifies_when_flipped():
    e, c = make(LED)
    to_step(e, c, 2, {"led": "missing", "button": "released"})
    back = {"led": "backwards", "button": "released"}
    c.advance(0.5, e, back)
    assert e.view().kind == "step"  # not yet: must persist FAULT_HOLD_S
    c.advance(0.7, e, back)
    assert e.view().kind == "fault" and status(e) == "FLIP THE LED AROUND"
    c.advance(0.2, e, {"led": "correct", "button": "released"})
    assert e.completed["s3"].how == "verified"


def test_rotated_button_blocks_confirm_and_cannot_fake_press():
    e, c = make(LED)
    good = {"led": "correct", "button": "released"}
    to_step(e, c, 3, good)
    rotated = {"led": "correct", "button": "pressed"}
    c.advance(0.3, e, rotated)
    e.on_input(voice("done"))  # refused while the fault is present
    assert "s4" not in e.completed and status(e) == "TURN BUTTON 90°"
    c.advance(1, e, good)
    e.on_input(voice("done"))
    c.advance(2, e, rotated)  # arrive at s5 already "pressed": edge check must not verify
    assert e.idx == 4 and "s5" not in e.completed
    c.advance(0.3, e, good)
    c.advance(0.3, e, rotated)
    assert e.completed["s5"].how == "verified"


def test_stale_jig_never_verifies_and_abstains():
    e2, c2 = make(LED)
    to_step(e2, c2, 1, {"led": "no_resistor", "button": "released"})
    c2.advance(3, e2)  # stale
    e2.on_input(voice("done"))
    c2.advance(3, e2)
    assert "s2" not in e2.completed and status(e2) == "JIG OFFLINE · " + ASK_MENTOR


def test_no_jig_mode_runs_everything_guided():
    e, c = make(LED, jig_enabled=False)
    for _ in LED.steps:
        assert e.view().mode == "GUIDED"
        e.on_input(voice("done"))
        c.advance(2, e)
    assert all(x.how == "confirmed" for x in e.completed.values())


@pytest.mark.parametrize("q,a", [
    ("Which leg is longer?", "LONG LEG = + · ROW 15"),
    ("which way does the LED go", "LONG LEG TO ROW 15"),
    ("why", "LEDS ONLY WORK ONE WAY"),
    ("what's the capital of France", ASK_MENTOR),
])
def test_answers_come_only_from_the_procedure(q, a):
    e, c = make(LED)
    to_step(e, c, 2, {"led": "missing", "button": "released"})
    e.on_input(voice(q))
    assert status(e) == a


def test_menu_and_help_and_back():
    e, c = make(LED)
    to_step(e, c, 2, {"led": "missing", "button": "released"})
    e.on_input(G2Input(kind="menu", text="WHERE DOES IT GO?"))
    assert status(e) == "LONG ROW 15 · SHORT ROW 20"
    e.on_input(G2Input(kind="menu", text="WHAT'S DONE?"))
    assert status(e) == "2/6 DONE · 1 VERIFIED"
    e.on_input(voice("help"))
    assert status(e) == "SHORT LEG IN ROW 20?"
    e.on_input(voice("go back"))
    assert e.idx == 1 and status(e) == VERIFIED_MARK


def test_complete_then_dark():
    e, c = make(CUP)
    to_step(e, c, len(CUP.steps), {})
    assert e.view().kind == "complete"
    c.advance(9, e)
    assert e.view().kind == "clear" and render(e.view()) == []


def test_hud_dedupes_and_rate_limits():
    e, c = make(CUP)
    hud = Hud(clock=c)
    assert hud.update(e.view()) is not None
    c.advance(1)
    assert hud.update(e.view()) is None  # unchanged -> nothing sent (quiet)
    assert hud.update(e.view(), force=True) is not None  # "repeat"
    e.on_input(voice("done"))
    assert hud.update(e.view()) is None  # < 250 ms since the last frame: held
    c.advance(0.3)
    f = hud.flush()
    assert f is not None and f.kind == "confirmed"
    assert all(len(line) <= 28 for line in f.lines) and len(f.lines) <= 4


def test_validator_rejects_bad_agent_output():
    bad = json.loads(json.dumps(store.dump(LED)))
    bad["steps"][0]["hud"] = "Grab the parts please, all three of them"
    bad["steps"][1]["check"]["jig_check"] = "measures_vibes"
    proc, errors = store.validate(bad, PROFILES)
    assert proc is None and any("steps.0.hud" in x for x in errors)
    bad["steps"][0]["hud"] = "GRAB THE PARTS"
    proc, errors = store.validate(bad, PROFILES)
    assert proc is None and errors == [
        "steps.1.check.jig_check 'measures_vibes' not in ['button_pressed', 'circuit_complete', 'led_correct', 'resistor_present']"
    ]


def test_stale_reading_that_would_pass_does_not_verify():
    e, c = make(LED)
    to_step(e, c, 1, {"led": "no_resistor", "button": "released"})
    c.advance(3, e)  # link stale
    e.jig_fields = {"led": "missing", "button": "released"}  # a passing value, but old
    e.on_input(voice("done"))
    c.advance(3, e)
    assert "s2" not in e.completed
