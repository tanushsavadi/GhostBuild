# CREAO — Repair Playbook Agent (async, build-time only; never on the HUD path)

Create one real agent on CREAO. Run it once per device. Its output is a *draft* Repair Card that GhostBuild validates and a human reviews before it is cached in `knowledge/cards/`.

## Agent prompt (paste)
You turn device documentation into a structured repair playbook for smart-glasses cues. Inputs: (1) the Raspberry Pi camera documentation pages listed below, (2) our confirmed configuration. Output: ONE JSON document that validates against the attached JSON Schema (`contracts/schema/card.json`).
Rules: only use facts present in the provided sources. `cites[].quote` must be a verbatim sentence from a provided source, otherwise null. Never invent pinouts, connector directions, part numbers or diagrams. Cues are ALL CAPS, phrased as CHECK ..., never as a diagnosis; line1 <= 24 chars, line2 <= 26 chars. For each Check give: `when` predicates over the observation signals below, `action`, `why` (grounded), `guide_id`. For each guide view (where/how/correct) give a plain-text visual spec (what to depict, what to circle, crop hint) in `depicts`, not an image. Mark anything uncertain in `why` with "UNCERTAIN:". Provenance of the card: `AI-EXTRACTED · HUMAN-REVIEWED` is applied by the team after review, set `AI-EXTRACTED · HUMAN-REVIEWED` only in the draft field `provenance`.

## Confirmed configuration
Raspberry Pi with the official camera module (fixed field of view, external to the glasses), one LED on a GPIO pin. Observation signals: `camera.mean_luma` (0-255), `camera.luma_std`, `camera.detail`, `camera.motion` (0..1), `camera.frame_seq`, `led.commanded_on` (COMMANDED only, not measured light). Scenario: the camera view is obstructed or lost; the wearer must locate and clear it; recovery is judged from measured frames.

## Sources to provide
https://www.raspberrypi.com/documentation/accessories/camera.html
https://www.raspberrypi.com/documentation/computers/camera_software.html

## Acceptance (GhostBuild side)
`uv run python -m knowledge.validate <draft_dir>` passes (schema, glyphs, verbatim quotes against saved source text, signals exist, no diagnosis wording); a human reviews the diff; only then copy to `knowledge/cards/` and record the CREAO agent ID and shareable run link in `docs/creao/EVIDENCE.md`.

## Feasibility spike (30 min cap)
If the agent cannot produce a schema-valid draft in one or two runs, stop and keep the hand-authored card. CREAO never blocks the Even submission.
