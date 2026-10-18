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
import {
  cardsFor, cardsForWord, cardsForAi, isKnownSentence, tokenize, faceImage, faceWords, CREDIT,
  type AiSign, type Card,
} from './matcher'
import top from './top.json'

// Open Palm on the glasses. A sentence becomes cards: hand picture, the sign's
// name, two how-to lines and a small face (top right) for ASL grammar + emotion.
//   (cards move on by themselves after 2.5-10 s; dots show the time left)
//   tap          pause / resume (while listening: done speaking; in the menu: choose)
//   swipe down   full HOW description of the sign (in the menu: move down)
//   swipe up     back (in the menu: move up)
//   long-press   open / close the menu: Speak, Prepare, Prepared sentences, Practice
//   double-tap   exit
// Sentences come from the phone page, or from speech (ElevenLabs via the laptop
// server); new ones get their ASL order from the local AI, prepared ones from CREAO.

const DEMO_PHRASES = ['Hello, nice to meet you', 'My name is Abdul', 'Thank you']
// Handshape drawing style (?style=thin|bold|bold96).
const STYLE = new URLSearchParams(location.search).get('style') ?? 'bold'

// The laptop server. In dev, Vite proxies /api on the same origin. A packaged
// .ehpk runs from the Even app, so it calls the fixed address it was built with
// (VITE_API_BASE, also whitelisted in app.json by `npm run pack`).
const API_BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '')

function api(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  // ngrok's free plan shows a warning page to browsers unless this header is set.
  if (API_BASE) headers.set('ngrok-skip-browser-warning', '1')
  return fetch(`${API_BASE}${path}`, { ...init, headers })
}

const INFO = { id: 1, name: 'info' }
const HAND = { id: 2, name: 'hand' }
const FACE = { id: 3, name: 'face' }

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
// The phone keeps a hold-to-talk button: press, speak, let go.
const talk = $<HTMLButtonElement>('talk')
talk.onpointerdown = e => { e.preventDefault(); void startListening('sentence') }
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
    const face = faceWords(card.face)
    parts.push(el('small', `ASL order: ${card.sentence}${face ? ` · Face: ${face}` : ''} (${by}, unchecked)`), el('br'))
  }
  parts.push(
    el('b', card.title), document.createTextNode(` ${n}/${total}`), el('br'),
    document.createTextNode(card.how[0]), el('br'),
    document.createTextNode(card.how[1]), el('br'),
    el('small', [card.label, card.order ? 'AI ORDER' : ''].filter(Boolean).join(' · ')),
  )
  if (card.detail) {
    const credit = el('small')
    credit.append('Adapted from ', link(card.detail.url, 'Wiktionary'), ', CC BY-SA 4.0')
    parts.push(el('p', card.detail.text), credit)
  }
  if (card.video) parts.push(el('br'), link(card.video, 'Reference video (ASL-LEX)'))
  phoneCard.replaceChildren(...parts)
}

// ---- glasses page: hand picture left, text right, face top right -------------

const bridge = await waitForEvenAppBridge()

await bridge.createStartUpPageContainer(
  new CreateStartUpPageContainer({
    containerTotalNum: 3,
    textObject: [
      new TextContainerProperty({
        xPosition: 176, yPosition: 80, width: 392, height: 200,
        borderWidth: 0, borderColor: 5, paddingLength: 4,
        containerID: INFO.id, containerName: INFO.name,
        content: ' ',
        isEventCapture: 1,
      }),
    ],
    imageObject: [
      new ImageContainerProperty({ xPosition: 16, yPosition: 72, width: 144, height: 144, containerID: HAND.id, containerName: HAND.name }),
      new ImageContainerProperty({ xPosition: 496, yPosition: 8, width: 64, height: 64, containerID: FACE.id, containerName: FACE.name }),
    ],
  }),
)

let cards: Card[] = []
let index = 0
/** -1 = the short card; 0.. = a page of the card's full description. */
let detailPage = -1
/** Shown instead of the card while listening, translating or planning. */
let status: string | null = null

// ---- menu (long-press) ------------------------------------------------------

type Mode = 'cards' | 'menu' | 'prepared'
let mode: Mode = 'cards'
let menuIndex = 0

interface MenuItem { label: string; choose: () => void }

