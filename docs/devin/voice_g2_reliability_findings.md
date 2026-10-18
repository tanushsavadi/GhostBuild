# Voice + G2 reliability: findings (b/voice @ 83f676e)

Suite: `tests/e2e/` (see its README). Real core subprocess + real `g2/src/main.ts` in Node with a fake Even Hub
SDK bridge and a fake speech-to-text provider. **Nothing here proves physical G2 behaviour**; it proves the
code paths. Production code was not changed. Each defect below has a strict-xfail repro; the test name is
the minimal reproduction (`uv run pytest tests/e2e -k <name> --runxfail` shows the failing assertion).

Results: 84 passed, 20 strict xfail (details under "Test run").

## What holds up (passing tests)

- Hold-to-talk: `/ptt start` shows `LISTENING...`, release posts one `/audio` clip, cancel restores the step.
  Holds < 400 ms and holds with no PCM are cancelled; taps during a hold and within 600 ms after are ignored;
  a duplicate release sends one clip. PCM arrives as `Uint8Array`, number array or base64 and is decoded.
- Short/empty clips (< 0.3 s) never reach the provider. Provider 401/429/500/503, a non-JSON 200 body
  (captive portal), unreachable host and the 15 s timeout all show `VOICE FAILED · TAP INSTEAD`, leave the
  step untouched, and the next clip works. Empty/null/missing `text` shows `DIDN'T CATCH THAT`. Slow STT never blocks taps (tap handled < 1 s while STT is in flight).
- The key is sent only from core (`xi-api-key` header, `scribe_v1`, `pcm_s16le_16`); `g2/src/main.ts`
  contains no key and no provider URL. No key -> `VOICE OFF · TAP INSTEAD`; `GB_VOICE=0` wins over a key.
- next/back/repeat/help/done work over the full voice path. Authored questions get authored FAQ/why/where
  text; clearly unrelated questions in the corpus (`tests/fixtures/questions.json`) get `ASK A MENTOR`.
- No voice phrase or tap ("done", "yes", "it's verified", "skip", "is it done") marks a jig step VERIFIED;
  jig offline -> `CHECKING...` then `JIG OFFLINE · ASK A MENTOR` (abstains, does not advance).
- Labels: a GUIDED run never emits "VERIFIED" anywhere; `--no-jig` runs jig steps as GUIDED; mixed runs
  show `DONE (YOU CONFIRMED)` for taps and `● VERIFIED` only after a fresh jig measurement; stale jig data
  abstains. Frame `source` is `simulated` under `--simulate-jig` and `live` otherwise.
- Transport: WS drop reconnects and input works; three WS failures switch to HTTP polling; a WebView that
  blocks WebSocket runs fully on polling; core kill/stop shows `GHOSTBUILD OFFLINE`; taps while offline are
  dropped, not replayed later; HUD rate limit (>= ~250 ms between frames) holds under a burst of inputs.

## Production defects (strict xfail)

