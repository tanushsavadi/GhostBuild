# GhostBuild live demo and filming plan

**GhostBuild — From knowledge to action.** An intelligent, hands-free guide for the things you build and fix.

This is an executable rehearsal plan, not a record of a completed performance. Evidence and remaining release gates live in [FINAL_SPRINT_STATUS.md](FINAL_SPRINT_STATUS.md). Older `11_DEMO_RUNBOOK.md` describes superseded hardware; do not use it for this release.

## Choose the show that can actually run

Use **IKEA discovery + Mac diagnosis**. Two contrasting tasks tell the story better than four rushed demos. Keep bicycle repair for questions; keep Prusa and fresh research outside the timed performance. Neither a guide nor a user report proves a physical repair.

| Scenario | Evidence available before final rehearsal | Presentation boundary |
|---|---|---|
| MICKE identification, cabinet choice, official manual diagram, part lookup, return to step | Actual backend + official simulator + browser; [11-check capture](evidence/fluid/simulator-result.json), [discovery procedure](IKEA_DISCOVERY_RUNBOOK.md) | Human must spot-check authored step wording against the PDF before anyone follows it physically. If not done, demonstrate discovery and manual lookup only. |
| Mac display question and external branch; paged answer and return | Simulator/browser, live assistant sample; [framework evidence](FRAMEWORK.md) | Use reported observations; do not imply a green-screen fault was diagnosed or repaired by a sensor. |
| Bicycle tube/tubeless identification and documented stop | AI-compiled cached card, engine tests, source pictures | Human review pending; do not ride a repaired bicycle on the strength of this demonstration. |
| Prusa MK4 troubleshooting | AI-compiled cached card with code-checked quotes/routes | Human review pending. No hot nozzle work on stage. A different model needs its own sources. |
| Uncached research | [One real Bosch compile](evidence/adaptive/live-uncached-compile.json), 32.8 s in that recorded run | Network-dependent and AI-compiled, not human-reviewed. Do not promise that latency or turn it into the climax. |

Corrections are a release acceptance check: confirmed alternate answer must reroute; uncertain alternate must reopen the question; a ruled-out option must not select it; new product/model must remove old guide visuals. Rehearse the final merged correction tests before adding any of those moments to the performance. This script does not depend on them passing unnoticed.

## Hardware and ten-minute preflight

Bring the charged G2, paired phone with Even app, laptop/charger, one reliable shared network or hotspot, a second device for filming, and a printed MICKE product/article reference. A real MICKE desk/parts and external monitor are useful only if actually available; paper labelled as a prop is enough for a software walkthrough. The Pi camera/LED is optional and must not be substituted by a fictitious Arduino setup.

1. Confirm the release HEAD and run the supported checks in [SETUP.md](SETUP.md). Preserve the currently working service and logs; do not start a second process on occupied `:8787`.
2. Confirm `/health`, `/catalog`, `/phone/` and `/phone/engine.html` load. Check `mac_display_colors` and the expected MICKE variant are present. Cached third-party image files are local runtime assets: verify them on the actual presenting laptop. A fresh clone alone does not establish that they exist.
3. In the Even app, open the GhostBuild Beta/dev app against the laptop's reachable LAN address. Rehearse a readable cue, one real image, next/back, answer pages/return, disconnect/reconnect, and system double-press exit on **physical G2**. Record who tested, time, package/hash and results in the final status. Simulator success does not fill this checkbox.
4. If the physical test cannot pass, present the official simulator with a visible **SIMULATOR** label. This remains a product walkthrough, but does **not** satisfy Even's physical judging requirement. See [submission gates](HACKATHON_SUBMISSION.md#submission-gates).
5. Verify any voice path independently: explicit microphone consent, transcript, validated intent, phone/earbud playback. G2 has no speaker or camera. Use phone text and G2 gestures unless actual G2 capture passes. A synthetically spoken provider test is not a human microphone test.
6. Spot-check the MICKE step used on stage against the linked manufacturer manual. Confirm product/article, cabinet orientation, page, fastener and quantities. If a reviewer is unavailable, skip assembly actions and show the source PDF.
7. Start a fresh rehearsal log directory if progress must be clean. Do not delete an operator session. Leave source links and the fallback article ready in a browser tab; turn off phone auto-lock for the show.

