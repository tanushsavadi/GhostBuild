import deck from './deck.json'
import asllex from './asllex.json'
import wiktionary from './wiktionary.json'
import phraseBook from './phrases.json'
import checkedFile from './checked.json'

// Words a person marked right after comparing with the reference video
// (exported from /review.html). Their cards say REF-CHECKED.
const checked = checkedFile.checked as Record<string, string>

// Turns an English phrase into the cards to sign, in order. Words in deck.json
// (hand-written lines) win; then every ASL-LEX 2.0 sign from asllex.json
// (lines composed from its phonology coding, built by tools/build_deck.py);
// anything else is fingerspelled. Cards whose gloss Wiktionary describes also
// carry that full description (tools/fetch_wiktionary.py, CC BY-SA 4.0).
// Pure, so it can be checked without glasses.

export type Status = 'REF-CHECKED' | 'UNCHECKED'

export interface Card {
  kind: 'sign' | 'letter' | 'unsupported'
  title: string
  how: [string, string]
  /** Handshape image id in public/handshapes, or null for no drawing. */
  handshape: string | null
  label: string
  /** Reference video for checking a sign (ASL-LEX), when there is one. */
  video?: string
  /** Full step-by-step description from Wiktionary (CC BY-SA 4.0), when it has the sign. */
  detail?: { text: string; url: string }
  /** Facial expression to hold while signing, when the card is part of a known sentence. */
  face?: string
  /** The ASL sentence this card belongs to, e.g. "YOUR NAME WHAT?". */
  sentence?: string
}

const descriptions = wiktionary as Record<string, { t: string; u: string }>

interface Sign {
  gloss: string
  words: string[]
  handshape: string
  how: string[]
  status: string
  video?: string
}

const letters = deck.letters as Record<string, { handshape: string | null; how: string }>
const skip = new Set(deck.skip)
// Words signed by fingerspelling them (e.g. TV = T-V), one card per letter.
const spelled = new Set(deck.spell)

// word -> [gloss, handshape, line 1, line 2, vimeo id, 1 = hand-written lines (tools/howto.json)]
type LexRow = [string, string | null, string, string, string, number]
const lexicon = asllex as unknown as Record<string, LexRow>

// Hand-written deck first, then ASL-LEX; the first sign registered for a word wins.
const byWord = new Map<string, Sign>()
for (const sign of deck.signs as Sign[]) for (const w of sign.words) byWord.set(w, sign)
for (const [word, [gloss, handshape, hands, motion, vimeo, handWritten]] of Object.entries(lexicon)) {
  if (byWord.has(word)) continue
  byWord.set(word, {
    gloss,
    words: [word],
    handshape: handshape ?? '',
    how: [hands, motion],
    status: handWritten ? 'UNCHECKED' : 'AUTO',
    video: vimeo ? `https://player.vimeo.com/video/${vimeo}` : undefined,
  })
}

// Longest phrase first, so "thank you" wins over a single "you".
const phrases = [...byWord.entries()]
  .map(([w, sign]) => ({ tokens: w.split(' '), sign }))
  .filter(p => p.tokens.length > 1)
  .sort((a, b) => b.tokens.length - a.tokens.length)

