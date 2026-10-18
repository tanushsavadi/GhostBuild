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
import { cardsFor, cardsForWord, CREDIT, type Card } from './matcher'
import top from './top.json'

// Open Palm: a phrase becomes a sequence of cards (handshape image + how-to
// lines). Tap = next card, double-tap = exit. The phrase comes from the phone
// page below; speech is added later (docs/OPEN_PALM_PLAN.md step 4).

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

// Built from text nodes: descriptions come from Wiktionary, so never as HTML.
function el(tag: string, text = '', attrs: Record<string, string> = {}): HTMLElement {
  const e = document.createElement(tag)
  e.textContent = text
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v)
  return e
}

function link(href: string, text: string): HTMLElement {
  return el('a', text, { href, target: '_blank', rel: 'noopener' })
}

function showOnPhone(card: Card | undefined, n: number, total: number): void {
  if (!card) {
    phoneCard.textContent = 'No phrase yet.'
    return
  }
  const parts: Node[] = []
  if (card.sentence) {
    parts.push(el('small', `ASL order: ${card.sentence}${card.face ? ` · Face: ${card.face}` : ''} (AI-drafted, unchecked)`), el('br'))
  }
  parts.push(
    el('b', card.title), document.createTextNode(` ${n}/${total}`), el('br'),
    document.createTextNode(card.how[0]), el('br'),
    document.createTextNode(card.how[1]), el('br'),
    el('small', card.label),
  )
  if (card.detail) {
    const credit = el('small')
    credit.append('Adapted from ', link(card.detail.url, 'Wiktionary'), ', CC BY-SA 4.0')
    parts.push(el('p', card.detail.text), credit)
  }
  if (card.video) parts.push(el('br'), link(card.video, 'Reference video (ASL-LEX)'))
  phoneCard.replaceChildren(...parts)
}

// ---- glasses ----------------------------------------------------------------

const bridge = await waitForEvenAppBridge()

await bridge.createStartUpPageContainer(
  new CreateStartUpPageContainer({
    containerTotalNum: 2,
    textObject: [
      new TextContainerProperty({
        xPosition: 176, yPosition: 16, width: 392, height: 256,
        borderWidth: 0, borderColor: 5, paddingLength: 4,
        containerID: INFO.id, containerName: INFO.name,
        content: 'OPEN PALM\nType or pick a phrase\non the phone.',
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
/** -1 = the short card; 0.. = a page of the card's full description. */
let detailPage = -1

// About 38 characters fit on a line and 9 lines in the text area; a page of
// ~190 characters leaves room for the header and footer lines.
function paginate(text: string, max = 190): string[] {
  const pages: string[] = []
  let page = ''
  for (const word of text.split(' ')) {
    if (page && page.length + word.length + 1 > max) {
      pages.push(page)
      page = word
    } else {
      page = page ? `${page} ${word}` : word
    }
  }
  if (page) pages.push(page)
  return pages
}

function lensText(): string {
  const card = cards[index]
  if (!card) return 'OPEN PALM\nType or pick a phrase\non the phone.'
  if (detailPage >= 0 && card.detail) {
    const pages = paginate(card.detail.text)
    const last = detailPage >= pages.length - 1
    return [
      `${card.title} · HOW ${detailPage + 1}/${pages.length}`,
      pages[Math.min(detailPage, pages.length - 1)],
      '',
      last ? '▲ BACK   TAP = NEXT SIGN' : '▼ MORE   ▲ BACK',
    ].join('\n')
  }
  const next = cards[index + 1]
  // About 36 characters fit on a line; long lines wrap, so drop the spacer.
  const long = card.how.some(line => line.length > 36)
  return [
    `${card.title}   ${index + 1}/${cards.length}`,
    card.how[0],
    card.how[1],
    // In a known sentence the face carries the grammar, so it takes the spacer's place.
    ...(card.face ? [`FACE: ${card.face}`] : long ? [] : ['']),
    card.detail ? `${card.label} · ▼ HOW` : card.label,
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
  detailPage = -1
  version++
  void render()
}

function next(): void {
  if (!cards.length) return
  index = (index + 1) % cards.length
  detailPage = -1
  version++
  void render()
}

/** Swipe down: open the full description, or its next page. */
function more(): void {
  const detail = cards[index]?.detail
  if (!detail) return
  const pages = paginate(detail.text).length
  if (detailPage >= pages - 1) return
  detailPage++
  version++
  void render()
}

/** Swipe up: previous description page, then back to the short card. */
function back(): void {
  if (detailPage < 0) return
  detailPage--
  version++
  void render()
}

// ?phrase=... starts a phrase on load (simulator checks and demo links).
// ?review=top steps through the 100 most-used signs, one card each.
const params = new URLSearchParams(location.search)
const initial = params.get('phrase')
if (params.get('review') === 'top') {
  cards = (top as string[]).flatMap(word => cardsForWord(word))
  version++
  void render()
} else if (initial) start(initial)
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
  else if (types.includes(OsEventTypeList.SCROLL_BOTTOM_EVENT)) more()
  else if (types.includes(OsEventTypeList.SCROLL_TOP_EVENT)) back()
})
