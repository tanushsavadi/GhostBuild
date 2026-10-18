import type { ConnStatus, G2Hello, G2Input } from './types'
import { log, warn } from './types'

/** Minimal WebSocket surface (browser WebSocket satisfies it; tests inject a fake). */
export interface WsLike {
  readyState: number
  send(data: string): void
  close(): void
  onopen: ((ev?: unknown) => void) | null
  onmessage: ((ev: { data: unknown }) => void) | null
  onclose: ((ev?: unknown) => void) | null
  onerror: ((ev?: unknown) => void) | null
}

export interface ConnOptions {
  /** e.g. http://192.168.1.20:8787 (read on every use so a runtime change takes effect on reconnect). */
  backend: () => string
  clientId: () => string
  sessionId: () => string | null
  surface: () => 'g2' | 'simulator'
  /** The last frame seq accepted (for GET /hud?after=). */
  afterSeq: () => number
  /** Every parsed inbound JSON object (HudFrame or anything else; caller routes). */
  onMessage: (msg: unknown) => void
  /** true once the server has answered us (first inbound message / successful poll); false when lost. */
  onHealth: (healthy: boolean) => void
  onStatus?: (s: ConnStatus) => void
  makeWs?: (url: string) => WsLike
  fetchFn?: typeof fetch
  wsFallbackMs?: number // default 4000: WS not open by then -> start polling
  pollMs?: number // default 300
  backoffMs?: number[] // default 500,1000,2000,4000,5000
  rehelloMs?: number // default 3000: socket open but silent -> hello again
}

export function wsUrl(backend: string): string {
  return `${backend.replace(/^http/i, 'ws').replace(/\/+$/, '')}/ws?role=g2`
}

/**
 * Transport: WebSocket first; if it cannot open within ~4 s, poll GET /hud?after=seq every 300 ms and use
 * POST /hello + POST /input. The WS keeps retrying with backoff while polling, and wins when it opens.
 * The first message on every (re)connect is a G2Hello; the server answers with the current frame.
 */
export class ConnectionManager {
  private ws: WsLike | null = null
  private wsOpen = false
  private attempt = 0
  private stopped = true
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private fallbackTimer: ReturnType<typeof setTimeout> | null = null
  private pollTimer: ReturnType<typeof setTimeout> | null = null
  private rehelloTimer: ReturnType<typeof setTimeout> | null = null
  private polling = false
  private pollEpoch = 0
  private pollHelloSent = false
  private pollFailures = 0
  private healthy = false
  private _status: ConnStatus = 'connecting'

  constructor(private readonly o: ConnOptions) {}

  get status(): ConnStatus {
    return this._status
  }

  start(): void {
    if (!this.stopped) return
    this.stopped = false
    this.connectWs()
    this.armFallback()
  }

  stop(): void {
    this.stopped = true
    this.clearTimers()
    this.stopPolling()
    const w = this.ws
    this.ws = null
    this.wsOpen = false
    if (w) {
      w.onopen = w.onmessage = w.onclose = w.onerror = null
      try { w.close() } catch { /* ignore */ }
    }
    this.setHealth(false)
  }

  /** Foreground restore or manual retry: drop the current transport and reconnect immediately. */
  reconnectNow(): void {
    if (this.stopped) return this.start()
    this.attempt = 0
    this.stopPolling()
    this.setHealth(false)
    this.dropWs()
    this.connectWs()
    if (this.polling) this.pollHelloSent = false
    this.armFallback()
  }

  /** Send a gesture. Returns false (and drops it) when there is no live transport: a stale recheck is meaningless later. */
  sendInput(input: G2Input): boolean {
    if (this.wsOpen && this.ws) {
      this.ws.send(JSON.stringify(input))
      return true
    }
    if (this.polling && this._status === 'poll') {
      void this.post('/input', input, true)
      return true
    }
    warn(`input ${input.gesture} dropped: no connection`)
    return false
  }

