# knowledge/

Repair Cards (`cards/`), their sources (`sources/`), guide pictures (`guides/`), and the build-time tools that check them.
Nothing here runs on the cue path. The runtime loads only `knowledge/cards/*.json`.

## Validate shipped cards
    uv run python -m knowledge.validate [cards_dir] [--check-images]

## Import a research-agent draft (no network)
The research agent (docs/sponsors/CREAO_AGENT_BRIEF.md) returns an envelope
`{run_id, request, card, source_texts, research}`. A human saves it to a file, then:

    uv run python -m knowledge.importer ENVELOPE.json

This validates the envelope (Card schema, cue glyphs and length, signals exist, guide ids resolve, no diagnosis words,
every non-null `cites[].quote` appears verbatim in `source_texts[cite.source]`, http(s) URLs only, 1 MB cap) and writes
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
