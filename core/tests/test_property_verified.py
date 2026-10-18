"""PROPERTY: a verified frame is never emitted unless the engine saw a measured pass.

Randomised observation/input/idle sequences (plain loop; hypothesis is not a project dependency).
The oracle is computed independently of the engine from the raw observations it was fed.
"""

import random

from conftest import Feeder, press

PASS_AFTER = 1000


def run_sequence(engine, clock, seed):
    rnd = random.Random(seed)
    feed = Feeder(engine, clock)
    history = []  # (t, usable, failing, led_commanded, motion)
    violations = []

    def pass_ok_times(t_emit):
        """times of observations that ended a >=1 s run of usable, non-failing observations"""
        out, run_start = [], None
        for (t, usable, failing, _led, _motion) in history:
            if usable and not failing:
                run_start = t if run_start is None else run_start
                if t - run_start >= PASS_AFTER:
                    out.append(t)
            else:
                run_start = None
        return [t for t in out if t_emit - 3000 <= t <= t_emit]

    def on_frame(f):
        t = clock.now_ms()
        if f.mode != "verified":
            return
        txt = f.cue.line1
        if not history or t - history[-1][0] > 5000:
            violations.append(("verified on stale link", f.seq))
            return
        if txt == "● CAMERA VIEW BACK" and not pass_ok_times(t):
            violations.append(("recovery without a measured pass window", f.seq))
        if txt == "ALL TESTS PASSING" and (not history[-1][1] or history[-1][2]):
            violations.append(("status claim on unusable/failing data", f.seq))
        if txt == "● LED COMMANDED":
            if not any(h[3] and h[4] > 0.15 and h[1] for h in history if t - 3000 <= h[0] <= t):
                violations.append(("LED claim without commanded_on + motion", f.seq))

    engine.hud.subscribe(on_frame)
    for _ in range(rnd.randint(30, 120)):
        kind = rnd.choice(["healthy", "blocked", "blocked", "null", "freeze", "idle", "motion", "input", "flicker"])
        ms = rnd.choice([100, 300, 700, 1200, 2500, 4000, 7000])
        n = ms // 100
        if kind == "input":
            engine.handle_input(press(rnd.choice(["press", "swipe_down", "swipe_up", "press", "hold_start"])))
            continue
        if kind == "idle":
            feed.idle(ms)
            continue
        for i in range(n):
            clock.advance(100)
            kw = {}
            if kind == "healthy":
                pass
            elif kind == "blocked":
                kw = dict(luma=6.0, std=1.0)
            elif kind == "null":
                kw = dict(camera=False)
            elif kind == "freeze":
                kw = dict(frame=False)
            elif kind == "motion":
                kw = dict(motion=0.6, led=rnd.random() < 0.5)
            elif kind == "flicker":
                kw = dict(luma=6.0, std=1.0) if i % 7 < 3 else {}
            o = feed.obs(**kw)
            cam = o.camera
            failing = bool(cam and cam.mean_luma < 25 and cam.luma_std < 8)
            frozen = kind == "freeze"  # engine may still be inside the 2 s tolerance; oracle is only conservative below
            history.append((clock.now_ms(), cam is not None, failing, bool(o.led and o.led.commanded_on), cam.motion if cam else 0.0))
            engine.ingest(o)
            engine.tick()
    return violations


def test_no_verified_without_measured_pass(card, asset_root):
    from ghostbuild_core.clock import ManualClock
    from ghostbuild_core.engine import Engine

    total_verified = 0
    for seed in range(250):
        clock = ManualClock()
        e = Engine(card, clock, asset_root=asset_root)
        v = run_sequence(e, clock, seed)
        assert v == [], f"seed {seed}: {v}"
        total_verified += sum(1 for f in e.frames if f.mode == "verified")
    assert total_verified > 50  # the property is not vacuous


def test_frame_seq_strictly_monotonic_and_no_duplicates(card, asset_root):
    from ghostbuild_core.clock import ManualClock
    from ghostbuild_core.engine import Engine

    for seed in range(100):
        clock = ManualClock()
        e = Engine(card, clock, asset_root=asset_root)
        run_sequence(e, clock, seed)
        seqs = [f.seq for f in e.frames]
        assert seqs == list(range(1, len(seqs) + 1))
        for a, b in zip(e.frames, e.frames[1:]):
            assert (a.mode, a.cue, a.image, a.menu, a.source, a.stale) != (b.mode, b.cue, b.image, b.menu, b.source, b.stale)