function menuItems(): MenuItem[] {
  if (mode === 'prepared') {
    return [
      ...book.sentences.map(s => ({ label: s.english, choose: () => { mode = 'cards'; start(s.english) } })),
      { label: 'Back', choose: () => openMenu('menu') },
    ]
  }
  return [
    { label: 'Speak a sentence', choose: () => { mode = 'cards'; void startListening('sentence') } },
    { label: 'Prepare a conversation', choose: () => { mode = 'cards'; void startListening('scenario') } },
    { label: `Prepared sentences (${book.sentences.length})`, choose: () => book.sentences.length ? openMenu('prepared') : flash('NOTHING PREPARED YET\nChoose "Prepare a conversation".') },
    { label: 'Practice signs', choose: () => { mode = 'cards'; practice() } },
    { label: 'Close', choose: () => closeMenu() },
  ]
}

function openMenu(which: 'menu' | 'prepared' = 'menu'): void {
  mode = which
  menuIndex = 0
  status = null
  version++
  void render()
}

function closeMenu(): void {
  mode = 'cards'
  resumeTimer()
  version++
  void render()
}

function moveMenu(step: number): void {
  const n = menuItems().length
  menuIndex = (menuIndex + step + n) % n
  version++
  void render()
}

/** Cut at a word boundary so a line never ends mid-word. */
function shorten(text: string, max: number): string {
  if (text.length <= max) return text
  const cut = text.slice(0, max + 1).replace(/\s+\S*$/, '')
  return cut || text.slice(0, max)
}

function menuText(): string {
  const title = mode === 'prepared' ? shorten(book.title.toUpperCase(), 30) : 'OPEN PALM'
  const items = menuItems()
  // Prepared sentences can be long: show a window of 5 around the cursor.
  const startAt = Math.max(0, Math.min(menuIndex - 2, items.length - 5))
  const lines = items.slice(startAt, startAt + 5).map((it, i) => `${startAt + i === menuIndex ? '>' : ' '} ${shorten(it.label, 32)}`)
  return [title, ...lines].join('\n')
}

// ---- what the lens shows -------------------------------------------------------

// About 38 characters fit on a line; a page of ~190 characters fits the text area.
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
  if (status) return status
  if (mode !== 'cards') return menuText()
  const card = cards[index]
  if (!card) return 'OPEN PALM\nLong-press for the menu.'
  const name = card.title.split('  ')[0]
  if (detailPage >= 0 && card.detail) {
    const pages = paginate(card.detail.text)
    return [`${name} · HOW ${detailPage + 1}/${pages.length}`, pages[Math.min(detailPage, pages.length - 1)]].join('\n')
  }
  // Ultra-minimal: the sign and how to make it. Status and progress are on the phone.
  return [name, card.how[0], card.how[1], timeDots()].filter(Boolean).join('\n')
}

function lensImages(): { hand: string; face: string } {
  const card = cards[index]
  if (status || mode !== 'cards' || !card) return { hand: 'handshapes/blank', face: 'faces/face_blank' }
  return {
    hand: card.handshape ? `handshapes/${card.handshape}_${STYLE}` : 'handshapes/blank',
    face: `faces/${faceImage(card.face) ?? 'face_blank'}`,
  }
}

