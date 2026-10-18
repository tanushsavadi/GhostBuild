import { describe, expect, it } from 'vitest'
import { blankView, centerBlock, centerLine, frameToView, offlineView, stepCounter } from './view'
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

describe('playbook step frames', () => {
  const step = (over: Record<string, unknown> = {}) => {
    const f = example('hud_step')
    return { ...f, step: { ...f.step!, ...over } }
  }
  it('step -> centred action cue (2 lines) plus a small counter on the tag line only', () => {
    const v = frameToView(step({ index: 2, count: 8 }), O) as { kind: string; text: string; tag: string }
    expect(v.kind).toBe('text')
    const lines = v.text.split('\n')
    expect(lines).toHaveLength(2)
    expect(lines[0]).toBe(centerLine('PUSH LED INTO BOARD', 50))
    expect(lines[1]).toBe(centerLine('LONG LEG TO THE RIGHT', 50))
    expect(v.text).not.toMatch(/\d\/\d/)
    expect(v.tag.trim().startsWith('3/8')).toBe(true) // index is 0-based on the wire, 1-based on screen
  })
  it('the fixture frame (index 1 of 3) reads 2/3 with its simulated source tag', () => {
    const v = frameToView(example('hud_step'), O) as { tag: string }
    expect(v.tag).toBe('2/3  SIMULATED  ▶ DONE ◀ BACK')
  })
  it('the gesture hint can be hidden without removing counter or evidence labels', () => {
    const v = frameToView(example('hud_step'), { ...O, askHint: false }) as {tag: string}
    expect(v.tag).toBe('2/3  SIMULATED')
  })
  it('manual step has no measured marker; measured step gets a bullet; confirmed adds a check (folded to OK)', () => {
    expect(stepCounter(step({ index: 2, count: 8 }), O)).toBe('3/8')
    expect(stepCounter(step({ index: 2, count: 8, check: 'measured' }), O)).toBe('● 3/8')
    expect(stepCounter(step({ index: 2, count: 8, confirmed: true }), O)).toBe('3/8 OK')
    expect(stepCounter(step({ index: 2, count: 8, check: 'measured', confirmed: true }), O)).toBe('● 3/8 OK')
  })
  it('the ascii glyph tier uses * for the measured bullet', () => {
    expect(stepCounter(step({ check: 'measured' }), { ...O, glyphTier: 'ascii' })).toBe('* 2/3')
  })
  it('out-of-range or malformed counters are clamped or dropped, never crash', () => {
    expect(stepCounter(step({ index: 99, count: 4 }), O)).toBe('4/4')
    expect(stepCounter(step({ count: 0 }), O)).toBe('')
    expect(stepCounter({ ...example('hud_step'), step: null }, O)).toBe('')
  })
  it('a step cue does not get the counter in the text and stays two lines even with a long counter', () => {
    const v = frameToView(step({ index: 11, count: 12, check: 'measured', confirmed: true }), O) as { text: string; tag: string }
    expect(v.text.split('\n')).toHaveLength(2)
    expect(v.tag).toContain('● 12/12 OK')
  })
  it('visual frame opened from a step: picture + caption + step counter and picture index', () => {
    const f = { ...example('hud_visual'), cue_id: 'card/x#where', step: { index: 2, count: 8, step_id: 'x', check: 'manual' as const, confirmed: false } }
    const v = frameToView(f, O)
    expect(v.kind).toBe('image')
    if (v.kind !== 'image') return
    expect(v.text).toContain('WHERE: CAMERA LENS')
    expect(v.tag).toBe('3/8  PIC 1/3  ▶ DONE ◀ BACK')
    expect(v.fallback.tag).toBe('3/8  ▶ DONE ◀ BACK')
  })
  it('gesture hints: measured steps only go back; a confirmed step goes next; menus move and select', () => {
    expect((frameToView(step({ index: 2, count: 8, check: 'measured' }), O) as { tag: string }).tag).toContain('◀ BACK')
    expect((frameToView(step({ index: 2, count: 8, check: 'measured' }), O) as { tag: string }).tag).not.toContain('DONE')
    expect((frameToView(step({ index: 2, count: 8, confirmed: true }), O) as { tag: string }).tag).toContain('▶ NEXT ◀ BACK')
    expect((frameToView(example('hud_menu'), O) as { tag: string }).tag).toContain('◀▶ MOVE ● SELECT')
    expect((frameToView(example('hud_menu'), { ...O, glyphTier: 'ascii' }) as { tag: string }).tag).toContain('<> MOVE * SELECT')
  })
  it("a step's own default picture keeps the step gestures", () => {
    const f = { ...example('hud_visual'), cue_id: 'card/x', step: { index: 0, count: 35, step_id: 'x', check: 'manual' as const, confirmed: false } }
    expect((frameToView(f, O) as { tag: string }).tag).toContain('▶ DONE ◀ BACK')
  })
  it('visual frame without a step keeps the plain picture index', () => {
    expect((frameToView(example('hud_visual'), O) as { tag: string }).tag).toBe('1/3')
  })
  it('counter changes the de-dup key (same cue text on the next step must still render)', () => {
    const a = frameToView(step({ index: 1 }), O)
    const b = frameToView(step({ index: 2 }), O)
    const c = frameToView(step({ index: 1, confirmed: true }), O)
    expect(new Set([a.key, b.key, c.key]).size).toBe(3)
  })
  it('stale step frames show STALE DATA, never the step cue or counter', () => {
    const v = frameToView({ ...step(), stale: true }, O) as { text: string; tag: string }
    expect(v.text).toContain('STALE DATA')
    expect(v.text).not.toContain('PUSH LED')
    expect(v.tag).not.toMatch(/\d\/\d/)
  })
  it('menu with three options marks the selection and keeps every option', () => {
    const f = { ...example('hud_menu'), menu: { prompt: 'WHAT NOW?', options: ['FIX', 'BUILD', 'PICK TASK'] as [string, string, string], selected: 2 } }
    const v = frameToView(f, O) as { text: string }
    const lines = v.text.split('\n').map((l) => l.trim())
    expect(lines).toEqual(['WHAT NOW?', 'FIX', 'BUILD', '> PICK TASK'])
  })
})
