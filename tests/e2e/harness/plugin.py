"""Python handle on the real G2 plugin (g2/src/main.ts) running under tests/e2e/harness/g2/driver.mjs."""

from __future__ import annotations

import itertools
import json
import queue
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent / "g2"
G2 = Path(__file__).resolve().parents[3] / "g2"

LISTENING = "LISTENING..."
OFFLINE = "GHOSTBUILD OFFLINE\nRECONNECTING..."


def node_ready() -> str | None:
    """Reason the plugin harness cannot run, or None."""
    if not shutil.which("node"):
        return "node not installed"
    if not (G2 / "node_modules" / "esbuild").exists():
        return "g2/node_modules missing: run `cd g2 && npm ci`"
    out = subprocess.run(["node", "-e", "process.exit(typeof WebSocket==='function'?0:1)"])
    if out.returncode:
        return "node has no global WebSocket (need Node >= 22)"
    return None


def build(out: Path) -> Path:
    subprocess.run(["node", str(HERE / "build.mjs"), str(out)], check=True)
    return out


class Plugin:
    def __init__(self, bundle: Path, core_url: str, ws: str = "normal") -> None:
        self.proc = subprocess.Popen(
            ["node", str(HERE / "driver.mjs"), f"--bundle={bundle}", f"--core={core_url}", f"--ws={ws}"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        self._ids = itertools.count(1)
        self._replies: queue.Queue = queue.Queue()
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()
        self.snap = self._wait("ready", 10)

    def _read(self) -> None:
        assert self.proc.stdout
        for line in self.proc.stdout:
            try:
                self._replies.put(json.loads(line))
            except ValueError:
                pass

    def _wait(self, rid: Any, timeout: float) -> dict:
        end = time.time() + timeout
        while time.time() < end:
            try:
                r = self._replies.get(timeout=0.2)
            except queue.Empty:
                if self.proc.poll() is not None:
                    raise RuntimeError(f"plugin driver exited: {self.proc.stderr.read() if self.proc.stderr else ''}")
                continue
            if r["id"] == rid:
                if r["error"]:
                    raise RuntimeError(r["error"])
                return r["snap"]
        raise TimeoutError(f"plugin driver: no reply to {rid}")

    def op(self, op: str, **kw: Any) -> dict:
        rid = next(self._ids)
        assert self.proc.stdin
        self.proc.stdin.write(json.dumps({"id": rid, "op": op, **kw}) + "\n")
        self.proc.stdin.flush()
        self.snap = self._wait(rid, 5)
        return self.snap

    def snapshot(self) -> dict:
        return self.op("snapshot")

    def shown(self) -> str | None:
        return self.snapshot()["shown"]

    def wait(self, pred: Callable[[dict], Any], timeout: float = 4.0, what: str = "plugin state") -> dict:
        end = time.time() + timeout
        s = self.snapshot()
        while time.time() < end:
            if pred(s):
                return s
            time.sleep(0.05)
            s = self.snapshot()
        raise AssertionError(f"timed out after {timeout}s waiting for {what}; glasses={s['shown']!r} "
                             f"phone={s['status']!r}")

    def wait_shown(self, needle: str, timeout: float = 4.0) -> dict:
        return self.wait(lambda s: s["shown"] and needle in s["shown"], timeout, f"glasses to show {needle!r}")

    def posts(self, path: str) -> list[dict]:
        return [f for f in self.snapshot()["fetches"] if f["url"] == path]

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait()
