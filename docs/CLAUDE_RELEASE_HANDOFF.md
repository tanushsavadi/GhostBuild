# Claude takeover: finish the GhostBuild release

**Handoff requested by the user at approximately 07:13 PDT, October 18, 2026.** Codex stopped release work and wrote this document. Continue the original release task; do not restart the audit or rebuild completed work.

**Deadline:** today at 12:00 PM Pacific. Internal target: Devpost by 10:30 AM, final physical rehearsal by 11:00 AM. Read the actual current time when resuming.

## 1. Start in the correct checkout

```sh
cd /Users/tanushsavadi/Documents/Hackathons/LA_Hacks/.worktrees/final-sprint
```

This is the integration worktree. The repository root is a DIFFERENT checkout on `lead/hw-pivot`; do not implement the release there.

Read this document, `docs/PIVOT_GHOSTBUILD.md` §0A including its final-release amendment, `docs/FINAL_SPRINT_STATUS.md`, and applicable AGENTS/CLAUDE instructions. The user's latest release request authorizes commit, push, PR creation and normal protected-workflow merge to main. It explicitly permits the current optional live source compiler; old blanket prohibitions on runtime compilation are superseded by the final-release amendment. Evidence honesty and device limits still apply.

Preserve every existing worktree and contribution. Never reset, force-push, broadly merge unrelated branches, or expose credentials. Keys remain in ignored `.env`; do not print it. Root-level untracked agent configuration and `skills-lock.json` belong to existing environment work and were left alone.

## 2. Exact Git state at handoff

| Ref | Exact commit / state |
|---|---|
| Local `codex/final-sprint` | `d5257c65926e69014a1bcfa49026414fb3f8556a` |
| Remote `origin/codex/final-sprint` | `4cab4ef5eb0a3e7783716889a16b2a82302cedf2` — independently confirmed with `git ls-remote` |
| Remote `main` | `7ccd064b50647b9547ee5705a0a3c6792958aa27` — unchanged, release NOT merged |
| Local integration cleanliness | Clean before writing this handoff. This handoff itself is intentionally uncommitted. |
| Latest local-only commit | `d5257c6`: fresh voice-provider results and accurate README/submission limits; needs pushing. |
| Temporary object-transfer branch | `codex/release-transfer-20261018`, tip `7336cfecdc7719de993ccb16390eb80d390f8314`. **NEVER MERGE THIS BRANCH.** See transport note below. |

The upload of `4cab4ef` finished just before handoff; it succeeded. There is no running Codex Git upload to resume or cancel. All subagents completed. No new release PR was successfully created, and no CI/main merge was claimed.

Existing open PRs when inspected:

