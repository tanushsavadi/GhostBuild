# 19 — Sponsor & Track Strategy

**Date:** 2026-10-16 (the day before the event). **Scope:** which sponsor and organizer tracks GhostBuild enters, what (if anything) gets built for each, who builds it, and when each one is killed.
**Authority:** this doc does **not** change GhostBuild's design, the spatial architecture, or docs 00–18. `18_SPATIAL_TWIN_PASS_V3.md` is authoritative for execution. Every sponsor item below is a separate process or a story layer over interfaces already locked at 12:45. Where this doc and V3 disagree on anything except sponsor work, V3 wins.
> **⚑ FINAL RECONCILIATION AMENDMENTS (2026-10-16). These override this doc wherever they differ.** The operational summary is `20_FINAL_IMPLEMENTATION_BIBLE.md`; the clock list is `21_HACKATHON_CHECKLIST.md`.
> 1. **Sentry entry condition (strengthened).** Select the Sentry challenge only if `docs/sentry_findings.md` holds **at least one real FINDING from our traces/logs AND at least one real engineering DECISION informed or validated by it** (the decision need not be a code change). Each entry records FINDING · EVIDENCE · DECISION · RESULT. No real decision by Sun 08:30 → do **not** select Sentry. Never invent a story; demo lines about "where the time goes" are spoken only if the trace shows it.
> 2. **`GB_CORE_URL` is required.** The Fetch agent runs on B's laptop, not Mac 1. There is **no localhost default**: if the variable is absent the agent fails fast with `GB_CORE_URL is required; point it at the GhostBuild Core host.` Hack-run config is e.g. `GB_CORE_URL=http://<MAC1-LAN-IP>:8787`. Tests may pass localhost explicitly when mock core runs in the same container.
> 3. **Two video exports from one master edit.** GENERAL (Devpost overall, Even, Beyond the Digital): **2:50–2:58**. FETCH: **3:10–3:30**, the same edit plus a 20–30 s ASI:One beat (intent → plan/state card → approval → physical job → VERIFIED card). No "one 3:00 cut for both".
> 4. **Formal feature-freeze exception.** 04:00 = GhostBuild **product** feature freeze: no changes to `core/`, `contracts/`, `perception/`, `g2/`, `spatial/`, planner behaviour or P0/P1 product behaviour. One pre-approved **isolated sponsor-client exception** may exist for `integrations/fetch_agent/` only if **all** hold: F1 green at the 00:30 standup; D approves the exception at 00:30; the agent's automated tests are green; code is isolated in `integrations/fetch_agent/`; it consumes only frozen APIs/contracts; it runs as a separate process on B's machine; `GB_AGENT_ARMED` defaults to 0; Even Beta QA is green before B spends time on it (06:45); and it cannot alter GhostBuild behaviour when not running. After 04:00 the exception may land the tested integration, set env vars, register/connect Agentverse, run ASI:One QA and fix sponsor-client-local bugs. It may **not** change GhostBuild interfaces, core, contracts, perception, planner logic, G2 or Spatial, or request a Beta rebuild. **If any forbidden change appears necessary, Fetch dies.**
> 5. **Collision fixes.** A's sponsor-table visits move from the 12:00–13:00 lunch (A is building the motor for S1) to **11:30–12:00**, after the opening and before hacking starts; unstaffed tables get the same question on the sponsor's Discord channel. B dispatches the Devin briefs **15:00–15:05, after reading G0 and before joining the Even workshop** (sequential, not during it). The Sentry Devpost section and screenshots move from A to **B** (Sun 09:00–10:30). The "any idle 10 min" Devpost draft is dropped; A has no idle time.
> 6. **Cognition is network-only.** The Cognition checkbox is **not** selected (final submission set: Even, Sentry, Fetch if green, Beyond the Digital, MLH Commit opt-in, Workday only if free). Devin stays a coding-capacity tool.

**Tags:** **[V]** read from a first-party source on 2026-10-16 (sources at the end) · **[3P]** third-party source · **[I]** inference · **[D]** decision · **[verify]** check at the event before depending on it · **UNKNOWN** = not published anywhere we could find.

---

# 1. EXECUTIVE DECISION

| | |
|---|---|
| **PRIMARY SPONSOR** | **Even Realities: Smart Glasses Building Challenge.** GhostBuild already *is* this entry. Incremental engineering ≈ 0. |
| **SECONDARY SPONSOR** | **Sentry: Best Use of Sentry.** A log-tailing bridge turns GhostBuild's existing session log into Sentry Tracing ("photon-to-HUD" traces) + Sentry Logs. It never touches P0. **1st place = a guaranteed interview for every team member** [V]. |
| **SECONDARY SPONSOR** | **Fetch.ai: ASI:One Agent Challenge.** A uAgent on Agentverse lets a remote supervisor start, monitor and close a physical job from ASI:One. It is a client of the locked REST/WS, armed only during demos, and **conditional**, with a hard kill at Sun 07:45. **1st, 2nd and 3rd each include an internship interview** [V]. |
| **OPTIONAL FOURTH ONLY IF ~ZERO COST** | **Workday: Future of Work** (framing only, 0 engineering hours; decided Sun 09:00). It enters only if organizers confirm unlimited company-challenge selection. It is never pitched ahead of Even. |
| **ORGANIZER/GENERAL TRACK** | **Beyond the Digital** ("intelligence into the physical world… hardware, augmented reality…") [V]. |
| **Zero-engineering opt-in (not a sponsor integration)** | **MLH Commit Fellowship Prize Category**: opt in on Devpost plus a supplemental form. The prize is an interview for the fellowship [V]. |
| **BEST SPONSOR TO WIN** | **Even Realities.** The brief names our category word for word ("repair guides while you fix a bike", "lab protocols while your hands are full") [V], loaner G2s cap the field, and the closed loop is unique. |
| **BEST SPONSOR FOR CAREER UPSIDE** | **Sentry.** "Every Member of the winning team gets a guaranteed interview… for our internship or new grad roles. Skip the resume pile entirely" [V]. |
| **BEST WIN + CAREER COMBINATION** | **Sentry.** It has the cheapest integration (≈1.3 human h, 0 on the critical path), the highest P(finish) of the secondaries, a field that is likely thin [I], and four guaranteed interviews. Runner-up: **Fetch.ai**, with three placings that each carry an internship interview, but a much riskier build. |
| **BEST COMPANY TO NETWORK WITH WITHOUT BUILDING FOR** | **Cognition.** It hires SF Software, Product, Applied AI and Deployed Engineers [V: Ashby board], and its workshop runs Sat 19:00. The challenge rewards *building with Devin* and does not fit GhostBuild's product (§5.4). Runner-up: **Workday** (an explicit "Early Career Opportunities" workshop, Sat 18:00) [V]. |
| **TOTAL INCREMENTAL SPONSOR ENGINEERING** | **≈ 4.5 human person-hours** during the hack, + ≈ 0.75 h of account setup on Friday night (no project code). About 4.5 h of code-equivalent is delegated to **Devin** as a capacity tool. Contingency: +3 h only if the spatial lane dies early and A hand-builds the Fetch agent. |
| **CRITICAL-PATH INCREMENTAL ENGINEERING** | **0 person-hours.** Nothing touches P0, `core/`, `contracts/`, perception or the G2 plugin. Nothing lands on C before 20:00 or on D before the D/core valves. The only borrowed slot is 0.5 h of B's pre-agreed polish valve (Sat 22:00). |

**Hypotheses we tested and the verdicts:**

| Prior hypothesis | Verdict | Why (short) |
|---|---|---|
| Even Realities | **KEEP: primary** | Brief, rubric and loaner scarcity all favour us (§5.1) |
| Fetch / ASI:One | **KEEP: conditional secondary** | The "complete workflow in ASI:One" rule is satisfiable if the agent owns *supervision* (intent → plan → approval → dispatch → verified report) and the glasses stay the technician's tool (§5.3). Past LA Hacks Fetch winners were physical projects (Lumos 2025, RIIS Apr 2026) [V: doc 00 §2]. |
| Cognition / Devin | **DROP as a target; use Devin as a tool** | The current wording is "Use Devin… to build something exciting… judged on creativity, novelty, and polish" [V]. There is **no** "Augment the Agent" wording. A "Devin verifies reality" MCP needs firmware-driven hardware we don't have, which makes it a disconnected second project (§5.4). |
| StepFun | **DROP** | It can't own a real GhostBuild capability without breaking D-08 (a VLM never decides state), or by duplicating a deterministic path. The VLM label is already gone from the V3 fallback. The prize is **UNKNOWN**, and the track has no Additional Info doc (§5.5). |
| *(new)* Sentry | **ADD: secondary** | It was not in our earlier docs. A guaranteed interview, a ≈1.3 h human cost, and it naturally owns our latency evidence and audit trail (§5.2). |

---

# 2. CAREER OPPORTUNITY ALERTS

> ### CAREER OPPORTUNITY ALERT 1: SENTRY
> | | |
> |---|---|
> | **COMPANY** | Sentry |
> | **OPPORTUNITY** | Guaranteed interview for **every member** of the 1st-place team, for internship **or** new-grad roles |
> | **EXACT OFFICIAL WORDING** | "(1st Place: Every Member of the winning team gets a guaranteed interview with the Sentry team for our internship or new grad roles. Skip the resume pile entirely)" |
> | **SOURCE** | Sentry "View Additional Information" doc linked from live.lahacks.com/tracks [V] |
> | **CONDITIONS** | Build with Sentry and use **at least two products beyond error monitoring** (Session Replay, Logs, Tracing, Profiling, Uptime Monitoring, or MCP/AI agent monitoring). "Show us how observability actually shaped what you built." |
> | **MUST WIN?** | **Yes: 1st place only.** A single prize. |
> | **WHICH GHOSTBUILD SKILLS MATCH?** | Real-time distributed Python/TypeScript systems; latency budgeting across camera → CV → planner → phone → BLE; the SDK, ingest and data-pipeline mindset. Sentry's new-grad roles cover Product (TS/React/Python/Django), Infra (Python/Rust/Kafka/ClickHouse/K8s), and SDK/Ingest (Vienna) [V/3P, §5 jobs]. |
> | **DOES THIS CHANGE OUR STRATEGY?** | **Yes.** Sentry is added as a secondary target. The integration is designed to be zero-risk to P0: a separate tail process (§6.2). |

> ### CAREER OPPORTUNITY ALERT 2: FETCH.AI
> | | |
> |---|---|
> | **COMPANY** | Fetch.ai (Innovation Lab) |
> | **OPPORTUNITY** | An internship interview opportunity attached to **each** of 1st, 2nd and 3rd place |
> | **EXACT OFFICIAL WORDING** | "Best Use of Fetch.ai - 1st Prize $1500 Cash + Internship Interview Opportunity" · "2nd Prize $1000 Cash + Internship Interview Opportunity" · "3rd Prize $500 Cash + Internship Interview Opportunity" |
> | **SOURCE** | fetch.ai/events/hackathons/la-hacks-ai-hackathon-2026/hackpack [V] |
> | **CONDITIONS** | Agent registered on Agentverse; Agent Chat Protocol; discoverable and usable in ASI:One; meaningful tool execution; "complete the primary user workflow entirely within an ASI:One conversation"; public GitHub with run instructions; README badges (`innovationlab`, `hackathon`) plus agent name and address; a **3–5 min** demo video; registration through the **LA Hacks ASI:One Submission Agent** (every teammate joins) [V] |
> | **MUST WIN?** | Yes, any of the top 3 placings. Three chances. |
> | **WHICH GHOSTBUILD SKILLS MATCH?** | Agent orchestration over real tools, a multi-step plan → approve → act → verify loop, and real-time data. The ask is "turn a user's request into an outcome" and ours is a *physical* outcome. |
> | **DOES THIS CHANGE OUR STRATEGY?** | **Yes.** Our earlier docs (01, 16 D-11) rejected Fetch. With three interview-bearing placings and a supervisor framing that satisfies the ASI:One-only rule, Fetch becomes a conditional secondary with a hard kill. |

> ### CAREER OPPORTUNITY ALERT 3: MLH COMMIT FELLOWSHIP (prize category, no sponsor tech)
> | | |
> |---|---|
> | **OPPORTUNITY** | A fellowship interview |
> | **EXACT OFFICIAL WORDING** | "An Interview with the Commit Fellowship Team & a copy of The Lean Startup" · "Exclusive Admission: A chance to interview for the highly selective Commit Fellowship 3-week sprint." |
> | **SOURCE** | la-ai-hackathon-2026.devpost.com prize list [V] |
> | **CONDITIONS** | "building a working prototype with a team, demonstrate a real problem worth solving, and opt into the Commit Fellowship Prize Category when you submit your project… submit this supplemental form". One winner, "selected post-event". |
> | **MUST WIN?** | Yes, selected post-event. |
> | **STRATEGY CHANGE?** | A 15-minute opt-in for A at Devpost time. No engineering. |

