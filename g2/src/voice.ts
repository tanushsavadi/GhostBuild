import { AudioInputSource } from '@evenrealities/even_hub_sdk'
import type { KeyValue } from './session'
import { log, warn } from './types'

/**
 * Hold-to-ask capture (optional lane; build with VITE_FLAG_VOICE=1, otherwise this module is inert and the manifest has NO
 * microphone permission).
 *
 * Contract with core (core/ghostbuild_core/voice.py):
 *   LONG_PRESS (hold_start)  -> [consent check] -> G2Input hold_start -> open WS /ws/voice, send {"type":"start","consent":true}
 *                               -> bridge.audioControl(true, Glasses) -> stream audioEvent.audioPcm as binary (~100 ms batches)
 *   LONG_PRESS_RELEASE / 10 s cap -> audioControl(false) -> {"type":"end"} -> G2Input hold_end
 *   any failure (audioControl false/throws, no audio frame within 1.5 s, socket lost, foreground exit, disconnect)
 *                            -> audioControl(false) -> {"type":"abort"} -> G2Input hold_end  (core then shows the fallback frame)
 * Consent: voice is only used after a deliberate hold on core's `HOLD TO TALK / AUDIO TO ELEVENLABS` screen. The first hold sends
 * {"start","consent":false} (no mic, no hold_start); core answers consent_required and shows that screen; a hold within
 * CONSENT_WINDOW_MS stores `gb.voice_consent.elevenlabs.v1=1` and then records. PCM format (docs device-apis): 16 kHz, s16le, mono.
 * The mic is opened ONLY inside a deliberate long press and every error path closes it.
 */
// Provider-specific version: consent to the retired provider must not authorize ElevenLabs.
export const CONSENT_KEY = 'gb.voice_consent.elevenlabs.v1'
export const FIRST_AUDIO_MS = 1500
export const CAP_MS = 10_000
export const CHUNK_BYTES = 3200 // 100 ms of 16 kHz s16le mono
export const CONSENT_WINDOW_MS = 8000

export interface VoiceCapture {
  readonly enabled: boolean
  start(): void
  stop(): void
  onAudio(pcm: unknown): void
  abort(reason: string): void | Promise<void>
  dispose(): void
}

export interface AudioBridge {
  audioControl(isOpen: boolean, source?: AudioInputSource): Promise<boolean>
}

export interface VoiceWs {
  readyState: number
  binaryType?: string
  send(data: string | Uint8Array): void
  close(): void
  onopen: ((ev?: unknown) => void) | null
  onmessage: ((ev: { data: unknown }) => void) | null
  onclose: ((ev?: unknown) => void) | null
  onerror: ((ev?: unknown) => void) | null
}

export interface VoiceOptions {
  bridge: AudioBridge
  kv: KeyValue
  backend: () => string
  sessionId: () => string | null
  /** Sends G2Input hold_start / hold_end to core (the controller does NOT send holds while voice is active). */
  sendHold: (g: 'hold_start' | 'hold_end') => void
  makeWs?: (url: string) => VoiceWs
  now?: () => number
}

export function voiceWsUrl(backend: string, sessionId: string | null): string {
  const base = backend.replace(/^http/i, 'ws').replace(/\/+$/, '')
  return `${base}/ws/voice?session_id=${encodeURIComponent(sessionId ?? '')}`
}

const inert: VoiceCapture = { enabled: false, start() {}, stop() {}, onAudio() {}, abort() {}, dispose() {} }

export function createVoice(enabled: boolean, opts?: VoiceOptions): VoiceCapture {
  return enabled && opts ? new Voice(opts) : inert
}

type Phase = 'idle' | 'starting' | 'recording' | 'closing'

function toBytes(pcm: unknown): Uint8Array | null {
  if (pcm instanceof Uint8Array) return pcm
  if (Array.isArray(pcm) && pcm.every((n) => typeof n === 'number')) return Uint8Array.from(pcm as number[])
  return null
}

