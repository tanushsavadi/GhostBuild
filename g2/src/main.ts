import {
  waitForEvenAppBridge,
  TextContainerProperty,
  TextContainerUpgrade,
  ImageContainerProperty,
  ImageRawDataUpdate,
  ImageRawDataUpdateResult,
  CreateStartUpPageContainer,
  OsEventTypeList,
  AudioInputSource,
} from '@evenrealities/even_hub_sdk'
import { cardsFor, cardsForWord, cardsForAi, isKnownSentence, tokenize, CREDIT, type AiSign, type Card } from './matcher'
import top from './top.json'

// Open Palm: a phrase becomes a sequence of cards (handshape image + how-to
// lines). Tap = next card, double-tap = exit, hold = speak the phrase. The
// phrase is typed on the phone page or spoken into the glasses microphone
// (ElevenLabs speech-to-text via the laptop server, /api/stt).

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
// Hold to talk from the phone too, in case the OS keeps the temple long-press.
const talk = $<HTMLButtonElement>('talk')
talk.onpointerdown = e => { e.preventDefault(); void startListening() }
for (const ev of ['pointerup', 'pointerleave', 'pointercancel'] as const) talk.addEventListener(ev, () => void stopListening())

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
    const by = card.order ? `chosen live by ${card.order}` : 'hand-written, AI-drafted'
    parts.push(el('small', `ASL order: ${card.sentence}${card.face ? ` · Face: ${card.face}` : ''} (${by}, unchecked)`), el('br'))
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

/** Shown instead of the card while listening or transcribing. */
let status: string | null = null

function lensText(): string {
  if (status) return status
  const card = cards[index]
  if (!card) return 'OPEN PALM\nHold the temple and say\nwhat you want to sign.\n\nOr type it on the phone.'
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
    [card.order ? 'AI ORDER' : '', card.label, card.detail ? '▼ HOW' : ''].filter(Boolean).join(' · '),
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

function show(newCards: Card[]): void {
  cards = newCards
  index = 0
  detailPage = -1
  status = null
  version++
  void render()
}

// ---- AI word order: new sentences go to the laptop's local model -------------
// Hand-written sentences and single words stay instant and offline. Anything
// else asks /api/translate (AI · LOCAL); if it fails or takes longer than
// AI_TIMEOUT_MS, the sentence is signed word by word as before. ?ai=off disables it.

const AI_ON = new URLSearchParams(location.search).get('ai') !== 'off'
const AI_TIMEOUT_MS = 8000
let request = 0

// ---- conversation prep (CREAO) and opt-in history ------------------------------

interface PreparedSentence { english: string; signs: AiSign[]; face: string }
interface Phrasebook { title: string; sentences: PreparedSentence[]; practice: string[]; source?: string }

const prepared = new Map<string, PreparedSentence>()
const key = (text: string) => tokenize(text).join(' ')
let book: Phrasebook = { title: '', sentences: [], practice: [] }

const rememberBox = $<HTMLInputElement>('remember')
try { rememberBox.checked = localStorage.getItem('open-palm-remember') === '1' } catch { /* storage blocked */ }
rememberBox.onchange = () => { try { localStorage.setItem('open-palm-remember', rememberBox.checked ? '1' : '0') } catch { /* ok */ } }

function remember(kind: 'sentence' | 'hard_sign', text: string): void {
  if (!rememberBox.checked) return
  void fetch('/api/history', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind, text }) }).catch(() => {})
}

function showBook(next: Phrasebook): void {
  book = next
  prepared.clear()
  for (const s of book.sentences) prepared.set(key(s.english), s)
  const list = $<HTMLDivElement>('book')
  list.replaceChildren()
  if (!book.sentences.length) return
  list.append(el('b', `${book.title} (${book.sentences.length} sentences, ${book.source ?? 'AI · CREAO'})`))
  for (const s of book.sentences) {
    const b = el('button', s.english) as HTMLButtonElement
    b.onclick = () => start(s.english)
    list.append(b)
  }
  if (book.practice.length) {
    const b = el('button', `Practice on glasses: ${book.practice.join(', ')}`) as HTMLButtonElement
    b.onclick = () => show(cardsForAi(book.practice.map(gloss => ({ gloss, spell: false })), '', 'AI · CREAO'))
    list.append(b)
  }
}

const bookLoaded = fetch('/api/phrasebook', { signal: AbortSignal.timeout(3000) })
  .then(r => r.ok ? r.json() : null).then(b => { if (b) showBook(b) }).catch(() => {})

$<HTMLButtonElement>('forget').onclick = () => {
  void fetch('/api/history', { method: 'DELETE' }).then(() => { $<HTMLParagraphElement>('prepstatus').textContent = 'History forgotten.' })
}

$<HTMLButtonElement>('prepare').onclick = async () => {
  const scenario = $<HTMLTextAreaElement>('scenario').value.trim()
  const statusLine = $<HTMLParagraphElement>('prepstatus')
  if (!scenario) { statusLine.textContent = 'Describe the conversation first.'; return }
  statusLine.textContent = 'CREAO is planning your conversation...'
  try {
    const res = await fetch('/api/prepare', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario, use_history: $<HTMLInputElement>('usehist').checked }),
    })
    if (!res.ok) throw new Error(await res.text())
    const { job } = await res.json() as { job: string }
    for (;;) {
      await new Promise(r => setTimeout(r, 3000))
      const s = await (await fetch(`/api/prepare/${job}`)).json() as { status: string; elapsed_s: number; error?: string; phrasebook?: Phrasebook }
      if (s.status === 'done' && s.phrasebook) {
        statusLine.textContent = `Ready in ${s.elapsed_s} s. Say or tap any sentence below; it shows instantly.`
        showBook(s.phrasebook)
        return
      }
      if (s.status === 'failed') throw new Error(s.error)
      statusLine.textContent = `CREAO is planning your conversation... ${s.elapsed_s} s`
    }
  } catch (err) {
    statusLine.textContent = `Prep failed: ${String(err).slice(0, 160)}`
  }
}

