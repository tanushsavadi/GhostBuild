"""Runs the phone page's CREAO logic tests (web/tests/creao-logic.test.mjs, node:test) so `make test` covers them."""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_web_creao_logic_node_tests():
    res = subprocess.run(["node", "--test", "web/tests/creao-logic.test.mjs"], cwd=REPO, capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stdout + res.stderr