> ### CAREER-ADJACENT (CONFIRMED, not a recruiting interview)
> - **Workday:** "the winning team may be invited to meet with the Workday Developer Relations team after the hackathon to discuss their prototype…" [V: Workday PDF]. This is a DevRel conversation, not hiring. Its workshop title includes "**Early Career Opportunities**" (Sat 18:00) [V: schedule].
> - **CREAO:** "Winning teams are also invited into CREAO Launchpad… founder mentorship, and launch support" [V]. It requires building on CREAO, so we are **not pursuing** it.
> - **Even Realities, Cognition, StepFun, Paper, QNX, Espressif, Visa, Intuit, Base44, Photon, Browser Use, veri:** no recruiting benefit published [V: their docs]. Event sponsors listed without tracks: Annapurna Labs (workshop Sat 14:00), AWS, a16z speedrun, Pebblebed, Accenture, Adobe, AppLovin, Alma, Pure Buttons [V: tracks page footer]. Their recruiting presence is **SPECULATIVE**.

---

# 3. COMPLETE TRACK INVENTORY

Source: live.lahacks.com/tracks plus every "View Additional Information" link, the Devpost prize list, and the sponsor hackpacks [V]. "Hours" means incremental person-hours for a winning-quality GhostBuild entry. Risk is shown as H/M/L.

### 3.1 Company challenges

| Sponsor | Challenge | Mandatory requirements | Prize | Career benefit | Fit /100 | Est. h | Risk | Verdict |
|---|---|---|---|---|---|---|---|---|
| **Even Realities** | Smart Glasses Building Challenge: "Quiet Tech" app for G2 | Even Hub **Beta** build uploaded; runs on **physical G2** at judging (loaners at table); Devpost + select challenge; Even Hub app name in submission; G2 in demo video; README install/run on G2 incl. accounts/keys; name ≤ 20 chars, no "Even"; no medical/financial/emergency-routing apps [V] | 1st: G2 per member (4 pairs, $2,400); 2nd: $250 OpenAI/ChatGPT gift card pp; 3rd: $100 pp [V] | None published | **94** | ~0.35 | M (Beta/LAN transport, already gated G0) | **PRIMARY** |
| **Sentry** | Best Use of Sentry | Build with Sentry; **≥ 2 products beyond error monitoring** (Replay, Logs, Tracing, Profiling, Uptime, MCP/AI agent monitoring); show how observability shaped the build [V] | 1st only: guaranteed interview for every member (intern/new grad) [V] | **CONFIRMED interview (1st)** | **74** | ~1.3 (+Devin) | L | **SECONDARY** |
| **Fetch.ai** | ASI:One Agent Challenge: From Intent to Action | Agentverse registration; Agent Chat Protocol; discoverable + usable in ASI:One; meaningful tool execution/orchestration; **primary workflow entirely in ASI:One, no custom frontend**; public GitHub; Submission Agent; README badges + agent addresses; 3–5 min video [V] | $1,500 / $1,000 / $500, each + internship interview [V] | **CONFIRMED interview (top 3)** | **70** | ~2.2 (+Devin) | H (internet, ASI:One unknowns, unowned capacity) | **SECONDARY, conditional** |
| **Workday** | Build the Future of Work with AI | Show the problem, user, prototype, how the agent works, what it does autonomously, where the human is involved, data/assumptions, responsible AI, organizational value [V] | Prize amount **UNKNOWN** ("any Workday Company Track prize"); DevRel follow-up for winners [V] | DevRel meeting (CONFIRMED, winners) | 52 | 0.25 | L | **Optional 4th (framing only)** |
| **Cognition** | Best Use of Devin | Use Devin to build; judged on creativity, novelty, polish; free Devin credits for every team [V] | $5,000 Devin credits, single prize [V] | None published | 48 | 0 (tool use only) | L | **Not a target**; Devin as a capacity tool |
| **StepFun** | Get It Done with Step 5 Preview | "Your app or workflow must call step-5-preview when it runs"; explain each model's role; judged on task completion, reliability, user understanding/control [V] | **UNKNOWN** (no Additional Info link) | None | 45 | 1–2 | M | **Drop** |
| **Paper** | Best Designed Hack | Judged on design fundamentals, ease of use, personal craft (not AI-looking). The Paper desktop app over MCP is set-up guidance [V] | $1,500 / $1,000 / $500 [V] | None | 38 | 4+ | M | Drop |
| **MLH: Commit Fellowship** | Prize category | Working team prototype; real problem; opt-in + supplemental form [V] | Fellowship interview + book [V] | **CONFIRMED fellowship interview** | 60 (n/a tech) | 0.15 | L | **Opt in (no engineering)** |
| MLH: Gemini API | Best Use of Gemini | Use the Gemini API | Swag kits [V] | None | 25 | 2 | M | Drop (duplicates Opus) |
| MLH: ElevenLabs | Best Use of ElevenLabs | Use ElevenLabs | Wireless earbuds [V] | None | 8 | 3 | M | Drop (G2 has no speaker; audio contradicts Quiet Tech) |
| MLH: Snowflake / Vultr / Solana / Tiger Data / GoDaddy / DEV Writing | Platform prizes | Use the platform; DEV = post-event blog | Hardware/gift cards/$100; tracks doc and Devpost list different items [V] | None | ≤ 20 | 2–4 | — | Drop (DEV post optional after the event) |
| **QNX** | Best use of QNX | Product uses QNX OS **and** an AI module from oss.qnx.com [V] | $1,000 / $250 / $250 [V] | None | 22 | 8+ | H | Drop (separate embedded project) |
| **Espressif** | Best Use of Espressif | Espressif hardware [V] | ESP-VoCat; M5Stack StopWatch [V] | None | 18 | 6+ | H | Drop |
| **Base44** | Build Something People Want | "built substantially using Base44"; live Base44 app [V] | $1,500 / $500 [V] | None | 12 | 10+ | H | Drop |
| **Visa** | Future of Shopping | AI commerce experience [V] | $2,000 [V] | None | 8 | — | — | Drop |
| **Intuit** | QuickBooks: System One models | Financial experience, realistic eval vs baselines [V] | $200 / $100 / $50 pp [V] | None | 6 | — | — | Drop |
| **Photon** | Messaging/calling agent with Photon 2.0 | Use Photon 2.0 beta [V: tracks card] | UNKNOWN | None | 20 | 3 | M | Drop (an SMS "VERIFIED" ping would be sponsor soup) |
| **Browser Use** | Best Use of Browser Use | Web agent [V] | UNKNOWN | None | 10 | — | — | Drop |
| **CREAO AI** | AI-First Disruptor / One-Person Co. / Team Empowerment | Build on CREAO [V] | $2,000 / $1,000 / $500 + Launchpad [V] | Launchpad founder mentorship | 15 | 6+ | M | Drop |
| **veri.studio** | Best use of an open-source model | Train on Veri; show before vs after [V] | GPU credits (UNKNOWN cash) [V] | None | 20 | 6+ | H | Drop (learned state contradicts D-02/D-08) |

### 3.2 Organizer / general tracks

| Track | Description [V] | Fit /100 | Verdict |
|---|---|---|---|
| **Beyond the Digital** | "brings intelligence into the physical world… embedded AI, hardware, augmented reality, virtual reality, or other emerging interfaces" | **95** | **SELECT** |
| Applied Intelligence | "AI to solve real-world problems beyond traditional AI applications" | 75 | Backup only |
| Agentverse (sponsored by Fetch.ai) | "Build and Register AI Agents on Agentverse… turn user intent into real, executable outcomes" | 50 | No. The agent is a layer, not the product. The Fetch company challenge is separate [I; verify at opening]. |
| Model Learning | "systems that learn, adapt, and improve from data" | 30 | No |

**Overall judging** (all projects) [V: Devpost]: Technical Depth · Product Thinking & Impact · Execution & Polish · Originality & Insight. Devpost lists overall prizes as "To Be Determined" and "10 non-cash prizes". **Rules** [V]: ≤ 4 members; in-person judging; "How does it apply to the company challenges you submitted to?" (plural) is a required Devpost field, so multiple company challenges are **LIKELY** allowed [I; verify at opening]. The rules page still shows a stale "8am… April 26" deadline; the hackpack and schedule say **Sun 12:00** [V].

---

# 4. FULL SPONSOR RANKING

Rubric: Fit 25 · Wow 20 · Tech central 15 · Buildability 15 · Reliability 10 · Eligibility 5 · Differentiation 5 · Prize 5. The probabilities are **comparative judgments, not measurements** [I].

| # | Sponsor | Fit | Wow | Central | Build | Rel. | Elig. | Diff. | Prize | **/100** | P(finish) | P(qualify) | P(win \| finished) | Value | **Expected sponsor value** | Career /10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **Even Realities** | 25 | 19 | 15 | 14 | 7 | 4 | 5 | 5 | **94** | 0.80 (loan + Beta) | 0.95 | 1st ≈ 0.40 · any ≈ 0.70 | $2.4k hardware, gift cards | **HIGHEST** | 5 |
| 2 | **Sentry** | 15 | 12 | 11 | 13 | 9 | 5 | 5 | 4 | **74** | 0.75 | 0.95 | 1st ≈ 0.35 | 4 interviews | **HIGH (career-weighted)** | **9** |
| 3 | **Fetch.ai** | 17 | 15 | 12 | 8 | 5 | 3 | 5 | 5 | **70** | 0.50 (spatial lives) · 0.65 (A freed) | 0.80 | top-3 ≈ 0.40 | $500–1.5k + interview | **MEDIUM** | **8** |
| 4 | MLH Commit Fellowship (opt-in) | — | — | — | 15 | 10 | 4 | 3 | 4 | 60* | 1.0 | 0.95 | ≈ 0.10 | fellowship interview | LOW-MED per minute spent: best | 6 |
| 5 | Workday (optional) | 11 | 10 | 5 | 15 | 10 | 3 | 3 | 2 | 52 (59 incl. "no required tech") | 0.95 | 0.80 | ≈ 0.12 | UNKNOWN + DevRel | LOW-MED | 6 |
| 6 | Cognition | 8 | 8 | 5 | 12 | 8 | 4 | 0 | 3 | 48 | 0.90 (if Devin used) | 0.90 | ≈ 0.07 | $5k credits | LOW | 6 |
| 7 | StepFun | 10 | 6 | 6 | 11 | 6 | 4 | 1 | 1 | 45 | 0.60 | 0.90 | ≈ 0.20 | UNKNOWN | LOW | 3 |
| 8 | Paper | 10 | 8 | 4 | 6 | 7 | 4 | 3 | 4 | 46→38 after design-time cost | 0.5 | 0.9 | ≈ 0.10 | $500–1.5k | LOW | 3 |
| 9 | MLH Gemini | 5 | 4 | 3 | 8 | 3 | 1 | 0 | 1 | 25 | — | — | — | swag | NONE | 2 |
| 10 | QNX | 5 | 5 | 3 | 1 | 2 | 2 | 2 | 2 | 22 | — | — | — | $1k | NONE | 4 |
| 11 | Photon · veri · Espressif · CREAO · Base44 · Browser Use · MLH platform prizes · Visa · Intuit | ≤ 6 | — | — | — | — | — | — | — | ≤ 20 | — | — | — | — | NONE | 3–5 |

\*The Commit Fellowship has no sponsor technology; its score is not comparable and only shows why the opt-in is worth 15 minutes.

**Reading:** Even (prize) and Sentry (career) dominate, and Fetch is a distant third. Fetch is worth doing only under the strict kill rules in §14. Sponsor-soup penalties applied: StepFun (a model added where a deterministic path already does the job), Gemini (duplicates Opus), Photon (a notification bolted onto an existing feature), Cognition ("we used Devin to code").

---

# 5. TOP 5 DEEP DIVES

## 5.1 Even Realities: PRIMARY

**A. What they want.** A G2 app for one real moment, where "a small piece of information, quietly placed in someone's line of sight" helps, and that "stays in the background until the moment it becomes useful". The brief lists the category we're in, "repair guides while you fix a bike… step-by-step lab protocols while your hands are full", and warns that "teleprompters, translators, and note-takers… won't stand out" [V]. The judge is rewarding **restraint plus a genuinely new moment**, experienced on the glasses *now*.

**B. Requirements.**
- **Mandatory** [V]:
  - Beta `.ehpk` uploaded and pushed;
  - physical G2 at judging;
  - Devpost, with the challenge selected and the Even Hub app name included;
  - G2 shown in the video (through the lens or the simulator);
  - a README covering G2 install/run, accounts and API keys;
  - an app name ≤ 20 characters, without "Even";
  - not a medical, financial or emergency-routing app;
  - the team present at judging, and the loaner returned.
