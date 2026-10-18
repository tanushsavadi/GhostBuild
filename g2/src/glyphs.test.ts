import { describe, expect, it } from 'vitest'
import { isAllowedGlyph, sanitizeLine, sanitizeText } from './glyphs'

describe('sanitizeText', () => {
  it('keeps A-Z 0-9 space and ASCII punctuation', () => {
    expect(sanitizeText('CHECK ECHO WIRE 10 (PIN-2)!')).toBe('CHECK ECHO WIRE 10 (PIN-2)!')
  })
  it('keeps documented glyphs in the full tier', () => {
    expect(sanitizeText('● CAMERA VIEW BACK')).toBe('● CAMERA VIEW BACK')
    expect(sanitizeText('→ PIN 10 · 90° ×2')).toBe('→ PIN 10 · 90° ×2')
  })
  it('replaces unsupported glyphs with verified fallbacks instead of dropping meaning', () => {
    expect(sanitizeText('✓ DONE')).toBe('OK DONE')
    expect(sanitizeText('“HI” — IT’S')).toBe('"HI" - IT\'S')
    expect(sanitizeText('WAIT…')).toBe('WAIT...')
    expect(sanitizeText('➡ GO')).toBe('→ GO')
  })
  it('ascii tier maps every non-ASCII glyph to ASCII', () => {
    expect(sanitizeText('● CAMERA VIEW BACK', 'ascii')).toBe('* CAMERA VIEW BACK')
    expect(sanitizeText('→ PIN 10 · 90°', 'ascii')).toBe('> PIN 10 - 90o')
    expect(/^[\x20-\x7e\n]*$/.test(sanitizeText('▲▼◀▶ ★ ✓ é ∞ 日本', 'ascii'))).toBe(true)
  })
  it('strips accents, drops everything else, never emits control chars', () => {
    expect(sanitizeText('CAFÉ')).toBe('CAFE')
    expect(sanitizeText('A\u0007B\tC\r\nD')).toBe('AB C\nD')
    expect(sanitizeText('日本語 OK')).toBe(' OK')
    expect(sanitizeText('😀 HI')).toBe(' HI')
  })
  it('sanitizeLine collapses whitespace and newlines', () => {
    expect(sanitizeLine('  A   B\nC  ')).toBe('A B C')
  })
  it('isAllowedGlyph', () => {
    expect(isAllowedGlyph('A')).toBe(true)
    expect(isAllowedGlyph('→')).toBe(true)
    expect(isAllowedGlyph('→', 'ascii')).toBe(false)
    expect(isAllowedGlyph('✓')).toBe(false)
  })
})
