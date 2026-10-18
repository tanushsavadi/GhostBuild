import { describe, expect, it } from 'vitest'
import { introFrames, WORDMARK } from './intro'
import { DEFAULT_VIEW_OPTIONS } from './view'

const lines = (t: string) => t.split('\n').map((l) => l.trim())

describe('launch intro', () => {
  it('reveals the wordmark left to right while a bar fills, then holds on the tagline', () => {
    const f = introFrames(DEFAULT_VIEW_OPTIONS)
    expect(f).toHaveLength(6)
    expect(lines(f[0].view.text)).toEqual(['G H', '●○○○○'])
    expect(lines(f[3].view.text)).toEqual([WORDMARK, '●●●●●'])
    expect(lines(f[4].view.text)).toEqual([WORDMARK, 'HANDS BUSY. MIND CLEAR.'])
    expect(lines(f[5].view.text)).toEqual(['SWIPE ▶ NEXT   ◀ BACK', 'TAP ● SELECT   ●● HOME']) // the whole navigation, once
    // letters appear in place: every partial frame is the full-width word, padded
    expect(f[1].view.text.split('\n')[0].length).toBe(f[3].view.text.split('\n')[0].length)
    const total = f.reduce((s, x) => s + x.ms, 0)
    expect(total).toBeGreaterThan(1500)
    expect(total).toBeLessThan(6000)
  })
  it('the ascii glyph tier keeps the bar readable', () => {
    expect(lines(introFrames({ ...DEFAULT_VIEW_OPTIONS, glyphTier: 'ascii' })[1].view.text)[1]).toBe('**ooo')
  })
})