## Start, connect and package

Run from the release checkout. `make setup` installs Python and G2 dependencies; this checkout pins Python **3.11**, and also needs Node and `uv`. Keep backend keys in the ignored `.env`; see [.env.example](../.env.example). The command below overrides research and voice flags so a surprise request cannot launch a paid job.

```sh
make setup
GB_DISCOVERY=1 GB_DISCOVERY_LIVE=0 GB_LIVE_RESEARCH=0 GB_VOICE=0 GB_TTS=0 \
  make core CORE_FLAGS="--port 8787 --log-dir logs/final-demo"
```

In another terminal, set `GHOSTBUILD_DEMO_HOST` to the presenting laptop's actual network address. On a Mac using Wi-Fi this command usually finds it; verify the result on the phone before using it.

```sh
export GHOSTBUILD_DEMO_HOST="$(ipconfig getifaddr en0)"
BACKEND="http://${GHOSTBUILD_DEMO_HOST}:8787" make g2-dev
```

Open `http://<laptop-address>:8787/phone/` on the phone, then `make g2-qr` for local dev sideload. The phone and G2 app must reach that laptop; `localhost` on a phone points to the phone. `make g2-qr` assumes the same `en0` address; if using a different interface, generate a QR with the reachable dev URL via the installed EvenHub CLI. The dev QR is **not** the sponsor-required Even Hub Beta upload.

```sh
# Third terminal: official simulator, clearly label it when presenting.
make g2-sim

# Release archive: use the same reachable backend address.
BACKEND="http://${GHOSTBUILD_DEMO_HOST}:8787" make g2-pack
```

Expected archive: `g2/ghostbuild.ehpk`. A package build does not prove installation, Beta publication, microphone permission or physical-device behavior. Enable the optional assistant only with its backend key; no key/error retains deterministic navigation and prepared answers. Do not type an unfamiliar request during a cached-only rehearsal.

## Exact five-minute presentation

Use one presenter and one operator. Phone text is the reliable input. Spoken variants below are optional only after the physical voice gate. Do not simulate an actual desk assembly or a successful repair. If a judge is wearing G2, the audience sees the matching companion mirror/simulator, explicitly labelled.

