# GhostBuild voice + G2 reliability suite (`tests/e2e/`)

Black-box tests against the **current b/voice code**: the real `ghostbuild_core` server (subprocess, real
port, real WebSocket) and the real `g2/src/main.ts` plugin (bundled with esbuild, run in Node with only the
Even Hub SDK bridge replaced). Speech-to-text is a local fake provider; no request ever leaves localhost and
no API key is read or needed (the core gets a dummy key so `stt.available()` is true).

```bash
uv run pytest tests/e2e -q -rxX              # everything (~4-5 min)
uv run pytest tests/e2e -q -rxX -m "not slow" # skip the two 15-17 s timeout tests
uv run pytest tests/e2e -q -m "not plugin"    # core only, no Node needed
```

Plugin tests need Node >= 22 and `g2/node_modules` (`cd g2 && npm ci`); they skip with a reason otherwise.

| file | covers |
|---|---|
| `test_voice_capture.py` | `/ptt`, `/audio`: short/empty/malformed clips, provider 4xx/5xx/garbage/unreachable/timeout, duplicates, recovery, request format |
| `test_conversation.py` | next/back/repeat/help/done, procedure-backed Q&A, abstention, no accidental confirm/verify |
| `test_g2_plugin.py` | real plugin: hold-to-talk lifecycle, PCM encodings, mic failure, WS reconnect, HTTP polling fallback, restarts, stale/offline HUD |
| `test_backend_and_labels.py` | raw WS input, duplicates, HUD rate limit, restart, GUIDED / YOU CONFIRMED vs measured VERIFIED, simulated vs live jig |

Known production defects are `xfail(strict=True)` with a finding id (F-xx) from
`docs/devin/voice_g2_reliability_findings.md`. When one is fixed the test XPASSes and fails the run, so
remove the marker in the same PR as the fix.

**Simulated only.** The fake SDK proves the plugin's logic, not the glasses: BLE latency, real mic PCM,
the WebView's WebSocket policy and on-lens rendering still need the real-device checklist in the findings doc.

`harness/`: `core_proc.py` (core subprocess + HTTP/WS helpers, kill/freeze), `fake_stt.py` (scriptable
provider), `run_core.py` (launches `create_app` without `.env`, points `stt.URL` at the fake),
`g2/` (fake SDK, esbuild bundle, Node driver), `plugin.py` (Python side of the driver).