export class Voice implements VoiceCapture {
  readonly enabled = true
  private phase: Phase = 'idle'
  private gen = 0
  private released = false
  private holdSent = false
  private micMaybeOpen = false
  private bytesSent = 0
  private buf = new Uint8Array(0)
  private ws: VoiceWs | null = null
  private wsOpen = false
  private pending: Array<string | Uint8Array> = []
  private consent: boolean | null = null
  private consentShownAt = -Infinity
  private firstAudioTimer: ReturnType<typeof setTimeout> | null = null
  private capTimer: ReturnType<typeof setTimeout> | null = null
  private wsCloseTimer: ReturnType<typeof setTimeout> | null = null
  private readonly now: () => number

  constructor(private readonly o: VoiceOptions) {
    this.now = o.now ?? (() => Date.now())
  }

  /** True while the microphone may be open (for tests/diagnostics). */
  get micOpen(): boolean {
    return this.micMaybeOpen
  }
  get busy(): boolean {
    return this.phase !== 'idle'
  }

  // ------------------------------------------------------------------ gestures
  start(): void {
    if (this.phase !== 'idle') return
    void this.begin()
  }

  stop(): void {
    if (this.phase === 'starting') this.released = true
    else if (this.phase === 'recording') void this.finish()
  }

  private async begin(): Promise<void> {
    this.phase = 'starting'
    const gen = ++this.gen
    this.released = false
    this.bytesSent = 0
    this.buf = new Uint8Array(0)
    if (this.consent === null) {
      let v: string | null = null
      try { v = await this.o.kv.get(CONSENT_KEY) } catch { v = null }
      this.consent = v === '1'
    }
    if (gen !== this.gen) return
    if (!this.consent && this.now() - this.consentShownAt <= CONSENT_WINDOW_MS) {
      this.consent = true // deliberate hold on the consent screen
      try { await this.o.kv.set(CONSENT_KEY, '1') } catch { /* consent still holds for this run */ }
      log('voice: consent stored')
    }
    if (gen !== this.gen) return
    if (!this.consent) {
      await this.showConsent(gen)
      if (gen === this.gen) this.phase = 'idle'
      return
    }
    this.o.sendHold('hold_start')
    this.holdSent = true
    this.openWs()
    if (gen !== this.gen) return // socket construction may synchronously abort; never open the mic after it
    this.sendCtl({ type: 'start', consent: true })
    let ok = false
    this.micMaybeOpen = true // assume open until audioControl(false) confirms: it may have thrown after opening
    try { ok = await this.o.bridge.audioControl(true, AudioInputSource.Glasses) } catch (e) { warn('voice: audioControl(true) threw', e); ok = false }
    if (gen !== this.gen) { await this.closeMic(); return } // aborted while the mic was opening
    if (!ok) { await this.abort('mic_open_failed'); return }
    this.phase = 'recording'
    this.firstAudioTimer = setTimeout(() => void this.abort('no_audio'), FIRST_AUDIO_MS)
    this.capTimer = setTimeout(() => void this.finish(), CAP_MS)
    if (this.released) void this.finish()
  }

  /** First hold (no consent yet): core shows HOLD TO TALK / AUDIO TO ELEVENLABS. No mic, no hold_start. */
  private async showConsent(gen: number): Promise<void> {
    const ws = this.makeWs()
    if (!ws) return
    await new Promise<void>((resolve) => {
      const done = () => { clearTimeout(t); resolve() }
      const t = setTimeout(done, 3000)
      ws.onopen = () => { try { ws.send(JSON.stringify({ type: 'start', consent: false })) } catch { done() } }
      ws.onmessage = (ev) => {
        if (parse(ev.data)?.type === 'consent_required' && gen === this.gen) this.consentShownAt = this.now()
        done()
      }
      ws.onclose = ws.onerror = () => done()
    })
    try { ws.close() } catch { /* ignore */ }
  }

  // ------------------------------------------------------------------ audio
  onAudio(pcm: unknown): void {
    if (this.phase !== 'recording' && this.phase !== 'closing') return // the mic should be closed: drop anything late
    const b = toBytes(pcm)
    if (!b || b.length === 0) return
    if (this.firstAudioTimer) { clearTimeout(this.firstAudioTimer); this.firstAudioTimer = null }
    const merged = new Uint8Array(this.buf.length + b.length)
    merged.set(this.buf, 0)
    merged.set(b, this.buf.length)
    this.buf = merged
    while (this.buf.length >= CHUNK_BYTES) {
      this.sendBin(this.buf.slice(0, CHUNK_BYTES))
      this.buf = this.buf.slice(CHUNK_BYTES)
    }
  }

