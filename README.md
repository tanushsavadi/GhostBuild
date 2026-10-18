# GhostBuild

> **v2 (Sat 2026-10-17 evening):** GhostBuild guides a hands-on build on Even G2 one step at a time and verifies what a test jig can measure. **[`CLAUDE.md`](CLAUDE.md) is the execution authority**; `docs/PIVOT_GHOSTBUILD.md` and everything below are historical and being rewritten.

An AI copilot for physical work: it reads the manual and the CAD, watches the real object, and shows one verified next action on Even G2 — going dark when the work matches the target.

**Team:** read [`START_HERE.md`](START_HERE.md), then [`docs/20_FINAL_IMPLEMENTATION_BIBLE.md`](docs/20_FINAL_IMPLEMENTATION_BIBLE.md) and [`docs/21_HACKATHON_CHECKLIST.md`](docs/21_HACKATHON_CHECKLIST.md). Contracts: [`docs/05_CONTRACTS.md`](docs/05_CONTRACTS.md).

## Developer quick start

Prerequisites: `uv` (Python 3.11 is pinned in `pyproject.toml`), Node ≥ 20, git. Lane extras: B — `npm i -g @evenrealities/evenhub-cli @evenrealities/evenhub-simulator` and a phone with the Even app; C — Arduino IDE or `arduino-cli`. No iOS app or Xcode is part of this project.

| Question | Command | Green means |
|---|---|---|
| Is my environment working? | `make setup && make doctor` | every line under "everyone" is `ok` |
| Are contracts valid? (**the 12:45 lock check**) | `make contracts` | `GREEN python …` and `GREEN ts …` |
| Can core start? | `make core` | `make health` shows core `/health` JSON |
| Can the mock path run? | `make core-mock` | HUD frames reach `make g2-sim` / `/twin?mode=2d` |
| Can tests run? | `make test` | contracts + lints + every existing lane's pytest/vitest pass |
| Any secret about to be committed? | `make check-secrets` | `check-secrets: ok` |

Targets for lanes that don't exist yet stop with `not yet: <path> missing (owner X)`. Run `make help` for the full list.

Secrets: copy `.env.example` to `.env` (gitignored) only for the keys your lane uses. `GB_CORE_URL` has no default by design.

### Contract lock (D, Sat 12:45)
`make contracts` runs `contracts/tools/lock_check.py` (export JSON Schema from `contracts/models.py`, validate every `contracts/examples/*.json`) and then `contracts/ts` (generate `index.ts`, validate the same examples with ajv, typecheck). It is red until all of these exist:
- `contracts/models.py` defining `SCHEMAS = {name: Model}` and `FIXTURES = {"<filename glob>": name}`;
- `contracts/examples/`: `observation_*.json`, `hud_*.json`, `g2_input_*.json`, `state_*.json`, `card_barrier.json` (docs/PIVOT_GHOSTBUILD.md §5.3).

Commit the generated `contracts/schema/` and `contracts/ts/index.ts`: B (G2 plugin) and A (phone page) read them without running Python.

## Service map

| Service | Owner | Machine | Port / endpoint | Consumes → produces | Env | Health check |
|---|---|---|---|---|---|---|
| core | D | Mac 1 | `:8787` HTTP + `ws?role=vision\|g2\|twin`, `/control/*`, `/knowledge/*`, `/twin` | observation, g2_input → hud, twin, `logs/session-*.jsonl` | — | `curl http://<mac1>:8787/health` |
| perception | C | Mac 1 | client of `ws://localhost:8787/ws?role=vision` | webcam → observation (`source: cv`) | — | `/health` `vision_fps` > 0 |
| G2 plugin | B | B's laptop (dev) → Even app on the phone → G2 | Vite `:5173`; client of `ws://<mac1>:8787/ws?role=g2` or Funnel `wss://<laptop>.<tailnet>.ts.net` | hud → display; menu/tap → g2_input | — | `/health` `g2_connected`; `make g2-sim` |
| 2D supervisor | B | served by core, shown on Mac 2 | `http://<mac1>:8787/twin?mode=2d` | twin → page | — | `/health` `twin_clients` |
| knowledge compiler | D | any Mac, build time only | — | PDF + LDraw → committed `knowledge/<task>/bundle.json` | `ANTHROPIC_API_KEY` | `make compile` exits 0 |
| Sentry bridge (optional) | Devin → B | Mac 1, `nice 19` | — (reads logs) | `logs/session-*.jsonl` → Sentry Tracing + Logs | `SENTRY_DSN` | `--dry-run` prints spans; trace visible in Sentry |
| Fetch agent (optional) | Devin → B | B's laptop | — (Agentverse mailbox) | ASI:One ↔ core `GET /health`, `/knowledge`, one-shot `ws?role=twin`; ARMED-only `POST /control/task\|reset\|goal` | `GB_CORE_URL` (required), `GB_AGENT_ARMED=0`, `AGENT_SEED`, `SENTRY_DSN` (opt.) | starts without exiting; answers in ASI:One |

`make health` probes core and `:5173` (set `CORE=http://<mac1>:8787 G2=<b-laptop>` from another machine).

## Git workflow

- `main` is the integration branch and must always run P0 (`make test` green before merging).
- Short-lived branches per owner/task, merged within hours: `a/web`, `b/g2`, `c/firmware`, `d/core`. Rebase on `main` before merging; small PRs.
- **Ownership = merge rights:** `contracts/` — only D merges (after 12:45, a shared-schema change also needs every consuming owner's OK in team chat; none after Sun 00:45). `integrations/*` — B lands Devin PRs; the diff must touch only its own directory.
- **Merge hotspots:** `contracts/` (D only) · `Makefile` (add your lane's target in its own small commit) · `pyproject.toml` / `uv.lock` (one dependency change at a time; after a rebase run `uv lock`, never hand-merge the lockfile) · `README.md`, `CLAUDE.md` (A or D) · `docs/` (frozen; B edits only `docs/sentry_findings.md`) · `scenarios/`, `knowledge/fixtures/` (D).
- Freezes: P0 freeze Sun 02:00 (nothing merges into the P0 path), product feature freeze 04:00 (bugs and rehearsal only; the isolated Fetch exception is the only feature work).