// "wants" -> "want", "learning" -> "learn", "studied" -> "study".
function lookup(word: string): Sign | undefined {
  const bare = word.replace(/'s$/, '')
  const candidates = [
    bare,
    bare.replace(/ies$/, 'y'),
    bare.replace(/es$/, ''),
    bare.replace(/s$/, ''),
    bare.replace(/ing$/, ''),
    bare.replace(/ing$/, 'e'),
    bare.replace(/ied$/, 'y'),
    bare.replace(/ed$/, ''),
    bare.replace(/d$/, ''),
  ]
  for (const c of candidates) {
    const sign = c.length > 1 || c === bare ? byWord.get(c) : undefined
    if (sign) return sign
  }
  return undefined
}

// "what's" -> "what is", "don't" -> "do not", so phrases and skips line up.
function expandContractions(text: string): string {
  return text
    .replace(/[‘’]/g, "'")
    .replace(/\bwon't\b/g, 'will not')
    .replace(/\bcan't\b|\bcan not\b/g, 'cannot') // one ASL sign, CANNOT
    .replace(/n't\b/g, ' not')
    .replace(/\b(what|how|where|who|when|why|that|it|there|he|she)'s\b/g, '$1 is')
    .replace(/'m\b/g, ' am')
    .replace(/'re\b/g, ' are')
    .replace(/'ll\b/g, ' will')
    .replace(/'ve\b/g, ' have')
}

export function tokenize(text: string): string[] {
  return expandContractions(text.toLowerCase())
    .replace(/[^a-z0-9' ]+/g, ' ')
    .split(/\s+/)
    .filter(Boolean)
}

// ---- known sentences (phrases.json) ------------------------------------------

type Step = string | { gloss: string; handshape: string; how: [string, string]; wikt?: string }
interface Phrase { en: string[]; asl: Step[]; face?: string }

const content = (text: string) => tokenize(text).filter(t => !skip.has(t))

const sentences = (phraseBook.phrases as Phrase[])
  .flatMap(p => p.en.map(en => ({ tokens: content(en), phrase: p })))
  .filter(s => s.tokens.length > 0)
  .sort((a, b) => b.tokens.length - a.tokens.length)

function phraseCards(p: Phrase): Card[] {
  const cards = p.asl.map(step => {
    if (typeof step !== 'string') {
      const d = step.wikt ? descriptions[step.wikt] : undefined
      return {
        kind: 'sign' as const,
        title: step.gloss,
        how: step.how,
        handshape: step.handshape,
        label: 'UNCHECKED',
        detail: d ? { text: d.t, url: d.u } : undefined,
      }
    }
    const sign = byWord.get(step)
    if (!sign) throw new Error(`phrases.json: no sign for "${step}"`)
    return signCard(sign)
  })
  const question = p.face?.toLowerCase().includes('question') ? '?' : ''
  const sentence = cards.map(c => c.title).join(' ') + question
  return cards.map(c => ({ ...c, face: p.face, sentence }))
}

function signCard(sign: Sign): Card {
  const d = descriptions[sign.gloss]
  const refChecked = sign.status === 'REF-CHECKED' || sign.words.some(w => checked[w] === 'ok')
  return {
    detail: d ? { text: d.t, url: d.u } : undefined,
    kind: 'sign',
    title: sign.gloss,
    how: [sign.how[0], sign.how[1]],
    handshape: sign.handshape || null,
    label: refChecked ? 'REF-CHECKED' : sign.status === 'AUTO' ? 'AUTO · UNCHECKED' : 'UNCHECKED',
    video: sign.video,
  }
}

/** The cards for one vocabulary word as-is (review mode); empty if it has no sign. */
export function cardsForWord(word: string): Card[] {
  if (spelled.has(word)) return spell(word, checked[word] === 'ok')
  const sign = byWord.get(word)
  return sign ? [signCard(sign)] : []
}

function spell(word: string, refChecked = false): Card[] {
  const chars = word.replace(/'/g, '')
  if (/[0-9]/.test(chars)) {
    return [{
      kind: 'unsupported',
      title: chars.toUpperCase(),
      how: ['Numbers are not in the deck', 'Write it down or show it'],
      handshape: null,
      label: 'NOT SUPPORTED',
    }]
  }
  const upper = chars.toUpperCase()
  return [...chars].map((ch, i) => ({
    kind: 'letter' as const,
    title: `${ch.toUpperCase()}  (${upper} ${i + 1}/${chars.length})`,
    how: [letters[ch].how, `Fingerspell ${upper}`] as [string, string],
    handshape: letters[ch].handshape,
    label: refChecked ? 'FINGERSPELL · REF-CHECKED' : 'FINGERSPELL · UNCHECKED',
  }))
}

// Known sentences first, then multi-word signs ("thank you"), then single words.
// Matching runs on content words only: ASL drops is/are/do/the...
export function cardsFor(text: string): Card[] {
  const tokens = content(text)
  const at = (i: number, pattern: string[]) => pattern.every((t, k) => tokens[i + k] === t)
  const cards: Card[] = []
  let i = 0
  while (i < tokens.length) {
    const sentence = sentences.find(s => at(i, s.tokens))
    if (sentence) {
      cards.push(...phraseCards(sentence.phrase))
      i += sentence.tokens.length
      // "Can you repeat that, please?": the sentence already signs PLEASE.
      if (tokens[i] === 'please' && sentence.phrase.asl.includes('please')) i += 1
      continue
    }
    const multi = phrases.find(p => at(i, p.tokens))
    if (multi) {
      cards.push(signCard(multi.sign))
      i += multi.tokens.length
      continue
    }
    const word = tokens[i]
    i += 1
    if (spelled.has(word)) {
      cards.push(...cardsForWord(word))
      continue
    }
    const sign = lookup(word)
    if (sign) cards.push(signCard(sign))
    else cards.push(...spell(word))
  }
  return cards
}

/** Throws if a phrases.json step names a word with no sign (run in tests/checks). */
export function checkPhrases(): void {
  for (const p of phraseBook.phrases as Phrase[]) phraseCards(p)
}

export const CREDIT = deck.credit
