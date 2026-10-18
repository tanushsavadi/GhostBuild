# Final sprint status

Updated Sun 2026-10-18 00:20 PDT by Claude Opus 5.5 (took over from Codex at its 00:05 usage-limit stop). Deadline Sun 12:00 PDT; Devpost by 10:30, final Beta QA 11:00.

## Where the work is
- Integration branch: `codex/final-sprint` in `.worktrees/final-sprint` (8 commits ahead of `origin/lead/hw-pivot` `cd83f6a`, plus Codex's WIP checkpoint `4c20d5e`, plus Claude commits after it). `git rev-parse HEAD` is the truth.
- `codex/final-g2`, `codex/final-voice`, `codex/final-creao` worker commits are already cherry-picked into final-sprint. Only leftover: uncommitted `g2/package*.json` edits + `g2/sim-shots/` in the final-g2 worktree (not integrated; inspect before using).
- Nothing pushed. `lead/hw-pivot` and all other worktrees untouched. Do not merge `b/voice` or PR #2 wholesale.

## Verified (2026-10-18 00:11-00:20, this commit lineage)
| Item | Result | Evidence |
|---|---|---|
| `make test` | PASS | contracts, lint-generic, secret scan ok; core 496, pi 77, knowledge 250, assets 41, g2 tsc + vitest 183 |
| `node --test web/tests/*.mjs` | PASS 17/17 | NOT part of `make test` (run manually) |
| Phone page `/phone/` in real Chromium (390x844) | PASS | renders; paper_cup chosen from catalog; mirror, step detail, sources, Q&A, voice toggle present; only console error = favicon 404 |
| Playbook engine via API (paper_cup) | PASS | manual confirm advances; press opens WHERE then HOW pictures; confirm from inside a picture refused 409; steps with `guide_id` serve PNGs |
| Guide images | PASS (visual) | `knowledge/guides/cup_*` diagrams legible, labeled "ORIGINAL DIAGRAM - SOURCE LINK ON PHONE" |
| `.ehpk` package | BUILT, NOT INSTALLED | `g2/ghostbuild.ehpk` 48402 B; whitelist `172.22.171.236:8787`; mic permission NOT declared (voice flag off) |

## Not verified
- **Physical G2**: operator reported (Codex session) phone LAN access + QR launch + GHOSTBUILD -> BUILD/FIX menu. Images, gestures, `.ehpk` install, voice, Beta: NOT RUN.
- **CREAO live run**: NOT RUN. `CREAO_API_KEY` absent (no `.env`, none in environment). Adapter uses `appId` key per Codex fix `82b448d`; only mock-tested.
- **ElevenLabs STT/TTS live**: NOT RUN. `ELEVENLABS_API_KEY` absent. Only browser fakes / unit tests.
- Pi camera/LED: not touched (P2).

## Authorizations on record (from earlier sprint prompt)
ONE CREAO research run, ONE short STT, ONE short TTS once local keys exist. Do not retry ambiguous paid starts.

## Services (Claude)
- Core test instance: `:8790`, log `/tmp/gb-core-8790.log`, event log `/tmp/gb-claude-logs`. For G2 the backend must be `:8787` on LAN `172.22.171.236` (the `.ehpk` whitelist). Run from the worktree: `PYTHONPATH=$PWD:$PWD/core:$PWD/pi uv run python -m ghostbuild_core --port 8787` (or `make core`).
- Leftover Codex processes (vite :5174, core :8789 / :8791, a Playwright daemon) are idle and can be killed.

## Next executable actions
1. Human: create gitignored `.env` in `.worktrees/final-sprint` with `CREAO_API_KEY`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `GB_ADMIN_TOKEN`; flags `GB_CREAO=1 GB_VOICE=1 GB_TTS=1`.
2. Human: start core on :8787, install `g2/ghostbuild.ehpk` (or QR from `make g2-dev`) and report first image/gesture results.
3. Claude: one bounded live CREAO run -> normalize -> human approve -> second non-paper-cup task through the same engine.
4. Claude: one STT + one TTS live check; voice build (`VITE_FLAG_VOICE`) re-pack with microphone permission.
5. Demo runbook, screenshots, Devpost checklist.

## Cut order if behind
P2 (Pi sensor, extra visuals, always-listening) first, then live voice (touch/text fallback stays), then live CREAO (cached approved cards stay).
