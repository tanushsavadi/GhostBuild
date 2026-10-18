// Glyph sanitizer. The G2 firmware draws one LVGL font and silently drops characters it lacks,
// so a dropped glyph can change the meaning of a cue. We whitelist instead.
//
// Sources (see g2/README.md for the open hardware checks):
//  - ASCII 0x20-0x7E: official docs ("Unicode works as long as the glyph is in the firmware's font set"),
//    community glyph table (all printable ASCII).
//  - ● ○ ■ □ ▲ △ ▶ ▷ ▼ ▽ ◀ ◁ ★ ☆: official design-guidelines "Useful characters" table.
//  - → ← ↑ ↓ · ° ×: community even-g2-notes table (simulator-tested, "real hardware may differ").
//    NOT yet proven on our physical G2. Set VITE_GLYPHS=ascii to fall back instantly after a failed hardware test.

export type GlyphTier = 'full' | 'ascii'

const OFFICIAL = '●○■□▲△▶▷▼▽◀◁★☆'
const COMMUNITY = '→←↑↓·°×'
const FULL_EXTRA = new Set((OFFICIAL + COMMUNITY).split(''))

/** Applied in both tiers before the whitelist: typographic and "unsupported" glyphs. */
const FOLD: Record<string, string> = {
  '‘': "'", '’': "'", '‚': "'", '“': '"', '”': '"', '„': '"',
  '–': '-', '—': '-', '−': '-', '‑': '-', '‐': '-',
  '…': '...', ' ': ' ', ' ': ' ', ' ': ' ', '　': ' ',
  '•': '-', '‣': '>', '·': '·',
  '✓': 'OK', '✔': 'OK', '☑': 'OK', '✗': 'X', '✘': 'X', '✕': 'X', '⚠': '!', '⇒': '→', '➜': '→', '➔': '→', '➡': '→',
}

/** Verified-ASCII stand-ins used when the tier is 'ascii'. */
const ASCII_FALLBACK: Record<string, string> = {
  '→': '>', '←': '<', '↑': '^', '↓': 'v',
  '●': '*', '○': 'o', '■': '#', '□': 'o', '▲': '^', '△': '^', '▼': 'v', '▽': 'v',
  '▶': '>', '▷': '>', '◀': '<', '◁': '<', '★': '*', '☆': '*',
  '·': '-', '°': 'o', '×': 'x',
}

function isPrintableAscii(ch: string): boolean {
  const c = ch.charCodeAt(0)
  return c >= 0x20 && c <= 0x7e
}

function stripMarks(ch: string): string {
  return ch.normalize('NFKD').replace(/[̀-ͯ]/g, '')
}

/**
 * Returns text containing only glyphs allowed for the tier. Newlines are kept; other control
 * characters and tabs become spaces/dropped. Unknown glyphs are dropped explicitly (never "tofu").
 */
export function sanitizeText(input: string, tier: GlyphTier = 'full'): string {
  let out = ''
  for (const raw of Array.from(input)) {
    if (raw === '\n') { out += '\n'; continue }
    if (raw === '\t' || raw === '\r') { out += raw === '\t' ? ' ' : ''; continue }
    const folded = FOLD[raw] ?? raw
    for (const ch of Array.from(folded)) out += mapOne(ch, tier)
  }
  return out
}

function mapOne(ch: string, tier: GlyphTier): string {
  if (isPrintableAscii(ch)) return ch
  if (tier === 'full' && FULL_EXTRA.has(ch)) return ch
  if (tier === 'ascii' && ASCII_FALLBACK[ch] !== undefined) return ASCII_FALLBACK[ch]
  const base = stripMarks(ch)
  if (base !== ch && base.length > 0) {
    let o = ''
    for (const b of Array.from(base)) if (isPrintableAscii(b)) o += b
    return o
  }
  return ''
}

/** Single-line sanitizer: collapses whitespace and trims. */
export function sanitizeLine(input: string, tier: GlyphTier = 'full'): string {
  return sanitizeText(input, tier).replace(/\n/g, ' ').replace(/ {2,}/g, ' ').trim()
}

export function isAllowedGlyph(ch: string, tier: GlyphTier = 'full'): boolean {
  return mapOne(ch, tier) === ch
}
