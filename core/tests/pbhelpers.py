"""Shared builders for playbook tests."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from contracts.models import Card, G2Input, Observation
from ghostbuild_core.clock import ManualClock
from ghostbuild_core.hud import Hud
from ghostbuild_core.playbook import PlaybookEngine

REPO = Path(__file__).resolve().parents[2]
EXAMPLE = REPO / "contracts" / "examples" / "card_playbook_example.json"


def example_card() -> Card:
    return Card.model_validate(json.loads(EXAMPLE.read_text()))


def step_dict(i: int, *, verify=None, guide_id=None, where=True, why=True, faq=True, troubleshoot=False) -> dict:
    d = {
        "id": f"s{i}",
        "title": f"Step {i}",
        "cue": {"line1": f"DO THING {i}", "line2": f"THEN LOOK {i}"},
        "detail": f"Full detail for step {i}.",
        "warnings": [],
        "faq": [],
        "troubleshoot": [],
        "guide_id": guide_id,
        "verify": verify,
        "requires": [],
    }
    if where:
        d["where"] = {"line1": f"WHERE {i} IS", "line2": "ON THE LEFT"}
    if why:
        d["why"] = {"line1": f"WHY {i}: SAFETY", "line2": ""}
    if faq:
        d["faq"] = [{"q": f"which part is thing {i}", "a": {"line1": f"PART {i} IS BLUE", "line2": ""}}]
    if troubleshoot:
        d["troubleshoot"] = [{"when": [], "action": {"line1": f"CHECK PART {i}", "line2": ""}, "why": f"Because part {i} often slips.", "cites": [], "guide_id": None}]
    return d


def verify_led(hold_ms=500, ok="● CHECK PASSED") -> dict:
    return {"when": [{"signal": "led.commanded_on", "op": "eq", "value": True}], "hold_ms": hold_ms, "ok": {"line1": ok, "line2": ""}}


def verify_luma(hold_ms=300) -> dict:
    return {"when": [{"signal": "camera.mean_luma", "op": "gt", "value": 60}], "hold_ms": hold_ms, "ok": {"line1": "● VIEW CLEAR", "line2": ""}}


def make_card(n: int = 8, *, card_id="synthetic", title="Synthetic task", measured: dict[int, dict] | None = None, goal_mode="build",
              aliases=None, guides=None, guide_steps: dict[int, str] | None = None, tests=None) -> Card:
    measured = measured or {}
    guide_steps = guide_steps or {}
    steps = [step_dict(i, verify=measured.get(i), guide_id=guide_steps.get(i), troubleshoot=(i == 1)) for i in range(n)]
    return Card.model_validate(
        {
            "v": 2, "card_id": card_id, "title": title, "provenance": "AUTHORED DEMO METADATA",
            "sources": [{"id": "x", "kind": "AUTHORED DEMO METADATA", "title": "fixture"}],
            "tests": tests or [], "steps": steps, "functional": None, "guides": guides or [],
            "goal_mode": goal_mode, "aliases": aliases if aliases is not None else [card_id.replace("_", " ")],
        }
    )


def guide_dict(gid="gd", n_views=2, prefix="knowledge/guides/gd") -> dict:
    names = ["where", "how", "correct"][:n_views]
    return {
        "id": gid, "title": "Guide",
        "views": [
            {"view": v, "step_id": f"{gid}.{v}", "title": v.upper(), "image": f"{prefix}/{v}.png", "phone_image": None,
             "provenance": "AUTHORED DEMO METADATA", "depicts": "fixture",
             "fallback": {"line1": f"FALLBACK {v.upper()}", "line2": "TEXT ONLY"}, "fov_note": None, "reference_url": None}
            for v in names
        ],
    }


def write_pngs(root: Path, prefix="knowledge/guides/gd", names=("where", "how", "correct")) -> None:
    d = root / prefix
    d.mkdir(parents=True, exist_ok=True)
    for i, n in enumerate(names):
        Image.new("L", (64, 32), color=40 + 60 * i).save(d / f"{n}.png")


def gi(g: str) -> G2Input:
    return G2Input(gesture=g, seq_seen=0)


class Obs:
    """Observation builder with a monotonic seq and frame_seq."""

    def __init__(self, clock: ManualClock, dev="pi-x"):
        self.c, self.dev, self.seq, self.frame = clock, dev, 0, 0

    def __call__(self, *, led=None, luma=None, camera=True, source="pi_live", new_frame=True) -> Observation:
        self.seq += 1
        if new_frame:
            self.frame += 1
        cam = None
        if luma is not None or camera:
            cam = dict(frame_seq=self.frame, frame_age_ms=30, mean_luma=118.0 if luma is None else luma, luma_std=40.0, detail=200.0, motion=0.0) if camera else None
        return Observation.model_validate(
            dict(dev=self.dev, seq=self.seq, ms=self.c.now_ms(), at=self.c.epoch_ms(), source=source, camera=cam,
                 led=None if led is None else dict(commanded_on=led, cmd_seq=1 if led else 0), error=None)
        )


class Rig:
    """PlaybookEngine on its own Hud + ManualClock."""

    def __init__(self, card: Card, asset_root: Path | None = None, **kw):
        self.clock = ManualClock()
        self.hud = Hud(self.clock, source="simulated")
        self.pb = PlaybookEngine(card, self.clock, hud=self.hud, asset_root=asset_root, **kw)
        self.obs = Obs(self.clock)

    @property
    def cur(self):
        return self.hud.current

    @property
    def frames(self):
        return self.hud.frames

    def wait(self, ms: int, step: int = 100) -> None:
        for _ in range(ms // step):
            self.clock.advance(step)
            self.pb.tick()

    def send(self, g: str):
        return self.pb.handle_input(gi(g))

    def feed(self, ms: int, step: int = 100, **kw) -> None:
        for _ in range(ms // step):
            self.clock.advance(step)
            self.pb.ingest(self.obs(**kw))
            self.pb.tick()

    def confirm(self):
        """Wait out the accidental-input guard, then swipe down."""
        self.wait(1600)
        return self.send("swipe_down")
