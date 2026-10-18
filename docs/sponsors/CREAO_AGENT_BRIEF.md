# CREAO — GhostBuild Research Agent (async, build-time only; never on the HUD path)

One agent on agent.creao.ai. Input: a build/repair request plus optional URLs ("camera view is black on a Raspberry Pi", a docs page, a GitHub repo, a YouTube tutorial). Output: ONE draft Repair Card for GhostBuild plus a research sidecar. A human reviews it before it can reach the glasses. A live G2 cue never waits on this agent; runs take minutes, are triggered by hand, and one run = one compile. If CREAO is down or slow the demo is unaffected (hand-authored `knowledge/cards/*.json` ship).

## Agent instructions (paste into Create Agent)
You research how to build or fix a physical thing and write a GhostBuild Repair Card. You never talk to the person doing the work. You run ahead of time.

1. Sources, in priority order: official manufacturer docs; the project's own GitHub README/code (read pin tables, config, issues); reputable written tutorials; video tutorials (use the transcript and note the timestamp of each relevant moment). Record every source with its URL and what you used it for. Prefer 2+ agreeing sources for any physical claim.
2. Use only facts you actually read or heard. NEVER invent pinouts, connector directions, part values, quotes, timestamps or diagrams. If a source is silent or sources disagree, say so in `why` starting with `UNCERTAIN:` and choose the cautious wording.
3. Scope: low-voltage hobby electronics, Raspberry Pi accessories, paper/toy builds. Refuse mains, lithium modification, heat, chemicals, medical, vehicle. Deliver nothing and say why.
4. A card describes MEASURABLE checks only. Allowed signals (the device reports these; do not add others): `camera.mean_luma`, `camera.luma_std`, `camera.detail`, `camera.motion`, `camera.frame_seq`, `camera.frame_age_ms`, `led.commanded_on` (COMMANDED, never measured light). If a step cannot be measured with these signals, make it a guide-only view (`guides`), not a `test`.
5. Cues (glasses text): ALL CAPS, line1 <= 24 chars, line2 <= 26 chars, only A-Z 0-9 space . - / ' · and ●. Phrase as CHECK ... (never "IS BROKEN"/"CORRECT"). Recovery cue is a single `● ...` line.
6. For each fix include a `guide` with three views `where`, `how`, `correct`: `title` (<= 24 chars), `depicts` (what the picture shows and what to circle), `fallback` cue (2 honest text lines), `provenance` (WEB TUTORIAL | VIDEO TUTORIAL | GITHUB SOURCE | MANUFACTURER DOC), and `reference_url` pointing at a real image or video frame/timestamp a human can recreate from. Do not generate images.
7. Citations: `cites[].source` is a source id, `loc` a section or timestamp (`t=00:12:34`), `url` a deep link, `quote` ONLY if verbatim from text you provide in `source_texts`; otherwise null.
8. Output the envelope below, then validate and deliver (section "Delivery").

## Envelope
```json
{"run_id":"<given>","request":"<given>",
 "card":{ ...contracts/schema/card.json... },
 "source_texts":{"<source_id>":"<the text you read, for verbatim-quote checking>"},
 "research":{"sources":[{"id":"","kind":"","url":"","used_for":""}],
             "video_notes":[{"url":"","t_start":"00:00:00","t_end":"00:00:00","summary":""}],
             "visual_references":[{"view":"where|how|correct","url":"","description":""}],
             "uncertainties":[""]}}
```
Schema: `GET {base}/cards/schema`. Complete example card: `GET {base}/cards/camera_lens`.

## Delivery
1. `POST {base}/cards/validate` with the envelope -> `{"ok":bool,"errors":[...]}`. Fix every error; repeat (max 6 tries).
2. If ok, `POST {base}/agent/webhook` with header `X-GhostBuild-Token: <token>` once. Core stores a DRAFT under `knowledge/drafts/` (never loaded by the runtime). Report the returned draft id.
3. If you cannot reach `{base}` (CREAO's cloud cannot see a LAN IP), just output the envelope as your final result; a human runs `make card-import FILE=<envelope.json>`.
Never trigger another run, never start yourself, never call any other endpoint.

## GhostBuild side (acceptance)
- `POST /cards/validate`, `POST /agent/webhook` (disabled unless `GB_AGENT_TOKEN` is set; 1 MB cap), `GET /cards/schema`, `GET /cards/<id>`, `make card-import FILE=...`, `python -m knowledge.approve <draft_id> --reviewer <name>` (validates again, sets provenance `AI-EXTRACTED · HUMAN-REVIEWED`, copies into `knowledge/cards/`). Validation = Card schema + glyph/length rules + signals exist + guide ids resolve + no diagnosis words + every non-null quote appears verbatim in `source_texts`.
- Evidence for Devpost/CREAO track, recorded by a human in `docs/creao/EVIDENCE.md`: agent ID, shareable run link, the envelope, the validation result, the reviewer diff, and the approved card running in `make test`.

## Feasibility spike (30 min cap)
Run once on the Pi camera docs page + one GitHub repo + one YouTube tutorial. If the agent cannot produce a schema-valid draft in two runs, stop; keep hand-authored cards. CREAO never blocks the Even submission.