| Time | Presenter dialogue | Operator input and visible result | Backend / G2 behavior to check |
|---|---|---|---|
| 0:00–0:30 | “You’re holding two pieces of furniture together. The next instruction is buried in a PDF on your phone. So you put everything down, zoom in, and try to remember which part you were looking at. Information is everywhere. Using it with your hands busy is still hard.” | Show real hands/parts if present, otherwise hold the printed manual and name it as a prop. | No invented device capture or fault. |
| 0:30–1:00 | “GhostBuild turns trusted instructions into the next action, right where you need it. A short cue on G2; the full explanation and sources on your phone. When you need a picture, just ask.” | Show real glasses, phone and current connection. Type **“I have a white IKEA desk with a drawer and cabinet.”** | Real product-photo shortlist appears. This is cached discovery in this run, not a live search. |
| 1:00–1:25 | “First, the right object. These desks look similar. GhostBuild identifies the product before giving instructions.” | Select MICKE 802.130.74, using the first thumbnail → enlarged photo → confirm. Choose **Cabinet on the left** if asked. | Product/article and orientation determine the guide. G2 shows the first diagram. Remembered orientation may skip that question. |
| 1:25–1:55 | “Now I’m at this part of the manual. ‘Wait, which fastener do I use?’” | Type **“Show me step 14.”**, then **“Which fastener do I use?”** in the current-step input. | Jump confirms no earlier step. The official crop identifies eight 103430 cam locks and excludes 110126. Show manual attribution. If wording wasn't reviewed, display the PDF/crop and do not instruct a physical action. |
| 1:55–2:30 | “The picture belongs to this step. I can ask a question, read the answer, and come straight back without losing my place.” | Type **“How do these round metal locks work, and how far do I turn them?”** only if the assistant is enabled and rehearsed; otherwise use **“Show me a closer look.”** Press to return. | Assistant: THINKING → paged answer; down/up pages, press returns. Prepared route: exact crop and return. Neither marks anything done. If no assembly was performed, do not swipe down to claim it was. |
| 2:30–3:00 | “This is the same engine helping with a completely different problem. My Mac’s screen has gone green. Which display is affected changes what I should try.” | Click **Change task**, enter **“My MacBook screen suddenly turned green.”** Choose the ready Mac guide if intake asks a question. | The display question appears; if prior facts answered it, explain the remembered choice or use a fresh rehearsal session. |
| 3:00–3:30 | “Only the external monitor. So it starts with that connection, rather than giving everyone the same checklist. My answer is a report; it isn't a measurement of my screen.” | Select **EXTERNAL DISPLAY**. Show **UNPLUG THE MONITOR / THEN PLUG IT BACK IN** and source on phone. Press for available help, return. | Branch selection records HUMAN CONFIRMED observation. No physical repair or diagnostic certainty is claimed. Never say the glasses can see the display. |
| 3:30–4:20 | “The intelligence happens before the instruction is shown. We find documentation, keep its source, compile a branching procedure and check its structure and quotes. Navigation and pictures then run through one state machine. A model doesn't decide that you completed a measured step. CREAO is an optional asynchronous research route; ElevenLabs supplies optional speech. The guide still works with text and gestures.” | Open `/phone/engine.html`, point to actual guide/source/branch counts and provenance. Show a short read-only source quote; no new research needed. | Distinguish reviewed authored cards from AI-compiled guides awaiting human review. Local navigation has no model call. |
| 4:20–5:00 | “Our aim is a patient specialist beside you: the next instruction, the right picture, and a useful response when you're unsure. Today we can show product discovery, manual references and stateful diagnosis. Human confirmations stay labelled; hardware verification needs real evidence. GhostBuild. From knowledge to action.” | Return to the same task and source. If a physical manual step was genuinely completed, demonstrate its deliberate confirmation and HUMAN CONFIRMED label; otherwise end on the open guide. | End on the actual state. Invite the judge to ask where/how or inspect the sources. |

For a correction proof after the timed demo, first choose built-in display, then use **“Actually the external monitor is green too.”** The expected route is BOTH, not external-only. Bicycle: **“I think it’s actually tubeless”** must ask again; **“Tubeless ready”** alone must not settle the answer. Product: **“It’s a MALM desk, not MICKE”** must clear MICKE imagery and return to identity. Prusa: **“It’s actually an MK3S+”** must not reuse MK4 instructions. Run only against the release with the correction regression suite passed, and label fresh research if it is needed.

## Reset and failure cards