- **Recommended:** Starter-pack QA [V]: 5-minute phone-lock recovery, permission denial, root double-tap exit, await the bridge, `isEventCapture`, CORS plus whitelist, and testing the *installed* Beta.
- **Bonus:** none listed.
- **Rubric:** **two published versions.**
  - The LA Hacks-linked doc: Made for G2 · **Quiet by Design** · Originality · Experience & Polish · Execution ("Can a judge put on G2 and experience the core idea right now?").
  - The starter pack: Made for G2 · Originality · User Experience · Technical Execution.
  - Judges will ask: "Who uses this, and when? Why G2? Can the judge try it right now?" [V].

**C. Technology.** Even Hub SDK: text and image containers, events, contextual menu, glasses mic, local storage, and a network whitelist. G2 has **no camera and no speaker** [V; 08]. All of this is already specified in 08.

**D. GhostBuild fit.** Total. The glasses *are* the delivery surface. Remove G2 and the product loses its point: one verified action, hands busy, eyes on the work.

**E. Winning integration.** Already built: the closed loop on G2 (instruction → act → verify → next → `● VERIFIED` → dark), with questions as contextual-menu actions rather than a chatbot. **Is it unusually competitive? Yes** [I]:
1. It is the only kind of entry where **the glasses react to the judge's own physical mistake** (`X DECK TOO EARLY`).
2. "Quiet by Design" is the core behaviour, not a setting.
3. The category is named in the brief.
4. It is visibly *not* a teleprompter, translator or note-taker.

Loaners are one per team and limited [V], so the field is small.

**Small changes that materially raise P(win), with no UI redesign:**

| # | Change | Cost | Owner | Why it moves the rubric |
|---|---|---|---|---|
| E-a | **Quiet metric** from the existing session log: HUD changes per run, plus % of task time the display was dark or dimmed. Added to the eval table and the Even pitch. | 0.25 h, inside D's existing 07:45 eval slot (no P0 code) | D | Turns "Quiet by Design" from a claim into a number. No competitor will have it. |
| E-b | **Three Even questions** answered on the phrase card in one sentence each. *Who:* someone repairing or assembling with a manual and their hands full. *When:* the moment they'd stop to search the manual. *Why G2:* hands in the work, eyes on the work, one action at a time. | 0.1 h | A | Matches the judges' stated questions word for word |
| E-c | **Even table visit Sat 16:00–20:00 with the stub Beta build** (already in 14/V2 for G0). Ask: "How do you judge: table visits after submission?" and "Is LAN `ws://` OK in Beta?" | 0 (already planned) | B | De-risks Execution; the team gets known by name |
| E-d | **Even judge script leads with the glasses**, not the phone mirror (§10). The second judge watches the twin. | 0 | A | The phone CAD must not upstage "Made for G2" |
| E-e | **End every Even demo on the dark display** and say nothing for one beat | 0 | A | Quiet by Design, experienced rather than told |

