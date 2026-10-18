"""Start the real core server for black-box tests, with ONE test seam: the speech-to-text provider URL.

Everything else (engine, HUD writer, endpoints, websockets, the urllib call in stt.transcribe) is the production
code path. GB_TEST_STT_URL points stt.URL at the local fake provider (tests/e2e/harness/fake_stt.py), so no
request ever leaves the machine and no real key is needed. The repo .env is NOT read (we bypass __main__.load_env).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "core")]

import uvicorn
from ghostbuild_core import server, stt


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--simulate-jig", action="store_true")
    ap.add_argument("--no-jig", action="store_true")
    ap.add_argument("--procedure")
    a = ap.parse_args()
    if os.environ.get("GB_TEST_STT_URL"):
        stt.URL = os.environ["GB_TEST_STT_URL"]
    app = server.create_app(server.Config(simulate_jig=a.simulate_jig, jig_enabled=not a.no_jig, procedure=a.procedure))
    uvicorn.run(app, host="127.0.0.1", port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