- [#1](https://github.com/tanushsavadi/GhostBuild/pull/1): old `lead/hw-pivot` → main integration. The final-sprint history contains this work and substantially more.
- [#2](https://github.com/tanushsavadi/GhostBuild/pull/2): `devin/b-voice-reliability` → `b/voice`, not the final integration.

Create a release PR from **codex/final-sprint → main** after pushing the last documentation commit/handoff as desired. Do not merge #1's older scope in place of the new release. A prepared PR body exists at `/tmp/ghostbuild-release-pr.md`; update its stale test counts/voice status before use.

Last repository-policy checks: main protection endpoint returned 404 “Branch not protected”; repository rulesets were empty; merge commits are allowed. Recheck before merging. Repository is currently **private**; no visibility change was authorized or performed. Devpost's public-source/judge-access requirement remains a human decision/action.

### HTTPS upload workaround — already completed

Large Git HTTPS posts repeatedly failed with HTTP 408, even per-commit at the large MICKE asset commit. SSH authentication was unavailable. We preserved all original commits and authors and preloaded their **existing blob objects** through 26 small pushes on the temporary transfer branch. The final push of the actual integration history then succeeded normally. No release history was rewritten.

The temporary branch contains transport-only commits with hash-named blobs and is NOT an application tree. Do not cherry-pick or merge it. The real release branch is `codex/final-sprint`. Once the release is safely on remote main, the temporary branch created for this session can be removed if appropriate; do not delete any pre-existing teammate branches.

Local transport notes, only if needed:

- `/tmp/ghostbuild-transfer-state.json`
- `/tmp/ghostbuild-transfer-existing-objects.py`
- `/tmp/ghostbuild-transfer-uploads.log`
- `/tmp/ghostbuild-release-push-batch.log`

The next push contains only small documentation changes and should not need that workaround again.

## 3. Commits already integrated — do not cherry-pick twice

Newest first:

- `d5257c6` — bounded fresh ElevenLabs results and submission limits (local only).
- `4cab4ef` — explicit ready-guide selection exits discovery; prepared AI review warning; final status/acceptance documentation.
- `e816740` — generic answer/model/product correction repair, 28 initial regression cases and live correction evidence.
- `3f5d7d3` — bundle original Mac diagrams and reproducible source assets; clean-clone portability tests.
- `1a71abf` — reliable setup, phone tests in make, CI/package workflow, stale task-caption fix and correct simulator gestures.
- `ae35f60` — live demo runbook, 120-second video plan, official track/prize curation and Devpost copy.
- `627efa7` — public README story, accurate architecture/setup and safe environment example.
- Prior implementation baseline: `65ce651`, plus the existing sprint history.

Isolated contributor worktrees remain under `.worktrees/release-story`, `.worktrees/release-demo`, `.worktrees/release-qa`; their completed changes are already cherry-picked. Earlier final-g2/final-voice/final-creao work was already integrated before this session.

`origin/test_sim` and related teammate history diverged into a different Open Palm/ASL application. It was intentionally NOT merged into GhostBuild. Preserve it separately. Do not infer final GhostBuild team roles from those branches. The final integration Git history currently attributes commits to Tanush Savadi; human team/provenance confirmation is still needed for Devpost.

## 4. What was fixed

Everything remains generic, driven by card data:

- A correction cue plus a changed answer to a question already on the route reroutes from that question.
- Uncertain corrections reopen that question instead of selecting a guessed configuration. “Tubeless ready” alone does not establish the actual setup.
- Ruled-out clauses such as “the external monitor looks fine” do not select that object. Affirmative outcome answers such as “It looks normal now” still work.
- New product/model identity removes incompatible guide steps and pictures. Negated old models do not mask the new model. Units/ordinals are not mistaken for models.
- Cache reuse cannot bypass a model conflict, including MK3S versus MK3S+ collisions in older cache keys.
- Rerouting clears stale downstream question observations AND question confirmations, including after backtracking. Completed physical action confirmations remain recorded. Back follows the new route.
- Correction cancels stale assistant work and increments the task revision.
- Choosing an exact prepared-guide title leaves unfinished product discovery; the ready-guide control no longer gets consumed as a product refinement.
- Phone task changes no longer retain the previous task's guide caption.
- Prepared AI guides now show **AI-ASSISTED · NOT HUMAN-REVIEWED** even without a live research record. No false claim that a cached compile was researched live.
- Three original Mac menu-path diagrams now ship from tracked `knowledge/guides/`, with originals/annotations in `assets/sources/`. They are labelled drawings, not screenshots.
- Fourteen third-party bike/Prusa views remain optional ignored local caches with honest source-link/text fallback. No new third-party photos were committed to make tests pass.
- `make setup` uses frozen dependencies and no longer swallows npm failures. `make test` now includes phone tests. New GitHub Actions workflow validates and builds a portable package.

## 5. Fresh checks actually completed

Final combined `make test` passed on the integration code:

- **1,161 Python tests:** core 688; Pi 77; knowledge 267; assets 41; IKEA 88.
- **32 phone tests**, **208 G2 Vitest tests**.
- Nine schemas exported, 22 Python examples and 22 TypeScript examples valid.
- TypeScript checking, generic-boundary lint, secret-pattern scan and `git diff --check` passed.
- Knowledge tests emit six existing PyMuPDF/Pillow deprecation warnings.
- Latest secret-pattern scan covered 893 entries. It is NOT a full historical-secret audit.
- `make setup`, fresh frozen Python bootstrap, `make doctor`, CLI helps and both package builds passed. Optional tailscale is absent; it is not required for the cached LAN demo.
- 59 relative documentation/image targets checked, zero missing. Recheck if moving documents.

Logs:

- `/tmp/ghostbuild-release-combined-tests.log` — final full suite.
- `/tmp/ghostbuild-release-final-tests.log`, `/tmp/ghostbuild-release-corrections-tests.log` — earlier integrated runs.
- `/tmp/ghostbuild-release-doctor.log`.
- `docs/evidence/release/VERIFICATION.md` — baseline QA scope, dependency advisories and final follow-up. Baseline counts differ from the final counts above.

**Remote CI has not run yet for this release PR, because the PR does not exist.** Workflow `.github/workflows/verify.yml` runs on pull requests and pushes to main, not arbitrary integration-branch pushes. It uses Ubuntu, Python3.11/uv, Node22, frozen npm/uv installs, make test and `npm run pack`, uploading `ghostbuild-g2`. It passed local actionlint, but do not claim Ubuntu execution until GitHub reports it.

### Browser and official simulator

- Official simulator: 15 checkpoints through two actual generic cards; three successful SDK image sends; contextual help/return; HUMAN CONFIRMED completion; final quiet frame with zero lit pixels. Simulator inputs do not prove physical task completion.
- Fresh Chromium desktop/mobile: no horizontal overflow at390px; Mac original diagram endpoints HTTP200; excluded external observation stays unanswered; built-in→BOTH correction works; answer return preserves step; bike uncertainty/readiness stays honest; MICKE→MALM drops old imagery and gives the official manual fallback.
- The final ready-guide switch regression was also browser-verified: active IKEA discovery → click Mac ready guide → discovery idle + Mac first question.
- Review banner patch was verified in actual browser; no false live claim.
- Final focused browser console: zero errors/warnings. Isolated browser/backend instances were stopped; operator services were untouched.

Local evidence:

- `/tmp/ghostbuild-release-final/browser-result.json`
- `/tmp/ghostbuild-release-final/ready-switch/result.json`
- `/tmp/ghostbuild-release-final/mac-guidance-{desktop,mobile}.png`
- `/tmp/ghostbuild-release-final/mac-unreviewed-mobile.png` (scrolled viewport; do not assume the banner is inside the screenshot)
- `/tmp/ghostbuild-release-qa/simulator/result.json`, screenshots and console.

## 6. Live providers and physical evidence — exact limits

### Fresh live source corrections: PASS

Tracked report: `docs/evidence/framework/release-live-corrections.json`.

- MALM: live official IKEA retrieval returned genuine MALM listings/photos/manual URLs. Selecting one offered its official PDF and honestly stated no prepared offline step guide exists. It did not retain MICKE instructions.
- Prusa: MK4→MK3S+ correction cleared the MK4 guide and researched two official Prusa pages. A13-step MK3S guide was compiled and marked unreviewed. Wall time111.63s in one run; compile91.85s/fetch6.3s/two rounds. This is not a guaranteed latency.
- The Runtime harness used a fixed ManualClock. Its nested `last.took_s=0` is NOT a latency measurement; the report explicitly explains the monotonic wall measurement.
- These fresh research calls used Anthropic, not CREAO. Dynamic compiled output remains ignored local runtime data, not human-approved knowledge.

Deterministic four-scenario evidence: `docs/evidence/framework/corrections-deterministic.json`; reproducible harness `docs/evidence/adaptive/harness/corrections.py`. Product-cache records may include prior live retrievals; that harness makes zero provider calls.

### Fresh ElevenLabs: mixed, do not conceal

Tracked report: `docs/evidence/release/elevenlabs-live.json`.

Exactly one consented STT provider session and one TTS request; no retries:

- TTS **PASS:** existing `/voice/speak`, HTTP200, valid12,556-byte MP3, mono22,050Hz,3.019s audio; request/generation1.391s. Parsing verified, audible playback NOT verified.
- STT **FAIL:** backend WebSocket upgraded101, provider startup failed after5.013s, no transcript. Input was synthetic macOS `say` PCM16/mono16k, not a microphone. Guide/progress recovered unchanged.
- Startup has outer5s `asyncio.wait_for`, while WebSocket default handshake timeout is10s. Timing suggests timeout, but generic `VoiceProviderError` discards underlying class/status; auth/permission versus network cannot be proven from logs. Installed WebSocket API is compatible; no concrete API defect was identified.
- Safe optional future diagnostic: retain exception class/numeric HTTPstatus only, NEVER raw headers/error URLs/tokens. Do not start an unfocused voice rewrite during release.
- `/voice/status` booleans reflect configuration, NOT proof of provider health.

Earlier status history reports successful synthetic-sample STT and CREAO artifact normalization. These are **historical reports**, not this session's fresh STT success. Submission copy now discloses fresh failure. The staged G2 package disables voice. Demo with text/gestures; TTS may be mentioned with its actual proof.

### Physical G2

The user replied: **“Those checks passed; I’ll provide the details.”** This referred to the current voice-disabled LAN package and readable cue/image, press/swipes, answer return and reconnect.

Record these as **operator-reported PASS, detailed record pending**. Do not turn that into independently automated physical verification. G2 microphone, head shake, audible playback and Pi telemetry remain NOT RUN/unverified in this release. G2 has no camera or speaker; optional Pi camera describes its fixed external view.

## 7. Running operator service — preserve it

Backend currently listening on `:8787`, PID **87398**, source checkout final-sprint with `4cab4ef` code (newest d5257c6 is docs only). It was reloaded at06:57 and07:09 PDT with its session data preserved.

- Command: `.venv/bin/python -m ghostbuild_core --port 8787 --log-dir <final-sprint>/logs/bench-0632`.
- Output: `/private/tmp/gb-core-8787.log`.
- State directory: `logs/bench-0632`.
- Backups: `logs/backup-release-20261018-065728`, `logs/backup-release-final-20261018-070928`.
- `.env` optional provider configuration was preserved. It may enable paid live research; do not blindly exercise unfamiliar requests on this operator service.
- Existing Vite operator services on5173/5176 were left alone.
- Use isolated ports/logs and provider flags off for further tests. Do not erase/reset the operator's session or assume restarting on the same logs is a fresh session.

## 8. Packages already built

| Package | Scope | SHA-256 |
|---|---|---|
| `g2/ghostbuild.ehpk` / `/tmp/ghostbuild-release-artifacts/ghostbuild-lan.ehpk` | 47,035B; backend `http://172.20.10.6:8787` and corresponding WebSocket origin; mic permission absent | `eb5859301a5fc7d0287b3225fde735b9ba385d4d2af05ee98e58b447295aa90a` |
| `/tmp/ghostbuild-release-artifacts/ghostbuild-portable.ehpk` | 47,015B; localhost backend, intended CI/local software artifact | `beca3e146f7e4904446b594205ea46e3742d1f0b1a674887463afa3da7c5bf6f` |

Rebuild LAN whitelist if laptop IP changes; do not hardcode this address into source. Installed Even SDK0.0.16, CLI0.1.14, simulator0.9.5. App manifest validated and packages stamped by actual CLI. Built does not imply Beta upload.

## 9. Security/rights limitations

- Locked Python dependency audit: no known advisories.
- Production npm audit (`--omit=dev`): zero advisories.
- Full development npm audit: **six affected dev dependencies: two critical, one high, three moderate**. Vite/Vitest major upgrades were deferred during freeze. Exact GHSA IDs and rationale are recorded in `docs/evidence/release/VERIFICATION.md`; do not call this a fully clean audit.
- Secrets remain backend-only. Never copy key literals into handoffs, command output, PRs or screenshots.
- No new third-party source photos were committed this session. Existing IKEA/manual assets were preserved with attribution. Broader distribution rights still need human review; do not fabricate permission or a license. Repository has no chosen source-code license.
- Keep original authorship/history. Do not merge transport/ASL branches or overwrite unrelated local agent configuration.

## 10. Launch documents are already finished

- `README.md`: “From knowledge to action”, actual simulator image, story, accurate components, scenarios, setup and limits.
- `docs/ARCHITECTURE.md`: current providers/state/evidence/persistence boundaries.
- `docs/SETUP.md`: reproducible local/simulator/G2/provider commands.
- `.env.example`: safe names/current flags, paid/live providers off.
- `docs/DEMO_RUNBOOK.md`: exact five-minute IKEA+Mac script, inputs/phone/G2/backend expectations, setup/reset/fallbacks; exact120-second shot/voiceover/filming plan.
- `docs/HACKATHON_SUBMISSION.md`: copy-ready Devpost content, sponsor evidence and all current tracks/challenges.
- `docs/FINAL_SPRINT_STATUS.md`: concise final matrix; **still has pending-push/merge wording that needs updating after the actual remote actions**.
- `docs/ACCEPTANCE.md` and `docs/OPERATORS.md`: clarified optional Pi scope and current onboarding/gestures.

Do not rewrite all these from scratch. Focus on GitHub release completion, accurate final result updates and missing human publication steps.

### Official LA Hacks curation already researched

Primary source: `https://live.lahacks.com/tracks`, public data `https://live.lahacks.com/api/content`. Local fetched snapshot: `/tmp/ghostbuild-official-event-content.json`. Four tracks and17 challenge entries were verified.

- Best fit: **Beyond the Digital**, then **Applied Intelligence** if multiple tracks allowed.
- Prioritize **Even Realities**. CREAO/ElevenLabs entries must use bounded actual evidence. Paper optional; do not pretend Paper was used.
- Do not add unrelated integrations to chase prizes. All17 sponsor/challenge entries are considered in the submission document.
- Official Devpost: `https://la-ai-hackathon-2026.devpost.com/`.
- Devpost overview asks for2–3min video, so our requested short video plan is exactly120s.
- Current live configuration/overview say Oct18 noon PDT. `/rules` retains a stale April26/8am line: human organizer confirmation needed; do not silently treat April as the actual deadline.
- Even brief requires Beta upload, physical G2 at judging, GhostBuild app name and install/account instructions; simulator footage is allowed in the video. Full prize amounts/links are in submission copy.

## 11. What remains — execute in this order

1. Read actual current time, Git state and remote refs. This handoff is the only intended uncommitted file.
2. Commit this handoff if appropriate; push latest small documentation commit(s) to `origin/codex/final-sprint`. Last confirmed remote HEAD was4cab4ef; local d5257c6 is one commit ahead before this document.
3. Create the final release PR to main. Use `/tmp/ghostbuild-release-pr.md` only after correcting its old counts to1,161Python/32phone/208G2 and adding the fresh STT failure/TTS success. Link current launch docs/evidence. Mention #1 is superseded and #2 remains separate.
4. Run/wait for GitHub's new verify/package workflow. Inspect actual logs; fix actual failures only. Do not assert missing CI passed. Local source code already passed full relevant checks; repeat only for real changes/failures/platform concerns.
5. Review final release diff/history and secrets before merge. Main was an ancestor of final-sprint; this is an additive integration preserving authorship, not a broad merge of independent experiments.
6. Merge normally after required CI/review gates pass. Prefer merge commit to preserve history; no force or protection bypass. User already authorized routine commit/push/merge, so do not ask again.
7. Fetch and independently verify remote main contains the intended release. If using a local main worktree, create a separate one and fast-forward normally; do not switch/reset the dirty root checkout.
8. Confirm CI and the `ghostbuild-g2` artifact on main. Record exact commit, PR, actual test result and artifact URL/path.
9. Update FINAL_SPRINT_STATUS pending publication/CI/merge rows with the actual result. Ensure the final docs accurately reflect the final state, then publish that update normally; do not claim a merge before it happens.
10. Remove only this session's temporary object-transfer branch if safe/desirable after all real release objects are reachable on main. Never merge it. Preserve teammate branches/worktrees.
11. Supply the final concise factual launch report, with remaining human actions below. Do not say Devpost/Beta/video were published unless an actual receipt/link exists.

## 12. Human actions still outstanding

- Detailed physical G2 test record for the reported pass; no fresh mic/head-shake/Pi claims without actual tests.
- Human spot-check of MICKE stage text/quantities against official PDF before giving practical assembly instructions. Compiled repair procedures also need human/expert review before practical reliance.
- Even Hub Beta upload. The available browser was opened at `https://hub.evenrealities.com/`, page2, and was **signed out**. No upload occurred. Do not enter/request passwords; the operator must sign in or upload the ready LAN package.
- Record/upload the two-minute video and verify a genuine public playback URL. No actual video was recorded/exported.
- Confirm actual Devpost teammates/roles, reused/AI-assisted work, source/asset rights, and public-source/judge access (repo currently private).
- Paste submission copy, select eligible categories, upload screenshots/video and submit; verify receipt. No Devpost submission occurred.
- Confirm official stale-rules deadline wording with an organizer if needed.

Do not let optional voice debugging, sponsor expansion or cosmetic refactors consume the remaining submission time. The reliable hero is IKEA identity/part lookup + Mac branching/correction, with cached text/gestures and clearly labelled simulator fallback.
