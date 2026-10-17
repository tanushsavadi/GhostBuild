# 10 — Evaluation Plan

**Owners:** D (harness + logs + eval table, Sun 07:45–08:30), C (vision runs), A (spatial trials + presentation). **Rule:** report only numbers we measured, with `n`. Never round up. If a metric isn't collected, delete its row from the Devpost.

> **Final reconciliation (2026-10-16).** Added: the Even quiet metric (E-a), the spatial task gates (18 v3 §6: Gate A confusion matrix, Gate B stability, measured σ and bias, derived thresholds; millimetre figures are diagnostics only), and the optional generality-proof counts. Voice and VLM rows apply only if those features shipped (voice P2; VLM label cut). Sentry shows the same latency split live, but the offline `make eval-latency` table stays the measurement of record. **Never claim functional verification of the rover motor: only installation state is measured.**

## 1. Ground truth by construction
A **config card deck** (`eval/configs/*.json` + printed cards): each card lists the exact state (part, anchor, rot). The operator builds the card's state, the harness records 30 frames, and ground truth = the card. No hand labelling needed.

## 2. Vision tests (E1/E1b; run first at venue Sat ~3–5 PM, again Sun ~4 AM)
| ID | Protocol | Metric | Pass |
|---|---|---|---|
| T1 | 10 configs × 30 frames | per-cell accuracy (single frame); per-part accuracy (single frame); per-part accuracy after vote | ≥ 99% / ≥ 98% / 100% |
| T1b | 10 trials each: 1-stud shift, 180° flip, 90° turn, swap | detection rate | 10/10 each |
| T2 | 3 min idle, people walking past, one phone flash | committed state changes | 0 |
| T3 | 20 trials hand leaves → committed | latency p50/p95 | p95 ≤ 1.0 s |
| T4 | 10 deliberate wrong placements | detected + replanned | 10/10 ≤ 2 s |
| T5 | 20 hand insertions incl. hover | instructions emitted while hand present | 0 |

## 3. System metrics (from `logs/session-*.jsonl`)
| Metric | How | Report |
|---|---|---|
| **Wrong instructions issued** | any HUD action contradicting the card's ground truth | count over all trials (target 0) |
| Physical-diff accuracy | diff items vs card-derived diff, 20 configs | exact-match rate |
| Next-action correctness | planner head vs expected (BFS shortest-path set) | rate, n=20 |
| Recovery after unexpected action | E5: 20 deliberate deviations | detected & corrected / 20 |
| Camera-to-HUD latency | `capture_ts` → core commit → `hud_ack` | p50/p95, n ≥ 30, split into vision / core / BLE |
| Task completion | full demo runs by teammates + volunteers | completed / attempted, median time |
| **HUD changes per run (E-a)** | count `hud` frames whose text/mode changed, per full run | median + n; supports "Quiet by Design" |
| **% of task time dark or dimmed (E-a)** | time in `idle` or brightness 2 ÷ run time, from the session log | median + n; quoted to the Even judge only if measured |

## 4. VLM baseline (the "insight" result) — OPTIONAL, unowned (A is at capacity; StepFun dropped). Run only if someone is genuinely idle; otherwise cite published benchmarks (17 §1) and delete the row.
- Inputs: the same 20 rectified frames + target JSON + part library.
- Prompt: "List every discrepancy between the board and the target as JSON `{part_id, kind, current, target}`". Strict schema; temperature 0; 1 call per frame per model.
- Models: one of Gemini Flash / Claude Haiku 5.5. *(StepFun dropped.)*
- Score: precision/recall/F1 of diff items vs ground truth; latency p50.
- Report it exactly as measured, even if a VLM does well. If a VLM does very well, say so and explain why we still keep deterministic perception (latency, determinism, abstention).

