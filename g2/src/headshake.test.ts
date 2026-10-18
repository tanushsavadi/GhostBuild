import { describe, expect, it } from 'vitest'
import { HeadShakeDetector, type ImuSample } from './headshake'

// Deterministic pseudo-noise so tests never flake.
function rng(seed: number): () => number {
  let s = seed
  return () => { s = (s * 1664525 + 1013904223) % 4294967296; return s / 4294967296 - 0.5 }
}

interface Opts { hz?: number; scale?: number; noise?: number }
function stream(fn: (t: number) => [number, number, number], ms: number, o: Opts = {}, start = 0): ImuSample[] {
  const hz = o.hz ?? 30, scale = o.scale ?? 1, r = rng(7)
  const out: ImuSample[] = []
  for (let t = 0; t <= ms; t += 1000 / hz) {
    const [x, y, z] = fn(t / 1000)
    const n = (o.noise ?? 0.02) * scale
    out.push({ t: start + t, x: x * scale + r() * n, y: y * scale + r() * n, z: z * scale + r() * n })
  }
  return out
}

const calm = (ms: number, o?: Opts, start = 0) => stream(() => [0, 0, 0], ms, o, start)
const shakeYaw = (hz: number, amp: number, ms: number, o?: Opts, start = 0) => stream((t) => [0.02, amp * Math.sin(2 * Math.PI * hz * t), 0.01], ms, o, start)

function run(det: HeadShakeDetector, samples: ImuSample[]): number[] {
  const fired: number[] = []
  for (const s of samples) if (det.push(s)) fired.push(s.t)
  return fired
}

describe('HeadShakeDetector', () => {
  it('detects a quick left-right-left-right shake after a calm moment', () => {
    const det = new HeadShakeDetector()
    const fired = run(det, [...calm(1500), ...shakeYaw(3, 1, 1500, undefined, 1500)])
    expect(fired.length).toBe(1)
    expect(fired[0]).toBeGreaterThan(1500)
    expect(fired[0]).toBeLessThan(3000)
  })

  it('does not care about the sensor scale or the report rate (units are undocumented)', () => {
    for (const [scale, hz] of [[0.01, 30], [1, 30], [250, 30], [1, 10], [1, 100], [40, 15]] as const) {
      const det = new HeadShakeDetector()
      const fired = run(det, [...calm(1500, { scale, hz }), ...shakeYaw(3.2, 1, 1600, { scale, hz }, 1500)])
      expect(fired.length, `scale=${scale} hz=${hz}`).toBe(1)
    }
  })

  it('ignores a slow nod or look-around (half-swings too slow) and a lone head turn', () => {
    const det = new HeadShakeDetector()
    expect(run(det, [...calm(1500), ...shakeYaw(0.6, 1, 4000, undefined, 1500)])).toEqual([])
    const turn = new HeadShakeDetector()
    expect(run(turn, [...calm(1500), ...stream((t) => [0, Math.min(1, t / 0.4), 0], 1500, undefined, 1500)])).toEqual([])
  })

  it('ignores plain sensor noise and a still head', () => {
    const det = new HeadShakeDetector()
    expect(run(det, calm(20000, { noise: 0.05 }))).toEqual([])
  })

  it('ignores whole-body bounce that moves every axis alike (walking)', () => {
    const det = new HeadShakeDetector()
    const walk = stream((t) => [0.8 * Math.sin(2 * Math.PI * 3 * t), 0.8 * Math.sin(2 * Math.PI * 3 * t + 0.3), 0.85 * Math.sin(2 * Math.PI * 3 * t + 0.6)], 4000, undefined, 1500)
    expect(run(det, [...calm(1500), ...walk])).toEqual([])
  })

  it('needs two full swings: a single wiggle is not a shake', () => {
    const det = new HeadShakeDetector()
    expect(run(det, [...calm(1500), ...shakeYaw(3, 1, 200, undefined, 1500), ...calm(2000, undefined, 1700)])).toEqual([])
  })

  it('cools down after a detection and then works again', () => {
    const det = new HeadShakeDetector()
    const first = [...calm(1500), ...shakeYaw(3, 1, 1500, undefined, 1500)]
    const again = [...calm(1500, undefined, 3000), ...shakeYaw(3, 1, 3000, undefined, 4500)]
    const fired = run(det, [...first, ...again])
    expect(fired.length).toBe(2)
    expect(fired[1] - fired[0]).toBeGreaterThanOrEqual(3500)
  })

  it('works on any axis (the sensor mounting is unknown)', () => {
    for (const axis of [0, 1, 2]) {
      const det = new HeadShakeDetector()
      const sh = stream((t) => { const v: [number, number, number] = [0, 0, 0]; v[axis] = Math.sin(2 * Math.PI * 3 * t); return v }, 1500, undefined, 1500)
      expect(run(det, [...calm(1500), ...sh]).length, `axis ${axis}`).toBe(1)
    }
  })
})
