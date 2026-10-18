// GhostBuild G2 plugin: shows the HUD frames core sends and forwards taps. It decides nothing itself:
// core/ghostbuild_core (the step engine + hud.py) chooses every line.
//
// SDK calls are the ones the official minimal template uses and that ran on our G2
// (createStartUpPageContainer, textContainerUpgrade, onEvenHubEvent, shutDownPageContainer).
//
// Core URL: `?core=http://<ip>:8787` on the dev-server URL, else the host serving this page on :8787
// (with `npm run dev` + `evenhub qr` that is the laptop running core).
import {
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

// --- input (routing rules kept from the official template) ----------------------------------------------

// CLICK_EVENT is 0 and protobuf omits zero values, so a tap arrives with eventType undefined.
// Resolve the default INSIDE the envelope check so events without that envelope never read as taps.
function eventTypeOf(envelope?: { eventType?: OsEventTypeList }): OsEventTypeList | null {
  if (!envelope) return null
  return envelope.eventType ?? OsEventTypeList.CLICK_EVENT
}

const unsubscribe = bridge.onEvenHubEvent((event) => {
  const sysType = eventTypeOf(event.sysEvent)
  const textType = eventTypeOf(event.textEvent)

  // Double-tap always exits (root-level, checked before tap).
  if (sysType === OsEventTypeList.DOUBLE_CLICK_EVENT || textType === OsEventTypeList.DOUBLE_CLICK_EVENT) {
    bridge.shutDownPageContainer(1)
    return
  }
  // Tap = "done" on a GUIDED step / recheck on a VERIFIED step (core decides which).
  if (sysType === OsEventTypeList.CLICK_EVENT || textType === OsEventTypeList.CLICK_EVENT) {
    send({ kind: 'tap' })
    return
  }
  if (sysType === OsEventTypeList.SYSTEM_EXIT_EVENT || sysType === OsEventTypeList.ABNORMAL_EXIT_EVENT) {
    unsubscribe()
    ws?.close()
  }
})

connect()