**F. Minimum qualifying version.** The rocket P0 on a Beta build on a physical G2, plus the Devpost fields. (This is already V3's floor.)

**G. Demo moment (≈25 s).** The judge wears G2 and sees `LIFT DECK` / `TO CHECK MOTOR`. They lift it, then put it straight back. The HUD shows `X DECK TOO EARLY` / `LIFT IT · BAR FIRST`. They fix it, and the HUD shows `● VERIFIED` / `MATCHES TARGET`. The display goes dark. Captain: "That's the whole interface. It only spoke when you needed it."

**H. Cost.** ≈ 0.35 h incremental. Failure modes (Beta transport, loan) are already gated at G0 15:00. Submission overhead: Beta pushed by 11:00, plus the README section (already in V3's schedule).

**I. Risk.** Technical M (LAN in Beta) · integration L · demo M (BLE in a crowded hall) · internet L (the LAN rung works offline) · submission L · scope creep L.

**J. Prize.** 1st: four G2 pairs ($2,400 total). 2nd: $1,000 in gift cards. 3rd: $400 in gift cards [V]. Career: none published. Even Realities raised a reported $150M, grew from 30–40 to 300–400 staff, and says ~80% of its developers are in the US [3P]. Relationship value with the developer ecosystem is **LIKELY**; recruiting is **SPECULATIVE**.

---

## 5.2 Sentry: SECONDARY (new)

**A. What they want.** Real use of observability beyond error capture, plus a *story*: "the slow endpoint you found in a trace, the broken flow you caught in a replay, the bug you squashed at 4am because your logs told you where to look" [V]. The judge rewards **observability that changed engineering decisions**, not a dashboard screenshot.

**B. Requirements.**
- **Mandatory:** use Sentry; ≥ 2 products beyond error monitoring [V].
- **Recommended:** the story of how it shaped the build [V].
- **Bonus:** none stated.
- **Separate form:** none found [verify at opening].

**C. Technology.**
- Python SDK: `sentry_sdk.init(..., traces_sample_rate, enable_logs=True)`. Logs need SDK ≥ 2.35.0 [V: docs.sentry.io].
- Custom spans via `sentry_sdk.start_span`, with a `start_timestamp` argument [3P/vendored source; **verify against the installed SDK**].
- `sentry_sdk.logger.*` for structured Logs [V].
- Error/Issue capture.
- (Optional) AI agent monitoring through manual spans on agent tool calls [verify].

**D. GhostBuild fit (does it solve a real problem?).** Yes. GhostBuild's two load-bearing claims are measured properties of a distributed real-time loop:
1. camera-to-glasses latency, split into vision / core / BLE (10 §3);
2. **0 wrong instructions** (10 §3; V3 §6.3).

Both are already computed offline from `logs/session-*.jsonl` (`make eval-latency`). Sentry can own the *live* version: every instruction on the glasses gets a trace back to the camera frame that justified it, and every abstention (HOLD, AMBIGUOUS, `uncertain`) becomes a searchable log line. That is a real debugging tool during the hack (tuning K, the vote, BLE pacing), not a logo.

**E. Winning integration: "photon-to-HUD tracing".**
- **What Sentry owns:** the live latency budget, plus the instruction audit trail.
- **Build:** `integrations/sentry_bridge/` is a **separate process** that tails the session jsonl on Mac 1 (`nice -n 19`, read-only). For each HUD instruction it emits one Sentry transaction `glasses_instruction` with spans:
  - `vision.process`: `observation.timing.capture_ts_ms` → observation `ts_ms`;
  - `core.vote`: first sighting of the new state → stable commit;
  - `core.plan_arbiter`: commit → `hud` emit;
  - `g2.ble_render`: `hud_ack.bridge_ms`.

  Each transaction carries the attributes `hud.line1`, `mode`, `alert`, `plan.last_event.kind`, `source` (`cv` | `spatial`) and `task_id`.
- **Logs:** every `plan.last_event` (deviation, premature, progress), every HUD instruction, every turn (intent, basis, citations), every abstention.
- **Issues:** `hud_ack.result ≠ ok`, WS disconnects, `no_board`.
- **Second process** (natural, near zero cost): the Fetch agent (if alive) calls `sentry_sdk.init` and wraps each tool call in a span, so one trace runs from an ASI:One sentence to the core endpoint it hit.
- **Visible to the judge:** a trace waterfall for the exact instruction they just saw on G2, and the log line where the system *refused* to instruct while their hand covered the part.
- **Worse without it?** The latency split and the abstention record would exist only as an offline table at 04:00. Sentry makes them inspectable during the build, which is when tuning happens.
- **One sentence:** "Every instruction on the glasses is a Sentry trace back to the camera frame that justified it."

**F. Minimum qualifying version.** The bridge emitting Tracing + Logs from the jsonl. That is two products beyond errors.

**G. Demo moment (≈20 s).** On the second laptop: "Here's the trace of the instruction you just saw: camera frame, our deliberate stability vote, planner, then the glasses render." *(Only if the trace actually shows it:)* "Most of the time is the vote, on purpose." "And here's where it refused to instruct while your hand covered the motor."

**H. Cost.**

| Item | Owner | h |
|---|---|---|
| Friday: org, project, DSN in the password manager, run the SDK's hello example (not project code) | A | 0.15 (pre-hack) |
| Devin task dispatch (brief pre-written, Appendix A) | B, Sat 15:00–15:05, after reading G0 and before joining the Even workshop | 0.05 |
| Bridge code + tests against a mock-core session log | **Devin** | (≈1.5 h-equivalent) |
| Review + land on Mac 1, check a live trace | B, Sat 22:00–22:30 (B's polish valve) | 0.5 |
| Findings log (`docs/sentry_findings.md`: FINDING · EVIDENCE · DECISION · RESULT; only true entries) | B keeps it; anyone may report a finding to B | 0.25 |
| Devpost section + 3 screenshots | B, Sun 09:00–10:30 | 0.5 |
| **Total human** | | **≈ 1.3 h** |

- Auth: one DSN as an env var, never in git.
- Deployment: none.
- Failure modes:
  - no internet: events drop silently, and the demo is unaffected;
  - log format surprises: the brief tells Devin to inspect real mock logs first;
  - SDK timestamp API differences [verify].

**I. Risk.** Technical L · integration L (read-only tail, no P0 imports) · demo L (screenshots back up the live dashboard) · internet M (hotspot cellular) · submission L · scope creep M (keep it to the bridge plus the agent spans; no plugin JS SDK, because the G2 whitelist would force a Beta repack).

**J. Prize.** 1st only: guaranteed interview for every member, for intern or new-grad roles [V]. No cash.

---

## 5.3 Fetch.ai: SECONDARY, CONDITIONAL

**A. What they want.** "Most AI applications stop at conversation… go further": an agent that understands intent and "take[s] meaningful action to solve a real-world problem… real utility, autonomy, and the ability to turn a user's request into an outcome. Avoid simple chatbots or thin wrappers around a single API" [V].

Weights [V: hackpack]:
- Functionality & technical implementation 25%;
- **Use of Fetch.ai technology 20%** (Agentverse registration, Chat Protocol, Payment Protocol);
- Innovation & creativity 20%;
- Real-world impact 20%;
- UX & presentation 15%.

The judges are Fetch.ai / Innovation Lab staff [V].

**B. Requirements.**
- **Mandatory** [V, tracks doc + hackpack + local PDF agree]:
  - ≥ 1 agent registered on Agentverse;
  - Agent Chat Protocol;
  - discoverable and usable in ASI:One;
  - meaningful tool execution or multi-agent orchestration;
  - **"Complete the primary user workflow entirely within an ASI:One conversation"** / "without requiring a custom frontend";
  - a public GitHub repo with run/test instructions;
  - Submission Agent registration, with **every teammate joining** (status flips to "Submitted" only when all have joined);
  - a README with each agent's name and address plus the `innovationlab` and `hackathon` badges ("All agents must be categorized under Innovation Lab");
  - a **demo video of 3–5 min** demonstrating the agents.
- **Recommended:** ASI1 Interactive Cards [V].
- **Bonus:** multi-agent collaboration; Payment Protocol with credible monetization; effective cards; reliability and recovery from failed tool calls; real-time data and external services; "could realistically continue operating after the hackathon" [V].

**C. Technology** [V: Innovation Lab docs].
- **uAgents** (`uagents==0.25.5` in the ASI-compatible example) with the `chat_protocol_spec` (AgentChatProtocol 0.3.0).
- Handlers for `ChatMessage` and `ChatAcknowledgement`.
- `publish_manifest=True`.
- **Mailbox agents** (`mailbox=True`) run locally and are registered through the Agent Inspector → Connect → Mailbox.
- **Interactive Cards** are a `MetadataContent` block with `card_protocol_version: "1"`, `card_kind ∈ {carousel, detail, form, review, custom}`, and `card_payload` as a JSON string.
  - Payload ≤ 64 KB; custom trees ≤ 8 levels.
  - An invalid payload silently falls back to plain text.
  - **Images are URLs only** (base64 is undocumented).
  - User selections come back as text (planner-narrated) or JSON (direct `@mention`).
  - **Updating a card in place is undocumented**: send a new card per step.
- Agentverse MCP servers exist (`mcp.agentverse.ai/sse`, `mcp-lite.agentverse.ai/mcp`) [V].
- **Not documented:** whether ASI:One shows *unsolicited* agent messages, and any response timeout [verify both at the 11:30 Fetch table visit or on the Fetch Discord].

**D. GhostBuild fit.** Real, in one specific role: **supervision.** In field service someone other than the technician owns the job: they decide what must be fixed, approve the plan, and need proof it was done. GhostBuild today has no remote-intent or verified-report surface; the phone goal chip is a local operator control. Fetch genuinely owns "**intent enters → plan approved → job dispatched → physical outcome verified → report delivered**". The glasses remain the technician's hands-free execution device. They are not the agent's frontend.

**Resolving "the complete primary workflow inside ASI:One".** The *agent's* primary user is the supervisor, and the supervisor's whole workflow happens in ASI:One:
1. state intent;
2. see the inspected state;
3. approve the plan (review card);
4. dispatch;
5. ask status / why;
6. receive the verified outcome (terminal card).

The physical work is the outcome the agent produces, done by a person on site. That is no more a "custom frontend" than a courier is for a delivery agent. Residual risk: a strict judge may read G2 as a frontend. Mitigation:
- Ask the Fetch team this exact question on Saturday (§12).
- Ensure the chat is coherent with the glasses never shown. The plan card lists the steps in plain text, so a technician *could* follow it from the chat alone.

The phrase card says: "The agent's workflow is complete in ASI:One; the glasses are the technician's tool."

**Evaluating the proposed architecture** (ASI:One → agent → understand goal → inspect → load docs/CAD → world state → planner → monitor → replan → verify): it is right in shape, but the agent must not *re-implement* any of it. The agent **orchestrates** GhostBuild's existing services; GhostBuild's planner does the planning. Mapping:

| Proposed step | Who actually does it | Agent tool (client of locked interfaces only) |
|---|---|---|
| understand the user's goal | ASI:One's LLM routes the text; the agent's **deterministic** router maps it to `{task, component}` (no second chatbot) | — |
| inspect physical workspace / query world state | core (world, diff, `spatial_state`) | `inspect_workspace()`: one-shot `ws ?role=twin` connect, read the snapshot core sends on connect, close (05 §13) |
| load documentation/CAD | the bundle already compiled at build time | `get_manual_evidence(step)`: `GET /knowledge/<task_id>` (05 §2) |
| invoke planner | core planner (and teardown, if CORE-FULL merged) | `start_job(task)`: `POST /control/task` + `/control/reset`; `set_goal(component)`: `POST /control/goal` (V3 §4.1 item 6) — **both ARMED-only, after review-card approval** |
| monitor physical changes / replan after mistakes | core (deviation, premature, replans) | `get_status()`: snapshot `plan.progress`, `plan.last_event`, `twin.log` |
| verify final physical outcome | core (`plan.status == verified`) | `verify_outcome()`: terminal card with evidence chips (TRACKED / LAST SEEN / CAD / citation) |
| answer "why?" | the planner's structured `why` + bundle evidence (deterministic) | `explain_step()`: **read-only; never `/control/ask`**, which would push an answer onto the technician's HUD |

**E. Winning integration.** **What Fetch owns:** remote intent, approval and verified reporting for physical jobs. **Positioning:**
> "Most agents turn intent into API calls. GhostBuild's agent turns intent into a *verified physical-world outcome*, and it shows you the evidence."

That is an excellent Fetch entry **if it runs live**: it hits "real-world problem", "multi-step orchestration", "real-time data" and "could keep operating", and it stands out against likely travel, shopping and booking agents [I]. It is **not** sponsor soup, because no other GhostBuild component does remote intake or reporting.

Cards (all `custom` or `review`; no images required):
1. **Workspace state:** per component, with honesty labels (`DECK TRACKED·IMG` · `MOTOR HIDDEN · NOT YET SEEN`);
2. **Plan review:** goal, teardown path, first action, Approve / Reject;
3. **Job progress:** step n/m, last event (e.g. "deck put back too early → replanned");
4. **VERIFIED** (`is_terminal`): matched target, evidence chips, time, citation.

Images are optional, and only if a snapshot URL can be served through the existing Funnel host [verify Funnel multi-port/path]; never base64.

**F. Minimum qualifying version.** A mailbox agent with ACP, three text-only tools (`inspect_workspace`, `start_job`, `get_status`), a review card, Agentverse registration, a shared chat, the Submission Agent, and the README badges.

**G. Demo moment (≈30 s).**
1. The laptop shows ASI:One: "Fix the motor assembly on the bench rover."
2. The state card appears: the motor is hidden and never seen; the deck and bar are on.
3. The plan card follows ("open deck → remove bar → inspect motor"), and the judge clicks **Approve**.
4. The technician's G2 lights up `LIFT DECK` / `TO CHECK MOTOR`. The physical run happens.
5. "status?" → the progress card shows "motor measured 90° off its documented orientation → rotate".
6. The **VERIFIED** card closes the job.

**H. Cost** (assuming spatial lives; Devin builds, a human lands it).

| Item | Owner | h |
|---|---|---|
| Friday: Agentverse + ASI:One accounts, promo `LAHACKSAI26LAHACKSAI26AV` [V], run the official ASI-compatible example, confirm it answers in ASI:One, then delete it (tool familiarity, not project code) | A | 0.5 (pre-hack) |
| Devin dispatch (Appendix B), with the Sentry brief | B, Sat 15:00–15:05 (same dispatch as Appendix A) | 0.05 |
| Agent + tools + cards + tests against `core --mock-vision` | **Devin** | (≈3 h-equivalent) |
| F1 read at the 00:30 standup (PR CI green?) | D | 0.05 |
| Land on B's laptop (not Mac 1) under the isolated sponsor-client exception (amendment 4), set `GB_CORE_URL` to Mac 1's LAN IP, mailbox connect, profile README + badges, ASI:One test (disarmed, then armed), F2 run (B is technician and supervisor) | B, Sun 06:45–07:45 | 1.25 |
| Shared chat recorded alongside one of C's normal rehearsal runs (C's rehearsal is not sponsor work) + 20–30 s ASI:One screen clip for the FETCH export | B | 0.25 |
| FETCH extended export (master edit + ASI:One beat, 3:10–3:30), 08:30–09:00 | A | 0.25 |
| Submission Agent: B creates; three teammates join with the Team ID | all | 0.35 |
| **Total human** | | **≈ 2.2 h** (+0.5 h pre-hack) |

- Auth: an Agentverse/ASI:One login and the agent seed in env.
- Deployment: a local mailbox agent, so no hosting.
- Internet: **required** (mailbox ↔ Agentverse ↔ ASI:One).
- Failure modes: ASI:One discoverability lag; unsolicited-message support [verify]; response timeouts [verify]; card schema rejection (it falls back to text, so the flow still works); venue internet (use hotspot cellular).

**I. Risk.** Technical M · integration L (client only) · **demo H** (needs the live rig, internet and an armed agent) · **internet H** · submission M (Submission Agent plus all teammates joining) · scope creep H (payments, multi-agent and images are all **out**).

**J. Prize.** $1,500 / $1,000 / $500, each with an internship interview [V]. One month of ASI:One Pro + Agentverse Premium for all participants [V].

**Kill time:** Sun **07:45** (F2: live end-to-end chat on the real rig). See §14.

---

## 5.4 Cognition / Devin: NOT A TARGET (Devin used as a tool)

**A. What they want (current wording, verified).** "Use Devin, the AI software engineer, to build something exciting. Ambitious ideas welcome: Devin plans, writes, tests, and ships the code alongside you, so aim bigger than a weekend normally allows. Projects judged on creativity, novelty, and polish. Every team gets free Devin credits" [V: tracks card + Additional Info]. **The "Augment the Agent" framing does not appear** in the current materials. The judge rewards projects *built with Devin* that are creative, novel and polished. The April 2026 winner, codebreaker, had autonomous agents as its product [V: doc 00 §2].

**B. Requirements.** **Mandatory:** use Devin [V]. Nothing else is published (no form, no MCP requirement).

**C. Technology.** Devin supports custom MCP servers ("Add Your Own"; STDIO, SSE or HTTP), and adding one may need a "Manage MCP Servers" permission [V/3P: docs.devin.ai]. Devin works in a cloud VM against a GitHub repo.

**D. Fit, and the "Devin verifies reality" MCP evaluated.**
- A **GhostBuild Physical-World MCP** (`inspect_physical_system`, `get_spatial_diff`, `verify_physical_outcome`, `wait_for_physical_change`, …) is technically compatible: it would be an HTTP MCP behind the Funnel.
- The **loop it promises** is "Devin edits code/firmware → GhostBuild checks real hardware". That needs a device *whose behaviour is controlled by code Devin edits*. Our rigs are passive LEGO assemblies; the rover "motor" is a brick model, not an electrical motor (V2 §7.2). Making it real needs Hardware Lab motors, drivers and sensors plus firmware (≈ 6–10 h, new owner, new failure modes): **a disconnected second project.**
- The physical-QA, field-engineering and hardware-in-the-loop angles all hit the same wall.
- It also widens the attack surface: `/control/*` publicly reachable for a cloud agent.
- **Verdict:** the strongest Cognition angle is not affordable and is not GhostBuild. Do not build it.

**E. What Devin is genuinely good for here.** Capacity. The team is ≈ 15 h over supply (V2 §11.1). Devin can write the **two sponsor integrations**, which are isolated, spec-complete, outside P0, and testable in its VM against `core --mock-vision` (Appendices A and B). That is the only Devin use we recommend. The rules for it:
- no P0, core or contract tasks;
- every task has a command that proves it in Devin's VM;
- a human lands it once;
- if Devin's PR isn't green at the kill time, the feature dies. **No human rescue** (except A, only if the spatial lane has already died; §14).

**F–G. Minimum and demo moment.** Only if Devin's PRs actually merge: the Devpost "built with" section names the two integrations Devin authored, with PR links. There is no demo beat.

**H. Cost.** 0 incremental. It *saves* ≈ 4.5 h of human code, at ≈ 0.6 h of dispatch and review.

**I. Risk.** Low. The main risk is that Devin's output is wrong, and the kill rule absorbs it.

**J. Prize.** $5,000 Devin credits, single winner [V]. ~~**Entering:** the Cognition checkbox is optional and decided at 10:00 Sun, only if both Devin PRs merged.~~ **SUPERSEDED (final reconciliation): the Cognition checkbox is not selected.** The honest story is "Devin built our sponsor integrations", which the brief explicitly calls weak. Cognition is network-only; Devin is a coding-capacity tool. **It does not count as an active sponsor.**

---

## 5.5 StepFun: DROP

**A. What they want.** "Pick a problem… build an app or agent that addresses it with Step 5 Preview. You could… use image understanding to guide the next action… Your app or workflow must call step-5-preview when it runs… explain what each [model] does… Judges will look at how well your project completes the task, how reliable the implementation is, and whether users can understand and control the workflow" [V].

**B. Requirements.** **Mandatory:** call `step-5-preview` at runtime, and explain each model's role [V]. **Prize: UNKNOWN.** The track card has no Additional Info link.

**C. Technology** [V: platform.stepfun.ai]:
- `step-5-preview`;
- input: text, images (URL or base64, up to 60 per request) and video;
- tool calling;
- JSON Schema;
- 1M context;
- reasoning effort low/medium/high.

The Hugging Face weights, open since Oct 15, and the third-party pricing are [3P]. A workshop runs Sat 20:00 [V].

**D. Fit.** "Use image understanding to guide the next action" sounds exactly like GhostBuild. But GhostBuild's founding insight is that **VLMs must not decide physical state** (D-08; 10 §4). The only VLM slot, W5's foreign-object label, is **not** in V3's fallback demo. The candidate roles all fail:
1. **Second-opinion VLM narration:** labelled as decorative. That is soup.
2. **Fetch agent's intent parser:** duplicates ASI:One's LLM plus our deterministic router.
3. **Manual extraction:** replaces Opus in K1, D's frozen path, and adds risk to a 17:00 valve.

None of them owns a capability we lack.

**E–G.** No winning integration exists that isn't sponsor soup. **Minimum:** a narration call per HUD change. Not recommended.

**H. Cost.** 1–2 h plus a runtime internet dependency. **I. Risk.** Medium, and it widens the claim-audit surface. **J. Prize:** UNKNOWN.

**Verdict:** drop. *(Applied in the final reconciliation: doc 01 §3 and D-11 updated.)*

---

### 5.6 Remaining sponsors, compact A–J

| Sponsor | A. Want | B. Mandatory | C. Tech | D. Fit | E/F. Best/min integration | G. Moment | H. Cost | I. Risk | J. Prize |
|---|---|---|---|---|---|---|---|---|---|
| **Workday** (optional 4th) | An agent that helps new employees ramp, find trusted info and complete everyday tasks, with humans in control. Agentic logic 30%, new-hire relevance 20%, responsible AI 20%, Workday relevance 15%, UX 10%, pitch 5% [V] | Show the problem, user, prototype, autonomy, human-in-the-loop, data, responsible AI, organizational value [V] | none required | Moderate: a **day-3 field technician** ramping on a service procedure; GhostBuild's abstention, honesty map and human-acts loop hit the 20% trust criterion hard | Framing plus a Devpost paragraph; no build | Same Even moment, plus "it abstains rather than guesses, and every answer cites the manual" | 0.25 h (A) | Off-brief judge reaction (L) | UNKNOWN + DevRel meeting |
| **Paper** | Best-designed interface: hierarchy, legibility, craft [V] | none beyond design (Paper app is set-up guidance) | Paper canvas over MCP | Weak: our design is restraint on a 576×288 mono HUD plus engineering panels | A design pass on phone/twin UI | — | 4+ h of A's time (A is at the limit) | M | $1.5k/$1k/$500 |
| **QNX** | Embedded AI system on QNX [V] | QNX OS + an oss.qnx.com AI module [V] | QNX on a Pi | None (Mac + phone) | A separate embedded project | — | 8+ h | H | $1k/$250/$250 |
| **Espressif** | Creative use of Espressif hardware [V] | Espressif hardware | ESP32 | None | Separate device | — | 6+ h | H | ESP-VoCat / M5Stack |
| **Base44 · Visa · Intuit · Photon · Browser Use · CREAO · veri · MLH platform prizes** | Their platforms or domains [V] | Platform use (Base44: "built substantially using Base44") | — | None or soup | — | — | — | — | per §3 |

---

### 5.7 Hardware Lab (2026_Hardware_Lab_Menu.pdf)

**Available** [V: local PDF]:
- Sensors and modules: servo, gear stepper + driver, 130 mini DC motor, motor/servo driver board, NFC/RFID, I2C color sensor, ultrasonic, 3-axis accelerometer, rotary angle, IR reflective, micro switch, touch, button.
- Devices: Raspberry Pi kit, **Logitech webcam**, Arduino kit, JBL Go, Google Nest Mini.
- Wiring kits.
- Workbench tools (multimeter etc.) are not rentable.

**Optional functional verification** (`run_post_repair_test()` → actuator moves → sensor confirms → "FUNCTION VERIFIED"):
- **Payoff:** real. It would close V3 §7's honest gap ("Whether the motor runs needs an electrical test").
- **Cost:** the rover motor is a LEGO model with no electrics. Making this real means a new powered motor module, a driver, a microcontroller, firmware, a sensor fixture, a new verifier, a new owner, and a reset step. ≈ 6–10 h, all on the fully loaded A and C, plus new rig failure modes.
- **Verdict: do not build.** Keep it as a Devpost "next step" and a networking talking point ("installation verified today; function verified next").

**Recommended (zero engineering):** C borrows a **Logitech webcam** at check-in as a spare for the P0 overhead camera. It is hardware redundancy for the one sensor the rocket depends on [D].

---

### 5.8 Current relevant roles at the top 5 career-relevant companies

| Company | Current relevant roles | Level | Location | Early-career fit | What GhostBuild demonstrates that matches |
|---|---|---|---|---|---|
| **Sentry** | "Software Engineer, New Grad (2027)" (Product or Infrastructure by team match; Product uses TS/React/Python/Django, Infra uses Python/Rust/Kafka/ClickHouse/K8s) [V: sentry.io/careers]; "Software Engineer, New Grad (2027)" Vienna (SDK team or Ingest) [V/3P]; "Software Engineer, Intern (Summer 2027)" [V: sentry.io/careers; details not retrieved] | New grad; intern | San Francisco; Vienna; intern location UNKNOWN | **Excellent** (explicit programs plus the hackathon interview) | Python real-time services, an SDK-based tracing bridge, latency budgeting, event pipelines |
| **Fetch.ai** | No specific listings retrieved; the careers page says "opportunities through paid work experience, internships and graduate schemes" [V]; an Innovation Lab "Internship Incubator Programme" exists [V: innovationlab.fetch.ai] | Intern / graduate | UNKNOWN | **Good** (the hackathon interview is explicit) | Agent orchestration over real tools; agents acting in the physical world |
| **Cognition** | "Software Engineer", "Software Engineer, Infrastructure", "Product Engineer", "Applied AI Engineer", "Deployed Engineer", "Research Engineer, Post-Training / ML Infrastructure / Mid-Training" [V: Ashby board] | Level not stated; no intern program per a [3P] July 2026 guide | San Francisco (plus international GTM roles) | **Weak-moderate** (no early-career track found) | Agent tooling, spec-driven delegation to coding agents, applied AI systems |
| **Even Realities** | **No current listings found** (evenrealities.com/careers returns 404; an older NoDesk posting is closed) [V/3P] | UNKNOWN | Shenzhen HQ; US presence reported [3P] | UNKNOWN | An Even Hub app that passed Beta QA; HUD and interaction design under BLE constraints |
| **Workday** | Summer 2027 intern postings exist (e.g. a product internship requiring graduation Dec 2027–Jun 2028) [3P]; roughly 300–400 interns a year, ~60% engineering [3P, estimate] | Intern | Multiple | **Good** (large structured program; "Early Career Opportunities" workshop) [V schedule] | Human-in-the-loop agent design, responsible-AI controls (abstention, provenance) |

Open jobs are **not** hackathon interviews. Only Sentry (1st) and Fetch (top 3) attach an interview to a result.

**Career scores (/10):** Sentry **9** · Fetch.ai **8** · Workday **6** · Cognition **6** · MLH Commit **6** (fellowship) · Even **5** · Visa 5 · Intuit 5 · QNX 4 · CREAO 4 · Browser Use 4 · StepFun 3 · Paper 3 · Photon 3 · Base44 3 · veri 3 · Espressif 3.

---

# 6. FINAL 2–3 SPONSOR STRATEGY

## 6.1 EVEN REALITIES (primary)

| | |
|---|---|
| **WHY WE CAN WIN** | The brief names the category; the rubric's "Quiet by Design" is our core behaviour; the judge experiences their own mistake caught on the glasses; loaners cap the field; teleprompters, translators and note-takers "won't stand out" [V]. |
| **WHAT WE BUILD** | Nothing new. E-a (quiet metric in the eval) and E-b (the three answers). |
| **WHAT SPONSOR TECH OWNS** | The entire user-facing guidance surface: one action, menu questions, the dark state. |
| **WHY IT IS NOT SPONSOR SOUP** | Remove G2 and GhostBuild has no hands-free guidance. |
| **EXACT DEMO MOMENT** | §5.1 G (25 s), ending on the dark display. |
| **IMPLEMENTATION HOURS** | ≈ 0.35 |
| **OWNER** | B (device/Beta, already planned); A (pitch); D (metric inside eval) |
| **DEPENDENCIES** | G2 loan (Sat 12:30), G0 transport (Sat 15:00), M3 (19:30), P0 freeze (02:00), Beta QA (§11 of 08) |
| **QUALIFICATION CHECKLIST** | ☐ Beta `.ehpk` uploaded + pushed + installed on physical G2 ☐ lock/permission/exit QA ×3 ☐ name "GhostBuild" (≤ 20, no "Even") ☐ not medical/financial/emergency ☐ team present ☐ G2 returned |
| **SUBMISSION CHECKLIST** | ☐ Devpost: Even challenge selected ☐ Even Hub app name in text ☐ G2 in video (through-lens) ☐ README: install/run on G2, accounts, API keys ☐ final Beta pushed by 11:00 |
| **KILL TIME** | None of its own. Inherits V3: no G2 loan → the Even prize is effectively lost (08 §14), and the team optimizes for Overall. |
| **FALLBACK** | Rocket P0 on G2 (V3 §9). |

## 6.2 SENTRY (secondary)

| | |
|---|---|
| **WHY WE CAN WIN** | The field is likely small and web-centric [I]. A *physical* loop with photon-to-HUD traces and an abstention audit trail is a memorable, novel use. The integration exists to answer real engineering questions we have to answer anyway (10 §3). |
| **WHAT WE BUILD** | `integrations/sentry_bridge/` (a tail process: Tracing + Logs + Issues), plus Sentry spans in the Fetch agent if it lives. |
| **WHAT SPONSOR TECH OWNS** | The live latency budget and the instruction audit trail. |
| **WHY IT IS NOT SPONSOR SOUP** | It replaces the "look at the jsonl after the fact" workflow during tuning. The traces answer "why was that instruction slow?" and "did we ever instruct during a hand cover?" |
| **EXACT DEMO MOMENT** | §5.2 G (20 s) |
| **IMPLEMENTATION HOURS** | ≈ 1.3 human (+≈ 1.5 Devin-equivalent) |
| **OWNER** | **B** lands it, keeps the findings log and writes the Devpost section; Devin writes the code |
| **DEPENDENCIES** | Session jsonl exists (M1 14:30); a live run (M3 19:30); internet via hotspot; DSN |
| **QUALIFICATION CHECKLIST** | ☐ Tracing visible (≥ 1 live `glasses_instruction` trace from a real run) ☐ Logs visible (instruction + abstention lines) ☐ (optional) agent spans ☐ ≥ 1 real FINDING **and** ≥ 1 real DECISION informed or validated by it, recorded in `docs/sentry_findings.md` with EVIDENCE and RESULT |
| **SUBMISSION CHECKLIST** | ☐ Devpost: Sentry challenge selected (only if the entry condition holds) ☐ "How observability shaped GhostBuild" paragraph built from the real FINDING → DECISION → RESULT entries only ☐ 3 screenshots (trace waterfall, logs view, issue) ☐ repo shows `sentry_sdk` usage ☐ no DSN in git |
| **KILL TIME** | **Sat 23:00:** a live trace from a real run visible in Sentry. Red → dropped, never reopened. **Sun 08:30:** no real FINDING plus real DECISION logged → do **not** select the Sentry challenge (no invented story). |
| **FALLBACK** | None. Offline `make eval-latency` remains the measurement of record either way. |

## 6.3 FETCH.AI (secondary, conditional)

| | |
|---|---|
| **WHY WE CAN WIN** | The only agent in the room whose "outcome" is a verified change in the physical world. Past LA Hacks Fetch winners were physical (Lumos, RIIS) [V: doc 00]. Three placings. |
| **WHAT WE BUILD** | The `integrations/fetch_agent/` uAgent (mailbox, ACP, 7 tools, 4 cards, ARMED switch), Appendix B |
| **WHAT SPONSOR TECH OWNS** | Remote intent intake, plan approval, dispatch and the verified report: the supervisor's whole workflow |
| **WHY IT IS NOT SPONSOR SOUP** | No GhostBuild component does remote intake or reporting. The agent adds a user (the supervisor), not a chatbot. It answers "why" deterministically from the planner. |
| **EXACT DEMO MOMENT** | §5.3 G (30 s) |
| **IMPLEMENTATION HOURS** | ≈ 2.2 human (+≈ 3 Devin-equivalent; +3 h human only if A hand-builds after a spatial kill) |
| **OWNER** | **B** lands it (Sun 06:45–07:45) under the isolated sponsor-client exception. If the spatial lane is killed at S2 (17:30) or S4 (19:30), **A** owns it and lands it Sat 23:00–01:00 (before the 04:00 freeze; B still runs the F2 QA in its 06:45–07:45 slot under the same exception). |
| **DEPENDENCIES** | Locked `/control/*` + twin WS (12:45); mock core (14:30); live rig; internet; Friday accounts |
| **QUALIFICATION CHECKLIST** | ☐ agent registered on Agentverse (mailbox) ☐ ACP handlers + manifest published ☐ reachable in ASI:One by name ☐ ≥ 3 tools execute against the live core ☐ intent → state → plan → approve → dispatch → status → VERIFIED completes in ASI:One ☐ README: agent name + address + `innovationlab` + `hackathon` badges ☐ public repo + run instructions |
| **SUBMISSION CHECKLIST** | ☐ shared-chat URL ☐ agent profile URL ☐ **Submission Agent: B creates, all 3 teammates join with the Team ID (status "Submitted")** ☐ Devpost Fetch challenge selected ☐ video: the **FETCH export (3:10–3:30)** URL in the Submission Agent; the GENERAL export (2:50–2:58) stays on Devpost |
| **KILL TIME** | F0 Fri night · F1 Sun 00:30 · **F2 Sun 07:45** · F3 Sun 08:15 (§14) |
| **FALLBACK** | None. Fetch is dropped; the GENERAL export is unaffected and no FETCH export is made. |

## 6.4 WORKDAY (optional fourth: framing only, 0 engineering)

Two objective gates. **Sun 09:00 gate 1:** organizers confirmed multiple company challenges are allowed **and** the video exports are done; otherwise not entered. **Sun 10:30 gate 2:** A has written the paragraph (story: "a field technician in week one, trusted because it abstains, cites and keeps the human acting") only after the Even/overall Devpost text was complete, **and** every primary material (Even, Sentry if entered, Fetch if alive, Beyond the Digital) is complete; otherwise not entered. It is never pitched ahead of Even.

---

# 7. ORGANIZER TRACK

**BEYOND THE DIGITAL: exactly one.**

| Criterion | GhostBuild evidence |
|---|---|
| "intelligence into the physical world" | A closed loop over observed physical state; the judge's physical action changes the plan |
| "hardware, augmented reality… emerging interfaces" | Even G2 HUD; a RealityKit CAD twin registered to the real rover; markerless tracking (if S5 passes) |
| "devices and environments more adaptive, interactive" | It replans from wherever the build actually is and goes dark when correct |

**Fit 95/100.** Applied Intelligence (75) is the backup only if organizers require a different track. The Agentverse organizer track (50) is wrong: it would frame the agent layer as the product.

---

# 8. UNIFIED ARCHITECTURE

```
                          REMOTE SUPERVISOR                         SENTRY (cloud)
                                │ "Fix the motor assembly."            ▲        ▲
                                ▼                                      │        │
                    ┌──────── ASI:One (Fetch) ────────┐               │        │
                    │ intent · cards · approval ·     │   [FETCH]     │        │ spans per tool call
                    │ status · VERIFIED report        │               │        │ [SENTRY]
                    └───────────────┬─────────────────┘               │        │
                                    │ ACP via Agentverse mailbox       │        │
        LAPTOP 3 (B's)   ┌──────────▼───────────────────┐              │        │
                         │ integrations/fetch_agent     │──────────────┼────────┘
                         │ deterministic router · 7 tools│              │
                         │ ARMED switch (default off)   │              │
                         └──────────┬───────────────────┘              │
                                    │ LAN only: GET /health, GET /knowledge/<task>,
                                    │ one-shot ws ?role=twin, POST /control/task|reset|goal (ARMED)
 ┌────────────────────── MAC 1 (unchanged, P0) ────────────────────────┼───────────────┐
 │ webcam ─► perception ─► core: world → diff → planner → HUD arbiter   │               │
 │ phone pose ─► adapters/spatial_pose ─┘    │                          │               │
 │                                           └─► logs/session-*.jsonl ─► integrations/sentry_bridge
 │                                                (read-only tail, nice 19) Tracing+Logs+Issues
 └───────────┬───────────────────────────────────────┬─────────────────────────────────────┘
             │ hud (LAN ws / Funnel wss)              │ twin v2
             ▼                                        ▼
   PHONE (Even app) ─BLE─► EVEN G2  [EVEN]       SPATIAL PHONE (RealityKit) → Mac 2 mirror
   one action · menu · VERIFIED · dark           CAD twin · target ghost · tracked motor
             ▲
             │  TECHNICIAN ACTS (hands) ─► camera/tracking observe ─► replan ─► VERIFIED
```

**Invariants:**
1. The **only** writes into GhostBuild from sponsor code are `/control/task`, `/control/reset` and `/control/goal`, all locked at 12:45, ARMED-only, and approval-gated.
2. No sponsor code is imported by, or runs in, P0 processes.
3. Nothing reaches the G2 plugin, so no whitelist change and no Beta repack.
4. Kill any sponsor process and GhostBuild is byte-for-byte unchanged.

---

# 9. UNIFIED 90-SECOND DEMO

V3 §10.1 stays the spatial-lead script **word for word**, except in the two places marked **Δ**. Sponsor relevance is marked discreetly: ⟨E⟩ Even · ⟨F⟩ Fetch · ⟨S⟩ Sentry. Read aloud, it is one product.

| t (s) | Beat | Spoken (captain) |
|---|---|---|
| 0–10 | Phone sweep; CAD stays registered | "This is the rover's own CAD, the model we built it from, registered to the real rover. Not a scan." |
| 10–20 **Δ** | Goal arrives. **Default:** the captain taps *Fix motor assembly*. **If F2 is green and a Fetch judge is present:** the goal comes from ASI:One on the laptop, and the judge clicks Approve. ⟨F⟩ | "Goal: fix the motor assembly" + *(Fetch variant only)* "sent from the supervisor's chat." "Using the rover's assembly relations, it opens only what's in the way." |
| 20–30 | Deck, then bar, onto the tray ⟨E⟩ `LIFT DECK` → `REMOVE YELLOW BAR` | — |
| 30–45 | Motor exposed and measured | "It didn't assume what was wrong. Now it can see the motor: installed 90° off its documented orientation. So the fix is a rotation." |
| 45–55 | **HERO:** the judge turns the motor; the CAD follows; ⟨E⟩ the glasses advance | "No marker on that motor." *(only if S5 passed markerlessly)* |
| 55–70 | The deck goes back too early ⟨E⟩ `X DECK TOO EARLY` | "It doesn't skip ahead. It replans from what you actually did." |
| 70–80 | Menu → WHY THIS STEP? ⟨E⟩ | "That's cited from the service sheet we wrote for this rover." |
| 80–88 | Bar, then deck → ⟨E⟩ `● VERIFIED` → dark ⟨F⟩ *(the VERIFIED card lands in chat, unspoken)* | — |
| 88–90 **Δ** | Honesty strip | "The model didn't just show the repair. It stayed synchronised with reality and drove the plan." ⟨S⟩ *(Sentry judge only, +5 s: "and every instruction you saw is a trace back to the camera frame that justified it.")* |

**Rocket lead** (doc 11 with the menu): same markers. The Fetch variant uses `start_job("rocket-v1")` instead of a goal.

**New claims added to the V3 §10.3 claim audit:**

| Claim | Class | True when |
|---|---|---|
| "sent from the supervisor's chat" | AGENT-ROUTED (deterministic router → locked endpoint) | F2 green **and** this run's goal was set by the agent |
| "a trace back to the camera frame" | MEASURED (log-derived spans) | the bridge is running and this run appears in Sentry |
| Chat VERIFIED card | DETERMINISTIC (core `plan.status`) | — |

---

# 10. SPONSOR-JUDGE VARIANTS (30 s each)

**IF EVEN JUDGE** (glasses first; the phone is for the second judge):
> "Put these on. Fix what it tells you." *(LIFT DECK → judge acts → puts the deck back early → `X DECK TOO EARLY` → fixes → `● VERIFIED` → dark; one beat of silence.)* "It's for anyone repairing something with a manual and their hands full, at the moment they'd stop to search it. It stays dark unless you're about to go wrong. In a full run the display changed __ times and was dark or dimmed __% of the time." *(numbers from E-a, only if measured)*

**IF FETCH JUDGE** (ASI:One first; glasses second):
> "Most agents turn intent into API calls. This one turns intent into a verified physical outcome." *(Type: "Fix the motor assembly on the bench rover" → state card: "motor hidden, never seen" → plan card → Approve → technician's G2 lights up → "status?" → "measured 90° off → rotate" → VERIFIED card.)* "The supervisor never leaves ASI:One. The planning is GhostBuild's verified planner; the agent orchestrates it, can't instruct without approval, and reports only what was observed."

**IF SENTRY JUDGE** (laptop with Sentry open):
> "Our product is a loop: camera to planner to glasses, and it has two promises: fast, and never a wrong instruction. Sentry is how we kept both. Here's the trace of the instruction you just saw *(say where the time goes only as the trace shows it)*. Here's the log where it refused to instruct while your hand covered the part. And here's a decision we made because of it: *(read one FINDING → DECISION → RESULT entry from `sentry_findings.md`, verbatim)*."

**IF WORKDAY JUDGE** (optional; only if entered):
> "Week one on the job, a technician gets a repair they've never done. GhostBuild shows one verified step at a time, cites the manual when asked why, and abstains rather than guess. The human always acts; the AI never instructs from uncertain evidence."

---

# 11. ENGINEERING OVERLAY (incremental sponsor work only)

| When | V3 event | Sponsor work (owner, h) | Collision? |
|---|---|---|---|
| **Fri night** | S0 toolchain check | Accounts: Agentverse/ASI:One + promo, Sentry org/DSN, Devin login; run the official hello examples, then delete them (A, 0.75; **no project code**) | None (pre-hack, tool familiarity per doc 13) |
| Sat 09:00 | check-in; G2 form | C borrows a spare Logitech webcam (0.1) | None |
| Sat 11:00–12:00 | opening | A listens for the multi-challenge rule and prizes; **11:30–12:00** A visits Fetch, Sentry and Even tables, ≤ 5 min each (§12); unstaffed → same question on the sponsor Discord | None (pre-hack; A's motor build starts 12:15) |
| **Sat 12:45** | **contract lock** | **No schema change requested.** The agent and bridge consume only locked fields and endpoints. | **None** |
| Sat 15:00 | G0; Even workshop (B) | **B reads G0, then pastes Devin briefs A + B (15:00–15:05), then joins the workshop** (0.05) | None (sequential) |
| **Sat 17:00** | **K1** | — | None |
| Sat 19:30 | M3 | — | None |
| **Sat 20:00** | **G2 perception** | — (nothing on C, ever) | **None** |
| **Sat 21:30** | **D valve** | — (nothing on D before this) | **None** |
| Sat 22:00–22:30 | B: brightness/glyph/map polish | **B lands the Sentry bridge** (0.5); **takes B's pre-agreed polish valve** | Minor: uses B's valve slot, as V2 §11.2 already plans |
| Sat 23:00 | — | **Sentry kill check** (live trace visible) | None |
| **Sat 23:30** | **D/core valve, S5** | — | **None** |
| **Sun 00:30** | S6; standup | D reads Devin's Fetch PR CI status and approves (or refuses) the isolated sponsor-client exception in writing (0.05) → F1 | None (read + one decision) |
| **Sun 00:45** | **core cutoff** | **No core change.** Sponsor code lives in `integrations/`, never `core/` or `contracts/`. | **None** |
| **Sun 02:00** | **P0 freeze** | — | **None** |
| **Sun 04:00** | **product feature freeze** | Fetch landing (06:45) is after this | **Resolved by the formal isolated sponsor-client exception (amendment 4).** D approves it in writing at the 00:30 standup only if F1 is green. Scope: `integrations/fetch_agent/` on B's laptop, a separate process, `GB_AGENT_ARMED=0` by default, reaching GhostBuild only through frozen endpoints. Allowed after 04:00: land, configure env, register/connect Agentverse, ASI:One QA, client-local fixes. Forbidden: any change to core, contracts, perception, planner, G2, Spatial, interfaces, or a Beta rebuild. Forbidden change needed, or no exception → Fetch dies. |
| Sun 06:45–07:45 | B: after Beta build #N + QA | **B lands Fetch** (1.25) | Only if Beta QA #N is signed by 06:45; otherwise Fetch dies (Even outranks Fetch) |
| Sun 07:45–08:30 | rehearsal; final video (A); eval (D) | B records the shared chat alongside one of C's rehearsal runs and delivers the 20–30 s ASI:One clip by 08:15 (0.25); A finishes the master edit and the **GENERAL export (2:50–2:58)** by 08:30; D adds E-a quiet metrics to the eval first (0.25) | None (within existing slots) |
| Sun 08:30–09:00 | (A's gap between video and Devpost) | A inserts the ASI:One beat into the master edit → **FETCH export (3:10–3:30)**, only if F3 is green (0.25) | None |
| Sun 09:00–10:30 | Devpost | B: Sentry section + screenshots (0.5, only if the entry condition holds), Fetch README section + Submission Agent creation; A: Workday paragraph (0.25, only if §6.4 holds) and Commit opt-in + form (0.15); all: Submission Agent join (0.35) | None |
| Sun 11:00–12:00 | final Beta; buffer | — | None |

**If the spatial lane dies at S2 (17:30) or S4 (19:30):**
- A builds W4-lite as V3 says (S2: 17:30–20:00; S4: 20:00–22:30).
- A then owns Fetch: land Devin's PR (or hand-build it if Devin is red) from **23:00 to 01:00**. Landing happens before the 04:00 freeze and stays outside `core/`. B's post-04:00 F2 QA (06:45–07:45, only after Beta QA is green) still runs under the isolated sponsor-client exception, which D approves at 00:30.
- In that case B's Sunday slot shrinks to the F2 QA (≈ 0.5 h).

**Totals.**

| | Human h (in hack) | Critical path |
|---|---|---|
| Even | 0.35 | 0 |
| Sentry | 1.30 | 0 (0.5 from B's polish valve) |
| Fetch | 2.20 | 0 |
| Workday (opt.) + Commit opt-in | 0.40 | 0 |
| Webcam borrow | 0.10 | 0 |
| **Total** | **≈ 4.5 h** (+0.75 h Friday; +3 h contingent on A after a spatial kill) | **0 h** |

---

# 12. SATURDAY SPONSOR ACTION PLAN

**Friday night (pre-hack; accounts and tools only, no project code):**
- ☐ **A:** Agentverse + ASI:One accounts; redeem `LAHACKSAI26LAHACKSAI26AV`. Run the official `asi-compatible-uagents` example with `mailbox=True`, confirm it replies inside ASI:One, record whether the agent can message unprompted [verify], then stop it and delete it. Note the **F0** result.
- ☐ **A:** Sentry org + Python project; DSN into the password manager; run the SDK quickstart once.
- ☐ **A:** Devin login; check whether free credits need an event code (announced at the event [V: "every team gets free Devin credits"]).
- ☐ **A:** Paste Appendices A and B into the team notes as ready-to-send Devin tasks.
- ☐ **B:** add nothing to the G2 whitelist. No sponsor traffic touches the plugin.

**Sat 09:00 check-in:**
- ☐ B: G2 borrow form (existing).
- ☐ **C:** Hardware Lab, borrow a **Logitech webcam** as the P0 spare.
- ☐ D: existing questions (Studio model rule), plus "**Can a project select multiple company challenges?**" (A-08).

**Sat 11:00 opening.** A listens for:
- the multi-challenge rule;
- Overall prizes;
- Workday and StepFun prize amounts;
- Devin credit distribution;
- any Sentry or Fetch submission form.

**Sat 11:30–12:00 (after the opening, before hacking starts; moved from the 12:00–13:00 lunch because A builds the motor 12:15–13:45).** A makes table visits of ≤ 5 min each. A table that is not staffed yet gets the same question on that sponsor's Discord channel, and A checks for answers at the 20:00 dinner break:
- **Fetch:** "Our agent's workflow is fully inside ASI:One (intent, plan approval, status, verified report), and a technician executes the physical steps hands-free. Does that meet 'no custom frontend'? Can an agent send an unprompted message into an ASI:One chat? Is there a reply timeout?" A "no" at any time kills Fetch. No answer by the F1 standup (00:30) counts as red.
- **Sentry:** "We'll derive traces from our system's event log with the Python SDK: spans with explicit timestamps, plus Logs. Does that count as Tracing? What would make it a winner for you?"
- **Even:** loaner count, how judging works (table visits after submission?), and Beta LAN `ws://` (B repeats this at the workshop).

**Sat 13:00 Fetch workshop:** nobody attends (all hands on M1). Watch the recording later only if one exists and the timing allows.
**Sat 14:00 Annapurna Labs workshop:** skip.
**Sat 15:00 Even workshop:** B (existing), plus pasting the Devin briefs.
**Sat 18:00 Workday (early-career) and 19:00 Cognition workshops:** skip; they collide with the M3 lead-up. Network on Sunday instead (§15).
**Sat 20:00 StepFun workshop:** skip (dropped).

**Submission setup:** ~~Sat, any idle 10 min, A~~ (A has no idle time). The Devpost draft and README sections (G2 install; Fetch agent name/address + badges; Sentry) are written Sun 09:00–10:30: A (overall, Even, Beyond the Digital, Commit), B (Sentry, Fetch), D (technical section + README G2 install/run + API keys).

---

# 13. SUBMISSION MATRIX

| | Even Realities | Sentry | Fetch.ai | Workday (opt.) | MLH Commit (opt-in) | Beyond the Digital |
|---|---|---|---|---|---|---|
| **Platform** | Devpost + Even Hub Beta | Devpost | Devpost **+ ASI:One Submission Agent** | Devpost | Devpost opt-in + supplemental form | Devpost |
| **Registration** | Even developer portal; Beta group with the phone account email | Sentry org/project | Agentverse agent (mailbox); ASI:One | — | form | — |
| **Repo** | public; README: install/run on G2, accounts, API keys | public; shows `sentry_sdk`; no DSN | public; README: agent name + address, `innovationlab` + `hackathon` badges, run instructions | public | public | public |
| **Deployment** | Beta `.ehpk` pushed | bridge runs locally | local mailbox agent online during judging | — | — | — |
| **Special form** | — | none found [verify] | Submission Agent: project, name, email, team size, problem, GitHub, Devpost URL, **video URL**; bonus: agent profile URLs + shared-chat URLs; teammates join with the Team ID | — | supplemental form | — |
| **Demo requirements** | runs on physical G2 at judging | live dashboard or screenshots | live ASI:One chat on the live rig; shared chat URL | items listed in their PDF | — | in-person judging |
| **Video** | GENERAL export (2:50–2:58) shows G2 (through-lens) | — | **3–5 min**: the **FETCH export (3:10–3:30)** | — | — | **2–3 min**: the **GENERAL export (2:50–2:58)** |
| **Separate submission** | Beta build | no | **yes** (Submission Agent) | no | form | no |
| **Deadline** | Sun 12:00 (Beta + Devpost) | Sun 12:00 | Sun 12:00 [V hackpack] | Sun 12:00 | per form | Sun 12:00 |
| **Owner** | B (Beta), A (Devpost) | B (bridge, findings, Devpost section) | B (agent, chat, Submission Agent), all (join) | A | A | A |

---

# 14. KILL RULES (clock-based; not green = killed; never reopened)

| Clock | Check | Red → automatic action |
|---|---|---|
| **Fri night (F0)** | The official example agent answers inside ASI:One from A's account | **Fetch dead before the hack.** |
| Sat 11:30 → 00:30 | Fetch table/Discord answers "no" to the workflow-in-ASI:One interpretation (no answer by 00:30 = red at F1) | **Fetch dead.** |
| Sat 15:15 | Devin briefs dispatched (B, 15:00–15:05) | Devin not used. Sentry: B hand-builds a 2-product minimum (Logs + one span type) inside the same 22:00 slot or it dies. Fetch: dead unless A is freed by a spatial kill. |
| **Sat 23:00 (S-K)** | A live `glasses_instruction` trace from a real run is visible in Sentry | **Sentry dead.** |
| **Sun 00:30 (F1)** | Devin's Fetch PR passes its tests against `core --mock-vision` (with `GB_CORE_URL` set explicitly), the Fetch clarification is "yes", **and** D approves the isolated sponsor-client exception (amendment 4) | **Fetch dead.** (If A owns Fetch after a spatial kill: F1 = landed by 01:00 with tests green; D's 00:30 approval covers B's post-04:00 F2 QA.) |
| Sun 06:45 | Even Beta QA #N signed green | **Fetch dead** (B stays on Even). |
| **Sun 07:45 (F2)** | Live in ASI:One: intent → state card → Approve → G2 instruction → status → VERIFIED card, on the real rig | **Fetch dead.** |
| Sun 08:15 (F3) | Shared chat URL saved and the 20–30 s ASI:One clip delivered to A | **Fetch dead.** Only the GENERAL export ships; no FETCH export. |
| Sun 08:30 | `sentry_findings.md` has ≥ 1 real FINDING **and** ≥ 1 real DECISION informed or validated by it (with EVIDENCE and RESULT) | Do not select the Sentry challenge. |
| Sun 09:00 | Workday gate 1: organizers confirmed unlimited company challenges **and** both video exports are done (or the GENERAL export is, if Fetch is dead) | Workday not entered. Gate 2 at 10:30: paragraph written and every primary material complete, else not entered. |
| ~~Sun 10:00~~ | ~~Both Devin PRs merged~~ | **SUPERSEDED:** the Cognition checkbox is never selected (amendment 6). |
| Sun 10:30 | All selected challenges have complete materials | Deselect any incomplete sponsor rather than submit it half-done. |
| Any time | A sponsor process misbehaves at the table | Kill the process. GhostBuild is unaffected by design. |
| Any time after 04:00 | The Fetch client needs a change outside `integrations/fetch_agent/` (core, contracts, perception, planner, G2, Spatial, an interface, or a Beta rebuild) | **Fetch dead.** |

---

# 15. NETWORKING PLAN

**Universal 30-second GhostBuild pitch:**
> "GhostBuild is a copilot for physical work. It reads the manual and the CAD, watches the real object, and recomputes the next verified action from wherever you actually are. That one action shows on Even G2, and the display goes dark when the work matches the target. Try breaking it: put the part back too early and it catches you, tells you why, and cites the page."

| Company | WHO TO FIND | WHAT TO SHOW THEM | TECHNICAL QUESTION TO ASK | CAREER TRANSITION |
|---|---|---|---|---|
| **Sentry** (selected) | Sentry engineers/judges at the table and in judging round 1 | The trace of the instruction they just saw on G2; the abstention log | "We derive spans from an event log with explicit timestamps. Would you model a camera-to-glasses loop as one trace, or span links across processes?" | "The new-grad posting mentions Product vs Infra by team match. Which team works on tracing ingestion? I'd love to learn how that interview loop works." |
| **Fetch.ai** (selected) | Sana Wajid, Attila Bagoly (judges); mentors Rajashekar Vennavelli, Dev Chauhan, Gautam Manak, Anish Kancherla, Aditya Lagad [V hackpack] | The ASI:One → G2 → VERIFIED card flow | "What's the recommended way for an agent to notify an ASI:One user when a long-running physical job finishes?" | "The prize mentions an internship interview. What do Innovation Lab interns work on, and what does the incubator programme look for?" |
| **Even Realities** (selected) | Even table staff (Sat 16:00–20:00, Sun 09:00+), workshop presenter | The quiet loop on the glasses; the dark-time metric | "What's the intended path for a Beta plugin to reach a LAN service? Will `ws://` origins stay allowed?" | "Who builds the Even Hub developer experience? Are you growing the developer-relations or SDK team in the US?" (recruiting is SPECULATIVE; ask, don't assume) |
| **Cognition** (not building) | Workshop host (Sat 19:00) or anyone at the Cognition table on Sunday | How we split specs so Devin could build two isolated services against our contracts and replay fixtures | "How do you see coding agents verifying behaviour that only exists on physical hardware?" | "Your Applied AI and Deployed Engineer roles look close to what we built. Is there an early-career path into them?" |
| **Workday** (opt.) | DevRel team (the workshop is titled "Early Career Opportunities") | The abstention and citations as responsible-AI design | "How does Workday think about AI guidance for frontline and hourly workers?" | "What does the early-career engineering pipeline look like for summer 2027?" |
| Annapurna Labs / AWS (opportunistic) | Workshop host (Sat 14:00) or the sponsor table | The on-device vs hosted split (Apple Vision local, hosted LLMs) | "Where do you see inference for always-on wearables landing, on the phone or at the edge?" | Ask about intern programs. **SPECULATIVE.** |

---

# 16. PRIZE-WIN RED TEAM

### Even: "If I were the Even judge, why would I NOT choose GhostBuild?"
| Objection | Fixable? | Fix |
|---|---|---|
| "The phone CAD twin is the star; the glasses are a sidekick." | Yes | The Even script starts with the glasses on and keeps the phone for the second judge (§10) |
| "It's a LEGO toy." | Partly | Say "rover service" and "anyone repairing with a manual"; LEGO is the breakable rig |
| "Too many features; you asked for one interaction." | Yes | Name the one interaction: "the next verified step, and silence when you're right" |
| "It didn't run from the Beta / it was flaky." | Gated | G0 at 15:00, Beta QA ×3, the Even table on Saturday |
| "Quiet? It talks at me constantly." | Yes | Measured dark-time % (E-a); end on the dark display |
| "Who is this for?" | Yes | One-sentence answers on the phrase card (E-b) |

### Sentry: "Why would I NOT choose GhostBuild?"
| Objection | Fixable? | Fix |
|---|---|---|
| "You tail a log file. That's not really using Sentry." | Yes | The bridge uses the SDK for custom spans and Logs (it is instrumentation, just out of process); the Fetch agent uses in-process spans; show both |
| "How did observability shape what you built?" | Only with real findings and real decisions | `sentry_findings.md` (FINDING · EVIDENCE · DECISION · RESULT) from Saturday night on; **no invented stories**; don't enter without a real decision (§14) |
| "Hardware projects don't need APM." | Yes | "Our product promise is latency and zero wrong instructions; Sentry is how we audit both" |
| "Only two products; others used five." | Partly | Tracing + Logs + Issues + agent spans. Don't add the plugin JS SDK (it would force a Beta repack and the BLE risk) |

### Fetch: "Why would I NOT choose GhostBuild?"
| Objection | Fixable? | Fix |
|---|---|---|
| "The real UI is the glasses: a custom frontend." | Mostly | Saturday clarification with Fetch; the supervisor workflow is complete in ASI:One; the plan card is readable on its own |
| "Thin wrapper over your own API." | Yes | Show the multi-step orchestration (inspect → plan → approve → dispatch → monitor → verify) and the live state changing between turns |
| "Light on Fetch tech: no payments, no multi-agent." | Accept | Use Agentverse + ACP + cards well; don't bolt on payments or a second agent (soup) |
| "It didn't work when I tried it later." | Partly | Graceful replies when the rig is offline ("workcell offline, last verified at …"); keep the agent running through judging |
| "Could it operate after the hackathon?" | Yes | The field-service supervisor story: any registered workcell can run it |

### Workday (optional): "Why NOT?"
"It's not about HR or workplace knowledge." Only partly fixable through the new-technician framing. That is why it stays optional and is never pitched ahead of Even.

---

# 17. FINAL RECOMMENDATION

**TARGET THESE SPONSORS:**
1. **Even Realities**: primary; no new engineering.
2. **Sentry**: photon-to-HUD tracing bridge; guaranteed-interview prize.
3. **Fetch.ai**: ASI:One supervisor agent; conditional, killed at 07:45 Sun if not green.

*(Optional fourth, 0 engineering: Workday, framing only, decided at 09:00 Sun. Zero-engineering opt-in: MLH Commit Fellowship.)*

**TARGET THIS ORGANIZER TRACK:**
1. **Beyond the Digital**

**NETWORK AGGRESSIVELY WITH:**
1. **Sentry**: interview prize; new-grad and intern programs.
2. **Fetch.ai**: three interview-bearing placings; Innovation Lab internships.
3. **Cognition**: Applied AI and Deployed Engineer roles; agent-tooling conversation (network only; the Cognition challenge is not entered).
4. **Even Realities**: the primary prize; developer-ecosystem relationship.
5. **Workday**: "Early Career Opportunities"; DevRel follow-up.

**DO NOT SPEND ENGINEERING TIME ON:**
- StepFun;
- a Devin "physical verification" MCP, or anything built *for* Cognition;
- functional verification with Hardware Lab motors and sensors;
- the Sentry JS SDK in the G2 plugin (whitelist and repack);
- the Fetch Payment Protocol, a second agent, or image cards beyond an optional URL;
- Paper, QNX, Espressif, Base44, Visa, Intuit, Photon, Browser Use, CREAO, veri, and the MLH platform prizes (Gemini, ElevenLabs, Snowflake, Vultr, Solana, Tiger Data, GoDaddy);
- any sponsor code in `core/`, `contracts/`, perception or `g2/`.

**TOTAL NEW ENGINEERING:**
**≈ 4.5 person-hours** of human time during the hack (+0.75 h Friday account setup; +≈4.5 h-equivalent delegated to Devin; +3 h contingent only if A hand-builds Fetch after a spatial kill).

**CRITICAL-PATH NEW ENGINEERING:**
**0 person-hours.**

---

## Appendix A: Devin brief: `integrations/sentry_bridge/`

> **Goal.** A standalone Python 3.11 process that tails GhostBuild's newest `logs/session-*.jsonl` (read-only) and sends Sentry data. **Do not modify anything outside `integrations/sentry_bridge/`. Do not import from `core/`, `perception/` or `contracts/` at runtime** (you may read `contracts/schema/*.json` in tests).
> 1. First run `core --mock-vision scenarios/demo.yaml` (see `docs/04` §3) to produce a real session log, and inspect its records before writing the parser.
> 2. `sentry_sdk.init(dsn=env SENTRY_DSN, traces_sample_rate=1.0, enable_logs=True, environment="hackathon")`. Pin the SDK version and confirm the API for explicit span start/end timestamps in that version.
> 3. For every `hud` record whose `line1` differs from the previous one, emit transaction `glasses_instruction`. Spans: `vision.process` (observation `timing.capture_ts_ms` → observation `ts_ms`), `core.vote` (first observation with the new component state → the `world` commit), `core.plan_arbiter` (`world` → `hud`), `g2.ble_render` (duration = matching `hud_ack.bridge_ms`). Attributes: `hud.line1`, `mode`, `alert`, `plan.last_event.kind`, `source`, `task_id`. Skip spans whose inputs are missing; never guess.
> 4. Sentry Logs (info): every HUD instruction, every `plan.last_event` ≠ none, every `turn` (intent, basis, citation ids), and every `status ∈ {uncertain, occluded, no_board}` or `mode ∈ {hold, uncertain}` transition.
> 5. Sentry Issues: `hud_ack.result ≠ "ok"`, and any record type `error`.
> 6. Flags: `--log PATH` (default: newest file), `--from-start`, `--dry-run` (print JSON instead of sending). Handle file rotation. Exit cleanly on SIGINT. CPU < 2% at 10 Hz observations.
> 7. Tests (`pytest`): a fixture log produces the expected transaction/span/log counts in `--dry-run`.
> 8. Env vars: `SENTRY_DSN` (required unless `--dry-run`). None in git.
> **Test command:** `cd integrations/sentry_bridge && pytest -q`.
> **Done** = tests green in your VM, plus a PR whose diff touches only `integrations/sentry_bridge/`, with a README (run command, env vars, what each signal means).
> **Kill rule:** if the PR is not green when B lands it (Sat 22:00), B hand-builds the 2-product minimum inside 22:00–22:30 or Sentry dies at 23:00. No other human rescue.

## Appendix B: Devin brief: `integrations/fetch_agent/`

> **Goal.** A Fetch.ai uAgent (mailbox) that lets a remote supervisor run a GhostBuild physical job entirely from ASI:One. **Do not modify anything outside `integrations/fetch_agent/`. Do not import from `core/`, `perception/`, `contracts/`, `g2/` or `spatial/` at runtime** (tests may read `contracts/schema/*.json` and `contracts/examples/*.json`). GhostBuild is reached only over HTTP/WS at **`GB_CORE_URL`, which is required and has no default**. If it is unset, exit non-zero at startup with exactly `GB_CORE_URL is required; point it at the GhostBuild Core host.` Never fall back to localhost. (The agent runs on B's laptop; the hack-run value is e.g. `GB_CORE_URL=http://<MAC1-LAN-IP>:8787`. Tests set `GB_CORE_URL=http://localhost:8787` explicitly when mock core runs in the same VM.) Use only these locked interfaces (`docs/05` §2, §12, §13 and `docs/18_SPATIAL_TWIN_PASS_V3.md` §4.1):
> `GET /health` · `GET /knowledge/<task_id>` · one-shot `ws(s)://…/ws?role=twin` (read the snapshot sent on connect, then close) · `POST /control/task {task_id}` · `POST /control/reset {}` · `POST /control/goal {component}` (may 404 when spatial is off; handle it).
> **Never call `/control/ask`** (it would push answers onto the technician's glasses).
> 1. Follow the official ASI-compatible example (`uagents==0.25.5`, `chat_protocol_spec`, ack every `ChatMessage`, `publish_manifest=True`, `mailbox=True`, `publish_agent_details=True`).
> 2. A deterministic keyword router (no LLM): `inspect/check/status/why/fix|start/verify` → tools. "motor" or "rover" → task `rover-v1` + goal `c_motor`; otherwise `rocket-v1`.
> 3. Tools:
>    - `inspect_workspace`: per-component state with honesty labels from `spatial_state` / world `source` / `stale`;
>    - `get_plan`: next action + `why`;
>    - `explain_step`: `why` + evidence page/section from the bundle;
>    - `start_job`;
>    - `set_goal`;
>    - `get_status`: `plan.progress`, `plan.last_event`, the last 5 `twin.log` entries;
>    - `verify_outcome`: `plan.status == "verified"`.
> 4. **Mutating tools (`start_job`, `set_goal`) run only if env `GB_AGENT_ARMED=1` AND the user approved a `review` card in this session.** Otherwise reply with a card: "Workcell in demo-safe mode."
> 5. Interactive Cards per the official spec (`card_protocol_version "1"`, payload ≤ 64 KB, JSON-encoded): `custom` Workspace State, `review` Plan (approve/reject; parse the selection via `json.loads` with a text fallback), `custom` Job Progress, `custom` VERIFIED with `is_terminal`. No images.
> 6. Resilience: core unreachable → "Workcell offline (last seen …)". All network calls time out at 3 s. No exceptions escape the handler.
> 7. `sentry_sdk.init` (env `SENTRY_DSN`, optional), with one span per tool call named `tool.<name>`.
> 8. README: agent name + address placeholder, `![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)` and `![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)`, run instructions, and the ARMED switch.
> 9. Tests (`pytest`) against a running `core --mock-vision` with `GB_CORE_URL` set explicitly: the router, each tool's output shape, the ARMED gate (default off), the offline path, and the missing-`GB_CORE_URL` fail-fast message.
> 10. Env vars: `GB_CORE_URL` (required), `GB_AGENT_ARMED` (default `0`), `SENTRY_DSN` (optional), the agent seed. None in git.
> **Test command:** `cd integrations/fetch_agent && GB_CORE_URL=http://localhost:8787 pytest -q` (with `core --mock-vision scenarios/demo.yaml` running).
> **Done** = tests green in your VM + a PR whose diff touches only `integrations/fetch_agent/`.
> **Kill rule:** if the PR is not green at F1 (Sun 00:30), Fetch dies. No human rescue (except A after a spatial kill, §14).

---

## Sources (checked 2026-10-16)

**First-party, event:**
- LA Hacks tracks: https://live.lahacks.com/tracks
- Schedule: https://live.lahacks.com/schedule
- Home: https://live.lahacks.com/
- Devpost overview and prizes: https://la-ai-hackathon-2026.devpost.com/
- Devpost rules: https://la-ai-hackathon-2026.devpost.com/rules

**Sponsor "Additional Info" docs** (Google Docs export):
- Even Realities: https://docs.google.com/document/d/1mRDOVuKf-cMgaM4QsWaTrB_E5fMw44BoqDoHRBVLZh8
- Fetch.ai: https://docs.google.com/document/d/18_z3Px6Vc0m6L2blLAk7DV8SelpGhoZy8t_8clSEroI
- Fetch.ai submission: https://docs.google.com/document/d/1UDW-X1C24hxZviFOQzjTeh0pXRNAoflMb8lhJqZP9Z0
- Cognition: https://docs.google.com/document/d/1E95qigDIP1YB4dP_j6e3QsTRc0pB2tgCSpvUd1GBO54
- Sentry: https://docs.google.com/document/d/1JIlPd5vxcm8klztORkRX0FPXp4F865mxUbteJY8MUAw
- Base44: https://docs.google.com/document/d/1SlIrPxU67Lc35i9OYpaVt7fdJTJIqt2Z6n9FyrzGyP0
- QNX: https://docs.google.com/document/d/1u0d-6YyJ1SzFu9b0myPdhUDPSyJhDg0pzgVMXqmbLtE
- Visa: https://docs.google.com/document/d/10vXJndQUMgbbc23v5NobI69DiV04nX62XKEHViC0ndA
- Espressif: https://docs.google.com/document/d/1Qf9i2LGiDqHdEGf1eZ49hdrAIIpv3aaYOrJCPWoyMdw
- Intuit: https://docs.google.com/document/d/1JGmvJvZugbFrJW2WSrrPF96r_wB_xaMkfqVM49LE4nU
- MLH: https://docs.google.com/document/d/1a9TbDI0u8P2DGFFfoGXb9zEON5vrdm5PVK9yKufYLVo
- veri: https://docs.google.com/document/d/1wxRMEND8Rgkyvb9Y1CCPHdmaW2NJEXh_y9LScwPTZmY
- Workday (PDF): https://drive.google.com/file/d/1cwiVFY_8sYZdA4Vxr36Hi7kyhZMNVPPA
- Paper: https://paper.design/la-hacks
- Not retrievable: the Fetch "Resources" Google Doc (sign-in wall); the Photon Notion page (unsupported-browser page); CREAO community page (empty render). Requirements for these were taken from the tracks page.

**Even Realities:**
- Challenge prompt: https://evenrealities-lahacks.vercel.app/
- Starter pack: https://evenrealities-lahacks.vercel.app/starterpack
- Docs: https://hub.evenrealities.com/docs

**Fetch.ai:**
- Hackpack: https://www.fetch.ai/events/hackathons/la-hacks-ai-hackathon-2026/hackpack
- Interactive Cards: https://innovationlab.fetch.ai/resources/docs/interactive-cards/asi-interactive-cards
- ASI-compatible uAgents: https://innovationlab.fetch.ai/resources/docs/examples/chat-protocol/asi-compatible-uagents
- Careers: https://fetch.ai/careers
- Internship incubator: https://innovationlab.fetch.ai/internship-incubator-programme

**Sentry:**
- Python Logs: https://docs.sentry.io/platforms/python/logs/
- Span lifecycle: https://docs.sentry.io/platforms/python/tracing/span-lifecycle/
- Careers: https://sentry.io/careers/ (New Grad 2027, Intern Summer 2027 postings)

**StepFun:**
- Model guide: https://platform.stepfun.ai/docs/en/guides/models/step-5-preview

**Cognition / Devin:**
- MCP docs: https://docs.devin.ai/work-with-devin/mcp
- Jobs: https://jobs.ashbyhq.com/cognition (API: https://api.ashbyhq.com/posting-api/job-board/cognition)

**Local files** (read, not modified):
- `~/Downloads/Fetch AI Track.pdf` (matches the current Fetch doc)
- `~/Downloads/2026_Hardware_Lab_Menu.pdf`

**Third-party [3P]:**
- Step 5 pricing and weights: cellcog.ai, benchlm.ai
- Cognition intern program: extern.com
- Workday intern estimates: extern.com
- Even Realities funding and headcount: mobileworldlive.com, techcrunch.com
- Sentry Vienna new grad: jobs.accel.com mirror