function start(phrase: string): void {
  remember('sentence', phrase)
  const ready = prepared.get(key(phrase))
  if (ready) {
    show(cardsForAi(ready.signs, ready.face, 'AI · CREAO'))
    return
  }
  const words = tokenize(phrase).length
  if (!AI_ON || words < 2 || isKnownSentence(phrase)) {
    show(cardsFor(phrase))
    return
  }
  const mine = ++request
  setStatus('TRANSLATING...')
  void (async () => {
    let aiCards: Card[] | null = null
    try {
      const res = await fetch('/api/translate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: phrase }),
        signal: AbortSignal.timeout(AI_TIMEOUT_MS),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = (await res.json()) as { signs: AiSign[]; face: string; source: string; ms: number }
      if (data.signs.length) aiCards = cardsForAi(data.signs, data.face, data.source)
      console.log(`[coach] AI order in ${data.ms} ms: ${aiCards?.map(c => c.title.split('  ')[0]).join(' ')}`)
    } catch (err) {
      console.warn('[coach] AI order unavailable, signing word by word', err)
    }
    if (mine !== request) return // a newer sentence arrived meanwhile
    show(aiCards ?? cardsFor(phrase))
  })()
}

function setStatus(text: string | null): void {
  status = text
  version++
  void render()
}

// ---- speech: hold to talk -----------------------------------------------------
// Glasses mic PCM (16 kHz, 16-bit, mono) is collected while the temple (or the
// phone button) is held, then sent once to /api/stt. Nothing is stored.

const MAX_LISTEN_MS = 15_000
let listening = false
let chunks: Uint8Array[] = []
let listenTimer: ReturnType<typeof setTimeout> | undefined

async function startListening(): Promise<void> {
  if (listening) return
  listening = true
  chunks = []
  setStatus('LISTENING...\nSay your sentence,\nthen let go.')
  listenTimer = setTimeout(() => void stopListening(), MAX_LISTEN_MS)
  const ok = await bridge.audioControl(true, AudioInputSource.Glasses)
  if (!ok) {
    listening = false
    clearTimeout(listenTimer)
    setStatus('MICROPHONE NOT AVAILABLE\nType the phrase on the phone.')
    setTimeout(() => status?.startsWith('MICROPHONE') && setStatus(null), 4000)
  }
}

async function stopListening(): Promise<void> {
  if (!listening) return
  listening = false
  clearTimeout(listenTimer)
  await bridge.audioControl(false)
  const pcm = new Uint8Array(chunks.reduce((n, c) => n + c.length, 0))
  let offset = 0
  for (const c of chunks) {
    pcm.set(c, offset)
    offset += c.length
  }
  chunks = []
  setStatus('TRANSLATING...')
  let text = ''
  try {
    const res = await fetch('/api/stt', { method: 'POST', body: pcm, headers: { 'Content-Type': 'application/octet-stream' } })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    text = ((await res.json()) as { text: string }).text
  } catch (err) {
    console.error('[coach] speech-to-text failed', err)
    setStatus("COULDN'T REACH THE LAPTOP\nType the phrase on the phone.")
    setTimeout(() => status?.startsWith('COULDN') && setStatus(null), 4000)
    return
  }
  if (!text) {
    setStatus("DIDN'T CATCH THAT\nHold the temple and try again.")
    setTimeout(() => status?.startsWith('DIDN') && setStatus(null), 3000)
    return
  }
  phraseInput.value = text
  console.log(`[coach] heard "${text}" from ${(pcm.length / 32000).toFixed(1)} s of audio`)
  start(text)
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
  if (detailPage < 0 && cards[index].kind === 'sign') remember('hard_sign', cards[index].title)
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
} else if (initial) void bookLoaded.then(() => start(initial)) // so prepared sentences match
else void render()

// A tap arrives with eventType undefined (CLICK = 0 is omitted on the wire), so
// only read eventType from an envelope that exists.
bridge.onEvenHubEvent(event => {
  if (event.audioEvent) {
    if (listening) chunks.push(event.audioEvent.audioPcm)
    return
  }
  const types = [event.sysEvent, event.textEvent]
    .filter(e => e !== undefined)
    .map(e => e.eventType ?? OsEventTypeList.CLICK_EVENT)
  if (types.includes(OsEventTypeList.DOUBLE_CLICK_EVENT)) {
    bridge.shutDownPageContainer(1)
    return
  }
  if (types.includes(OsEventTypeList.LONG_PRESS_EVENT)) void startListening()
  else if (types.includes(OsEventTypeList.LONG_PRESS_RELEASE_EVENT)) void stopListening()
  else if (listening) return
  else if (types.includes(OsEventTypeList.CLICK_EVENT)) next()
  else if (types.includes(OsEventTypeList.SCROLL_BOTTOM_EVENT)) more()
  else if (types.includes(OsEventTypeList.SCROLL_TOP_EVENT)) back()
})
