// Head-shake detector: left-right-left-right "no" gesture from the glasses' IMU stream. Pure: samples in, a boolean out.
//
// The SDK documents IMU samples as { x, y, z } floats but not their units or axes (acceleration, angular rate or orientation are all
// plausible), and the report rate is a protocol pacing code, not Hz. So nothing here assumes a scale or a sample rate:
//  - the threshold is relative to each axis's own calm-state noise (an adaptive estimate of its standard deviation),
//  - timing uses the sample timestamps the caller supplies,
//  - a shake is >= 4 alternating extrema on ONE dominant axis, each swing well above noise, spaced like a fast head movement.
// Not verified on hardware: tune with VITE_HEADSHAKE_* after a real test. A false positive only starts a listen that ends by itself.

export interface ImuSample { t: number; x: number; y: number; z: number }

export interface HeadShakeOptions {
  windowMs?: number       // all extrema must fall inside this window
  minExtrema?: number     // alternating peaks/valleys required (4 = two full left-right swings)
  minHalfMs?: number      // fastest believable half-swing
  maxHalfMs?: number      // slowest half-swing that still counts as a shake (slower is a nod, a look around, walking sway)
  relSwing?: number       // swing must exceed this many noise standard deviations
  dominance?: number      // the shaking axis must move this many times more than each other axis
  cooldownMs?: number     // ignore everything this long after a detection
  warmupSamples?: number  // learn the noise level before detecting anything
}

const DEFAULTS: Required<HeadShakeOptions> = {
  windowMs: 2000, minExtrema: 4, minHalfMs: 60, maxHalfMs: 600, relSwing: 8, dominance: 1.6, cooldownMs: 3500, warmupSamples: 12,
}

interface Extremum { t: number; v: number }

class AxisTrack {
  private mean = 0
  private varEwma = 0
  private n = 0
  private dir: 0 | 1 | -1 = 0
  private hi = -Infinity
  private lo = Infinity
  private hiT = 0
  private loT = 0
  extrema: Extremum[] = []
  path: Array<{ t: number; d: number }> = []
  private last: number | null = null

  get sigma(): number { return Math.sqrt(this.varEwma) }
  get ready(): boolean { return this.n >= 8 }

  /** Update the calm-state estimate; samples far outside it (a shake in progress) do not pollute it. */
  private learn(v: number): void {
    this.n++
    if (this.n === 1) { this.mean = v; return }
    const dev = v - this.mean
    const calm = this.n <= 8 || this.varEwma === 0 || Math.abs(dev) < 4 * Math.sqrt(this.varEwma)
    if (calm) {
      const a = this.n <= 20 ? 0.2 : 0.03
      this.mean += a * dev
      this.varEwma = (1 - a) * this.varEwma + a * dev * dev
    }
  }

  push(t: number, v: number, windowMs: number, relSwing: number): void {
    this.learn(v)
    if (this.last !== null) this.path.push({ t, d: Math.abs(v - this.last) })
    this.last = v
    while (this.path.length && t - this.path[0].t > windowMs) this.path.shift()
    while (this.extrema.length && t - this.extrema[0].t > windowMs) this.extrema.shift()
    if (!this.ready) return
    const h = Math.max(relSwing * this.sigma, 1e-12)
    if (v > this.hi) { this.hi = v; this.hiT = t }
    if (v < this.lo) { this.lo = v; this.loT = t }
    if (this.dir === 0) {
      if (this.hi - v >= h) { this.extrema.push({ t: this.hiT, v: this.hi }); this.dir = -1; this.lo = v; this.loT = t }
      else if (v - this.lo >= h) { this.extrema.push({ t: this.loT, v: this.lo }); this.dir = 1; this.hi = v; this.hiT = t }
    } else if (this.dir === 1 && this.hi - v >= h) {
      this.extrema.push({ t: this.hiT, v: this.hi }); this.dir = -1; this.lo = v; this.loT = t
    } else if (this.dir === -1 && v - this.lo >= h) {
      this.extrema.push({ t: this.loT, v: this.lo }); this.dir = 1; this.hi = v; this.hiT = t
    }
  }

  get pathLength(): number { return this.path.reduce((s, p) => s + p.d, 0) }
  reset(): void { this.extrema = []; this.dir = 0; this.hi = -Infinity; this.lo = Infinity }
}

export class HeadShakeDetector {
  private readonly o: Required<HeadShakeOptions>
  private readonly axes = [new AxisTrack(), new AxisTrack(), new AxisTrack()]
  private lastFire = -Infinity
  private count = 0

  constructor(opts: HeadShakeOptions = {}) {
    this.o = { ...DEFAULTS, ...opts }
  }

  /** Feed one sample; true exactly when a head shake has just been completed. */
  push(s: ImuSample): boolean {
    const v = [s.x, s.y, s.z]
    this.count++
    for (let i = 0; i < 3; i++) this.axes[i].push(s.t, v[i], this.o.windowMs, this.o.relSwing)
    if (this.count < this.o.warmupSamples || s.t - this.lastFire < this.o.cooldownMs) return false
    const paths = this.axes.map((a) => a.pathLength)
    for (let i = 0; i < 3; i++) {
      const ex = this.axes[i].extrema
      if (ex.length < this.o.minExtrema) continue
      const tail = ex.slice(-this.o.minExtrema)
      let ok = true
      for (let k = 1; k < tail.length; k++) {
        const gap = tail[k].t - tail[k - 1].t
        if (gap < this.o.minHalfMs || gap > this.o.maxHalfMs) { ok = false; break }
      }
      if (!ok) continue
      const others = paths.filter((_, j) => j !== i)
      if (paths[i] < this.o.dominance * Math.max(...others, 1e-12)) continue
      this.lastFire = s.t
      this.axes.forEach((a) => a.reset())
      return true
    }
    return false
  }

  reset(): void {
    this.axes.forEach((a) => a.reset())
    this.lastFire = -Infinity
  }
}
