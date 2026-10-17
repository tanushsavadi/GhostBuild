# Sentry findings log

**Owner:** B. Anyone may report a finding to B. Nobody spends core-lane time on Sentry.
**Rule:** the Sentry challenge is selected only if, by **Sun 08:30**, this file holds at least one real FINDING from our traces/logs **and** at least one real engineering DECISION that the finding informed or validated (19, final amendment 1). The decision does not have to be a code change. **Do not invent entries.** An empty log means we do not enter Sentry.

Each entry has four parts:

- **FINDING:** what the traces or logs showed, in one sentence.
- **EVIDENCE:** the Sentry link (trace ID, log query or screenshot path) and the session log file it came from.
- **DECISION:** what we decided because of it, who decided, and when. "We kept X because Y" counts.
- **RESULT:** what happened after the decision, measured where possible (numbers with n).

Illustrative shape only. These are **not** findings:
> FINDING: the temporal-stability vote dominates the latency budget. · EVIDENCE: trace `…`, `logs/session-….jsonl`. · DECISION: we tested a shorter vote window and kept the safer value because the short window committed during occlusion. · RESULT: p50 unchanged at __ s; 0 unsafe commits over __ trials.

---

## Entries

*(none yet)*
