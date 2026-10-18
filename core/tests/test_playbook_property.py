"""Randomized gesture/observation/ask sequences (plain loop, fixed seeds). The honesty invariants must hold for ALL of them."""

from __future__ import annotations

import random

import pytest

from ghostbuild_core.engine import eval_all
from ghostbuild_core.hud import _frame_key
from pbhelpers import Rig, guide_dict, make_card, verify_led, verify_luma, write_pngs

GESTURES = ["press", "swipe_down", "swipe_down", "swipe_down", "swipe_up", "hold_start", "hold_end"]
ASKS = ["where", "why", "which part is thing 1", "what if it didn't work", "next", "back", "show picture", "which step am I on", "gibberish qq"]


def random_card(rnd: random.Random):
    n = rnd.randint(2, 8)
    measured = {}
    for i in range(n):
        r = rnd.random()
        if r < 0.3:
            measured[i] = verify_led(rnd.choice([0, 300, 800]), ok=f"● STEP {i} CHECKED")
        elif r < 0.45:
            measured[i] = verify_luma(rnd.choice([0, 400]))
            measured[i]["ok"] = {"line1": f"● STEP {i} SEEN", "line2": ""}
    guide_steps = {i: "gd" for i in range(n) if rnd.random() < 0.4}
    return make_card(n, measured=measured, guides=[guide_dict("gd", rnd.randint(1, 3))], guide_steps=guide_steps)


@pytest.mark.parametrize("seed", range(200))
def test_honesty_invariants_under_random_use(seed, tmp_path):
    rnd = random.Random(seed)
    card = random_card(rnd)
    if rnd.random() < 0.5:
        write_pngs(tmp_path)  # sometimes the pictures exist, sometimes only the fallback
    r = Rig(card, tmp_path)
    steps = card.steps
    all_measured = all(s.verify for s in steps)
    allowed_bullets = {s.verify.ok.line1 for s in steps if s.verify} | ({"● PLAYBOOK VERIFIED"} if all_measured else set())
    satisfied_while_current: set[str] = set()

    def snap():
        return (r.pb.index, r.pb.done, list(r.pb.verified), list(r.pb.confirmed))

    state = {"prev": snap()}

    def check(seed=seed):
        pb, before, after = r.pb, state["prev"], snap()
        state["prev"] = after
        assert abs(after[0] - before[0]) <= 1, (seed, before, after)  # the index never skips
        if after[0] == before[0] + 1 or (after[1] and not before[1]):
            done_step = steps[before[0]]
            assert done_step.id in pb.confirmed or done_step.id in pb.verified
            if done_step.verify is not None:
                # a measured step is only passed with evidence that satisfied it while it was current
                assert done_step.id in pb.verified and done_step.id in satisfied_while_current, (seed, done_step.id)
        for sid in pb.confirmed:  # confirmations only for manual steps, verification only for measured ones
            assert next(s for s in steps if s.id == sid).verify is None
        for sid in pb.verified:
            assert next(s for s in steps if s.id == sid).verify is not None and sid in satisfied_while_current

    for _ in range(150):
        pb = r.pb
        kind = rnd.random()
        if kind < 0.45:
            g = rnd.choice(GESTURES)
            r.clock.advance(rnd.choice([0, 100, 700, 1600, 2200]))
            pb.tick()
            check()
            r.send(g)
            check()
        elif kind < 0.85:
            ms = rnd.choice([100, 200, 600, 1200])
            for _i in range(ms // 100):
                r.clock.advance(100)
                led = rnd.random() < 0.6
                camera = rnd.random() < 0.7
                ob = r.obs(led=led if rnd.random() < 0.8 else None, camera=camera, luma=rnd.choice([10.0, 118.0]), new_frame=rnd.random() < 0.9,
                           source=rnd.choice(["pi_live", "pi_live", "simulated"]))
                if not pb.done and steps[pb.index].verify and steps[pb.index].id not in pb.verified and eval_all(steps[pb.index].verify.when, ob):
                    satisfied_while_current.add(steps[pb.index].id)
                pb.ingest(ob)
                check()
                pb.tick()
                check()
        elif kind < 0.93:
            r.clock.advance(rnd.choice([100, 3000, 9000]))
            pb.tick()
            check()
        else:
            pb.ask(rnd.choice(ASKS))
            check()

    frames = r.frames
    # no two consecutive identical frames
    for a, b in zip(frames, frames[1:]):
        assert _frame_key(a) != _frame_key(b), (seed, a, b)
    # no error frames ever, no stale frames
    assert not [f for f in frames if f.mode == "error" or f.stale]
    # a verified-mode frame or a bullet cue exists only for evidence-backed text
    for f in frames:
        if f.mode == "verified":
            assert f.cue.line1 in allowed_bullets, (seed, f.cue)
        if f.cue and "●" in f.cue.line1:
            assert f.cue.line1 in allowed_bullets
        if f.mode == "step":
            assert 0 <= f.step.index < f.step.count == len(steps)
    for e in r.pb.events:
        if e.label == "HUMAN CONFIRMED":
            sid = e.text.split()[1]
            assert next(s for s in steps if s.id == sid).verify is None