- **Between tasks:** use the phone's Change task control and enter the new goal. Between clean rehearsals: stop only the terminal process you started, restart the same command with a new log directory (for example `logs/final-demo-take2`), then reload both clients. Do not erase old logs or another person's session. A normal restart with the same logs should retain progress; that is a resume test, not a reset.
- **No product match:** enter `802.130.74` or the [official MICKE product URL](https://www.ikea.com/us/en/p/micke-desk-white-80213074/), confirm the actual product and orientation. If the guide is unavailable, open the official manual and say so.
- **No network/model:** stay on cached discovery/manual cards; use prepared questions and gestures. Skip explanatory AI Q&A, live research and voice. Do not describe the cached path as live retrieval.
- **Image failure:** use its text fallback and open the source on the phone. Do not substitute an unrelated or generated part image.
- **G2 disconnect:** show the real companion and labelled simulator, reconnect and verify current step; do not advance while the judge cannot see it. State the physical-device limitation.
- **Voice failure/noisy room:** type the exact same input. Optional audio plays on phone/earbuds, never from G2. Never treat an uncertain transcript as confirmation.
- **Assistant stalls:** press to return to the step; a late answer belongs on the phone and must not jump the glasses away. Use the prepared visual question.
- **Out of time:** keep IKEA identity + part lookup, Mac question + branch, and the source/evidence explanation. Drop the explanation call, live compile, bicycle and Prusa.

## Exactly 120-second product video

This is a **filming plan**, not an exported video. The official [Devpost overview](https://la-ai-hackathon-2026.devpost.com/) asks for 2–3 minutes. Make the requested 90–120 second plan **120 seconds** to fit both. Record real application behavior; trim pauses with a visible cut, never imply a network operation was instantaneous.

Capture phone screen using its native recording; capture the actual browser/official simulator with the OS screen recorder. Try through-the-lens G2 footage only if readable; otherwise label the view **OFFICIAL G2 SIMULATOR** throughout. A re-render of logged output must say **DISPLAY RECREATION FROM CAPTURED OUTPUT**; do not call it lens footage. Record voiceover separately in a quiet room. Crop private tabs, credentials, device IDs and bystanders; avoid full redistribution of third-party manuals or high-resolution product photos without permission.

| Time | Real shot / action | Exact voiceover or dialogue |
|---|---|---|
| 0:00–0:10 | Hands holding parts, stopping to zoom into a real manual. No manufactured UI. | “There’s a gap between knowing what to do and actually doing it. Especially when your hands are busy.” |
| 0:10–0:20 | Wearer puts on G2; actual companion opens. Small GhostBuild title. | “GhostBuild turns trusted documentation into a guide that stays with you, one step and one picture at a time.” |
| 0:20–0:35 | Real typed desk request → product shortlist → actual MICKE choice. Show cached label. | “Start with what you have. It helps identify the product, then chooses the matching manual and configuration.” |
| 0:35–0:50 | Jump to step 14; user: **“Which fastener do I use?”** Show actual diagram/crop + source label. | User line, then: “The relevant picture belongs to the step you’re on.” |
| 0:50–1:05 | Ask a rehearsed question; page the actual answer; press to return. If assistant unavailable, use closer-look visual and return. | “Ask without losing your place. The full answer stays available, and one press brings you back.” |
| 1:05–1:20 | Change to Mac guide; display question → EXTERNAL DISPLAY → actual connection cue. | “Different task, same system. Troubleshooting branches on what you report instead of handing everyone the same checklist.” |
| 1:20–1:35 | Actual engine/source page; briefly highlight source, question, route and review label. | “Sources become structured procedures. Quotes and routes are checked in code. Navigation is deterministic, and AI-compiled guides are clearly labelled for review.” |
| 1:35–1:50 | Actual return to step, source shown, human confirmation only if the step was really performed. Optional genuinely recorded speech transcript/audio, with phone output visible. | “G2 has no camera or speaker. Voice is optional; text and gestures remain. A user confirmation is never presented as a measured repair.” |
| 1:50–2:00 | Actual glasses and phone beside the project; minimal title card. | “Less time looking things up. More confidence taking the next step. GhostBuild. From knowledge to action.” |

Use simple cuts, short on-screen captions and natural workshop sound. Keep every text frame readable for several seconds. If voice evidence cannot be recorded, omit audio-product claims and retain the honest optional-voice line. Final card: **GhostBuild · From knowledge to action · github.com/tanushsavadi/GhostBuild**. Do not insert a nonexistent demo link.

Required props: charged glasses/phone/laptop, filmer, real manual access, labelled paper or actual desk parts, optional external monitor. Do not film hazardous bike riding or hot printer work. Upload the finished video, verify public playback while signed out, paste its real URL into Devpost, and retain the master. No video has been recorded or uploaded by this document.
