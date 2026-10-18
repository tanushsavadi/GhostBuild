"""python -m ghostbuild_core [--host 0.0.0.0 --port 8787] [--simulate] [--cards knowledge/cards] [--log-dir logs]"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from .cards import load_cards


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m ghostbuild_core")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--simulate", action="store_true", help="feed SIMULATED observations (dev/test only, never a judge demo)")
    ap.add_argument("--cards", default="knowledge/cards", help="directory of Repair Card JSON files")
    ap.add_argument("--log-dir", default="logs")
    ap.add_argument("--root", default=".", help="repo root: guide image paths and web/ resolve against it")
    ap.add_argument("--log-level", default="info")
    ap.add_argument("--voice", action="store_true", help="enable the optional hold-to-ask voice lane (also GB_VOICE=1); needs CARTESIA_API_KEY")
    args = ap.parse_args(argv)
    logging.basicConfig(level=args.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    cards = load_cards(args.cards)
    if not cards:
        print(f"ghostbuild_core: no valid Repair Card in {args.cards!r}; refusing to start without one.", file=sys.stderr)
        return 2

    import uvicorn

    from .runtime import Runtime
    from .server import create_app

    rt = Runtime(cards, log_dir=args.log_dir, asset_root=Path(args.root), simulate=args.simulate)
    from .voice import VoiceService, voice_enabled_from_env

    if args.voice or voice_enabled_from_env():
        VoiceService(rt)
    app = create_app(rt)
    banner = "SIMULATED observations (dev only)" if args.simulate else "live Pi observations"
    logging.getLogger("ghostbuild").info("cards: %s | %s | log: %s", ", ".join(c.card_id for c in cards), banner, rt.elog.path)
    if rt.voice is not None and not os.environ.get("CARTESIA_API_KEY"):
        logging.getLogger("ghostbuild").warning("voice ON but CARTESIA_API_KEY is not set: holds will show VOICE UNAVAILABLE / USE TOUCH")
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level.lower())
    return 0


if __name__ == "__main__":
    sys.exit(main())
