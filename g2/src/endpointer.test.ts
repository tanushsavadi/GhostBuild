import { describe, expect, it } from 'vitest'
import { Endpointer, rms16 } from './endpointer'

// 100 ms of 16 kHz s16le PCM at a constant amplitude (square-ish wave so RMS == amp).
function chunk(amp: number, ms = 100): Uint8Array {
  const n = (16000 * ms) / 1000
  const b = new Uint8Array(n * 2)
  const dv = new DataView(b.buffer)
  for (let i = 0; i < n; i++) dv.setInt16(i * 2, i % 2 === 0 ? amp : -amp, true)
  return b
}

function feed(ep: Endpointer, plan: Array<[number, number]>): { decision: string; at: number } {
  let t = 0
  for (const [amp, ms] of plan) {
    for (let k = 0; k < ms / 100; k++) {
      t += 100
      const d = ep.push(chunk(amp), t)
      if (d !== 'continue') return { decision: d, at: t }
    }
  }
  return { decision: 'continue', at: t }
}

describe('Endpointer', () => {
  it('rms16 measures amplitude', () => {
    expect(Math.round(rms16(chunk(1000)))).toBe(1000)
    expect(rms16(new Uint8Array(0))).toBe(0)
  })

  it('ends about a second after the person stops talking', () => {
    const r = feed(new Endpointer(), [[80, 400], [3000, 1500], [80, 3000]])
    expect(r.decision).toBe('end')
    expect(r.at).toBeGreaterThanOrEqual(2900)
    expect(r.at).toBeLessThanOrEqual(3200)
  })

  it('gives up quietly when nobody speaks', () => {
    const r = feed(new Endpointer(), [[80, 8000]])
    expect(r.decision).toBe('no_speech')
    expect(r.at).toBeLessThanOrEqual(4700)
  })

  it('a short blip is not speech', () => {
    const r = feed(new Endpointer(), [[80, 500], [3000, 100], [80, 8000]])
    expect(r.decision).toBe('no_speech')
  })

  it('does not cut off a pause inside a sentence', () => {
    const r = feed(new Endpointer(), [[80, 400], [3000, 800], [80, 600], [3000, 800], [80, 3000]])
    expect(r.decision).toBe('end')
    expect(r.at).toBeGreaterThan(3000)
  })

  it('adapts to a noisy room: steady loud noise is not speech', () => {
    const r = feed(new Endpointer(), [[700, 8000]])
    expect(r.decision).toBe('no_speech')
  })

  it('caps a very long utterance', () => {
    const r = feed(new Endpointer(), [[80, 300], [3000, 12000]])
    expect(r.decision).toBe('end')
    expect(r.at).toBeLessThanOrEqual(9100)
  })
})