## 4b. Ambition-pass metrics (collect only for features that passed their gate)
| Metric | How | Report |
|---|---|---|
| **Manual extraction accuracy** | Opus StepRecords vs LDraw per-step part multiset | n/m steps match (also shown live on the twin) |
| Task-graph correctness | compiled graph == golden target (unit test) | pass/fail |
| **Citation validity** | each answer's evidence ID resolves to a real page/step | % (expected 100% by construction; verify) |
| **Intent accuracy** (only if P2 voice shipped) | 20 scripted hall utterances via the G2 mic, labelled by hand | correct/20 (gate G5 ≥ 17) |
| Answer correctness | the same 20 + menu questions vs expected answers from the planner | correct/n |
| Voice latency (only if P2 voice shipped) | `ptt end` → `hud_ack` of the answer; split STT / intent / render | p50 / p90, n ≥ 20 |
| Menu answer correctness | items 1–5 on scenario snapshots vs expected planner-derived answers | correct/n |
| Premature/deviation catch | 20 deliberate order violations (cap early, wrong spot) | caught + correct fix / 20 |
| Hallucinated actions on HUD | any HUD action not produced by the planner | count (must be 0 by construction; log-checked) |
| Hand-gate false commits | 20 hand insertions | count (target 0) |
| Generality proof (optional, offline) | external guide through the same compiler: components · steps · warnings · evidence refs (quotes verified verbatim) | counts; "compiled, not executed" |

## 4c. Spatial metrics (18 v3 §6; only for gates that ran)
| Metric | How | Report |
|---|---|---|
| **Gate A confusion matrix** | 18 v3 §6.2 trials scored from committed adapter output: CORRECT vs MISORIENTED (incl. direction), LIFTED, REMOVED, hand cover 1.2 s / 3 s, deck/bar classes | counts per row; **unsafe errors (target 0)** vs safe misses (abstentions) |
| Gate B tracking stability | catastrophic flips over 10 hero rotations; % visible frames tracked during a 10 s rotation; re-acquire after 1 s cover; ≥ 30 fps with 2 image anchors; S7 live loop (10 trials, 10-min drift check) | counts / % / s; **0 wrong G2 instructions** |
| Measured noise | σ_xy, σ_z, σ_yaw, σ_tilt and bias b per component (10 s static × 3 reseats; motor also at 90°); `e_q = 3σ_q + |b_q|` | table |
| Derived thresholds | `params.yaml` values from 18 v3 §6.4 and whether any clamp bound | table |
| Diagnostics (not kill conditions) | static jitter, F7 residual, overlay edge error at 40 cm, final Δyaw vs truth, base drift over 5 min | mm / ° |
| Pose → G2 latency | physical change → `hud_ack` | p50 / p95 |

## 5. Optional (only if time; label as anecdotal)
Time-to-repair with vs without GhostBuild (paper photo of the target), n = 4–6 volunteers, same defects. Report medians and n; no significance claims.

## 6. Devpost results table (template)
| Metric | Result | n |
|---|---|---|
| Per-part state accuracy (after vote) | __% | __ frames |
| Wrong instructions issued | __ | __ runs |
| Deviation recovery | __/__ | __ |
| Hand-leaves → glasses latency p50 / p95 | __ s / __ s | __ |
| VLM-only diff F1 (model) vs ours | __ vs __ | 20 frames |
| Planner plan length = BFS optimum | __% of states | __ states |
| LLM step extraction vs CAD | __/__ steps | 1 manual |
| Order-violation catches | __/20 | 20 |
| HUD changes per run · % time dark or dimmed | __ · __% | __ runs |
| Spatial Gate A unsafe errors (motor 0° vs 90°, direction, lifted, removed, occlusion) | __ | __ trials |
| Spatial S7 wrong G2 instructions | __ | 10 trials |
| *(only if shipped)* Voice intent accuracy · release→glasses p50/p90 | __/20 · __ s / __ s | 20 |

## 7. Tooling
`make eval-vision CONFIGS=eval/configs` · `make eval-latency LOG=logs/x.jsonl` (also prints the E-a quiet metrics) · `make eval-vlm` (optional) · spatial trials via `adapters/spatial_pose` replay over A's recordings → `eval/results/*.json` + `eval/RESULTS.md` generated.
