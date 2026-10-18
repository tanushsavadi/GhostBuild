"""Local stand-in for ElevenLabs POST /v1/speech-to-text. Scripted per request; records what core sent."""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from email.parser import BytesParser
from email.policy import HTTP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


@dataclass
class Reply:
    text: str | None = ""
    status: int = 200
    body: bytes | None = None  # raw body overrides `text`
    delay: float = 0.0


@dataclass
class Seen:
    headers: dict
    fields: dict
    file: bytes
    at: float = field(default_factory=time.time)


class FakeSTT:
    def __init__(self) -> None:
        self.script: deque[Reply] = deque()
        self.default = Reply(text="")
        self.requests: list[Seen] = []
        self._lock = threading.Lock()
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a) -> None:
                pass

            def do_POST(self) -> None:
                raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                msg = BytesParser(policy=HTTP).parsebytes(
                    f"Content-Type: {self.headers.get('Content-Type')}\r\n\r\n".encode() + raw)
                fields, file = {}, b""
                for part in msg.iter_parts() if msg.is_multipart() else []:
                    name = part.get_param("name", header="content-disposition")
                    payload = part.get_payload(decode=True) or b""
                    if name == "file":
                        file = payload
                    else:
                        fields[name] = payload.decode()
                with fake._lock:
                    fake.requests.append(Seen({k.lower(): v for k, v in self.headers.items()}, fields, file))
                    reply = fake.script.popleft() if fake.script else fake.default
                if reply.delay:
                    time.sleep(reply.delay)
                body = reply.body if reply.body is not None else json.dumps({"text": reply.text}).encode()
                try:
                    self.send_response(reply.status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_port}/v1/speech-to-text"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self) -> FakeSTT:
        self.thread.start()
        return self

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def say(self, text: str | None = "", **kw) -> None:
        """Queue the next transcript (or error via status/body/delay)."""
        self.script.append(Reply(text=text, **kw))
