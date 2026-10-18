"""Scripted SIMULATED Pi (source="simulated"). For tests and dev only; never a judge demo.

Scripted timeline (loops every 100 s): healthy -> blocked at t+20 s -> recovered at t+60 s ->
motion with LED commanded at t+75 s -> healthy. POST /sim/scenario?name=... pins a scenario instead.
"""

from __future__ import annotations

import random

from contracts.models import Observation

from .clock import Clock

SCENARIOS = ("script", "healthy", "blocked", "recover", "freeze", "null_camera", "motion")
LOOP_MS = 100_000


class SimPi:
    def __init__(self, clock: Clock, dev: str = "sim-pi", seed: int = 7) -> None:
        self.clock = clock
        self.dev = dev
        self.scenario = "script"
        self._t0 = clock.now_ms()
        self._seq = 0
        self._frame_seq = 0
        self._cmd_seq = 0
        self._rnd = random.Random(seed)
        self._led_on = False

    def set_scenario(self, name: str) -> None:
        if name not in SCENARIOS:
            raise ValueError(f"unknown scenario {name!r}; one of {', '.join(SCENARIOS)}")
        self.scenario = name
        self._t0 = self.clock.now_ms()

    def phase(self) -> str:
        el = self.clock.now_ms() - self._t0
        if self.scenario == "script":
            t = el % LOOP_MS
            if t < 20_000:
                return "healthy"
            if t < 60_000:
                return "blocked"
            if t < 75_000:
                return "healthy"
            if t < 78_000:
                return "motion"
            return "healthy"
        if self.scenario == "motion":
            return "motion" if 500 <= el < 3500 else "healthy"
        if self.scenario == "recover":
            return "healthy"
        return self.scenario  # healthy | blocked | freeze | null_camera

    def observe(self) -> Observation:
        now = self.clock.now_ms()
        ph = self.phase()
        self._seq += 1
        base = dict(dev=self.dev, seq=self._seq, ms=now, at=self.clock.epoch_ms(), source="simulated", error=None)
        if ph == "null_camera":
            return Observation.model_validate({**base, "camera": None, "led": None, "error": "camera_open_failed"})
        if ph != "freeze":
            self._frame_seq += 1
        j = self._rnd.uniform(-1.0, 1.0)
        if ph == "blocked":
            luma, std, detail, motion = 6.0 + abs(j) * 0.4, 1.0 + abs(j) * 0.1, 3.0, 0.0
        else:
            luma, std, detail, motion = 118.0 + j * 3, 41.0 + j, 255.0, 0.01
        led_on = False
        reason = None
        if ph == "motion":
            motion, led_on, reason = 0.35, True, "motion_in_roi"
            if not self._led_on:
                self._cmd_seq += 1
        self._led_on = led_on
        return Observation.model_validate(
            {
                **base,
                "camera": dict(frame_seq=self._frame_seq, frame_age_ms=40, mean_luma=round(luma, 2), luma_std=round(std, 2),
                               detail=detail, motion=motion, marker_found=None, marker_id=None),
                "led": dict(commanded_on=led_on, cmd_seq=self._cmd_seq, reason=reason),
            }
        )
