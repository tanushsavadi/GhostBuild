# 12 — Risk Register (ranked by expected damage)

> **Final reconciliation (2026-10-16).** Rows 1–30 are kept; rows touched by later decisions are annotated. New: spatial risks (18 v3 §9) as rows 31–38 and sponsor/integration risks (19) as rows 39–46. The automatic clock valves (18 v3 §8, 19 §14) are the mitigation of record: anything not green at its clock is red, and killed work is never reopened.

| # | Failure mode | Detection | Mitigation | Fallback | Demo impact |
|---|---|---|---|---|---|
| 1 | **Beta build can't reach the laptop** (LAN http/ws blocked in packaged build; mixed content) | E2 in hours 1–5; `/health g2_connected=false` | Whitelist all ladder origins from build #1; Tailscale Funnel `wss` rung; reconnect logic | QR sideload on own LAN for judging (phone auto-lock off); ask Even table before 8 PM Sat | Fatal for Even if unsolved; mitigated |
| 2 | **Wrong instruction from misperception** | T1/T4 logs; "wrong instructions issued" metric | Own light panel; LAB + grey-patch normalisation; abstention (`?`, `ADJUST BRICK`); 5-frame vote; adversarial tests | Plan B AprilTag caps; reduce parts | Credibility-fatal → top priority |
| 3 | **No G2 loan approval** | Email by 12:30 PM Sat | Apply 9:00 AM sharp with a crisp "why G2"; answer the SDK question honestly; ask at the Even table in person | Build/test in simulator; ask to borrow time on a demo unit; optimise for Overall; through-lens video impossible → simulator video | Even prize likely lost |
| 4 | **Delayed device pickup** | No device by 1:30 PM | Simulator-first development (everything is mocked) | Same as above for a few hours | Low if mocks exist |
| 5 | Simulator works, hardware fails (glyphs, layout, image) | E3/E7 on first hardware run (~2:30 PM) | Text-first; glyph whitelist; test on glass early | Text-only HUD | Low |
| 6 | Venue Wi-Fi blocks local networking | QR scan fails / `ping` fails | Never use venue Wi-Fi: travel router or iPhone hotspot | Funnel over cellular | None if prepared |
| 7 | Phone lock / background kills WS | QA checklist | iPhone (WKWebView keeps running); reconnect on `FOREGROUND_ENTER`; `setLocalStorage` restore; auto-lock off during judging | Tap to retry | Low |
| 8 | CV fails under venue lighting | T1/T2 at venue Sat afternoon | Light panel/tent; recalibrate at table; matte surfaces; tilt camera | Tags (Plan B) → Duplo (Plan C); spare Hardware Lab Logitech webcam if the camera itself fails | Medium |
| 9 | Orientation ambiguity | T1b | Dot stickers; 2×2s symmetric by design | Tags | Low |
| 10 | Visually similar parts | Calibration validation | LAB-distant palette; no orange+red+yellow together | Fewer colours | Low |
| 11 | Occlusion (hands, sleeves, judge's head) | T5 | Marker-loss + motion gate; edge-touching `?` gate; freeze & dim | Tap to recheck | Low |
| 12 | Latency feels slow | E4 | Text before image; K/quiet tuning; image only on step change | Drop map | Low |
| 13 | Supervisor view overrun | M10 21:30 | 2D supervisor (B); no Mac 3D unless spatial dies early (W4-lite, gate 23:00) | Core-served text page | None |
| 14 | Planner complexity / flapping | Unit tests; demo replay snapshot | Pure functions; stickiness; BFS test | Disable cap dependency | Low |
| 15 | Judge does something unexpected | Rehearse with outsiders | Abstain + ad-libs (11) | Operator freeze + honest explanation | Low |
| 16 | API/cloud outage (Funnel) | Timeouts | LAN rung first (VLM label cut) | QR LAN | Low |
| 17 | Packaging failure (`evenhub pack` errors) | First stub pack Sat ~4 PM | Follow 08 §9 schema; `-c` check; no "Even" in name | Fix-forward; Even table help | Medium if found late |
| 18 | Beta submission failure (portal, group, firmware floor) | First Beta push Sat ~5 PM | `--sdk-ver 0.0.16`; update Even app ≥ 2.2.10; correct account email | Even table Sun 9 AM | High if found Sunday → test Saturday |
| 19 | Laptop sleeps / dependency breaks | — | `caffeinate`; lockfiles; `make demo` | Backup video | Low |
| 20 | Team fatigue → late integration bugs | — | Integration from hour 1; code freeze 10:30 AM; staggered sleep | Buffer 11:00–12:00 | Medium |

## Ambition-pass risks
| # | Failure mode | Detection | Mitigation | Fallback | Demo impact |
|---|---|---|---|---|---|
| 21 | P1 work starves P0 (C pulled off perception; D overloaded) | Gate misses at 18:00/20:00 | Rebalanced team (13); C on P0 until G2; P0 freeze 02:00 | Turn P1 off by flag | High → controlled |
| 22 | ~~Voice fails in hall noise~~ — retired: voice is P2 opportunistic and in no script | G1/G5 only if it starts | Menu is the question path | Menu | None |
| 23 | Opus extraction inaccurate on diagram pages | K1 match score | CAD gives the structure; mismatched steps use CAD text, labelled | `authored` evidence (labelled) | Low |
| 24 | Studio LDraw export lacks steps / part mapping errors | G3 test | LeoCAD/LPub3D fallback; golden target | Golden target | Low |
| 25 | W4-lite twin GPU contention or mapping bugs (only if built) | 23:00 | Mac 2; render-count test | `?mode=2d` | None for G2 loop |
| 26 | ~~Hero tag pollutes P0 colour reading~~ — retired: hero tag cut | — | — | — | None |
| 27 | Cloud outage at judging | `/health` | Precompiled bundles; deterministic answers; menu input is local; nothing on the demo path calls a cloud API | — | Low (Sentry/Fetch only) |
| 28 | Rules: Studio model/PDF authored before 12:00 counted as prior work | Ask at check-in | Author after 12:00 if unclear (≈1.5–2 h) | Hand-drawn instruction PDF from LeoCAD | Medium if ignored |
| 29 | Judge perceives "LLM wrapper + eye candy" | Rehearsal feedback | Lead with closed-loop verification + dependency catch; provenance panel; "we don't trust VLMs for state" insight | — | Medium |
| 30 | Demo runs long (> 90 s) | Rehearsal timing | 90 s / 45 s scripts; cut gated extras | 45 s version | Medium |

## Spatial risks (18 v3 §9)
| # | Failure mode | Detection | Mitigation | Fallback | Demo impact |
|---|---|---|---|---|---|
| 31 | A2 motor quality in standard mode (Apple recommends extended training) | S5 Gate A + B | Upright viewing angles; constrained motion (yaw in place); asymmetric motor | Motor card; spatial cannot lead | Medium |
| 32 | Image + object tracking coexistence (`trackingObjects` + `detectionImages`) | S2 / S5 [verify] | Slot budget ≤ 4 images; test at S2 | B2-continuous base / cards only | Medium |
| 33 | Base drift or bump | S7 (seated motor and deck still CORRECT after 10 min without re-lock) | Glued baseplate; re-lock before every run, only between runs | B2-continuous (`image_continuous`); B0 manual is bannered and banned from lead runs | Medium |
| 34 | Session interruption under thermal/CPU load | `sessionWasInterrupted` / relocalizing | `base.state = unset` → NO_COMMIT for all components → re-lock | Rocket leads | Low (safe) |
| 35 | Gear-direction class of bug (V2's `GEAR TO THE LEFT`) | test T2 / T2b | Directions only in the judge's frame; never from the mirror | — | High if missed → covered by T2 |
| 36 | Unsafe commit during occlusion or lift | Gate A rows (hand cover 1.2 s / 3 s; lifted) | 18 v3 state machine: losing tracking never means absent; LIFTED before SETTLING; HOLD/LOST only | Spatial cannot lead | Credibility-fatal → gate is 0 unsafe errors |
| 37 | C and D over capacity (C ≈ 22.75 h, D ≈ 24.5 h vs ≈ 18 h) | standups | The 17:00, 21:30, 23:30 valves are expected to fire; C never starts the adapter if G2 is red | CORE-MIN; visual-only spatial | Controlled |
| 38 | Fallback richness reduced if spatial dies late (no W4, no voice, no live iFixit, no VLM label) | — | Stated honestly (18 v3 §9); P0 reliability and the closed loop unchanged | Rocket demo | Accepted |

## Sponsor / integration risks (19)
| # | Failure mode | Detection | Mitigation | Fallback | Demo impact |
|---|---|---|---|---|---|
| 39 | Sponsor work steals core time | standups | Devin writes both integrations; B lands Sentry only in its 22:00 polish valve and Fetch only after Beta QA at 06:45; nothing on C; D only reads F1 and approves the exception | Kill the sponsor | None by design |
| 40 | Fetch needs a change outside `integrations/fetch_agent/` after 04:00 | landing / QA | Isolated sponsor-client exception forbids it | **Fetch dies** | None |
| 41 | Fetch agent pointed at the wrong core (localhost on B's laptop) | startup | `GB_CORE_URL` required, no default; fail fast | — | None |
| 42 | Fetch "workflow entirely in ASI:One" rejected by judges | 11:30 table / Discord | Supervisor workflow complete in chat; plan card readable alone | Fetch dead | None for others |
| 43 | Venue internet for Agentverse / ASI:One / Sentry | F2, 23:00 | Hotspot cellular | Kill sponsor feature | None for P0 |
| 44 | Sentry entered without a real story | 08:30 | Entry requires a real FINDING + DECISION in `sentry_findings.md` | Do not select Sentry | None |
| 45 | Devin PR red at its gate | 22:00 / F1 | Strict scope, exact interfaces, test command; no human rescue | Kill that sponsor feature | None |
| 46 | Sponsor soup in the pitch | rehearsal | One story; sponsor variants change emphasis only (11, 20 §15) | — | Medium if ignored |

**Honesty rules for fallbacks**
- Manual override exists only for visual/demo recovery and is always labelled (`M` on HUD, red banner on the screen). It never appears in eval numbers.
- Never present recorded video as live. Never present an override as inference.
- Never imply the LLM built the task graph when it came from CAD; always show `graph_source`. If K1 fails, label evidence `authored`.
- A question typed by an operator must be labelled "typed question".
- If we fall back to QR sideload for judging, the Beta build still exists and is submitted; say so if asked.
- Never say "the motor isn't broken" or "functional verification": only installation state is verified.
- Never present authored rover relations as CAD-derived; the chip says `AUTHORED RELATIONS`.
- Never invent a Sentry finding or decision.