  sendHello(): void {
    const hello: G2Hello = {
      type: 'g2_hello',
      v: 2,
      client_id: this.o.clientId(),
      session_id: this.o.sessionId(),
      surface: this.o.surface(),
    }
    if (this.wsOpen && this.ws) this.ws.send(JSON.stringify(hello))
    else if (this.polling) void this.post('/hello', hello, true)
  }

  // --------------------------------------------------------------------- WebSocket
  private connectWs(): void {
    if (this.stopped) return
    this.setStatus(this.polling ? this._status : 'connecting')
    let ws: WsLike
    try {
      ws = (this.o.makeWs ?? ((u) => new WebSocket(u) as unknown as WsLike))(wsUrl(this.o.backend()))
    } catch (e) {
      warn('WebSocket construct failed', e)
      this.scheduleReconnect()
      return
    }
    this.ws = ws
    ws.onopen = () => {
      if (this.ws !== ws) return
      this.wsOpen = true
      this.attempt = 0
      this.clear('fallbackTimer')
      this.stopPolling()
      this.setHealth(false) // the new socket must answer before it can restore the old session
      this.setStatus('ws')
      log('ws open')
      this.sendHello()
      this.armRehello()
    }
    ws.onmessage = (ev) => {
      if (this.ws !== ws) return
      this.clear('rehelloTimer')
      const msg = parseJson(ev.data)
      if (msg === undefined) return
      this.setHealth(true)
      this.o.onMessage(msg)
    }
    const lost = () => {
      if (this.ws !== ws) return
      this.ws = null
      this.wsOpen = false
      ws.onopen = ws.onmessage = ws.onclose = ws.onerror = null
      this.clear('rehelloTimer')
      log('ws closed')
      if (!this.polling) {
        this.setHealth(false)
        this.setStatus('down')
      }
      this.armFallback()
      this.scheduleReconnect()
    }
    ws.onclose = lost
    ws.onerror = lost
  }

  private dropWs(): void {
    const w = this.ws
    this.ws = null
    this.wsOpen = false
    this.clear('reconnectTimer')
    this.clear('rehelloTimer')
    if (w) {
      w.onopen = w.onmessage = w.onclose = w.onerror = null
      try { w.close() } catch { /* ignore */ }
    }
  }

