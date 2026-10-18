# Phone companion (`/phone`)

Static HTML+CSS+JS, no build step, no external requests. Core serves this folder at `/phone`
(and should serve `knowledge/guides/` at `/guides/`, including `<view>.phone.png` and `manifest.json`).

* Live: open `http://<core>:8787/phone` on the phone (same Wi-Fi). It polls `GET /state` at 1 Hz, `GET /card` on card change,
  and posts `POST /session/goal` (`GoalRequest`, `via: phone_text`).
* Page on another origin: `?core=http://<laptop-ip>:8787` (core must then send CORS headers).
* No backend (fixtures): from the repo root run `python3 -m http.server 8000` and open
  `http://localhost:8000/web/dev.html?fixture=1` (or `?fixture=state_visual|state_healthy|state_verified|state_simulated|state_pi_down|state_menu`).
  The page then shows a FIXTURE banner and never a plain LIVE badge. The dev bar can simulate a core outage / stale data.
* Fixtures in `web/fixtures/` are valid contract messages (checked by `assets/tests/test_web_fixtures.py`).
* Screenshots: `web/screens/`.
