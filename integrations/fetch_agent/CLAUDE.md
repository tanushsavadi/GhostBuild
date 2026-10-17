<!-- Verbatim copy of docs/19_SPONSOR_AND_TRACK_STRATEGY.md appendix (incl. final amendments). If they differ, docs/19 wins. -->

## Appendix B: Devin brief: `integrations/fetch_agent/`

> **Goal.** A Fetch.ai uAgent (mailbox) that lets a remote supervisor run a GhostBuild physical job entirely from ASI:One. **Do not modify anything outside `integrations/fetch_agent/`. Do not import from `core/`, `perception/`, `contracts/`, `g2/` or `spatial/` at runtime** (tests may read `contracts/schema/*.json` and `contracts/examples/*.json`). GhostBuild is reached only over HTTP/WS at **`GB_CORE_URL`, which is required and has no default**. If it is unset, exit non-zero at startup with exactly `GB_CORE_URL is required; point it at the GhostBuild Core host.` Never fall back to localhost. (The agent runs on B's laptop; the hack-run value is e.g. `GB_CORE_URL=http://<MAC1-LAN-IP>:8787`. Tests set `GB_CORE_URL=http://localhost:8787` explicitly when mock core runs in the same VM.) Use only these locked interfaces (`docs/05` §2, §12, §13 and `docs/18_SPATIAL_TWIN_PASS_V3.md` §4.1):
> `GET /health` · `GET /knowledge/<task_id>` · one-shot `ws(s)://…/ws?role=twin` (read the snapshot sent on connect, then close) · `POST /control/task {task_id}` · `POST /control/reset {}` · `POST /control/goal {component}` (may 404 when spatial is off; handle it).
> **Never call `/control/ask`** (it would push answers onto the technician's glasses).
> 1. Follow the official ASI-compatible example (`uagents==0.25.5`, `chat_protocol_spec`, ack every `ChatMessage`, `publish_manifest=True`, `mailbox=True`, `publish_agent_details=True`).
> 2. A deterministic keyword router (no LLM): `inspect/check/status/why/fix|start/verify` → tools. "motor" or "rover" → task `rover-v1` + goal `c_motor`; otherwise `rocket-v1`.
> 3. Tools:
>    - `inspect_workspace`: per-component state with honesty labels from `spatial_state` / world `source` / `stale`;
>    - `get_plan`: next action + `why`;
>    - `explain_step`: `why` + evidence page/section from the bundle;
>    - `start_job`;
>    - `set_goal`;
>    - `get_status`: `plan.progress`, `plan.last_event`, the last 5 `twin.log` entries;
>    - `verify_outcome`: `plan.status == "verified"`.
> 4. **Mutating tools (`start_job`, `set_goal`) run only if env `GB_AGENT_ARMED=1` AND the user approved a `review` card in this session.** Otherwise reply with a card: "Workcell in demo-safe mode."
> 5. Interactive Cards per the official spec (`card_protocol_version "1"`, payload ≤ 64 KB, JSON-encoded): `custom` Workspace State, `review` Plan (approve/reject; parse the selection via `json.loads` with a text fallback), `custom` Job Progress, `custom` VERIFIED with `is_terminal`. No images.
> 6. Resilience: core unreachable → "Workcell offline (last seen …)". All network calls time out at 3 s. No exceptions escape the handler.
> 7. `sentry_sdk.init` (env `SENTRY_DSN`, optional), with one span per tool call named `tool.<name>`.
> 8. README: agent name + address placeholder, `![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)` and `![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)`, run instructions, and the ARMED switch.
> 9. Tests (`pytest`) against a running `core --mock-vision` with `GB_CORE_URL` set explicitly: the router, each tool's output shape, the ARMED gate (default off), the offline path, and the missing-`GB_CORE_URL` fail-fast message.
> 10. Env vars: `GB_CORE_URL` (required), `GB_AGENT_ARMED` (default `0`), `SENTRY_DSN` (optional), the agent seed. None in git.
> **Test command:** `cd integrations/fetch_agent && GB_CORE_URL=http://localhost:8787 pytest -q` (with `core --mock-vision scenarios/demo.yaml` running).
> **Done** = tests green in your VM + a PR whose diff touches only `integrations/fetch_agent/`.
> **Kill rule:** if the PR is not green at F1 (Sun 00:30), Fetch dies. No human rescue (except A after a spatial kill, §14).

