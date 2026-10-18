import deck from './deck.json'

// Turns an English phrase into the cards to sign, in order. Only signs in
// deck.json become sign cards; every other word is fingerspelled. Pure, so it
// can be checked without the glasses.

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

const signs = deck.signs as Sign[]
const letters = deck.letters as Record<string, { handshape: string | null; how: string }>
const skip = new Set(deck.skip)

// Longest phrase first, so "thank you" wins over a single "you".
const phrases = signs
  .flatMap(sign => sign.words.map(w => ({ tokens: w.split(' '), sign })))
  .sort((a, b) => b.tokens.length - a.tokens.length)

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
    handshape: sign.handshape,
    label: sign.status === 'REF-CHECKED' ? 'REF-CHECKED' : 'UNCHECKED',
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
    } else {
      if (!skip.has(tokens[i])) cards.push(...spell(tokens[i]))
      i += 1
    }
  }
  return cards
}

export const CREDIT = deck.credit
