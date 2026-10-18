import type { HudFrame } from './types'

/** Runtime guard: transport JSON is untrusted. Malformed frames are dropped, never rendered. */
export function isHudFrame(x: unknown): x is HudFrame {
  if (!x || typeof x !== 'object') return false
  const f = x as Record<string, unknown>
  if (f.type !== 'hud') return false
  if (typeof f.seq !== 'number' || !Number.isFinite(f.seq) || f.seq < 0) return false
  if (typeof f.mode !== 'string') return false
  if (f.mode !== 'quiet') {
    const cue = f.cue as Record<string, unknown> | null | undefined
    if (!cue || typeof cue.line1 !== 'string') return false
  }
  return true
}

/**
 * De-duplication: a frame is accepted only if its seq is strictly greater than the last accepted
 * one (never backwards, never the same seq twice). `reset()` runs on every (re)connection because
 * the server answers the hello with the *current* frame and may have restarted (seq restarts).
 */
export class SeqGate {
  private last = -1
  get lastSeq(): number {
    return this.last
  }
  accept(seq: number): boolean {
    if (seq <= this.last) return false
    this.last = seq
    return true
  }
  reset(): void {
    this.last = -1
  }
}
