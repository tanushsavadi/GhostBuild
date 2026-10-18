# Optional ElevenLabs voice

Status: backend implementation and local protocol/HTTP tests pass. No live provider call or physical microphone/audio pass is claimed. Continuous conversation mode is deferred until physical G2 capture is proven; PTT, text and touch remain available.

Configure backend-only environment variables: `GB_VOICE=1`, `ELEVENLABS_API_KEY`, optional `ELEVENLABS_STT_MODEL=scribe_v2_realtime`. Spoken replies additionally require `ELEVENLABS_VOICE_ID` from an available, authorized stock voice and optional `ELEVENLABS_TTS_MODEL=eleven_flash_v2_5`. Never put these in Vite variables, the G2 manifest, a frontend bundle or a commit.

## Runtime protocol

The existing core WebSocket `/ws/voice` accepts:

1. JSON `{"type":"start","consent":true}`. Show the user that microphone audio goes through the backend to ElevenLabs before obtaining consent. This also enters LISTENING for phone PTT; temple PTT may send its existing hold events.
2. Binary signed PCM16 little-endian mono at **16,000 Hz**, even byte count, at most 640,000 bytes per utterance. The backend transcodes transport to base64 JSON upstream, not the audio itself. Resample a browser AudioContext before sending.
3. JSON `{"type":"end"}` commits exactly once and enters THINKING. JSON `{"type":"abort"}` cancels, closes upstream and never acts on speech. Clients must close mic tracks, audio contexts and WebSocket on stop, background, disconnect or exit.
4. Server result `{"type":"done","origin":"elevenlabs_stt","transcript":"...","text":"documented response","ignored":false}`. `fake_test` means a test double, never live microphone evidence. `ignored:true` means the task changed while listening, so nothing was applied. `unavailable`, `busy` and `consent_required` preserve touch/text operation.

No partial transcript acts on the application. One active socket prevents conflicting captures. Provider startup, finalization and closure have bounded timeouts. Short clips under 300 ms do not commit; other clips shorter than two seconds receive silent padding because the provider documents that initial processing starts at two seconds. The application never retries an uncertain paid request automatically. Rate limits and failures invite the user to try again explicitly.

`await integrations.elevenlabs.client.synthesize(text, consent=True)` returns bounded MP3 bytes for the paired phone/earbuds. It accepts at most 500 characters; cancellation propagates and closes the HTTP request. The server route enforces the feature flag and cooldown; the browser stops old audio before requesting/playing another reply. The G2 has no speaker. Sending a question never marks a measured step complete.

GhostBuild never writes audio to disk. The existing event log records transcripts; provider retention follows the configured ElevenLabs account policy. Do not promise provider zero retention: its documented zero retention entitlement is account-dependent.

## Verification before claiming sponsor evidence

- Grant microphone consent on the paired phone. Record a deliberate contextual request on the foreground G2 or phone; confirm final text and provider origin, useful current-step response and no progress change from partial/background speech.
- Ask “Where is that?”; confirm the correct visual remains primary. Ask a question while changing steps through touch; confirm the stale transcript is ignored.
- Choose an authorized available stock voice. Enable replies; obtain dynamic audio from the actual documented current-step answer. Confirm phone/earbud playback, mute and interruption without overlap. Audio never comes from glasses.
- Disable audio, revoke microphone permission, disconnect network and remove provider credentials; complete the guide by touch/text.
- Record actual provider run evidence separately from local mocks. No permanent credentials should appear in screenshots or logs.

## Sources checked 2026-10-17

- [Realtime STT API](https://elevenlabs.io/docs/api-reference/speech-to-text/v-1-speech-to-text-realtime): `xi-api-key`, `model_id`, `pcm_16000`, manual commits, partial/committed messages and errors.
- [Commit strategy guide](https://elevenlabs.io/docs/eleven-api/guides/how-to/speech-to-text/realtime/transcripts-and-commit-strategies): explicit commit and two-second initial input requirement.
- [TTS API](https://elevenlabs.io/docs/api-reference/text-to-speech/convert): POST and output format.
- [Official low-latency TTS example](https://elevenlabs.io/docs/eleven-api/guides/how-to/text-to-speech/streaming): `eleven_flash_v2_5`, `mp3_22050_32`.

`b/voice` and PR #2 were inspected, not merged. Their stale-transcript finding was adapted to the current session/playbook engine; no old contracts, jig assumptions or prerecorded audio were brought over.
