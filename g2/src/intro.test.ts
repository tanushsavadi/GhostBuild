import { describe, expect, it } from 'vitest'
import { introFrames, WORDMARK } from './intro'
import { DEFAULT_VIEW_OPTIONS } from './view'

const lines = (t: string) => t.split('\n').map((l) => l.trim())

describe('launch intro', () => {
  it('reveals the wordmark left to right while a bar fills, then holds on the tagline', () => {
    const f = introFrames(DEFAULT_VIEW_OPTIONS)
    expect(f).toHaveLength(5)
    expect(lines(f[0].view.text)).toEqual(['G H', '●○○○○'])
    expect(lines(f[3].view.text)).toEqual([WORDMARK, '●●●●●'])
    expect(lines(f[4].view.text)).toEqual([WORDMARK, 'HANDS BUSY. MIND CLEAR.'])
    // letters appear in place: every partial frame is the full-width word, padded
    expect(f[1].view.text.split('\n')[0].length).toBe(f[3].view.text.split('\n')[0].length)
    const total = f.reduce((s, x) => s + x.ms, 0)
    expect(total).toBeGreaterThan(1500)
    expect(total).toBeLessThan(3500)
  })
  it('the ascii glyph tier keeps the bar readable', () => {
    expect(lines(introFrames({ ...DEFAULT_VIEW_OPTIONS, glyphTier: 'ascii' })[1].view.text)[1]).toBe('**ooo')
  })
})
