"""Non-blocking Observation sender: POST ${core}/observation, 1 retry max, bounded queue, backoff.

The sender thread never raises into the capture loop. When the core is down it keeps running and
drops old observations rather than queueing them (delivering stale observations later would be
worse than losing them).
"""

from __future__ import annotations

import json
import logging
import threading
from collections import deque
from typing import Any, Callable, Deque, Dict, Optional

from .clock import Clock

log = logging.getLogger("ghostbuild_pi.client")

PostFn = Callable[[str, bytes, float], int]  # (url, body, timeout_s) -> http status; raises on transport error


def normalize_core_url(core: str) -> str:
    core = core.strip().rstrip("/")
    if "://" not in core:
        core = "http://" + core
    return core


def default_post(url: str, body: bytes, timeout_s: float) -> int:
    headers = {"Content-Type": "application/json"}
    try:
        import httpx  # type: ignore
    except ImportError:
        import urllib.error
        import urllib.request

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code
    return httpx.post(url, content=body, headers=headers, timeout=timeout_s).status_code


def default_get(url: str, timeout_s: float):
    """Returns (status, text). Raises on transport error. Used by tools/spike.py."""
    try:
        import httpx  # type: ignore
    except ImportError:
        import urllib.error
        import urllib.request

        try:
            with urllib.request.urlopen(url, timeout=timeout_s) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, ""
    r = httpx.get(url, timeout=timeout_s)
    return r.status_code, r.text


class ObservationClient:
    def __init__(self, core_url: str, clock: Optional[Clock] = None, post: Optional[PostFn] = None,
                 timeout_s: float = 1.0, max_queue: int = 8, max_age_ms: float = 2000.0,
                 backoff_start_s: float = 0.5, backoff_max_s: float = 5.0, log_every_s: float = 10.0):
        self.url = normalize_core_url(core_url) + "/observation"
        self.clock = clock or Clock()
        self._post = post or default_post
        self.timeout_s, self.max_age_ms = timeout_s, max_age_ms
        self.backoff_start_s, self.backoff_max_s, self.log_every_s = backoff_start_s, backoff_max_s, log_every_s
        self._q: Deque = deque(maxlen=max_queue)
        self._cv = threading.Condition()
        self._stop = False
        self._thread: Optional[threading.Thread] = None
        self._backoff_until_ms = 0.0
        self._backoff_s = backoff_start_s
        self._last_log_ms = -1e18
        self.sent = self.failed = self.dropped = 0
        self.last_error: Optional[str] = None

    # public -------------------------------------------------------------
    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="obs-sender", daemon=True)
        self._thread.start()

    def submit(self, obs: Dict[str, Any]) -> None:
        """Never blocks. If the queue is full the oldest entry is dropped."""
        with self._cv:
            if len(self._q) == self._q.maxlen:
                self.dropped += 1
            self._q.append((self.clock.now_ms(), obs))
            self._cv.notify()

    def stop(self, flush_timeout_s: float = 1.0) -> None:
        with self._cv:
            self._stop = True
            self._cv.notify_all()
        if self._thread:
            self._thread.join(timeout=flush_timeout_s)

    def stats(self) -> Dict[str, Any]:
        return {"sent": self.sent, "failed": self.failed, "dropped": self.dropped, "last_error": self.last_error}

    # internals ----------------------------------------------------------
    def _run(self) -> None:
        while True:
            with self._cv:
                while not self._q and not self._stop:
                    self._cv.wait(timeout=0.5)
                if self._stop and not self._q:
                    return
                queued_at, obs = self._q.popleft()
            self.process_one(queued_at, obs)

    def process_one(self, queued_at_ms: float, obs: Dict[str, Any]) -> bool:
        """Deliver one observation (testable without the thread)."""
        now = self.clock.now_ms()
        if now - queued_at_ms > self.max_age_ms or now < self._backoff_until_ms:
            self.dropped += 1
            return False
        body = json.dumps(obs, separators=(",", ":")).encode("utf-8")
        err: Optional[str] = None
        for attempt in range(2):  # first try + 1 retry max
            try:
                status = self._post(self.url, body, self.timeout_s)
            except Exception as e:
                err = "%s: %s" % (type(e).__name__, e)
                continue
            if 200 <= status < 300:
                self.sent += 1
                self._backoff_s = self.backoff_start_s
                if self.last_error:
                    log.info("core reachable again at %s", self.url)
                self.last_error = None
                return True
            err = "HTTP %d" % status
            if 400 <= status < 500:
                break  # our payload was rejected; retrying the same bytes will not help
        self.failed += 1
        self.last_error = err
        self._backoff_until_ms = self.clock.now_ms() + self._backoff_s * 1000.0
        self._backoff_s = min(self._backoff_s * 2.0, self.backoff_max_s)
        t = self.clock.now_ms()
        if t - self._last_log_ms >= self.log_every_s * 1000.0:
            self._last_log_ms = t
            log.warning("POST %s failed (%s); backing off, will keep running", self.url, err)
        return False


class Recorder:
    """Append each observation as one JSON line (for --replay)."""

    def __init__(self, path: str):
        import os

        d = os.path.dirname(os.path.abspath(path))
        os.makedirs(d, exist_ok=True)
        self._f = open(path, "a", encoding="utf-8")

    def write(self, obs: Dict[str, Any]) -> None:
        self._f.write(json.dumps(obs, separators=(",", ":")) + "\n")
        self._f.flush()

    def close(self) -> None:
        try:
            self._f.close()
        except Exception:
            pass
