"""python -m ghostbuild_core [--simulate-jig] [--no-jig] [--procedure ID] [--port 8787]"""

from __future__ import annotations

import argparse

import uvicorn

from .server import Config, create_app


def main() -> None:
    ap = argparse.ArgumentParser(prog="ghostbuild_core")
    ap.add_argument("--simulate-jig", action="store_true", help="dev only: fake jig via POST /sim/jig (frames labelled simulated)")
    ap.add_argument("--no-jig", action="store_true", help="jig gate red: run every step GUIDED, never claim VERIFIED")
    ap.add_argument("--procedure", help="approved procedure id to load at start")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8787)
    a = ap.parse_args()
    app = create_app(Config(simulate_jig=a.simulate_jig, jig_enabled=not a.no_jig, procedure=a.procedure))
    uvicorn.run(app, host=a.host, port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
