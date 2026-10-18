import { describe, expect, it } from 'vitest'
import { SeqGate, isHudFrame } from './gate'
import { example } from './test/fixtures'
import { fakePng } from './test/fixtures'
import { readPngInfo, sizeWithinLimits } from './png'

describe('SeqGate', () => {
  it('accepts only strictly newer seqs', () => {
    const g = new SeqGate()
    expect(g.accept(5)).toBe(true)
    expect(g.accept(5)).toBe(false)
    expect(g.accept(4)).toBe(false)
    expect(g.accept(6)).toBe(true)
    expect(g.lastSeq).toBe(6)
  })
  it('reset allows a restarted server (lower seq) after reconnect', () => {
    const g = new SeqGate()
    g.accept(50)
    g.reset()
    expect(g.accept(1)).toBe(true)
  })
  it('accepts seq 0', () => {
    expect(new SeqGate().accept(0)).toBe(true)
  })
})

describe('isHudFrame', () => {
  it('accepts all contract examples', () => {
    for (const n of ['hud_welcome', 'hud_menu', 'hud_intervene', 'hud_visual', 'hud_verified', 'hud_quiet']) {
      expect(isHudFrame(example(n))).toBe(true)
    }
  })
  it('rejects garbage', () => {
    for (const x of [null, 1, 'x', {}, { type: 'hud' }, { type: 'hud', seq: -1, mode: 'quiet' }, { type: 'hud', seq: 1, mode: 'intervene' }, { type: 'hud', seq: 1, mode: 'intervene', cue: {} }]) {
      expect(isHudFrame(x)).toBe(false)
    }
  })
})

describe('png', () => {
  it('reads IHDR', () => {
    expect(readPngInfo(fakePng(288, 144))).toMatchObject({ w: 288, h: 144, bitDepth: 4, colorType: 0 })
  })
  it('rejects non-PNG', () => {
    expect(() => readPngInfo(new Uint8Array(40))).toThrow()
    expect(() => readPngInfo(new Uint8Array(3))).toThrow()
  })
  it('limits', () => {
    expect(sizeWithinLimits(288, 144)).toBe(true)
    expect(sizeWithinLimits(289, 144)).toBe(false)
    expect(sizeWithinLimits(288, 145)).toBe(false)
    expect(sizeWithinLimits(19, 50)).toBe(false)
  })
})