const pngCache = new Map<string, Uint8Array>()
async function png(path: string): Promise<Uint8Array> {
  let bytes = pngCache.get(path)
  if (!bytes) {
    const res = await fetch(`${import.meta.env.BASE_URL}${path}.png`)
    if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`)
    bytes = new Uint8Array(await res.arrayBuffer())
    pngCache.set(path, bytes)
  }
  return bytes
}

// Render loop: one bridge call in flight, latest state wins, and each picture is
// only resent when it changes.
let version = 0
let rendered = -1
let rendering = false
const shown = { hand: '', face: '' }

async function sendImage(slot: 'hand' | 'face', path: string): Promise<void> {
  if (shown[slot] === path) return
  const target = slot === 'hand' ? HAND : FACE
  const t0 = performance.now()
  const result = await bridge.updateImageRawData(
    new ImageRawDataUpdate({ containerID: target.id, containerName: target.name, imageData: await png(path) }),
  )
  console.log(`[coach] ${slot} ${path} ${Math.round(performance.now() - t0)} ms ${result}`)
  if (result === ImageRawDataUpdateResult.success) shown[slot] = path
}

async function render(): Promise<void> {
  if (rendering) return
  rendering = true
  try {
    while (rendered !== version) {
      const v = version
      showOnPhone(cards[index], index + 1, cards.length)
      // Text first: it is the quickest feedback; pictures follow.
      await bridge.textContainerUpgrade(
        new TextContainerUpgrade({ containerID: INFO.id, containerName: INFO.name, content: lensText() }),
      )
      const images = lensImages()
      await sendImage('hand', images.hand)
      await sendImage('face', images.face)
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
  mode = 'cards'
  paused = false
  startCardTimer()
  version++
  void render()
}

function setStatus(text: string | null): void {
  status = text
  if (!text) resumeTimer()
  version++
  void render()
}

// ---- hands-free: cards advance by themselves ------------------------------------
// Each card stays for a time that suits it; five dots under the lines empty as it
// runs out. Tap pauses / resumes; reading HOW (swipe down) pauses until you swipe
// back up. After the last sign the lens clears 5 s later. ?review=top stays manual.

const AUTO = new URLSearchParams(location.search).get('review') !== 'top'
const DOTS = 5
const END_HOLD_MS = 5000
let paused = false
let total = 0
let remaining = 0
let tickTimer: ReturnType<typeof setTimeout> | undefined
let endTimer: ReturnType<typeof setTimeout> | undefined

/** ~5 s for a simple sign, up to ~10 s for two hands or a complex movement, 2.5 s a letter. */
function dwell(card: Card): number {
  if (card.kind === 'letter') return 2500
  if (card.kind === 'unsupported') return 4000
  const how = card.how.join(' ').toLowerCase()
  let ms = 5000
  if (/both|other|two hands|hands/.test(how)) ms += 2500
  if (/circle|zigzag|repeat|twice|x2|then|swap|alternate|wiggle|flip|roll/.test(how)) ms += 1500
  return Math.min(ms, 10_000)
}

function timeDots(): string {
  if (!AUTO || !cards.length || total <= 0) return ''
  const left = Math.max(0, Math.ceil((remaining / total) * DOTS))
  return '●'.repeat(left) + '○'.repeat(DOTS - left) + (paused ? '  PAUSED' : '')
}

function canRun(): boolean {
  return AUTO && !paused && mode === 'cards' && !status && detailPage < 0 && cards.length > 0
}

function startCardTimer(): void {
  clearTimeout(tickTimer)
  clearTimeout(endTimer)
  tickTimer = undefined
  total = remaining = cards[index] ? dwell(cards[index]) : 0
  resumeTimer()
}

function resumeTimer(): void {
  if (tickTimer || remaining <= 0 || !canRun()) return
  const step = total / DOTS
  tickTimer = setTimeout(() => {
    tickTimer = undefined
    if (!canRun()) return // paused meanwhile; resumeTimer() picks it up again
    remaining -= step
    if (remaining > 1) {
      version++
      void render()
      resumeTimer()
    } else {
      advance()
    }
  }, step)
}

function pauseTimer(): void {
  clearTimeout(tickTimer)
  tickTimer = undefined
}

function advance(): void {
  remaining = 0
  if (index < cards.length - 1) {
    index++
    detailPage = -1
    startCardTimer()
  } else {
    // Last sign: keep it a little longer, then go quiet.
    endTimer = setTimeout(() => { cards = []; total = 0; version++; void render() }, END_HOLD_MS)
  }
  version++
  void render()
}

function togglePause(): void {
  if (!cards.length) return
  paused = !paused
  if (paused) pauseTimer()
  else if (remaining > 0) resumeTimer()
  else startCardTimer() // paused on an ended sentence: play it again from here
  version++
  void render()
}

/** A short message that clears itself. */
function flash(text: string, ms = 3000): void {
  setStatus(text)
  setTimeout(() => status === text && setStatus(null), ms)
}

// ---- AI word order: new sentences go to the laptop's local model -------------
// Hand-written sentences and single words stay instant and offline. Anything
// else asks /api/translate (AI · LOCAL); if it fails or takes longer than
// AI_TIMEOUT_MS, the sentence is signed word by word. ?ai=off disables it.

const AI_ON = new URLSearchParams(location.search).get('ai') !== 'off'
const AI_TIMEOUT_MS = 8000
let request = 0

// ---- conversation prep (CREAO) and opt-in history ------------------------------

interface PreparedSentence { english: string; signs: AiSign[]; face: string; emotion?: string }
interface Phrasebook { title: string; sentences: PreparedSentence[]; practice: string[]; source?: string }

const prepared = new Map<string, PreparedSentence>()
const key = (text: string) => tokenize(text).join(' ')
let book: Phrasebook = { title: '', sentences: [], practice: [] }

const rememberBox = $<HTMLInputElement>('remember')
try { rememberBox.checked = localStorage.getItem('open-palm-remember') === '1' } catch { /* storage blocked */ }
rememberBox.onchange = () => { try { localStorage.setItem('open-palm-remember', rememberBox.checked ? '1' : '0') } catch { /* ok */ } }

function remember(kind: 'sentence' | 'hard_sign', text: string): void {
  if (!rememberBox.checked) return
  void api('/api/history', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind, text }) }).catch(() => {})
}

function practice(): void {
  if (!book.practice.length) return flash('NOTHING TO PRACTICE YET\nPrepare a conversation first.')
  show(cardsForAi(book.practice.map(gloss => ({ gloss, spell: false })), '', 'AI · CREAO'))
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
    b.onclick = practice
    list.append(b)
  }
}

const bookLoaded = api('/api/phrasebook', { signal: AbortSignal.timeout(3000) })
  .then(r => r.ok ? r.json() : null).then(b => { if (b) showBook(b) }).catch(() => {})

$<HTMLButtonElement>('forget').onclick = () => {
  void api('/api/history', { method: 'DELETE' }).then(() => { $<HTMLParagraphElement>('prepstatus').textContent = 'History forgotten.' })
}

/** Ask CREAO to plan a conversation; progress shows on the phone and the lens. */
async function prepareConversation(scenario: string): Promise<void> {
  const statusLine = $<HTMLParagraphElement>('prepstatus')
  const progress = (s: string, lens: string) => { statusLine.textContent = s; setStatus(lens) }
  progress('CREAO is planning your conversation...', `PLANNING WITH CREAO...\n"${scenario.slice(0, 60)}"`)
  try {
    const res = await api('/api/prepare', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario, use_history: $<HTMLInputElement>('usehist').checked }),
    })
    if (!res.ok) throw new Error(await res.text())
    const { job } = await res.json() as { job: string }
    for (;;) {
      await new Promise(r => setTimeout(r, 3000))
      const s = await (await api(`/api/prepare/${job}`)).json() as { status: string; elapsed_s: number; error?: string; phrasebook?: Phrasebook }
      if (s.status === 'done' && s.phrasebook) {
        statusLine.textContent = `Ready in ${s.elapsed_s} s. Say or tap any sentence below; it shows instantly.`
        showBook(s.phrasebook)
        openMenu('prepared')
        return
      }
      if (s.status === 'failed') throw new Error(s.error)
      progress(`CREAO is planning your conversation... ${s.elapsed_s} s`, `PLANNING WITH CREAO...\n${s.elapsed_s} s`)
    }
  } catch (err) {
    statusLine.textContent = `Prep failed: ${String(err).slice(0, 160)}`
    flash("COULDN'T PREPARE\nTry again from the menu.", 4000)
  }
}

$<HTMLButtonElement>('prepare').onclick = () => {
  const scenario = $<HTMLTextAreaElement>('scenario').value.trim()
  if (!scenario) { $<HTMLParagraphElement>('prepstatus').textContent = 'Describe the conversation first.'; return }
  void prepareConversation(scenario)
}

function start(phrase: string): void {
  remember('sentence', phrase)
  const ready = prepared.get(key(phrase))
  if (ready) {
    show(cardsForAi(ready.signs, ready.face, 'AI · CREAO', ready.emotion))
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
      const res = await api('/api/translate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: phrase }),
        signal: AbortSignal.timeout(AI_TIMEOUT_MS),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = (await res.json()) as { signs: AiSign[]; face: string; emotion?: string; source: string; ms: number }
      if (data.signs.length) aiCards = cardsForAi(data.signs, data.face, data.source, data.emotion)
      console.log(`[coach] AI order in ${data.ms} ms: ${aiCards?.map(c => c.title.split('  ')[0]).join(' ')} [${data.face}/${data.emotion ?? ''}]`)
    } catch (err) {
      console.warn('[coach] AI order unavailable, signing word by word', err)
    }
    if (mine !== request) return // a newer sentence arrived meanwhile
    show(aiCards ?? cardsFor(phrase))
  })()
}

// ---- speech -------------------------------------------------------------------
// From the menu: listening starts at once and a tap ends it. From the phone:
// hold the button. Glasses-mic PCM goes once to /api/stt; nothing is stored.

const MAX_LISTEN_MS = 15_000
type Purpose = 'sentence' | 'scenario'
let listening: Purpose | null = null
let chunks: Uint8Array[] = []
let listenTimer: ReturnType<typeof setTimeout> | undefined

async function startListening(purpose: Purpose): Promise<void> {
  if (listening) return
  listening = purpose
  chunks = []
  setStatus(purpose === 'sentence' ? 'LISTENING...\nSay your sentence,\nthen tap.' : 'LISTENING...\nDescribe the conversation,\nthen tap.')
  listenTimer = setTimeout(() => void stopListening(), MAX_LISTEN_MS)
  const ok = await bridge.audioControl(true, AudioInputSource.Glasses)
  if (!ok) {
    listening = null
    clearTimeout(listenTimer)
    flash('MICROPHONE NOT AVAILABLE\nType it on the phone.', 4000)
  }
}

async function stopListening(): Promise<void> {
  const purpose = listening
  if (!purpose) return
  listening = null
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
    const res = await api('/api/stt', { method: 'POST', body: pcm, headers: { 'Content-Type': 'application/octet-stream' } })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    text = ((await res.json()) as { text: string }).text
  } catch (err) {
    console.error('[coach] speech-to-text failed', err)
    flash("COULDN'T REACH THE LAPTOP\nType it on the phone.", 4000)
    return
  }
  if (!text) return flash("DIDN'T CATCH THAT\nLong-press to try again.")
  console.log(`[coach] heard "${text}" from ${(pcm.length / 32000).toFixed(1)} s of audio`)
  if (purpose === 'scenario') {
    $<HTMLTextAreaElement>('scenario').value = text
    void prepareConversation(text)
  } else {
    phraseInput.value = text
    start(text)
  }
}

// ---- cards: tap / swipe --------------------------------------------------------

/** Tap on a card: pause / resume when hands-free, otherwise the next card (review mode). */
function tap(): void {
  if (AUTO) togglePause()
  else next()
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
  pauseTimer() // reading HOW holds the card
  detailPage++
  version++
  void render()
}

/** Swipe up: previous description page, then back to the short card. */
function back(): void {
  if (detailPage < 0) return
  detailPage--
  if (detailPage < 0) resumeTimer() // back on the card: carry on
  version++
  void render()
}

// ?phrase=... starts a phrase on load (simulator checks and demo links).
// ?review=top steps through the 100 most-used signs, one card each.
// ?menu=1 opens the menu on load.
const params = new URLSearchParams(location.search)
const initial = params.get('phrase')
if (params.get('review') === 'top') {
  cards = (top as string[]).flatMap(word => cardsForWord(word))
  version++
  void render()
} else if (initial) void bookLoaded.then(() => start(initial)) // so prepared sentences match
else if (params.get('menu')) void bookLoaded.then(() => openMenu('menu'))
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
  const is = (t: OsEventTypeList) => types.includes(t)
  if (is(OsEventTypeList.DOUBLE_CLICK_EVENT)) {
    bridge.shutDownPageContainer(1)
    return
  }
  if (listening) {
    if (is(OsEventTypeList.CLICK_EVENT)) void stopListening()
    return
  }
  if (is(OsEventTypeList.LONG_PRESS_EVENT)) {
    if (mode === 'cards') openMenu('menu')
    else closeMenu()
    return
  }
  if (mode !== 'cards') {
    if (is(OsEventTypeList.SCROLL_BOTTOM_EVENT)) moveMenu(1)
    else if (is(OsEventTypeList.SCROLL_TOP_EVENT)) moveMenu(-1)
    else if (is(OsEventTypeList.CLICK_EVENT)) menuItems()[menuIndex]?.choose()
    return
  }
  if (is(OsEventTypeList.CLICK_EVENT)) tap()
  else if (is(OsEventTypeList.SCROLL_BOTTOM_EVENT)) more()
  else if (is(OsEventTypeList.SCROLL_TOP_EVENT)) back()
})
