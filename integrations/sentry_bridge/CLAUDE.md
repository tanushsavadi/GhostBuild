<!-- Verbatim copy of docs/19_SPONSOR_AND_TRACK_STRATEGY.md appendix (incl. final amendments). If they differ, docs/19 wins. -->

## Appendix A: Devin brief: `integrations/sentry_bridge/`

> **Goal.** A standalone Python 3.11 process that tails GhostBuild's newest `logs/session-*.jsonl` (read-only) and sends Sentry data. **Do not modify anything outside `integrations/sentry_bridge/`. Do not import from `core/`, `perception/` or `contracts/` at runtime** (you may read `contracts/schema/*.json` in tests).
> 1. First run `core --mock-vision scenarios/demo.yaml` (see `docs/04` §3) to produce a real session log, and inspect its records before writing the parser.
> 2. `sentry_sdk.init(dsn=env SENTRY_DSN, traces_sample_rate=1.0, enable_logs=True, environment="hackathon")`. Pin the SDK version and confirm the API for explicit span start/end timestamps in that version.
> 3. For every `hud` record whose `line1` differs from the previous one, emit transaction `glasses_instruction`. Spans: `vision.process` (observation `timing.capture_ts_ms` → observation `ts_ms`), `core.vote` (first observation with the new component state → the `world` commit), `core.plan_arbiter` (`world` → `hud`), `g2.ble_render` (duration = matching `hud_ack.bridge_ms`). Attributes: `hud.line1`, `mode`, `alert`, `plan.last_event.kind`, `source`, `task_id`. Skip spans whose inputs are missing; never guess.
> 4. Sentry Logs (info): every HUD instruction, every `plan.last_event` ≠ none, every `turn` (intent, basis, citation ids), and every `status ∈ {uncertain, occluded, no_board}` or `mode ∈ {hold, uncertain}` transition.
> 5. Sentry Issues: `hud_ack.result ≠ "ok"`, and any record type `error`.
> 6. Flags: `--log PATH` (default: newest file), `--from-start`, `--dry-run` (print JSON instead of sending). Handle file rotation. Exit cleanly on SIGINT. CPU < 2% at 10 Hz observations.
> 7. Tests (`pytest`): a fixture log produces the expected transaction/span/log counts in `--dry-run`.
> 8. Env vars: `SENTRY_DSN` (required unless `--dry-run`). None in git.
> **Test command:** `cd integrations/sentry_bridge && pytest -q`.
> **Done** = tests green in your VM, plus a PR whose diff touches only `integrations/sentry_bridge/`, with a README (run command, env vars, what each signal means).
> **Kill rule:** if the PR is not green when B lands it (Sat 22:00), B hand-builds the 2-product minimum inside 22:00–22:30 or Sentry dies at 23:00. No other human rescue.
