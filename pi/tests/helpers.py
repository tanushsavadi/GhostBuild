import numpy as np

from ghostbuild_pi.camera import FakeCamera
from ghostbuild_pi.clock import FakeClock
from ghostbuild_pi.features import FeatureExtractor
from ghostbuild_pi.led import DryRunDriver, LedController, MotionLedRule
from ghostbuild_pi.runner import Station

STEP_MS = 200  # 5 Hz


def make_station(scenario, with_led=True, source="simulated", hz_ms=STEP_MS, **kw):
    clock = FakeClock()
    cam = FakeCamera(scenario, clock, **kw)
    led = rule = None
    if with_led:
        led = LedController(DryRunDriver(17), clock)
        rule = MotionLedRule(led)
    st = Station(cam, FeatureExtractor(), source, dev="pi-01", led=led, rule=rule, clock=clock,
                 report_led=with_led, seq_start=0)
    return st, clock, cam


def run(st, clock, seconds, hz_ms=STEP_MS):
    out = []
    for _ in range(int(seconds * 1000 / hz_ms)):
        out.append(st.step())
        clock.advance(hz_ms)
    return out


def gray_rgb(a):
    g = np.clip(np.rint(a), 0, 255).astype(np.uint8)
    return np.stack([g, g, g], axis=2)
