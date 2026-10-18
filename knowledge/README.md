# knowledge/

Repair Cards (`cards/`), their sources (`sources/`), guide pictures (`guides/`), and the build-time tools that check them.
Nothing here runs on the cue path. The runtime loads only `knowledge/cards/*.json`.

## Shipped cards
| card_id | mode | what | steps | measured steps | sources |
|---|---|---|---|---|---|
| `paper_cup` | build | fold a paper cup from a sheet of paper (the 5-minute demo; needs only paper, scissors only if the sheet is not square) | 8 manual | none | origami.me cup tutorial + rectangle-to-square page (WEB TUTORIAL, verbatim quotes in `sources/paper_cup__*.md`) |
| `pi_camera_setup` | build | set up the Pi camera station | 7 (5 manual, 2 measured) | `camera_feed` (`camera.frame_seq`, `camera.mean_luma`), `led_test` (`led.commanded_on`, COMMANDED only) | official Raspberry Pi docs (MANUFACTURER DOC) |
| `led_breadboard` | build | light an LED on a breadboard with a resistor and a 9 V battery | 7 manual (never claims verification) | none | For Dummies, SparkFun, Adafruit (WEB TUTORIAL) |
| `camera_lens` | fix | Pi camera view lost: lens obstructed (fault `tests`, guide `camera_lens`) | tests | n/a | Raspberry Pi docs |
| `setup_station` | build | earlier Pi station setup as fault tests; overlaps `pi_camera_setup` (leave both; no identical alias, but a bare "set up" request still matches only setup_station) | tests | n/a | Raspberry Pi docs |

`paper_cup` has two schematic placeholder guides (`cup_fold_half`, `cup_pinch`; real photos are a human job, see assets/README.md).

## Add a playbook by hand
1. Pick `card_id` (`^[a-z0-9][a-z0-9_-]*$`), create `cards/<card_id>.json` (file stem must equal `card_id`). Copy `contracts/examples/card_playbook_example.json` as the shape.
2. Fetch the real tutorial or docs page. Save the text you rely on as `sources/<card_id>__<source_id>.md` (URL, fetch date, the page text). Declare it in `sources[]` with `file`. A `cites[].quote` is allowed only if it is pasted verbatim from that file; otherwise `quote: null`.
3. One physical action per step. `cue` line1 <= 24, line2 <= 26 chars, ALL CAPS, only A-Z 0-9 space . - / ' · ● , : ? ! ( ) + =. No check mark (the G2 plugin folds it to OK), no diagnosis words (IS, ARE, BROKEN, DEAD, FAULTY, WRONG, BAD, DEFECTIVE, DAMAGED). Manual steps (no `verify`) never say VERIFIED or CORRECT. `verify` only with `camera.mean_luma|luma_std|detail|motion|frame_seq|frame_age_ms` or `led.commanded_on`, and an LED `verify.ok` never says VERIFIED. `requires` names earlier steps. `faq[].q` lowercase spoken questions. Put UNCERTAIN: in `why` wherever the source is silent or disagrees.
4. `provenance` `AUTHORED DEMO METADATA` for hand-authored cards; `aliases` lowercase and unique per `goal_mode` across all cards (the resolver matches substrings).
5. Optional pictures: at most two steps; add `assets/sources/<guide_id>/` (see assets/README.md), `make guides`, paste the `guide` object from `guides/<guide_id>/manifest.json` into the card and add `reference_url`.
6. `uv run python -m knowledge.validate knowledge/cards --check-images` then `make test`.

## CREAO import flow (async, optional, never on the cue path)
Research agent (docs/sponsors/CREAO_AGENT_BRIEF.md) -> envelope JSON -> `make card-import FILE=envelope.json` (draft under `knowledge/drafts/`, gitignored) -> human `knowledge.approve <draft_id> --reviewer <name> --dry-run`, review the diff, then without `--dry-run` -> `cards/<card_id>.json` with provenance `AI-EXTRACTED · HUMAN-REVIEWED` and the source texts stored as `sources/<card_id>__<source_id>.md` -> `make test`. Playbook drafts are validated and approved exactly like fault cards. `knowledge/fixtures/envelope_paper_cup.json` is a HAND-MADE sample envelope (NOT produced by CREAO) used by the tests; approving it over the shipped `paper_cup` is refused (hand-authored) unless `--force`.

## Validate shipped cards
    uv run python -m knowledge.validate [cards_dir] [--check-images]

## Import a research-agent draft (no network)
The research agent (docs/sponsors/CREAO_AGENT_BRIEF.md) returns an envelope
`{run_id, request, card, source_texts, research}`. A human saves it to a file, then:

    uv run python -m knowledge.importer ENVELOPE.json

This validates the envelope (Card schema, cue glyphs and length, signals exist, guide ids resolve, no diagnosis words,
playbook step rules (unique step ids, `requires` earlier steps, `verify` only allowed signals, manual steps never VERIFIED/CORRECT), every non-null `cites[].quote` (fault checks and step troubleshoot) appears verbatim in `source_texts[cite.source]`, http(s) URLs only, 1 MB cap) and writes
`knowledge/drafts/<card_id>-<UTC yyyymmddThhmmss>/{envelope.json,card.json}`. Nothing is fetched, and drafts are never
loaded by the runtime.

The same checks run behind the running core:

    GET  /cards/schema          Card JSON Schema (from contracts.models.Card)
    GET  /cards/<card_id>       a loaded card; 404 if unknown
    POST /cards/validate        envelope -> {"ok": bool, "errors": [...]}
    POST /agent/webhook         header X-GhostBuild-Token must equal env GB_AGENT_TOKEN; 503 "webhook disabled" if the
                                env var is unset; revalidates, stores a draft, returns {"draft_id": ...}

## Approve a draft (human step)
    uv run python -m knowledge.approve <draft_id> --reviewer "<name>" --dry-run   # validate and show the diff only
    uv run python -m knowledge.approve <draft_id> --reviewer "<name>"

Approval re-validates, prints a diff against any existing `cards/<card_id>.json`, sets provenance to
`AI-EXTRACTED · HUMAN-REVIEWED` (only here), stores each `source_texts` entry as `sources/<card_id>__<source_id>.md`
so the shared validator keeps re-checking quotes, writes `cards/<card_id>.json`, and logs `drafts/<draft_id>/review.json`
`{reviewer, at, validator_ok}`. A hand-authored card (`AUTHORED DEMO METADATA`) is only replaced with `--force`.
Guide images are not produced; add them under `knowledge/guides/` or the cards fall back to their text cues.
After approving, run `make test`.
