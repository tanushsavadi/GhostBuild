# Final sprint status

Updated Sun 2026-10-18 ~01:10 PDT by Claude Opus 5.5 (took over from Codex at its 00:05 usage-limit stop). Deadline Sun 12:00 PDT; Devpost by 10:30, final Beta QA 11:00.

## Where the work is
- Integration branch `codex/final-sprint` in `.worktrees/final-sprint` (ahead of `origin/lead/hw-pivot` `cd83f6a`). `git log --oneline` is the truth. Nothing pushed. `b/voice` / PR #2 not merged.
- Codex worker branches final-g2 / final-voice / final-creao are already cherry-picked. Leftover (not integrated): uncommitted `g2/package*.json` edits + `g2/sim-shots/` in the final-g2 worktree.

## Verification (label = strongest evidence we have)
| Capability | Label | Evidence |
|---|---|---|
| `make test` | PASS | core 501, pi 77, knowledge 253, assets 41, g2 183, lint-generic, secret scan; web `node --test web/tests/*.mjs` 17 (not in make) |
| CREAO live run | LIVE VERIFIED | agent GhostBuild Intelligence, app-scoped `POST /api/v1/apps/{appId}/runs` (docs.creao.ai), run `f255860d-...` completed in ~3 min (status `completed`); raw saved (gitignored) at `knowledge/requests/creao_raw/` |
| CREAO output -> playbook | LIVE VERIFIED | playbook is a JSON artifact (`result.artifacts[]`, S3 redirect, key not forwarded) -> `attach_json_artifacts` -> normalizer -> `validate_envelope` OK: 7 steps, 7 sources (4 official/manufacturer type), troubleshooting branches mapped |
| Human review + approval of that card | PENDING HUMAN | draft `pi_gpio_led_blink-20261018T080246` (gitignored `knowledge/drafts/`); needs `python -m knowledge.approve <id> --reviewer "<name>"` by a human. Reviewer edits are in `/tmp/gbv/review.py` (curated checks, guides attached, title shortened) |
| ElevenLabs STT | LIVE VERIFIED | `/ws/voice` with consent: spoken "Where exactly is that?" (macOS `say`, 16 kHz PCM) -> transcript exact in 0.55 s -> task-aware `rt.ask` -> HUD switched to `cup_fold_half/where.png` |
| ElevenLabs TTS | LIVE VERIFIED | `/voice/speak` consent=true, voice Matilda `XrExE9yKIg1WjnnlVkGX` (premade, chosen via ElevenLabs MCP; API key lacks `voices_read`): HTTP 200, valid MP3 6.2 s, 0.63 s |
| Phone playback | SIMULATOR VERIFIED | Chromium: text question -> `speak()` -> `Audio.play()` resolved, duration 6.3 s (the real MP3, network-intercepted so no extra quota). Audible output NOT confirmed |
| WHERE / HOW / CORRECT | SIMULATOR VERIFIED | API on paper_cup + the LED card: press/ask opens the right image for the current step; "Wait, where exactly is that?" -> `led_pins/where.png`; CORRECT tested; confirm from inside a picture = 409 |
| Stateful troubleshooting | MOCK/ENGINE TESTED | "that didn't work" walks current-step checks, then already-confirmed steps (most recent first), never repeats, then NO MORE CHECKS HERE; never confirms a step; 4 new tests |
| `.ehpk` | BUILT, NOT INSTALLED | `g2/ghostbuild.ehpk` (no mic permission; LAN `172.22.171.236:8787`) |
| Physical G2 | NOT RUN beyond Codex's report | operator reported (earlier session) LAN + QR + first frame + BUILD/FIX. Images, gestures, voice: awaiting operator |