  private scheduleReconnect(): void {
    if (this.stopped || this.reconnectTimer) return
    const steps = this.o.backoffMs ?? [500, 1000, 2000, 4000, 5000]
    const delay = steps[Math.min(this.attempt, steps.length - 1)]
    this.attempt++
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      this.connectWs()
    }, delay)
  }

  private armRehello(): void {
    this.clear('rehelloTimer')
    this.rehelloTimer = setTimeout(() => {
      if (this.wsOpen && !this.healthy) {
        log('ws open but silent; hello again')
        this.sendHello()
        this.armRehello()
      }
    }, this.o.rehelloMs ?? 3000)
  }

  // --------------------------------------------------------------------- polling fallback
  private armFallback(): void {
    if (this.fallbackTimer || this.polling || this.wsOpen || this.stopped) return
    this.fallbackTimer = setTimeout(() => {
      this.fallbackTimer = null
      if (!this.wsOpen && !this.stopped) this.startPolling()
    }, this.o.wsFallbackMs ?? 4000)
  }

  private startPolling(): void {
    if (this.polling) return
    log('ws unavailable; polling GET /hud')
    this.polling = true
    this.pollHelloSent = false
    this.pollFailures = 0
    this.setStatus('down')
    void this.pollLoop()
  }

  private stopPolling(): void {
    this.pollEpoch++ // invalidate every outstanding HTTP response from the previous transport
    this.polling = false
    this.clear('pollTimer')
  }

  private async pollLoop(): Promise<void> {
    if (!this.polling || this.stopped) return
    const epoch = this.pollEpoch
    const current = () => !this.stopped && this.polling && epoch === this.pollEpoch
    try {
      if (!this.pollHelloSent) {
        const ok = await this.post('/hello', this.helloBody(), true)
        if (!current()) return
        if (!ok) throw new Error('hello failed')
        this.pollHelloSent = true
      }
      const after = this.o.afterSeq()
      const res = await this.timedFetch(`${this.o.backend()}/hud?after=${after}`, { method: 'GET', cache: 'no-store' })
      if (!current()) return
      if (!res.ok) throw new Error(`poll ${res.status}`)
      this.pollFailures = 0
      this.setStatus('poll')
      this.setHealth(true)
      if (res.status !== 204) {
        const text = await res.text()
        if (!current()) return
        const body = text ? parseJson(text) : undefined
        for (const m of extractFrames(body)) this.o.onMessage(m)
      }
    } catch (e) {
      if (!current()) return
      this.pollFailures++
      if (this.pollFailures === 1) warn('poll failed', (e as Error).message)
      this.pollHelloSent = false // server may have restarted: say hello again on recovery
      this.setHealth(false)
      this.setStatus('down')
    }
    if (current()) {
      this.pollTimer = setTimeout(() => void this.pollLoop(), this.o.pollMs ?? 300)
    }
  }

  private helloBody(): G2Hello {
    return {
      type: 'g2_hello',
      v: 2,
      client_id: this.o.clientId(),
      session_id: this.o.sessionId(),
      surface: this.o.surface(),
    }
  }

  private async timedFetch(url: string, init: RequestInit): Promise<Response> {
    const f = this.o.fetchFn ?? ((...a: Parameters<typeof fetch>) => globalThis.fetch(...a))
    const ctl = typeof AbortController !== 'undefined' ? new AbortController() : null
    const t = ctl ? setTimeout(() => ctl.abort(), 2000) : null
    try {
      return await f(url, { ...init, signal: ctl?.signal })
    } finally {
      if (t) clearTimeout(t)
    }
  }

  private async post(path: string, body: unknown, deliverReply = false): Promise<boolean> {
    const epoch = this.pollEpoch
    const current = () => !this.stopped && epoch === this.pollEpoch
    try {
      const res = await this.timedFetch(`${this.o.backend()}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!current() || !res.ok) return false
      if (deliverReply && res.status !== 204) {
        const text = await res.text()
        if (!current()) return false
        const parsed = text ? parseJson(text) : undefined
        // Reset the sequence gate BEFORE the hello frame, including a restarted server at seq=1.
        this.setHealth(true)
        for (const m of extractFrames(parsed)) this.o.onMessage(m)
      }
      return true
    } catch (e) {
      warn(`POST ${path} failed`, (e as Error).message)
      return false
    }
  }

  // --------------------------------------------------------------------- state
  private setHealth(h: boolean): void {
    if (this.healthy === h) return
    this.healthy = h
    this.o.onHealth(h)
  }

  private setStatus(s: ConnStatus): void {
    if (this._status === s) return
    this._status = s
    this.o.onStatus?.(s)
  }

  private clear(k: 'reconnectTimer' | 'fallbackTimer' | 'pollTimer' | 'rehelloTimer'): void {
    const t = this[k]
    if (t) clearTimeout(t)
    this[k] = null
  }

  private clearTimers(): void {
    for (const k of ['reconnectTimer', 'fallbackTimer', 'pollTimer', 'rehelloTimer'] as const) this.clear(k)
  }
}

export function parseJson(data: unknown): unknown {
  if (typeof data !== 'string') return undefined
  try {
    return JSON.parse(data)
  } catch {
    return undefined
  }
}

/** Poll/hello replies may be one frame, an array of frames, {frame}, {frames}, or empty. */
export function extractFrames(body: unknown): unknown[] {
  if (body == null) return []
  if (Array.isArray(body)) return body
  if (typeof body === 'object') {
    const b = body as Record<string, unknown>
    if (Array.isArray(b.frames)) return b.frames
    if (b.frame && typeof b.frame === 'object') return [b.frame]
    if (Object.keys(b).length === 0) return []
  }
  return [body]
}
