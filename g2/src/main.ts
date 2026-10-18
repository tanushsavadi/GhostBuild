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
import { cardsFor, CREDIT, type Card } from './matcher'

// Sign coach: a phrase becomes a sequence of cards (handshape image + how-to
// lines). Tap = next card, double-tap = exit. The phrase comes from the phone
// page below; speech is added later (docs/SIGN_COACH_PLAN.md step 4).

const DEMO_PHRASES = ['Hello, nice to meet you', 'My name is Abdul', 'Thank you']
// Handshape drawing style; switch after the step 0 lens test (?style=thin|bold|bold96).
const STYLE = new URLSearchParams(location.search).get('style') ?? 'bold'

const IMG = { id: 2, name: 'hand' }
const INFO = { id: 1, name: 'info' }

// ---- phone page -------------------------------------------------------------

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T
const phraseInput = $<HTMLInputElement>('phrase')
const phoneCard = $<HTMLDivElement>('card')
$<HTMLParagraphElement>('credit').textContent = CREDIT
for (const p of DEMO_PHRASES) {
  const b = document.createElement('button')
  b.textContent = p
  b.onclick = () => start(p)
  $<HTMLDivElement>('demos').append(b)
}
$<HTMLFormElement>('form').onsubmit = e => {
  e.preventDefault()
  if (phraseInput.value.trim()) start(phraseInput.value)
}

function showOnPhone(card: Card | undefined, n: number, total: number): void {
  if (!card) {
    phoneCard.textContent = 'No phrase yet.'
    return
  }
  const video = card.video ? `<a href="${card.video}" target="_blank" rel="noopener">Reference video (ASL-LEX)</a>` : ''
  phoneCard.innerHTML =
    `<b>${card.title}</b> <span>${n}/${total}</span><br>${card.how[0]}<br>${card.how[1]}` +
    `<br><small>${card.label}</small><br>${video}`
}

// ---- glasses ----------------------------------------------------------------

const bridge = await waitForEvenAppBridge()

await bridge.createStartUpPageContainer(
  new CreateStartUpPageContainer({
    containerTotalNum: 2,
    textObject: [
      new TextContainerProperty({
        xPosition: 176, yPosition: 40, width: 384, height: 208,
        borderWidth: 0, borderColor: 5, paddingLength: 4,
        containerID: INFO.id, containerName: INFO.name,
        content: 'SIGN COACH\nType or pick a phrase\non the phone.',
        isEventCapture: 1,
      }),
    ],
    imageObject: [
      new ImageContainerProperty({
        xPosition: 16, yPosition: 72, width: 144, height: 144,
        containerID: IMG.id, containerName: IMG.name,
      }),
    ],
  }),
)

let cards: Card[] = []
let index = 0

function lensText(): string {
  const card = cards[index]
  if (!card) return 'SIGN COACH\nType or pick a phrase\non the phone.'
  const next = cards[index + 1]
  return [
    `${card.title}   ${index + 1}/${cards.length}`,
    card.how[0],
    card.how[1],
    '',
    card.label,
    next ? `NEXT ${next.title.split('  ')[0]}` : 'LAST · TAP TO REPEAT',
  ].join('\n')
}

const pngCache = new Map<string, Uint8Array>()
async function png(key: string): Promise<Uint8Array> {
  let bytes = pngCache.get(key)
  if (!bytes) {
    const res = await fetch(`/handshapes/${key}.png`)
    if (!res.ok) throw new Error(`handshape ${key}: HTTP ${res.status}`)
    bytes = new Uint8Array(await res.arrayBuffer())
    pngCache.set(key, bytes)
  }
  return bytes
}

// Render loop: one bridge call in flight, latest state wins, and the image is
// only resent when the handshape changes.
let version = 0
let rendered = -1
let rendering = false
let shownImage = ''

async function render(): Promise<void> {
  if (rendering) return
  rendering = true
  try {
    while (rendered !== version) {
      const v = version
      const card = cards[index]
      showOnPhone(card, index + 1, cards.length)
      const image = card?.handshape ? `${card.handshape}_${STYLE}` : 'blank'
      if (image !== shownImage) {
        const t0 = performance.now()
        const result = await bridge.updateImageRawData(
          new ImageRawDataUpdate({ containerID: IMG.id, containerName: IMG.name, imageData: await png(image) }),
        )
        console.log(`[coach] image ${image} ${Math.round(performance.now() - t0)} ms ${result}`)
        if (result === ImageRawDataUpdateResult.success) shownImage = image
      }
      await bridge.textContainerUpgrade(
        new TextContainerUpgrade({ containerID: INFO.id, containerName: INFO.name, content: lensText() }),
      )
      rendered = v
    }
  } catch (err) {
    console.error('[coach] render failed', err)
  } finally {
    rendering = false
  }
}

function start(phrase: string): void {
  cards = cardsFor(phrase)
  index = 0
  version++
  void render()
}

function next(): void {
  if (!cards.length) return
  index = (index + 1) % cards.length
  version++
  void render()
}

// ?phrase=... starts a phrase on load (simulator checks and demo links).
const initial = new URLSearchParams(location.search).get('phrase')
if (initial) start(initial)
else void render()

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
  if (types.includes(OsEventTypeList.CLICK_EVENT)) next()
})
