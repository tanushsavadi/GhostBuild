import deck from './deck.json'
import asllex from './asllex.json'

// Turns an English phrase into the cards to sign, in order. Words in deck.json
// (hand-written lines) win; then every ASL-LEX 2.0 sign from asllex.json
// (lines composed from its phonology coding, built by tools/build_deck.py);
// anything else is fingerspelled. Pure, so it can be checked without glasses.

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
}

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

export function tokenize(text: string): string[] {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9' ]+/g, ' ')
    .split(/\s+/)
    .filter(Boolean)
}

function signCard(sign: Sign): Card {
  return {
    kind: 'sign',
    title: sign.gloss,
    how: [sign.how[0], sign.how[1]],
    handshape: sign.handshape || null,
    label: sign.status === 'REF-CHECKED' ? 'REF-CHECKED' : sign.status === 'AUTO' ? 'AUTO · UNCHECKED' : 'UNCHECKED',
    video: sign.video,
  }
}

function spell(word: string): Card[] {
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
    label: 'FINGERSPELL · UNCHECKED',
  }))
}

export function cardsFor(text: string): Card[] {
  const tokens = tokenize(text)
  const cards: Card[] = []
  let i = 0
  while (i < tokens.length) {
    const hit = phrases.find(p => p.tokens.every((t, k) => tokens[i + k] === t))
    if (hit) {
      cards.push(signCard(hit.sign))
      i += hit.tokens.length
      continue
    }
    const word = tokens[i]
    i += 1
    if (skip.has(word)) continue
    const sign = lookup(word)
    if (sign) cards.push(signCard(sign))
    else cards.push(...spell(word))
  }
  return cards
}

export const CREDIT = deck.credit
