import { describe, expect, it } from 'vitest'
import { blankView, centerBlock, centerLine, frameToView, offlineView } from './view'
import { example, frame } from './test/fixtures'

const O = { centerCols: 50, glyphTier: 'full' as const }

describe('frameToView', () => {
  it('quiet -> blank single space', () => {
    const v = frameToView(example('hud_quiet'), O)
    expect(v).toMatchObject({ kind: 'text', text: ' ', tag: ' ' })
  })
  it('intervene -> two centred lines in one text view', () => {
    const v = frameToView(example('hud_intervene'), O)
    expect(v.kind).toBe('text')
    const lines = (v as { text: string }).text.split('\n')
    expect(lines).toHaveLength(2)
    expect(lines[0].trim()).toBe('CAMERA VIEW LOST')
    expect(lines[1].trim()).toBe('CHECK CAMERA LENS')
    expect(lines[0]).toBe(centerLine('CAMERA VIEW LOST', 50))
    expect(lines[0].length).toBeGreaterThan('CAMERA VIEW LOST'.length)
  })
  it('single-line cue yields one line', () => {
    const v = frameToView(example('hud_verified'), O)
    expect((v as { text: string }).text.split('\n')).toHaveLength(1)
    expect((v as { text: string }).text.trim()).toBe('● CAMERA VIEW BACK')
  })
  it('menu marks the selected option and aligns the block', () => {
    const f = example('hud_menu')
    const v = frameToView(f, O) as { text: string }
    const lines = v.text.split('\n').map((l) => l.trim())
    expect(lines[0]).toBe('BUILD OR FIX?')
    expect(v.text).toContain('> FIX')
    expect(v.text).toContain('  BUILD')
    expect(lines.find((l) => l.startsWith('>'))).toBe('> FIX')
    // selected moves
    const v2 = frameToView({ ...f, menu: { ...f.menu!, selected: 1 } }, O) as { text: string }
    expect(v2.text).toContain('> BUILD')
    expect(v2.text).not.toContain('> FIX')
  })
  it('menu with out-of-range selected clamps instead of crashing', () => {
    const f = example('hud_menu')
    const v = frameToView({ ...f, menu: { ...f.menu!, selected: 9 } }, O) as { text: string }
    expect(v.text).toContain('> BUILD')
  })
  it('menu without menu data falls back to the cue', () => {
    const f = { ...example('hud_menu'), menu: null }
    expect((frameToView(f, O) as { text: string }).text).toContain('BUILD OR FIX?')
  })
  it('visual -> image view with caption and a text fallback', () => {
    const v = frameToView(example('hud_visual'), O)
    expect(v.kind).toBe('image')
    if (v.kind !== 'image') return
    expect(v.image.url).toBe('/guides/camera_lens/where.png')
    expect(v.text).toContain('WHERE: CAMERA LENS')
    expect(v.fallback.text).toBe(v.text)
    expect(v.tag).toContain('1/3')
  })
  it('visual frame without an image is just its cue', () => {
    const v = frameToView({ ...example('hud_visual'), image: null }, O)
    expect(v.kind).toBe('text')
  })
  it('welcome shows two lines', () => {
    const v = frameToView(example('hud_welcome'), O) as { text: string }
    expect(v.text.split('\n').map((l) => l.trim())).toEqual(['GHOSTBUILD', 'BUILD OR FIX?'])
  })
  it('non-live sources are labelled on screen', () => {
    expect((frameToView(frame({ seq: 1, source: 'simulated' }), O) as { tag: string }).tag).toBe('SIMULATED')
    expect((frameToView(frame({ seq: 1, source: 'replay' }), O) as { tag: string }).tag).toBe('REPLAY')
    expect((frameToView(frame({ seq: 1, mode: 'quiet', cue: null, source: 'replay' }), O) as { tag: string }).tag).toBe('REPLAY')
    expect((frameToView(frame({ seq: 1 }), O) as { tag: string }).tag).toBe(' ')
  })
  it('stale frames never show their cue', () => {
    const v = frameToView(frame({ seq: 1, stale: true, mode: 'verified', cue: { line1: '● CAMERA VIEW BACK' } }), O) as { text: string }
    expect(v.text).not.toContain('CAMERA VIEW BACK')
    expect(v.text).toContain('STALE DATA')
  })
  it('sanitizes cue text with the chosen tier', () => {
    const f = frame({ seq: 1, cue: { line1: '✓ DONE', line2: '→ PIN 10' } })
    expect((frameToView(f, O) as { text: string }).text).toContain('OK DONE')
    expect((frameToView(f, { ...O, glyphTier: 'ascii' }) as { text: string }).text).toContain('> PIN 10')
  })
  it('a cue that sanitizes to nothing is not shown as blank/healthy', () => {
    const f = frame({ seq: 1, cue: { line1: '日本語' } })
    expect((frameToView(f, O) as { text: string }).text.trim()).toBe('NO CUE TEXT')
  })
  it('identical frames produce identical keys; different content differs', () => {
    const a = frameToView(frame({ seq: 1 }), O)
    const b = frameToView(frame({ seq: 2 }), O)
    const c = frameToView(frame({ seq: 3, cue: { line1: 'OTHER' } }), O)
    expect(a.key).toBe(b.key)
    expect(a.key).not.toBe(c.key)
  })
})

describe('helpers', () => {
  it('offline view is honest', () => {
    const v = offlineView(O)
    expect(v.text).toContain('GHOSTBUILD OFFLINE')
    expect(v.text).toContain('RECONNECTING')
    expect(v.text).not.toMatch(/VERIFIED|BACK|OK\b/)
  })
  it('blankView is a single space', () => {
    expect(blankView().text).toBe(' ')
  })
  it('centerBlock pads uniformly', () => {
    const [a, b] = centerBlock(['> FIX', '  BUILD'], 50)
    expect(a.indexOf('>')).toBe(b.length - 'BUILD'.length - 2)
  })
})
