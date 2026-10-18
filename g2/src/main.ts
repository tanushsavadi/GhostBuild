// GhostBuild G2 plugin: shows the HUD frames core sends and forwards taps and hold-to-talk audio.
// It decides nothing itself:
// core/ghostbuild_core (the step engine + hud.py) chooses every line.
//
// SDK calls are the ones the official minimal template uses and that ran on our G2
// (createStartUpPageContainer, textContainerUpgrade, onEvenHubEvent, shutDownPageContainer), plus
// audioControl / audioEvent / LONG_PRESS_* as typed in even_hub_sdk 0.0.16 and documented at
// hub.evenrealities.com/docs/build/device-apis (PCM: 16 kHz, s16le, mono).
//
// Hold-to-talk: long-press the temple -> mic on (glasses), PCM buffered here; release -> 250 ms tail,
// mic off, the clip is POSTed to core /audio, which transcribes it server-side (no keys in the plugin)
// and runs it as a voice command or question.
//
// Core URL: `?core=http://<ip>:8787` on the dev-server URL, else the host serving this page on :8787
// (with `npm run dev` + `evenhub qr` that is the laptop running core).
import {
  AudioInputSource,
  waitForEvenAppBridge,
  TextContainerProperty,
  CreateStartUpPageContainer,
  TextContainerUpgrade,
  OsEventTypeList,
} from '@evenrealities/even_hub_sdk'

type HudFrame = { type: 'hud'; seq: number; kind: string; lines: string[]; source: string }

const CORE = new URLSearchParams(location.search).get('core') ?? `http://${location.hostname}:8787`
const WS_URL = CORE.replace(/^http/, 'ws') + '/ws?role=g2'
const POLL_MS = 300

const phone = document.getElementById('app')
const status = (text: string) => {
  if (phone) phone.textContent = text
}

const bridge = await waitForEvenAppBridge()

await bridge.createStartUpPageContainer(
  new CreateStartUpPageContainer({
    containerTotalNum: 1,
    textObject: [
      new TextContainerProperty({
        xPosition: 0,
        yPosition: 0,
        width: 576,
        height: 288,
        borderWidth: 0,
        borderColor: 5,
        paddingLength: 4,
        containerID: 1,
        containerName: 'main',
        content: 'GHOSTBUILD\nCONNECTING...',
        isEventCapture: 1,
      }),
    ],
  }),
)

let shown = ''
function show(lines: string[]) {
  const content = lines.length ? lines.join('\n') : ' ' // blank = dark
  if (content === shown) return
  shown = content
  bridge.textContainerUpgrade(new TextContainerUpgrade({ containerID: 1, containerName: 'main', content }))
}

// --- transport: WebSocket first, HTTP polling if the WebView blocks it ----------------------------------

let ws: WebSocket | null = null
let lastSeq = 0
let wsFailures = 0
let polling = false

function onFrame(f: HudFrame) {
  if (f.type !== 'hud' || f.seq === lastSeq) return
  lastSeq = f.seq
  show(f.lines)
}

function connect() {
  status(`Connecting to ${WS_URL}`)
  ws = new WebSocket(WS_URL)
  ws.onopen = () => {
    wsFailures = 0
    status(`Connected to ${CORE} (WebSocket)`)
  }
  ws.onmessage = (m) => onFrame(JSON.parse(m.data))
  ws.onclose = () => {
    ws = null
    wsFailures += 1
    if (wsFailures >= 3 && !polling) {
      startPolling()
      return
    }
    show(['GHOSTBUILD OFFLINE', 'RECONNECTING...'])
    status(`Cannot reach ${WS_URL} (try ${wsFailures}); check the laptop IP, Wi-Fi and that core is running`)
    setTimeout(connect, 1000)
  }
}

function startPolling() {
  polling = true
  status(`WebSocket blocked; polling ${CORE}/state`)
  const tick = async () => {
    try {
      const r = await fetch(`${CORE}/state`)
      const s = await r.json()
      if (s.hud) onFrame(s.hud)
      status(`Connected to ${CORE} (polling)`)
    } catch {
      show(['GHOSTBUILD OFFLINE', 'RECONNECTING...'])
      status(`Cannot reach ${CORE}/state`)
    }
    setTimeout(tick, POLL_MS)
  }
  tick()
}

function send(input: { kind: 'tap' | 'voice' | 'menu'; text?: string }) {
  const msg = { type: 'g2_input', seq_seen: lastSeq, text: null, ...input }
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg))
  else fetch(`${CORE}/input`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(msg) })
}

