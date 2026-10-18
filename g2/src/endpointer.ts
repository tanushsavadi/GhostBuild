// Silence endpointing for a hands-free listen: decide, from the PCM itself, when the person has finished speaking.
// Pure and rate-free: the caller passes the clock. PCM is 16 kHz signed 16-bit little-endian mono (the SDK's format), so 32 bytes = 1 ms.

export type EndDecision = 'continue' | 'end' | 'no_speech'

export interface EndpointerOptions {
  silenceMs?: number      // silence after speech that ends the utterance
  noSpeechMs?: number     // give up when nobody starts talking within this long
  maxMs?: number          // hard cap
  minSpeechMs?: number    // ignore blips shorter than this
  floorFactor?: number    // speech must exceed the measured noise floor by this factor
  minRms?: number         // and this absolute level (16-bit scale)
  calibrateMs?: number    // the first moments set the noise floor
}

const D: Required<EndpointerOptions> = { silenceMs: 1100, noSpeechMs: 4500, maxMs: 9000, minSpeechMs: 220, floorFactor: 3, minRms: 450, calibrateMs: 300 }

export function rms16(pcm: Uint8Array): number {
  const n = pcm.length >> 1
  if (n === 0) return 0
  const dv = new DataView(pcm.buffer, pcm.byteOffset, n * 2)
  let sum = 0
  for (let i = 0; i < n; i++) { const s = dv.getInt16(i * 2, true); sum += s * s }
  return Math.sqrt(sum / n)
}

export class Endpointer {
  private readonly o: Required<EndpointerOptions>
  private started: number | null = null
  private floor = 0
  private floorMs = 0
  private speechMs = 0
  private lastSpeechAt: number | null = null

  constructor(opts: EndpointerOptions = {}) {
    this.o = { ...D, ...opts }
  }

  push(pcm: Uint8Array, nowMs: number): EndDecision {
    if (this.started === null) this.started = nowMs
    const chunkMs = pcm.length / 32
    const level = rms16(pcm)
    const elapsed = nowMs - this.started
    if (elapsed <= this.o.calibrateMs && this.speechMs === 0) {
      this.floor = (this.floor * this.floorMs + level * chunkMs) / Math.max(1, this.floorMs + chunkMs)
      this.floorMs += chunkMs
    }
    const threshold = Math.max(this.o.minRms, this.floor * this.o.floorFactor)
    if (elapsed > this.o.calibrateMs && level > threshold) {
      this.speechMs += chunkMs
      this.lastSpeechAt = nowMs
    }
    const spoke = this.speechMs >= this.o.minSpeechMs
    if (elapsed >= this.o.maxMs) return spoke ? 'end' : 'no_speech'
    if (!spoke && elapsed >= this.o.noSpeechMs) return 'no_speech'
    if (spoke && this.lastSpeechAt !== null && nowMs - this.lastSpeechAt >= this.o.silenceMs) return 'end'
    return 'continue'
  }
}
