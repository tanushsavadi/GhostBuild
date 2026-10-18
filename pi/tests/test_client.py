import http.server
import json
import threading

from ghostbuild_pi.client import ObservationClient, Recorder, normalize_core_url
from ghostbuild_pi.clock import FakeClock

OBS = {"v": 2, "dev": "pi-01", "seq": 1, "ms": 1, "at": 1, "source": "simulated", "camera": None, "led": None,
       "error": "camera_open_failed"}


def test_normalize():
    assert normalize_core_url("192.168.1.2:8787/") == "http://192.168.1.2:8787"
    assert normalize_core_url("https://x/") == "https://x"


def test_connection_error_never_raises_and_retries_once():
    calls = []

    def post(url, body, timeout):
        calls.append(url)
        raise ConnectionError("refused")

    clock = FakeClock()
    c = ObservationClient("http://core:8787", clock=clock, post=post)
    assert c.process_one(clock.now_ms(), OBS) is False
    assert calls == ["http://core:8787/observation"] * 2  # first try + exactly 1 retry
    assert c.failed == 1 and "ConnectionError" in c.last_error


def test_backoff_drops_instead_of_hammering_then_recovers():
    state = {"up": False, "n": 0}

    def post(url, body, timeout):
        state["n"] += 1
        if not state["up"]:
            raise ConnectionError("down")
        return 200

    clock = FakeClock()
    c = ObservationClient("http://core", clock=clock, post=post)
    c.process_one(clock.now_ms(), OBS)
    n_after_first = state["n"]
    clock.advance(100)
    c.process_one(clock.now_ms(), OBS)  # inside backoff window
    assert state["n"] == n_after_first and c.dropped == 1
    state["up"] = True
    clock.advance(5000)
    assert c.process_one(clock.now_ms(), OBS) is True and c.sent == 1 and c.last_error is None


def test_stale_observations_are_dropped_not_delivered():
    sent = []
    clock = FakeClock()
    c = ObservationClient("http://core", clock=clock, post=lambda u, b, t: sent.append(b) or 200, max_age_ms=2000)
    queued = clock.now_ms()
    clock.advance(2500)
    assert c.process_one(queued, OBS) is False and not sent and c.dropped == 1


def test_4xx_is_not_retried_and_counts_as_failure():
    n = []
    c = ObservationClient("http://core", clock=FakeClock(), post=lambda u, b, t: n.append(1) or 422)
    assert c.process_one(c.clock.now_ms(), OBS) is False and len(n) == 1 and c.last_error == "HTTP 422"


def test_queue_is_bounded_and_submit_never_blocks():
    c = ObservationClient("http://core", clock=FakeClock(), post=lambda *a: 200, max_queue=4)  # not started
    for i in range(100):
        c.submit(dict(OBS, seq=i))
    assert len(c._q) == 4 and c.dropped == 96
    assert [o["seq"] for _, o in c._q] == [96, 97, 98, 99]


def test_end_to_end_against_local_http_server_and_unreachable_port():
    got = []

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            got.append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        c = ObservationClient("http://127.0.0.1:%d" % srv.server_port)
        c.start()
        c.submit(OBS)
        c.stop(flush_timeout_s=3)
        assert got == [("/observation", OBS)] and c.sent == 1
    finally:
        srv.shutdown()
    dead = ObservationClient("http://127.0.0.1:1")  # nothing listens here
    dead.start()
    dead.submit(OBS)
    dead.stop(flush_timeout_s=3)
    assert dead.sent == 0 and dead.failed >= 1


def test_recorder_writes_jsonl(tmp_path):
    p = tmp_path / "sub" / "r.jsonl"
    r = Recorder(str(p))
    r.write(OBS)
    r.write(dict(OBS, seq=2))
    r.close()
    lines = p.read_text().splitlines()
    assert [json.loads(l)["seq"] for l in lines] == [1, 2]
