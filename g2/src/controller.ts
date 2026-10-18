import type { G2Input, View } from './types'
import { log, warn } from './types'
import { isHudFrame, SeqGate } from './gate'
import { blankView, frameToView, offlineView, sourceTag, DEFAULT_VIEW_OPTIONS, type ViewOptions } from './view'
import type { GestureAction } from './gestures'

export interface ControllerDeps {
  render: (v: View) => void
  /** Sends a gesture to the backend; returns false if dropped (no connection). */
  sendInput: (i: G2Input) => boolean
  /** Ask the transport for the current frame again (re-hello). */
  rehello: () => void
  /** Local exit: shutDownPageContainer(1). Double press on the home screen, or when the backend is unreachable. */
  exit: () => void
  surface: () => 'g2' | 'simulator'
  /** Hold-to-ask capture (voice.ts). Only present when built with VITE_FLAG_VOICE=1; it then OWNS hold_start/hold_end
   *  (sends them to core itself, after the consent gate), so the controller does not send holds directly. */
  voice?: { start: () => void; stop: () => void }
  viewOptions?: ViewOptions
  /** ms disconnected before the honest OFFLINE view replaces whatever is on screen. */
  offlineAfterMs?: number
  onFrameRendered?: (seq: number) => void
}

const joinSource = (s: Parameters<typeof sourceTag>[0]): string => sourceTag(s) || ' '

/**
 * Glue between transport, rendering and gestures. No SDK calls here, so it is fully unit-testable.
 * Invariants:
 *  - a frame is rendered only if seq is strictly newer than the last accepted one (gate reset per connection)
 *  - an identical view is never re-rendered
 *  - ttl_ms clears locally to blank as a fallback
 *  - unhealthy transport for > offlineAfterMs shows GHOSTBUILD OFFLINE / RECONNECTING; an old success never lingers
 */
export class Controller {
  private gate = new SeqGate()
  private seqSeen = 0
  private lastKey: string | null = null
  private ttlTimer: ReturnType<typeof setTimeout> | null = null
  private offlineTimer: ReturnType<typeof setTimeout> | null = null
  private rehelloTimer: ReturnType<typeof setTimeout> | null = null
  private expired: { seq: number; key: string } | null = null
  private offlineShown = false
  private healthy = false
  /** Double press: system exit on a root screen (core tags it cue_id "home", as Even QA requires); Home everywhere else. */
  private atRoot = false
  private homeSentAt: number | null = null
  private opts: ViewOptions

  constructor(private readonly d: ControllerDeps) {
    this.opts = d.viewOptions ?? DEFAULT_VIEW_OPTIONS
  }

  get lastSeq(): number {
    return this.gate.lastSeq
  }
  get isOfflineShown(): boolean {
    return this.offlineShown
  }

  /** Start in the "not yet connected" state so the 3 s offline timer runs from boot. */
  boot(): void {
    this.onHealth(false)
  }

  // ------------------------------------------------------------------- transport signals
  onHealth(ok: boolean): void {
    this.healthy = ok
    if (ok) {
      this.clear('offlineTimer')
      // New connection: the server replies with its current frame, which may have a lower seq if it restarted.
      this.gate.reset()
      this.armRehello()
      return
    }
    this.clear('rehelloTimer')
    if (!this.offlineTimer && !this.offlineShown) {
      this.offlineTimer = setTimeout(() => {
        this.offlineTimer = null
        this.showOffline()
      }, this.d.offlineAfterMs ?? 3000)
    }
  }

  /** While the offline view is showing and the server is "healthy" but has sent no frame, ask again. */
  private armRehello(): void {
    this.clear('rehelloTimer')
    if (!this.offlineShown) return
    this.rehelloTimer = setTimeout(() => {
      this.rehelloTimer = null
      if (this.offlineShown && this.healthy) {
        this.d.rehello()
        this.armRehello()
      }
    }, 2000)
  }

  private showOffline(): void {
    this.clear('ttlTimer')
    this.offlineShown = true
    const v = offlineView(this.opts)
    this.lastKey = v.key
    this.d.render(v)
    log('offline view shown')
  }

  // ------------------------------------------------------------------- frames
  onMessage(msg: unknown): void {
    if (!isHudFrame(msg)) {
      const t = (msg as { type?: unknown } | null)?.type
      if (t !== undefined && t !== 'hud') return // non-HUD server chatter is not an error
      warn('dropped malformed frame', msg)
      return
    }
    const frame = msg
    if (!this.gate.accept(frame.seq)) {
      log(`dropped frame seq=${frame.seq} (last=${this.gate.lastSeq})`)
      return
    }
    this.seqSeen = frame.seq
    this.atRoot = frame.cue_id === 'home'
    const view = frameToView(frame, this.opts)

    if (this.expired && this.expired.seq === frame.seq && this.expired.key === view.key) {
      // The backend is reachable, but this transient success already expired locally.
      // Clear OFFLINE without resurrecting the success or leaving re-hello running forever.
      this.clear('rehelloTimer')
      this.clear('offlineTimer')
      this.offlineShown = false
      const blank = blankView(joinSource(frame.source))
      if (this.lastKey !== blank.key) {
        this.lastKey = blank.key
        this.d.render(blank)
      }
      this.d.onFrameRendered?.(frame.seq)
      return
    }
    if (view.key === this.lastKey) {
      this.d.onFrameRendered?.(frame.seq)
      return // identical content: never re-render
    }

    this.clear('ttlTimer')
    this.clear('rehelloTimer')
    this.lastKey = view.key
    this.offlineShown = false
    this.d.render(view)
    this.d.onFrameRendered?.(frame.seq)

    if (frame.ttl_ms != null && frame.ttl_ms > 0) {
      const seq = frame.seq
      const key = view.key
      this.ttlTimer = setTimeout(() => {
        this.ttlTimer = null
        this.expired = { seq, key }
        const blank = blankView(joinSource(frame.source))
        this.lastKey = blank.key
        this.d.render(blank)
      }, frame.ttl_ms)
    }
  }

  // ------------------------------------------------------------------- gestures
  onAction(a: GestureAction): void {
    if (a.kind === 'exit') {
      // Double press: system exit at root, offline, or when the last Home changed nothing; otherwise Home from any step.
      const last = this.gate.lastSeq
      if (!this.healthy || this.atRoot || last === this.homeSentAt) {
        this.d.exit()
        return
      }
      this.homeSentAt = last
      if (!this.d.sendInput({ type: 'g2_input', v: 2, gesture: 'home', seq_seen: this.seqSeen, surface: this.d.surface() })) this.d.exit()
      return
    }
    if (a.kind !== 'send') return
    if (this.d.voice && (a.gesture === 'hold_start' || a.gesture === 'hold_end')) {
      if (a.gesture === 'hold_start') this.d.voice.start()
      else this.d.voice.stop()
      return
    }
    const input: G2Input = {
      type: 'g2_input',
      v: 2,
      gesture: a.gesture,
      seq_seen: this.seqSeen,
      surface: this.d.surface(),
    }
    this.d.sendInput(input)
  }

  dispose(): void {
    for (const k of ['ttlTimer', 'offlineTimer', 'rehelloTimer'] as const) this.clear(k)
  }

  private clear(k: 'ttlTimer' | 'offlineTimer' | 'rehelloTimer'): void {
    const t = this[k]
    if (t) clearTimeout(t)
    this[k] = null
  }
}