// --- hold-to-talk ---------------------------------------------------------------------------------------

const TAIL_MS = 250 // keep the mic open briefly after release so the last word isn't clipped
const MIN_HOLD_MS = 400 // shorter holds are accidental: cancel silently
let recording = false
let holdStart = 0
let chunks: Uint8Array[] = []
let releasedAt = 0
const TAP_GUARD_MS = 600 // a click right after a long press is part of the press, not a tap

async function startTalk() {
  if (recording) return
  recording = true
  holdStart = Date.now()
  chunks = []
  fetch(`${CORE}/ptt`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{"phase":"start"}' })
  const ok = await bridge.audioControl(true, AudioInputSource.Glasses)
  status(ok ? 'Listening (glasses mic)' : 'Glasses mic failed to open (check the g2-microphone permission)')
  if (!ok) recording = false
}

async function stopTalk() {
  if (!recording) return
  releasedAt = Date.now()
  const held = releasedAt - holdStart
  await new Promise((r) => setTimeout(r, TAIL_MS))
  recording = false
  await bridge.audioControl(false)
  const total = chunks.reduce((n, c) => n + c.length, 0)
  if (held < MIN_HOLD_MS || total === 0) {
    status(`Voice cancelled (held ${held} ms, ${total} bytes)`)
    fetch(`${CORE}/ptt`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{"phase":"cancel"}' })
    return
  }
  const pcm = new Uint8Array(total)
  let off = 0
  for (const c of chunks) {
    pcm.set(c, off)
    off += c.length
  }
  chunks = []
  status(`Sent ${(total / 32000).toFixed(1)} s of audio`)
  try {
    const r = await fetch(`${CORE}/audio`, { method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: pcm })
    const res = await r.json()
    status(res.ok ? `Heard: "${res.text}"` : `Voice error: ${res.error}`)
  } catch {
    status(`Cannot reach ${CORE}/audio`)
  }
}

function pcmOf(raw: unknown): Uint8Array | null {
  // The SDK types this as Uint8Array; over the bridge it may arrive as number[] or base64.
  if (raw instanceof Uint8Array) return raw
  if (Array.isArray(raw)) return Uint8Array.from(raw)
  if (typeof raw === 'string') return Uint8Array.from(atob(raw), (ch) => ch.charCodeAt(0))
  return null
}

// --- input (routing rules kept from the official template) ----------------------------------------------

// CLICK_EVENT is 0 and protobuf omits zero values, so a tap arrives with eventType undefined.
// Resolve the default INSIDE the envelope check so events without that envelope never read as taps.
function eventTypeOf(envelope?: { eventType?: OsEventTypeList }): OsEventTypeList | null {
  if (!envelope) return null
  return envelope.eventType ?? OsEventTypeList.CLICK_EVENT
}

const unsubscribe = bridge.onEvenHubEvent((event) => {
  // Audio frames carry no sysEvent/textEvent, so they can never read as taps.
  if (event.audioEvent) {
    const pcm = pcmOf(event.audioEvent.audioPcm)
    if (recording && pcm?.length) chunks.push(pcm)
    return
  }
  const sysType = eventTypeOf(event.sysEvent)
  const textType = eventTypeOf(event.textEvent)

  // Double-tap always exits (root-level, checked before tap).
  if (sysType === OsEventTypeList.DOUBLE_CLICK_EVENT || textType === OsEventTypeList.DOUBLE_CLICK_EVENT) {
    bridge.shutDownPageContainer(1)
    return
  }
  // Long press arrives on sysEvent (device-apis docs); textEvent is checked too, like taps.
  if (sysType === OsEventTypeList.LONG_PRESS_EVENT || textType === OsEventTypeList.LONG_PRESS_EVENT) {
    startTalk()
    return
  }
  if (sysType === OsEventTypeList.LONG_PRESS_RELEASE_EVENT || textType === OsEventTypeList.LONG_PRESS_RELEASE_EVENT) {
    stopTalk()
    return
  }
  // Tap = "done" on a GUIDED step / recheck on a VERIFIED step (core decides which).
  if (sysType === OsEventTypeList.CLICK_EVENT || textType === OsEventTypeList.CLICK_EVENT) {
    if (recording || Date.now() - releasedAt < TAP_GUARD_MS) return
    send({ kind: 'tap' })
    return
  }
  if (sysType === OsEventTypeList.SYSTEM_EXIT_EVENT || sysType === OsEventTypeList.ABNORMAL_EXIT_EVENT) {
    if (recording) bridge.audioControl(false)
    unsubscribe()
    ws?.close()
  }
})

connect()