## First-run flow (changed 01:30 PDT on operator feedback)
- No BUILD/FIX question. Glasses: welcome `WHAT DO YOU NEED?` -> first screen lists every startable task (`HOLD TO SPEAK OR PICK` when voice is on). Spoken or typed goals match across all tasks; build/fix is only a hint (core retries the other mode). Phone: one box, no toggle.
- A fault-mode card (needs live Pi telemetry) is offered only while the Pi reports; fixes "STALE DATA / CHECK LINK" on a bench with no Pi (operator saw it after pressing the old FIX default). SIMULATOR VERIFIED + tests (core 507); physical re-test pending.
- Dev-server QR sideload: Vite is run with `VITE_FLAG_VOICE=1`; whether the sideloaded app gets the microphone permission is UNVERIFIED (a missing permission degrades to `VOICE UNAVAILABLE / USE TOUCH`).

## Gestures (one meaning everywhere, changed 02:25 PDT after the operator's first physical session)
- Physical G2 evidence from the operator log: welcome, task list, press-to-start, swipes and picture requests reached core on real glasses (first step-through of paper_cup). Pain points found there: 1.5 s swipe dead zone, swipes meaning different things inside pictures, blank dead end after completion.
- Now: swipe down = next step (confirms a manual step; refuses a measured one), swipe up = back, press = picture button (WHERE -> HOW -> CORRECT -> back). Swipe from a picture: up = back to its step, down = confirm + next. First step shows immediately (no title card). Any gesture skips the welcome. After "ALL STEPS DONE" the next press/swipe-down opens the task list. Settle guard 600 ms (was 1500). Core 509 tests; still NOT re-tested on the glasses.

## Live research (03:10 PDT, on operator request)
- An unmatched spoken/typed request now researches live instead of "QUEUED FOR RESEARCH": glasses show `RESEARCHING m:ss / <task>` (5 s steps), the phone shows a thinking panel, then the guide starts by itself with `AI RESEARCHED, UNREVIEWED`. Phone banner: AI-RESEARCHED · NOT HUMAN-REVIEWED. Opt-in `GB_LIVE_RESEARCH=1` (now set in `.env`), cap `GB_LIVE_RESEARCH_MAX=3` per server start, one at a time, >=2 words, same request is served from the finished draft for free.
- LIVE VERIFIED (1 real CREAO run, push button on a Raspberry Pi, run r-fb9f9298): thinking screen ticked 0:00-5:00, run ~5 min, card auto-started (6 steps, 5 sources). The agent drew a PNG diagram; picture pipeline (SVG or PNG -> 288x144 G2 image + phone image, labelled AI-generated diagram, not a photo) verified OFFLINE on that real artifact and in tests, not yet re-run live end to end.
- Deliberate change to the earlier rule that only reviewed cards reach the glasses: these cards pass the same validator but are not human-reviewed; they stay drafts on disk and in memory only until a human approves.
- Tests: core 519, knowledge 257, assets 41, g2 184, web 18.

## Not done / blocked
- Physical G2 image + gesture + reconnect test (operator). Voice on G2 needs a voice-build `.ehpk` (`VITE_FLAG_VOICE=1`, declares g2-microphone) and a real device test.
- Human approval of the LED card (above). Hero hardware (Pi / breadboard / LED / 330 ohm) availability unconfirmed with the operator.
- Second live CREAO task: not run (the one authorized run is spent). Generality is shown with hand-authored paper_cup + pi_camera_setup + the researched LED card on the same engine.

## Services (Claude)
- Operator-facing: core `:8787` (from `.env`: GB_VOICE/GB_TTS/GB_CREAO on) and Vite `:5173`, LAN `172.22.171.236`. QR: `make g2-qr`.
- Claude test instances: core `:8793` (cards in `/tmp/gbv/cards`), static server `:8899`. Stale Codex processes (:8788/:8789/:8791/:5174) idle.

## Next executable actions
1. Operator: physical G2 steps; approve the LED card.
2. Claude: voice-build `.ehpk`; demo runbook + backup path; screenshots; Devpost text and sponsor evidence; freeze by ~10:00.
