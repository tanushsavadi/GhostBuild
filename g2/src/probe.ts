import {
  waitForEvenAppBridge,
  TextContainerProperty,
  TextContainerUpgrade,
  ImageContainerProperty,
  ImageRawDataUpdate,
  ImageRawDataUpdateResult,
  CreateStartUpPageContainer,
  OsEventTypeList,
} from '@evenrealities/even_hub_sdk'

// Step 0 probe (docs/OPEN_PALM_PLAN.md): can a wearer name ASL-LEX handshapes
// on the real lens, and how long does each image send take?
// Tap 1 reveals the handshape name, tap 2 shows the next card. Double-tap exits.

const HANDSHAPES = ['open_b', 'closed_b', '1', 'h', 'a', 's']
const VARIANTS = ['bold', 'thin', 'bold96']
const CARDS = VARIANTS.flatMap(variant => HANDSHAPES.map(id => ({ id, variant })))

const IMG = { id: 2, name: 'hand' }
const INFO = { id: 1, name: 'info' }

const bridge = await waitForEvenAppBridge()

const info = new TextContainerProperty({
  xPosition: 176,
  yPosition: 40,
  width: 384,
  height: 208,
  borderWidth: 0,
  borderColor: 5,
  paddingLength: 4,
  containerID: INFO.id,
  containerName: INFO.name,
  content: 'LOADING HANDSHAPES',
  isEventCapture: 1,
})

const hand = new ImageContainerProperty({
  xPosition: 16,
  yPosition: 72,
  width: 144,
  height: 144,
  containerID: IMG.id,
  containerName: IMG.name,
})

await bridge.createStartUpPageContainer(
  new CreateStartUpPageContainer({ containerTotalNum: 2, textObject: [info], imageObject: [hand] }),
)

// Fetch every PNG up front so send timing measures only the bridge + BLE.
const pngs = new Map<string, Uint8Array>()
for (const { id, variant } of CARDS) {
  const key = `${id}_${variant}`
  const res = await fetch(`${import.meta.env.BASE_URL}handshapes/${key}.png`)
  pngs.set(key, new Uint8Array(await res.arrayBuffer()))
}

const sendTimes: number[] = []
let index = 0
let revealed = false
let lastSend = ''

function median(xs: number[]): number {
  const s = [...xs].sort((a, b) => a - b)
  return s.length ? s[Math.floor(s.length / 2)] : 0
}

async function setInfo(): Promise<void> {
  const card = CARDS[index]
  const name = revealed ? card.id.toUpperCase() : '? (TAP TO REVEAL)'
  const content = [
    `HANDSHAPE ${index + 1}/${CARDS.length}`,
    name,
    `STYLE ${card.variant.toUpperCase()}`,
    '',
    lastSend,
    `MEDIAN ${median(sendTimes)} MS (N=${sendTimes.length})`,
  ].join('\n')
  await bridge.textContainerUpgrade(
    new TextContainerUpgrade({ containerID: INFO.id, containerName: INFO.name, content }),
  )
}

// One image send in flight at a time (SDK rule); a busy tap is ignored.
let busy = false
async function showCard(): Promise<void> {
  if (busy) return
  busy = true
  try {
    const card = CARDS[index]
    const t0 = performance.now()
    const result = await bridge.updateImageRawData(
      new ImageRawDataUpdate({
        containerID: IMG.id,
        containerName: IMG.name,
        imageData: pngs.get(`${card.id}_${card.variant}`),
      }),
    )
    const ms = Math.round(performance.now() - t0)
    if (result === ImageRawDataUpdateResult.success) sendTimes.push(ms)
    lastSend = `SEND ${ms} MS ${result === ImageRawDataUpdateResult.success ? 'OK' : String(result).toUpperCase()}`
    console.log(`[probe] ${card.id}_${card.variant} ${ms} ms ${result}`)
    await setInfo()
  } finally {
    busy = false
  }
}

await showCard()

// A tap arrives with eventType undefined (CLICK = 0 is omitted on the wire), so
// only read eventType from an envelope that exists.
bridge.onEvenHubEvent(event => {
  const types = [event.sysEvent, event.textEvent]
    .filter(e => e !== undefined)
    .map(e => e.eventType ?? OsEventTypeList.CLICK_EVENT)
  if (types.includes(OsEventTypeList.DOUBLE_CLICK_EVENT)) {
    bridge.shutDownPageContainer(1)
    return
  }
  if (types.includes(OsEventTypeList.CLICK_EVENT) && !busy) {
    if (!revealed) {
      revealed = true
      void setInfo()
    } else {
      revealed = false
      index = (index + 1) % CARDS.length
      void showCard()
    }
  }
})
