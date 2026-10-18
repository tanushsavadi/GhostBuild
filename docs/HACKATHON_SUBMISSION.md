# GhostBuild submission package

**Prepared 2026-10-18, 06:55 PDT.** Copy below into Devpost after confirming the final status. This file is submission material; it does not mean the project, video or Even Hub Beta has been published.

## Official event sources and deadlines

The [live event Tracks page](https://live.lahacks.com/tracks) loads its current tracks and sponsor briefs from the public [event content endpoint](https://live.lahacks.com/api/content). Both were retrieved on October 18, 2026; the endpoint returned four tracks and seventeen company/challenge entries. The live site's submission link points to the [official Devpost event](https://la-ai-hackathon-2026.devpost.com/). Sponsor links below are the links published there, not inferred affiliations.

The live event configuration and Devpost overview agree on **Sunday October 18, 12:00 PM PDT**. The [Devpost rules](https://la-ai-hackathon-2026.devpost.com/rules) retain an inconsistent April 26, 8 AM sentence. Ask an organizer to confirm that stale text; do not silently use it as the current deadline. Work toward the earlier internal 10:30 AM submission target. Devpost requests a public repository, description/track/challenge explanation and a **2–3 minute video**; the [filming plan](DEMO_RUNBOOK.md#exactly-120-second-product-video) therefore runs exactly two minutes. Judging requires in-person attendance. The published rules limit teams to four students and require disclosure of reused work; verify actual participant eligibility in the account before submitting.

## Track selection

This is our fit assessment against all four current live-site tracks, not an eligibility decision by organizers.

| Official track | GhostBuild fit / decision |
|---|---|
| Beyond the Digital | **Primary.** A wearable interface guides real physical tasks, keeping hands available and diagrams within a glance. Lead with the interaction and hardware limits. |
| Applied Intelligence | **Secondary, if multiple selections are allowed.** Practical AI assistance for assembly, repair and learning, with sources and persistent task state. |
| Model Learning | **Do not select.** We use existing models; no training or learning-system contribution is established. |
| Agentverse, sponsored by Fetch.ai | **Do not select.** No verified current Agentverse/ASI:One registration or discovery path in the released experience. |

The Devpost prize listing assigns a robot-car kit to Beyond the Digital, a mini projector to Applied Intelligence and AirPods 4 to Model Learning; overall awards are $2,000 / $1,500 / $1,000. The listing contains duplicate entries, so these are award descriptions, not additive totals or promised winnings. Recheck the actual category controls at submission. [Official prize listing](https://la-ai-hackathon-2026.devpost.com/).

## Sponsor curation

**Prioritize Even Realities.** Its [official brief](https://docs.google.com/document/d/1mRDOVuKf-cMgaM4QsWaTrB_E5fMw44BoqDoHRBVLZh8/edit) requires an Even Hub Beta upload, physical G2 during judging, the app name in Devpost, installation/account instructions, and a G2 experience in the video (simulator is allowed for that footage). App name: **GhostBuild**, within its naming limit. The published first prize is G2 glasses per team member; second and third are $250 and $100 OpenAI/ChatGPT gift cards per member. No Beta upload or final physical verification is established by a package build.

**CREAO: Best AI-First Disruptor, conditional on disclosing the actual research role.** The [live challenge](https://live.lahacks.com/tracks) lists $2,000 for Disruptor, $1,000 for One-Person Company and $500 for Team Empowerment, plus Launchpad invitations for winners. [Official CREAO challenge page](https://community.creao.ai/AI_hackathon_UCLA2026?utm_source=ucla-ai&utm_medium=hackathon&utm_campaign=hackathons-oct-2026) returned 403 during this check; additional sponsor-specific criteria remain unverified. Use the ready-to-copy bounded evidence below, and confirm details with the sponsor. Do not claim that all cached Mac/bike/Prusa guides were researched by CREAO: their compiler path uses Anthropic.

**ElevenLabs: Best Use of ElevenLabs, conditional on an accessible real evidence demonstration.** The [official MLH page](https://www.mlh.com/events/ucla-ai-hackathon-2026/prizes) lists wireless earbuds. Present actual STT and TTS proof, plus the limits of the capture. This is optional voice input/output, not a deployed ElevenLabs conversational agent. Do not claim hands-free G2 microphone capture or audible playback was verified if only provider responses were checked.

**Paper: Best Designed Hack, optional.** The [sponsor page](https://paper.design/la-hacks) evaluates visual fundamentals, usability and personal craft; prizes are $1,500 / $1,000 / $500. Its public challenge text does not state Paper usage as a hard requirement. Describe the actual interface; do not invent a Paper design file or claim use of Paper. Confirm any entry requirements with the sponsor if selecting it.

All other live challenge entries were considered, rather than adding integrations to chase prizes:

| Current challenge | Decision for this release |
|---|---|
| Fetch.ai — ASI:One Agent Challenge | Exclude: current registration, discovery and action evidence absent. |
| Cognition — Best Use of Devin | Exclude unless a real hackathon Devin session/contribution is documented; no paid session is started for eligibility. |
| Base44 — Build Something People Want | Exclude: no released Base44 implementation evidenced. |
| QNX — Best use of QNX | Exclude: QNX OS plus an eligible open-source AI module are explicit requirements; neither is evidenced. |
| Workday — Future of Work | Exclude from this general assembly/repair submission; no employee onboarding/workplace workflow was verified. |
| StepFun — Step 5 Preview | Exclude: the brief requires runtime `step-5-preview`; release uses Anthropic instead. |
| Photon — Messaging/Calling Agent | Exclude: no Photon messaging/calling workflow. |
| Visa — Future of Shopping | Exclude: no verified commerce/payment workflow. |
| Sentry — Best Use | Exclude: brief requires two products beyond error monitoring and evidence that observability improved the product; historical directory names are not proof. |
| Espressif — Best Use | Exclude: no confirmed Espressif hardware contribution. Raspberry Pi is not Espressif. |
| Intuit — QuickBooks/System One | Exclude: no relevant financial workflow/model use. |
| MLH challenges | ElevenLabs only on current evidence. Gemini, Snowflake, Vultr, Solana, Tiger Data and GoDaddy domain categories have no demonstrated released use. |
| Browser Use — Best Use | Exclude: developer browser testing does not demonstrate a Browser Use powered product. |
| veri.studio — Open-sourced model | Exclude: no Veri post-training/fine-tuning demonstrated. |

These entries, together with Even, CREAO and Paper above, cover all seventeen live challenge entries. The separate Devpost listing also mentions Commit Fellowship: consider it only if the team wants the post-event program and completes its supplemental form. A general product story alone does not meet a missing integration requirement. Full awards and changing monetary details remain at the official Devpost listing; do not add duplicate awards together.

## Ready-to-copy Devpost content

### Project title

GhostBuild

### Elevator pitch

From knowledge to action. GhostBuild turns trusted documentation into step-by-step guidance, relevant diagrams and context-aware help on smart glasses, while keeping your hands on the task.

### Inspiration

You are halfway through assembling a desk. One hand is holding a panel, the other is searching for a fastener. The answer is somewhere in a forty-page PDF on your phone.

We have made information easy to find, but applying it while working with our hands is still awkward. Manuals do not know where we are. Videos move at someone else's pace. A generic answer may not even apply to the product in front of us.

We wanted a patient specialist beside us: someone who helps identify the right thing, gives one useful instruction, and understands “Wait, where does this go?” without making us start again.

### What it does

GhostBuild helps a person describe a build or repair task, identify the relevant product or configuration, and follow a structured procedure. Even Realities G2 shows a short instruction or the relevant visual reference. The phone keeps the complete explanation, source material and task context accessible.

The IKEA flow starts with real product candidates, distinguishes the MICKE model and cabinet orientation, and opens the matching manual guide. A question about a part retrieves the diagram for that step. Contextual help can be paged and dismissed without advancing the task or losing the user's place.

A contrasting Mac display workflow asks which display is affected and follows the appropriate troubleshooting route. Bicycle and Prusa examples use the same procedure engine, with explicit stops where the prepared guide does not cover the configuration. These AI-compiled repair guides are labelled as awaiting human review; they are demonstrations, not a promise that every physical repair is supported.

Manual progress is deliberately user-confirmed. Steps that require measured evidence cannot be completed by a gesture or a spoken claim. An optional external Raspberry Pi camera station demonstrates that distinction separately: receiving a frame is measured, interpreting an unobstructed view is inferred, and commanding an LED does not prove it illuminated. G2 itself has no camera or speaker.

### How we built it

The system separates knowledge preparation from task execution. Source adapters retrieve official documentation and specialist material. A source-to-procedure compiler uses structured model output, validates quotes against retrieved text, checks routes and wearable text constraints, and caches the resulting action graph. These checks establish structural/source consistency; they do not replace expert safety review.

The Python backend runs a state machine shared by assembly and diagnosis. Questions select routes; instructions retain progress; contextual answers and pictures return to their owning step. A single HUD writer controls what reaches G2. The TypeScript EvenHub client renders those frames, handles gestures and keeps a text fallback when images are unavailable. The phone companion exposes sources, longer answers and optional input controls.

Anthropic supplies conversational intake, grounded explanations and the optional source compiler. CREAO supplies a separate asynchronous research route whose returned artifact can be normalized into a draft card for human approval. ElevenLabs supplies optional speech recognition and speech synthesis through backend-held credentials and explicit consent. Speech is treated as untrusted input and mapped into existing controls. Navigation and prepared visual retrieval do not wait on a model; unknown tasks can research asynchronously when enabled.

### Challenges we ran into

The difficult part was preserving meaning across interruptions. Looking at a picture must not complete a step. Reading an answer must not lose the current diagram. An observation reported by a person must not become a sensor measurement. A guide for one model must not quietly continue after the model changes.

We also had to make the interface fit a wearable. Long answers need pagination, images need compact monochrome versions and text fallbacks, and the phone needs enough detail without turning the glasses into a floating chat window. Network services add uncertainty, so cached guides and deterministic controls remain useful when optional providers fail.

### Accomplishments we're proud of

One engine handles product-specific assembly, branching diagnosis and source-backed repair procedures. The data changes; the navigation and evidence rules stay consistent. We can trace a visible instruction to its guide and source, return from help to the same task state, and distinguish user confirmation from measured verification. The IKEA discovery and manual experience has browser and official simulator evidence, and the repository records bounded live-provider tests separately from hardware claims.

### What we learned

A wearable assistant needs restraint. The useful output is often a single instruction or a picture, while the complexity belongs behind it. Source grounding is also more demanding than attaching a link: the instruction, product identity, branch and picture all need to agree. Finally, honest uncertainty makes a tool more useful. Asking again or stopping is better than confidently continuing with the wrong procedure.

### What's next

Complete physical G2 validation across images, voice and reconnects; review the compiled procedures with experienced users; expand product identification and source adapters; and evaluate real task completion with novices. Broader coverage should follow demonstrated reliability, with clear review and evidence labels.

### Built with

Python, FastAPI, Pydantic, TypeScript, Vite, Even Realities G2, EvenHub SDK, Anthropic SDK, Claude, CREAO, ElevenLabs, Pillow, pytest, Vitest, plain HTML/CSS/JavaScript. Raspberry Pi and Pi camera are optional telemetry hardware. Include a technology only if it remains in the submitted build; tool usage during development is not a product integration.

### Links and media

- Source: [github.com/tanushsavadi/GhostBuild](https://github.com/tanushsavadi/GhostBuild). The integrator reports that the repository is currently private; confirm judge access and the event's public-source requirement before submitting. This document does not change visibility.
- Installation and architecture: root README and the linked setup/architecture documents in that repository.
- Demo video: **not yet supplied; record/upload the 120-second plan and paste a verified public URL.**
- Even Hub app name: **GhostBuild**. Beta listing/build URL: **not yet established; add after upload.**
- Screenshots: use actual companion and official simulator captures after rights/privacy review. Existing [Mac companion capture](evidence/framework/phone-mac-color-filters.png), [Mac branch capture](evidence/framework/mac-04-external-branch.png) and [engine page capture](evidence/framework/engine-page.png) are application evidence, not physical lens photographs. Do not upload a full third-party manual or its high-resolution page assets without permission.

## Sponsor evidence copy

**Even Realities:** GhostBuild is an EvenHub app designed for the moment a person's hands are occupied. It shows concise instructions and step-owned diagrams, uses deliberate gestures to navigate, and returns from contextual help without losing place. Official simulator and browser captures establish the software path. The operator reports readable cues/images, gestures, answer return and reconnect passed on the final voice-disabled build; detailed evidence remains pending. Even Hub Beta publication is not yet established. Microphone capture has not been independently verified.

**CREAO:** A recorded live app-scoped CREAO run returned a JSON research artifact, which our adapter fetched, normalized and validated into a seven-step, seven-source draft. Human approval of that draft remains pending. CREAO is asynchronous research, not a live dependency for every cue or the provider behind all cached demonstration guides. Evidence: the provider record described in [FINAL_SPRINT_STATUS.md](FINAL_SPRINT_STATUS.md), [client](../knowledge/creao.py), [normalizer](../knowledge/creao_normalize.py) and their validation tests. The raw response/draft are ignored local artifacts and must be inspected by the presenter; they are not public proof links. Do not run a fresh paid job merely to recreate a missing screenshot.

**ElevenLabs:** Fresh bounded verification through the existing backend returned a valid 3.019-second MP3 from a consented TTS request (HTTP 200, 1.391 seconds). A single fresh realtime STT attempt failed during provider startup after 5.013 seconds; it produced no transcript, and the guide recovered with progress unchanged. Earlier sprint notes report synthetic-sample STT success, but do not present that as a fresh passing speech test. The staged G2 build disables voice. No physical G2 microphone or audible playback is claimed. [Fresh voice evidence](evidence/release/elevenlabs-live.json). Use TTS as the demonstrated integration and disclose the current STT limitation; do not script live STT until independently rehearsed.

## Credits and provenance

Git author history inspected for this release records **Tanush Savadi**. Add the other actual team members and their roles from their confirmed Devpost accounts; do not infer identities from lane letters or assistant names. Preserve teammate commit authorship. Team membership/roles and submission rights need the team's confirmation.

Disclose AI-assisted development using Codex/Claude and any other tool actually used. Manufacturer documentation and third-party photographs remain their owners' work: IKEA for product/manual content, Apple Support for Mac material, Park Tool for bicycle references and Prusa Knowledge Base for printer references. A link or attribution is not a redistribution license. Runtime caches of third-party images are not a claim that we created them.

The repository contains historical designs and third-party tools. **Before submission, the team must confirm any pre-hackathon code and identify the features added during the event.** Commit timestamps alone cannot establish when an idea or component was created. Do not paste an unqualified “everything built this weekend” claim. The public rules explicitly distinguish reused open-source components from newly judged functionality.

## Submission gates

| Gate | Status at document preparation | Remaining action |
|---|---|---|
| Copy, track fit and official source links | PASS | Refresh current category controls before submitting. |
| Source/build/tests and remote release | NOT RUN here | Integrator fills actual results in final status. Software merge success is separate from hardware readiness and prize eligibility. |
| Public judge access | BLOCKED on repository owner | Repository is currently private per integrator inspection. Owner must address official public-source requirement or obtain organizer approval for an alternative; visibility is not changed by this task. |
| Even Hub Beta upload | BLOCKED on publication | Upload actual `.ehpk`, record listing/build and installation instructions. A QR dev sideload is insufficient. |
| Physical G2 judging run | BLOCKED on operator | Test actual release hardware and attend in person. Simulator footage is allowed for video, not a substitute for this requirement. |
| Authored MICKE wording / compiled repair review | BLOCKED on human review | Spot-check manual wording and label AI-compiled guides; avoid performing unreviewed hazardous actions. |
| Demo video | BLOCKED on recording/upload | Record 120 seconds, label simulator footage, upload, verify public playback and paste URL. |
| Account, team and provenance | BLOCKED on participants | Confirm up to four eligible members, accepted/RSVP status, reused work and tool credits. |
| Deadline discrepancy | BLOCKED on organizer clarification | Ask which published rules sentence governs; ship toward Oct 18 noon / internal 10:30 target. |
| Actual Devpost submission | NOT RUN | Participant pastes content, selects eligible challenges, attaches assets and clicks submit; verify receipt. |

No Devpost page, video, Beta upload, award eligibility or physical-device success is claimed by preparing this package.