  private flushTail(): void {
    if (this.buf.length > 0) { this.sendBin(this.buf); this.buf = new Uint8Array(0) }
  }

  // ------------------------------------------------------------------ end paths
  private async finish(): Promise<void> {
    if (this.phase !== 'recording') return
    this.phase = 'closing'
    const gen = this.gen
    this.clearTimers()
    await this.closeMic()
    if (gen !== this.gen) return // a background/disconnect abort won while native mic close was pending
    this.flushTail()
    if (this.bytesSent === 0) { // nothing was captured: do not pretend
      await this.abort('no_audio')
      return
    }
    this.sendCtl({ type: 'end' })
    this.sendHoldEnd()
    this.phase = 'idle'
    this.wsCloseTimer = setTimeout(() => this.closeWs(), 12_000) // the ack ('done') closes it sooner
  }

  /** Idempotent. Always leaves the mic closed, tells core, returns to idle. */
  async abort(reason: string): Promise<void> {
    if (this.phase === 'idle' && !this.holdSent && !this.micMaybeOpen && !this.ws) return
    warn(`voice: abort (${reason})`)
    this.gen++
    this.phase = 'closing'
    this.clearTimers()
    await this.closeMic()
    this.sendCtl({ type: 'abort', reason })
    this.sendHoldEnd()
    this.closeWs()
    this.buf = new Uint8Array(0)
    this.phase = 'idle'
  }

  dispose(): void {
    void this.abort('dispose')
    this.closeWs()
  }

  private sendHoldEnd(): void {
    if (this.holdSent) { this.holdSent = false; this.o.sendHold('hold_end') }
  }

  private async closeMic(): Promise<void> {
    try { await this.o.bridge.audioControl(false) } catch (e) { warn('voice: audioControl(false) threw', e) }
    this.micMaybeOpen = false
  }

  private clearTimers(): void {
    for (const k of ['firstAudioTimer', 'capTimer', 'wsCloseTimer'] as const) {
      const t = this[k]
      if (t) clearTimeout(t)
      this[k] = null
    }
  }

  // ------------------------------------------------------------------ socket
  private makeWs(): VoiceWs | null {
    try {
      const url = voiceWsUrl(this.o.backend(), this.o.sessionId())
      const ws = (this.o.makeWs ?? ((u) => new WebSocket(u) as unknown as VoiceWs))(url)
      ws.binaryType = 'arraybuffer'
      return ws
    } catch (e) {
      warn('voice: websocket construction failed', e)
      return null
    }
  }

  private openWs(): void {
    this.closeWs()
    const ws = this.makeWs()
    this.ws = ws
    this.wsOpen = false
    this.pending = []
    if (!ws) { void this.abort('ws_unavailable'); return }
    ws.onopen = () => {
      this.wsOpen = true
      for (const m of this.pending) ws.send(m)
      this.pending = []
    }
    ws.onmessage = (ev) => {
      const t = parse(ev.data)?.type
      if (t === 'unavailable' || t === 'consent_required') void this.abort(`server_${t}`)
      else if (t === 'done') this.closeWs()
    }
    ws.onclose = ws.onerror = () => {
      if (this.ws === ws && (this.phase === 'recording' || this.phase === 'starting')) void this.abort('ws_closed')
    }
  }

  private closeWs(): void {
    const w = this.ws
    this.ws = null
    this.wsOpen = false
    this.pending = []
    if (this.wsCloseTimer) { clearTimeout(this.wsCloseTimer); this.wsCloseTimer = null }
    if (w) {
      w.onopen = w.onmessage = w.onclose = w.onerror = null
      try { w.close() } catch { /* ignore */ }
    }
  }

  private sendRaw(m: string | Uint8Array): void {
    if (!this.ws) return
    if (this.wsOpen) this.ws.send(m)
    else if (this.pending.length < 200) this.pending.push(m)
  }
  private sendCtl(o: Record<string, unknown>): void {
    this.sendRaw(JSON.stringify(o))
  }
  private sendBin(b: Uint8Array): void {
    this.bytesSent += b.length
    this.sendRaw(b)
  }
}

function parse(data: unknown): { type?: string } | null {
  if (typeof data !== 'string') return null
  try { return JSON.parse(data) as { type?: string } } catch { return null }
}
