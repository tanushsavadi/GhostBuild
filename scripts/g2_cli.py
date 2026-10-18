"""Terminal stand-in for the G2 plugin: shows HUD frames, sends what you type as voice text.

  make g2-cli                       (core must be running: make core-sim)
  <anything>        voice transcript, e.g. "done", "which leg is longer?", "teach me to fold a paper boat"
  /tap              temple tap               /menu why | where | done | next   contextual menu item
  /load <id>        load an approved procedure (e.g. led-button-v1, origami-cup-v1)
  :<field> <value>  simulated jig reading, e.g. ":led backwards", ":button pressed" (core --simulate-jig)
  /quit
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.request

import websockets

CORE = os.environ.get("CORE", "http://localhost:8787")
MENU = {"why": "WHY THIS STEP?", "where": "WHERE DOES IT GO?", "done": "WHAT'S DONE?", "next": "WHAT NEXT?"}


def post(path: str, body: dict) -> dict:
    req = urllib.request.Request(CORE + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode()[:200]}


def show(frame: dict) -> None:
    lines = frame.get("lines") or ["(dark)"]
    tag = f" {frame['kind']} · seq {frame['seq']} · {frame['source']} "
    print("\n┌" + tag.center(30, "─") + "┐")
    for line in lines:
        print(f"│ {line:<28} │")
    print("└" + "─" * 30 + "┘")


async def main() -> None:
    url = CORE.replace("http", "ws", 1) + "/ws?role=g2"
    async with websockets.connect(url) as ws:
        print(__doc__)

        async def reader() -> None:
            async for msg in ws:
                data = json.loads(msg)
                show(data) if data.get("type") == "hud" else print("!", data)

        task = asyncio.create_task(reader())
        while True:
            line = (await asyncio.to_thread(sys.stdin.readline)).strip()
            if not line:
                continue
            if line == "/quit":
                break
            if line == "/tap":
                msg = {"type": "g2_input", "kind": "tap"}
            elif line.startswith("/menu"):
                key = line.split(maxsplit=1)[1] if " " in line else "why"
                msg = {"type": "g2_input", "kind": "menu", "text": MENU.get(key, key)}
            elif line.startswith("/load"):
                print(post("/session/load", {"procedure_id": line.split(maxsplit=1)[1]}))
                continue
            elif line.startswith(":"):
                k, _, v = line[1:].partition(" ")
                print(post("/sim/jig", {k: v}))
                continue
            else:
                msg = {"type": "g2_input", "kind": "voice", "text": line}
            await ws.send(json.dumps(msg))
        task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
