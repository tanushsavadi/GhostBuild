"""Fixtures for the GhostBuild voice + G2 end-to-end reliability suite.

Everything runs the production code as black boxes: the real core server in a subprocess (only the speech-to-text
URL is redirected to a local fake), and the real g2/src/main.ts bundled with a fake Even SDK bridge.
Simulated tests never prove physical G2 behaviour (rendering, BLE, mic, touch); see docs/devin/.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.e2e.harness import plugin as plugin_mod
from tests.e2e.harness.core_proc import Core
from tests.e2e.harness.fake_stt import FakeSTT

LED = "led-button-v1"
CUP = "origami-cup-v1"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "slow: waits on a real timeout (>10 s)")
    config.addinivalue_line("markers", "plugin: drives the real g2/src/main.ts in Node (needs node>=22 + g2/node_modules)")


@pytest.fixture
def stt():
    fake = FakeSTT().start()
    yield fake
    fake.stop()


@pytest.fixture
def make_core(stt, tmp_path: Path):
    started: list[Core] = []

    def make(*args: str, voice_key: bool = True, env: dict | None = None, start: bool = True) -> Core:
        c = Core(*args, stt_url=stt.url, voice_key=voice_key, env=env, log_dir=tmp_path)
        started.append(c)
        return c.start() if start else c

    yield make
    for c in started:
        c.stop()


@pytest.fixture
def core(make_core) -> Core:
    """Core with a simulated jig (frames source=simulated) and voice on (dummy key, fake provider)."""
    return make_core("--simulate-jig")


@pytest.fixture(scope="session")
def plugin_bundle(tmp_path_factory) -> Path:
    why = plugin_mod.node_ready()
    if why:
        pytest.skip(f"G2 plugin harness unavailable: {why}")
    return plugin_mod.build(tmp_path_factory.mktemp("g2") / "plugin.mjs")


@pytest.fixture
def make_plugin(plugin_bundle):
    started: list[plugin_mod.Plugin] = []

    def make(core: Core, ws: str = "normal") -> plugin_mod.Plugin:
        p = plugin_mod.Plugin(plugin_bundle, core.url, ws=ws)
        started.append(p)
        return p

    yield make
    for p in started:
        p.close()
