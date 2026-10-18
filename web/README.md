# Phone companion (`/phone`)

Static HTML+CSS+JS, no build step, no external requests. Core serves this folder at `/phone`
(and should serve `knowledge/guides/` at `/guides/`, including `<view>.phone.png` and `manifest.json`).

* Live: open `http://<core>:8787/phone` on the phone (same Wi-Fi). It polls `GET /state` at 1 Hz, `GET /card` on card change,
  and posts `POST /session/goal` (`GoalRequest`, `via: phone_text`), `POST /ask` and `POST /research/request`.
* Page on another origin: `?core=http://<laptop-ip>:8787` (core must then send CORS headers).
* No backend (fixtures): from the repo root run `python3 -m http.server 8000` and open
  `http://localhost:8000/web/dev.html?fixture=1` (or `?fixture=state_visual|state_healthy|state_verified|state_simulated|state_pi_down|state_menu`).
  The page then shows a FIXTURE banner and never a plain LIVE badge. The dev bar can simulate a core outage / stale data.
* Fixtures in `web/fixtures/` are valid contract messages (checked by `assets/tests/test_web_fixtures.py`).
* Screenshots: `web/screens/`.

## Playbook panel (State.playbook + GET /card)

* Shown when `State.playbook` is present: step list with the current step highlighted, badge per step (`HUMAN CONFIRMED` / `MEASURED` / `pending`), the current step's cue, full `detail`, warnings, why/where, FAQ, troubleshoot `CHECK` items with cites (a video cite shows its `t=` timestamp and deep link), guide pictures (placeholder badges as before) and sources with kind badges (`WEB TUTORIAL`, `VIDEO TUTORIAL`, `GITHUB SOURCE`, `MANUFACTURER DOC`, ...). Card provenance is shown in words: `AUTHORED DEMO METADATA` (not extracted from the sources) vs `AI-EXTRACTED · HUMAN-REVIEWED`.
* The glasses mirror shows step frames with the small counter (`3/8`, bullet for a measured step, `OK` when confirmed).
* Pi rows/banners appear only when the link is not down or the active card uses telemetry (fault tests or a step with `verify`); a manual playbook works with no Pi and never shows a Pi banner (`logic.js`, unit-tested from `g2/tools/web-logic.test.mjs`).
* Ask box: `POST /ask {session_id, text}` -> `{answer:{line1,line2}|null, text, intent}`. A 404 is shown as `ASK NOT AVAILABLE`, never as an answer.
* Research box: `POST /research/request {session_id, mode, text}` -> `GoalResolution`. Only ever shows `saved for async research - not available now` (or that nothing was saved).
* Playbook fixtures: `?fixture=state_playbook_manual|state_playbook_measured|state_playbook_completed|state_playbook_unsupported` (cards `card_<card_id>.json` are loaded by `State.card_id`). The dev bar can simulate a 404 on `/ask` and `/research/request`. Fixture ask/research/goal answers are labelled `FIXTURE RESPONSE`.
