"""Shared fixtures: contract example card (3 guide views), tiny generated PNGs, observation builders."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from contracts.models import Card, G2Input, Observation
from ghostbuild_core.clock import ManualClock
from ghostbuild_core.engine import Engine

REPO = Path(__file__).resolve().parents[2]
CARD_PATH = REPO / "contracts" / "examples" / "card_camera_lens.json"


def make_card_dict(views=("where", "how", "correct")) -> dict:
    d = json.loads(CARD_PATH.read_text())
    g = d["guides"][0]
    base = g["views"][0]
    g["views"] = []
    for v in views:
        nv = dict(base)
        nv.update(
            view=v,
            step_id=f"camera_lens.{v}",
            title=v.upper(),
            image=f"knowledge/guides/camera_lens/{v}.png",
            fallback={"line1": f"FALLBACK {v.upper()}", "line2": "TEXT ONLY"},
        )
        g["views"].append(nv)
    d["aliases"] = ["camera", "inspection station"]
    return d


@pytest.fixture
def card_dict() -> dict:
    return make_card_dict()


@pytest.fixture
def card(card_dict) -> Card:
    return Card.model_validate(card_dict)


@pytest.fixture
def asset_root(tmp_path) -> Path:
    root = tmp_path / "root"
    gdir = root / "knowledge" / "guides" / "camera_lens"
    gdir.mkdir(parents=True)
    for i, v in enumerate(("where", "how", "correct")):
        im = Image.new("L", (64, 32), color=40 + i * 60)
        im.save(gdir / f"{v}.png")
    return root


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock()


@pytest.fixture
def engine(card, clock, asset_root) -> Engine:
    return Engine(card, clock, asset_root=asset_root)


class Feeder:
    """Feeds observations at a fixed cadence and keeps the engine ticking."""

    def __init__(self, engine: Engine, clock: ManualClock, dev: str = "pi-01", step_ms: int = 100):
        self.e, self.c, self.dev, self.step = engine, clock, dev, step_ms
        self.seq = 0
        self.frame_seq = 0

    def obs(self, *, luma=118.0, std=41.0, detail=200.0, motion=0.01, led=False, camera=True, source="pi_live", frame=True, error=None) -> Observation:
        self.seq += 1
        if frame:
            self.frame_seq += 1
        cam = None
        if camera:
            cam = dict(frame_seq=self.frame_seq, frame_age_ms=40, mean_luma=luma, luma_std=std, detail=detail, motion=motion)
        return Observation.model_validate(
            dict(
                dev=self.dev, seq=self.seq, ms=self.c.now_ms(), at=self.c.epoch_ms(), source=source, camera=cam,
                led=dict(commanded_on=led, cmd_seq=1 if led else 0), error=error,
            )
        )

    def run(self, ms: int, **kw) -> None:
        n = ms // self.step
        for _ in range(n):
            self.c.advance(self.step)
            self.e.ingest(self.obs(**kw))
            self.e.tick()

    def healthy(self, ms: int, **kw) -> None:
        self.run(ms, **kw)

    def blocked(self, ms: int, **kw) -> None:
        self.run(ms, luma=6.0, std=1.0, **kw)

    def idle(self, ms: int) -> None:
        """No observations; time passes and the engine ticks."""
        for _ in range(ms // self.step):
            self.c.advance(self.step)
            self.e.tick()


@pytest.fixture
def feed(engine, clock) -> Feeder:
    return Feeder(engine, clock)


def press(g="press", surface="g2") -> G2Input:
    return G2Input(gesture=g, seq_seen=0, surface=surface)


@pytest.fixture(autouse=True)
def _research_requests_never_land_in_the_repo(monkeypatch, tmp_path_factory):
    """Tests that run a Runtime on the real repo root must not drop request files into knowledge/requests/."""
    from ghostbuild_core.research import ResearchQueue

    orig = ResearchQueue.__init__

    def init(self, asset_root, clock):
        orig(self, asset_root, clock)
        if Path(asset_root).resolve() == REPO:
            self.dir = tmp_path_factory.mktemp("requests")

    monkeypatch.setattr(ResearchQueue, "__init__", init)