| id | sev | where | defect | repro test | needed fix (not applied) |
|---|---|---|---|---|---|
| F-01 | high | `core/.../answer.py` | Keyword fallback answers unrelated questions with the step's where/why/FAQ line ("where is the bathroom" -> `ROWS 10 AND 15, LEFT SIDE`; "why is the sky blue" -> `LEDS ONLY WORK ONE WAY`). Violates "out of scope -> say so". | `test_off_topic_question_must_abstain` | Require a minimum overlap with content words of the matched FAQ/why/where (stopword-filtered), not single generic tokens like "where"/"why"; otherwise `ASK A MENTOR`. |
| F-02 | high | `answer.py` | With no current-step match, answers come from another step's FAQ ("which way does it go" on PRESS THE BUTTON -> LED orientation). Not "the current procedure step". | `test_vague_question_is_not_answered_from_another_step` | Answer only from the current step, or prefix other-step answers with that step ("STEP 3: ...") and require a stronger score. |
| F-03 | high | `server.py` `/audio` | Transcript applies to whatever step is current when STT returns. User says "done", taps meanwhile, the late "done" confirms step 2 they never saw. | `test_late_transcript_does_not_confirm_the_next_step` | Snapshot `hud.seq`/step at `/ptt start` or `/audio` receipt; drop (or show "IGNORED · STEP CHANGED") a transcript whose step changed. Same mechanism as F-15. |
| F-04 | med | `g2/src/main.ts` | No max hold. If `LONG_PRESS_RELEASE` is lost (BLE drop), mic stays open, PCM buffers without bound and every tap is ignored until a release arrives. | `test_lost_release_does_not_disable_taps_forever` (slow) | Auto-stop after N s (e.g. 10 s, below core's 15 s notice) and cap buffer bytes. |
| F-05 | med | `main.ts` `startTalk` | `/ptt start` is posted before `audioControl(true)`; on mic failure no cancel is sent, so the glasses show `LISTENING...` for 15 s with the mic off. | `test_mic_unavailable_does_not_leave_listening_on_glasses` | Post `/ptt cancel` when `audioControl` returns false/throws (or post start after the mic opens). |
| F-06 | low | `main.ts` | A second hold starting within the 250 ms tail of the first is swallowed (`recording` still true). | `test_second_hold_inside_release_tail_is_not_lost` | Clear `recording` (or queue the start) at release time, not after the tail. |
| F-08 | high | `main.ts` `onFrame` + `server.py` WS connect | After a WS drop or a failed poll to the **same** core, core resends `hud.last` with the seq the plugin already saw; `onFrame` drops it, so glasses stay on `GHOSTBUILD OFFLINE` while the phone says Connected, until the HUD next changes. | `test_ws_drop_restores_the_step_on_glasses`, `test_polling_blip_restores_the_step_on_glasses` | In the plugin, reset `lastSeq = 0` whenever it shows OFFLINE (or always `show()` on the first frame after (re)connect). |
| F-12 | high | `main.ts` | No heartbeat/staleness. A core that stops answering without closing TCP (laptop sleep, hung loop, Wi-Fi gone without FIN) leaves the last frame, possibly an instruction or VERIFIED, on the glasses forever. `ttl_ms` is ignored. | `test_frozen_backend_is_flagged_on_glasses` | Core pings every ~2 s (or resends `hud.last`); plugin shows OFFLINE after ~5 s silence. |
| F-14 | high | `main.ts` / `hud.py` render | Frames carry `source="simulated"` but the plugin renders only `lines`; a simulated `● VERIFIED` is indistinguishable from a measured one on the glasses. Violates "never demo simulated as live". | `test_simulated_verified_is_labelled_on_glasses` | `hud.render` (only writer of lines) should append/prefix a `SIM` tag when source != live; or the plugin shows it. |
| F-15 | med | `server.py` / `engine.py` | `G2Input.seq_seen` is ignored. Three deliveries of one tap (same `seq_seen`) confirm step 1, skip its ack, then confirm step 2 the user never saw. | `test_duplicate_inputs_for_one_frame_complete_at_most_one_step` | Drop a tap/voice whose `seq_seen` is older than the frame that the step was entered with. |
| F-16 | policy | `engine.py` view | `back` to a step verified earlier shows the stored `● VERIFIED` even while the live jig now contradicts it. Decision for D: show stored result as history, or re-measure. | `test_revisited_step_does_not_show_stale_verified` | Re-evaluate the jig check on revisit; show `CHECKING...`/mismatch instead of stored VERIFIED. |
| F-17 | med | `hud.py` seq + `main.ts` | `hud.seq` restarts at 1 every core boot; if the plugin's last seq from the old core equals the new core's first seq, the first frame is dropped and the glasses stay OFFLINE after a restart. Seen as an intermittent failure (2 of 3 runs) of the restart test before this deterministic repro. | `test_backend_restart_with_colliding_seq_restores_glasses` | Same fix as F-08 (reset `lastSeq` on reconnect); optionally add a boot id to frames. |
| F-18 | med | `main.ts` `connect` | No WebSocket connect timeout. If TCP connects but the upgrade never completes (core mid-shutdown, captive portal, hung accept), the plugin waits on the WebView's own timeout: no OFFLINE, no retry, no polling fallback. | `test_websocket_handshake_that_never_completes_is_abandoned` | Close and retry if `onopen` has not fired within ~3 s (counts as a WS failure). |

## Observed behaviour worth knowing (asserted as current behaviour, not xfail)

- F-07: `/audio` does not validate PCM (odd byte count, a WAV container or random bytes are forwarded to the
  provider). Safe today because a provider error fails safe, but it costs a provider round-trip.
- F-09: backend restart loses the session (in-memory); glasses show `LOAD A BUILD ON THE PHONE`; the phone
  must reload. `--procedure <id>` restarts at step 1, not at the step the user was on.
- F-10: jig link down blocks a jig step entirely (`next`/`skip`/`done` do not advance) until the jig returns
  or core restarts with `--no-jig`. Correct per the abstain rule; the demo runbook needs that fallback.
- F-11: once the plugin falls back to polling it never retries WebSocket for the session.
- F-13: `repeat` makes core send a new seq with identical lines, but the plugin dedupes on content and does not
  call `textContainerUpgrade` again, so `repeat` cannot recover a display update lost over BLE.

## Real-device G2 tests still required (not covered by anything here)

1. Mic permission prompt and `audioControl(true)` on the real glasses; first-use permission denial (F-05).
2. Real `audioEvent` payload shape and rate (the harness assumes s16le 16 kHz mono, as the README says);
   record one real clip and confirm ElevenLabs transcribes it.
3. Long-press / release timing on the real touchpad: hold < 400 ms, normal hold, release while BLE is weak,
   lost release (F-04), press within 250 ms of the previous release (F-06).
4. Tap vs click-after-long-press (TAP_GUARD_MS 600) and double-tap exit on the real gesture recogniser.
5. Even App WebView: does WebSocket to `ws://<laptop-ip>:8787` work, or does it fall back to polling? Measure
   frame latency for both.
6. Wi-Fi drop / laptop sleep / core restart with the real phone: do the glasses recover the step (F-08, F-12,
   F-17, F-18)? How long is OFFLINE shown?
7. On-lens rendering of every HUD string: `●`, `·`, the progress bar, 4 lines x HUD_MAX chars, no clipping.
8. End-to-end voice latency (release -> answer on lens) with real STT on venue Wi-Fi; check < 3 s.
9. Real jig: fresh measurement -> `● VERIFIED`; unplug jig mid-step -> `JIG OFFLINE · ASK A MENTOR`.
10. Noise: the demo floor's ambient noise produces empty/garbled transcripts that must not advance a step.

## Harness notes

- Node 22's built-in WebSocket fires only `error` (no `close`) on ECONNREFUSED and stays CONNECTING; browsers
  fire `close`. The driver maps `error` to `close` so the plugin sees WebView behaviour. Without that, the
  "3 failures -> polling" path looked hung; that was a harness artifact, not a plugin bug.
- `test_backend_restart_reconnects_but_session_is_lost` failed 2 of 3 runs before it waited for the glasses to
  catch up with the old core's seq; the root cause is F-17, now its own deterministic test.

## Test run

`uv run pytest tests/e2e -p no:cacheprovider -rfxX -q` on Linux, Python 3.11, Node 22.23.3, at b/voice 83f676e:

```
84 passed, 20 xfailed, 6 warnings in 286.51s (0:04:46)
```

20 xfails = F-01 x6, F-02 x2, F-03, F-04, F-05, F-06, F-08 x2, F-12, F-14, F-15, F-16, F-17, F-18. The 6
warnings are `websockets` deprecation notices from the test client. Existing `core/tests`: 19 passed;
`g2` `tsc --noEmit`: ok; `scripts/check_secrets.sh`: ok.
