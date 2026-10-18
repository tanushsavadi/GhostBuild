"""Run the real core as a subprocess on a free port and talk to it over HTTP/WebSocket like the plugin does."""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[3]
RUN_CORE = Path(__file__).with_name("run_core.py")
DUMMY_KEY = "test-key-not-real-0000"  # obviously fake; the provider is always the local FakeSTT


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_until(pred: Callable[[], Any], timeout: float = 3.0, every: float = 0.05, what: str = "condition") -> Any:
    end = time.time() + timeout
    last = None
    while time.time() < end:
        last = pred()
        if last:
            return last
        time.sleep(every)
    raise AssertionError(f"timed out after {timeout}s waiting for {what} (last={last!r})")


class Core:
    def __init__(self, *args: str, stt_url: str | None = None, voice_key: bool = True, env: dict | None = None,
                 log_dir: Path | None = None) -> None:
        self.args = list(args)
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        e = {k: v for k, v in os.environ.items() if not (k.startswith("GB_") or k.startswith("ELEVENLABS"))}
        e["PYTHONPATH"] = f"{ROOT}{os.pathsep}{ROOT / 'core'}"
        if stt_url:
            e["GB_TEST_STT_URL"] = stt_url
        if voice_key:
            e["ELEVENLABS_API_KEY"] = DUMMY_KEY
        e.update(env or {})
        self.env = e
        self.log_dir = log_dir
        self.proc: subprocess.Popen | None = None
        self._out = None

    # --- lifecycle ---------------------------------------------------------------------------------------------

    def start(self, timeout: float = 15.0) -> Core:
        out = open(self.log_dir / f"core-{self.port}.log", "ab") if self.log_dir else subprocess.DEVNULL
        self._out = out
        self.proc = subprocess.Popen([sys.executable, str(RUN_CORE), "--port", str(self.port), *self.args],
                                     env=self.env, cwd=ROOT, stdout=out, stderr=subprocess.STDOUT)
        wait_until(self._healthy, timeout, 0.1, "core /health")
        return self

    def _healthy(self) -> bool:
        if self.proc and self.proc.poll() is not None:
            raise RuntimeError(f"core exited with {self.proc.returncode}")
        try:
            return self.get("/health", timeout=0.5)[0] == 200
        except OSError:
            return False

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.send_signal(signal.SIGCONT)
            self.proc.terminate()
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        self.proc = None

    def kill(self) -> None:
        """Abrupt crash (SIGKILL): no graceful websocket close from the server side."""
        if self.proc:
            self.proc.kill()
            self.proc.wait()
            self.proc = None

    def freeze(self) -> None:
        """SIGSTOP: the process stays alive and TCP stays open but nothing answers (laptop sleep / hung loop)."""
        assert self.proc
        self.proc.send_signal(signal.SIGSTOP)

    def thaw(self) -> None:
        assert self.proc
        self.proc.send_signal(signal.SIGCONT)

    # --- http --------------------------------------------------------------------------------------------------

    def request(self, method: str, path: str, body: Any = None, raw: bytes | None = None,
                timeout: float = 30.0) -> tuple[int, Any]:
        data, headers = None, {}
        if raw is not None:
            data, headers = raw, {"Content-Type": "application/octet-stream"}
        elif body is not None:
            data, headers = json.dumps(body).encode(), {"Content-Type": "application/json"}
        req = urllib.request.Request(self.url + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                text = r.read()
                return r.status, (json.loads(text) if text else None)
        except urllib.error.HTTPError as e:
            text = e.read()
            try:
                return e.code, json.loads(text)
            except ValueError:
                return e.code, text.decode(errors="replace")

    def get(self, path: str, timeout: float = 30.0) -> tuple[int, Any]:
        return self.request("GET", path, timeout=timeout)

    def post(self, path: str, body: Any = None, raw: bytes | None = None, timeout: float = 30.0) -> tuple[int, Any]:
        return self.request("POST", path, body=body if raw is None else None, raw=raw, timeout=timeout)

    def state(self) -> dict:
        return self.get("/state")[1]

    def hud(self) -> dict | None:
        return self.state().get("hud")

    def lines(self) -> list[str]:
        h = self.hud()
        return h["lines"] if h else []

    def load(self, pid: str) -> None:
        code, body = self.post("/session/load", {"procedure_id": pid})
        assert code == 200, body
        self.wait_hud(lambda h: h.get("procedure_id") == pid, what=f"{pid} loaded")

    def tap(self) -> dict:
        return self.post("/input", {"type": "g2_input", "kind": "tap"})[1]

    def text(self, text: str, kind: str = "voice") -> dict:
        return self.post("/input", {"type": "g2_input", "kind": kind, "text": text})[1]

    def sim_jig(self, **fields: str) -> None:
        code, body = self.post("/sim/jig", fields)
        assert code == 200, body

    def wait_hud(self, pred: Callable[[dict], Any], timeout: float = 3.0, what: str = "hud") -> dict:
        return wait_until(lambda: (h := self.hud()) and pred(h) and h, timeout, what=what)

    def wait_status(self, text: str, timeout: float = 3.0) -> dict:
        return self.wait_hud(lambda h: text in h["lines"], timeout, what=f"HUD line {text!r}")

    def step_index(self) -> int | None:
        return self.state().get("step_index")

    def completed(self) -> dict[str, str]:
        return {c["step_id"]: c["how"] for c in self.state()["completed"]}

    def ws(self, role: str = "g2"):
        return connect(f"ws://127.0.0.1:{self.port}/ws?role={role}", open_timeout=5)


class FrameRecorder:
    """Subscribes as role=mirror and records every HUD frame core broadcasts (same frames the G2 gets)."""

    def __init__(self, core: Core) -> None:
        self.frames: list[tuple[float, dict]] = []
        self._ws = core.ws("mirror")
        self._stop = False
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    def _run(self) -> None:
        try:
            for msg in self._ws:
                d = json.loads(msg)
                if d.get("type") == "hud":
                    self.frames.append((time.time(), d))
        except Exception:
            pass

    def close(self) -> None:
        self._ws.close()
        self._t.join(2)

    def texts(self) -> list[str]:
        return ["\n".join(f["lines"]) for _, f in self.frames]
