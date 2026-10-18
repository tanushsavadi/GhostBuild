# Fast reuse and help without losing your place

2026-10-18, `codex/final-sprint`. All changes remain uncommitted. Operator services on 8787/5173 and the working G2 package were preserved. Preview: `http://127.0.0.1:8797/phone/` (cached product search; no new research).

## What the person sees

- A small **“Ask anytime — I’ll keep your place.”** link under the step heading focuses the question box. G2 has a dim **ASK ANYTIME** beside the step counter, with no extra onboarding or screen.
- Current instructions and the official manual picture remain in the left column. The step's conversation stays on the right. Mobile orders the same workspace vertically without horizontal overflow. Selected-product details move below the working area after selection.
- A new question shows **Thinking…**, then the answer and its source. **Back to my step** clears only the glasses answer overlay and focuses the existing instructions. (Superseded 05:30 PDT: answers now stay open as full pages until an explicit return; see FINAL_SPRINT_STATUS.md.) The original step and selected picture remain on the phone.
- Answers belong to a session/card/step. An answer arriving after navigation stays in its original step's conversation and does not cover the new step. Conversation, profile, notes, product configuration and progress survive their supported reconnect/restart paths.
- MICKE steps now show their official diagram on G2 automatically. Press opens PARTS; press again returns to the default diagram (step 32 also has ADJUST). Manual confirmation retains its guard and HUMAN CONFIRMED label. Asking, dismissing and navigation never invent measured completion.
- Explanatory questions such as “What does a cam lock engage with?” reach the assistant. “Which fastener do I use?” still returns the manual's exact identifiers and quantities immediately.

## Reuse policy

`reuse-cache.json` beside `sessions.json` stores completed generic guides, successful product query mappings, and standalone guide-grounded answers. `assistant.json` persists conversation state there. These live in the ignored log directory. Cache writes are atomic; missing/corrupt files fall back to normal lookup. Entries are bounded (120 guide mappings, 250 each for answer/product mappings). `GET /cache/status` returns counts only.

Equivalent goal wording shares a key after conservative normalization of courtesy words, order and common synonyms. Model/article IDs, mode, colours, sides, negation and quantities remain significant; quantity/negation relationships are preserved. A generic saved guide starts before conversational intake or a new research request, even when research providers are disabled after restart. Unreviewed research snapshots keep their review warning. This is conservative reuse, not an embedding-based claim that every paraphrase is equivalent.

For products: exact article/URL lookup first, verified saved matches second, official-site search on a miss. If fresh official facts cover the description, the list appears without launching a background search. A novel product still searches when enabled. Successful query mappings expire after 14 days; old records cannot satisfy freshness checks. Failed/empty searches are not cached as successful results. **Search the official site again** is available explicitly; choices are not renumbered beneath the user. “Mine has a drawer and cabinet” refines the desk's features instead of changing its category to cabinet.

Answer reuse requires the same complete card definition, step, selected product/configuration, experience profile, confirmed/tried context and normalized standalone question. It expires after seven days. Follow-up pronouns, general/unsure answers, questions needing clarification, and measured steps do not enter the reusable answer cache. Every reused answer is labelled saved; it is never evidence of physical completion. Repeated deterministic manual commands already need no model or network.

Flags: `GB_SMART_CACHE=0` disables the new reuse cache; `GB_STEP_IMAGES=0` disables automatic default step pictures. Existing optional backend Q&A remains independent of CREAO. `VITE_FLAG_HELP_HINT=0` hides the small G2 hint. No CREAO agent or ElevenLabs configuration change was needed. `GB_DISCOVERY_RESEARCH` remains off.

## Verification

| Check | Result |
|---|---|
| `make test` | PASS: core **628**, Pi **77**, knowledge **257**, assets **41**, IKEA **79**, G2 **208** |
| Contracts | PASS: nine schemas, 22 Python + 22 TypeScript examples; optional `Card.step_image` is additive |
| Web | **28/28** pass; all edited browser scripts parse |
| Generic lint / secrets / whitespace | PASS |
| G2 production build | PASS, TypeScript + Vite |
| Official simulator 0.9.5 + actual runtime | **11/11** checks, successful photo/manual SDK sends, zero simulator console errors; [result](evidence/fluid/simulator-result.json) |
| Real Chromium desktop and 390×844 mobile | Five real shortlist photos; hint focuses input; same DOM step/image retained while pending and answered; back restores G2 diagram; no horizontal overflow |
| Conversation ownership | Browser: step-14 question completes after moving to 15; no answer overlay/thread leaks into 15; returning to 14 restores its thread |
| Offline and recovery | Browser: “Connection lost. Your step stays here.” then normal state after reconnect; deliberate offline/restart probes produced expected browser resource/socket errors |
| Normal question flow | Zero page exceptions and zero HTTP 4xx/5xx responses |
| Persistence/cache boundaries | Tests cover restart with research/brain off, expiry/corruption, new IDs/counts/sides/mode/negation, profile/source/step changes, no caching general/follow-up answers, dismiss without advancement |

Browser Q&A used an explicitly labelled **MOCK** delayed backend in a separate temporary harness, with real runtime/endpoints/assets. This proves the UI orchestration, ownership and reuse, not the model's answer quality. In that harness a repeated explanatory question rendered its saved answer in **25 ms** (one sample), with one total fake-brain call before and after repeat. Saved conversations also survived page reload; runtime restart reuse is covered by tests.

[Desktop](evidence/fluid/phone-desktop.png), [thinking state](evidence/fluid/phone-thinking.png), [mobile](evidence/fluid/phone-mobile.png), [G2 hint + diagram](evidence/fluid/sim-07-manual-step14-visible.png).

## Latency and live-search evidence

New cached shortlist benchmark: **8.53–12.12 ms**, **9.81 ms median**, ten warm local HTTP requests including persistence and G2 thumbnail composition. [Samples](evidence/fluid/cache-http-latency.json). This excludes physical BLE and phone-network time.

No new paid-provider calls were made for this follow-up: **zero Anthropic calls, zero CREAO calls**. Previous live discovery proof remains in [the IKEA report](IKEA_DISCOVERY_REPORT.md): Anthropic `web_search_20250305`, `claude-opus-5-5`, restricted to `ikea.com`, followed by official-page/photo/article/manual-PDF validation. The unfamiliar black glass-door query produced five real validated candidates in **11.675 s**; a separate red-cabinet no-match took **14.309 s**. Those were two earlier calls, separate from the cached measurements above.

Physical G2 legibility, BLE transfer timing and on-glasses microphone capture remain unverified. **The authored MICKE step text still needs a human spot-check against the official PDF.** The exact demo gestures and utterances are in [the runbook](IKEA_DISCOVERY_RUNBOOK.md).
