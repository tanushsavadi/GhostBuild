import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AudioInputSource } from '@evenrealities/even_hub_sdk'
import { CAP_MS, CHUNK_BYTES, CONSENT_KEY, FIRST_AUDIO_MS, Voice, createVoice, voiceWsUrl, type VoiceWs } from './voice'

class FakeWs implements VoiceWs {
  static all: FakeWs[] = []
  readyState = 0
  binaryType = ''
  sent: Array<string | Uint8Array> = []
  closed = false
  onopen: VoiceWs['onopen'] = null
  onmessage: VoiceWs['onmessage'] = null
  onclose: VoiceWs['onclose'] = null
  onerror: VoiceWs['onerror'] = null
  constructor(public url: string) { FakeWs.all.push(this) }
  send(d: string | Uint8Array) { this.sent.push(d) }
  close() { this.closed = true; this.readyState = 3 }
  open() { this.readyState = 1; this.onopen?.() }
  reply(o: unknown) { this.onmessage?.({ data: JSON.stringify(o) }) }
  drop() { this.readyState = 3; this.onclose?.() }
  ctl() { return this.sent.filter((m): m is string => typeof m === 'string').map((m) => JSON.parse(m)) }
  bin() { return this.sent.filter((m): m is Uint8Array => typeof m !== 'string') }
}

function rig(opts: { consent?: boolean; audio?: 'ok' | 'false' | 'throw' | 'slow'; wsFail?: boolean; preconsent?: boolean } = {}) {
  const log: string[] = []
  const store = new Map<string, string>()
  if (opts.consent !== false) store.set(CONSENT_KEY, '1')
  let release: ((ok: boolean) => void) | null = null
  const bridge = {
    audioControl: vi.fn(async (open: boolean, src?: AudioInputSource) => {
      log.push(`mic:${open ? 'open' : 'close'}${src ? ':' + src : ''}`)
      if (!open) return true
      if (opts.audio === 'throw') throw new Error('boom')
      if (opts.audio === 'false') return false
      if (opts.audio === 'slow') return new Promise<boolean>((r) => { release = r })
      return true
    }),
  }
  const kv = {
    get: async (k: string) => store.get(k) ?? null,
    set: async (k: string, v: string) => { store.set(k, v) },
  }
  const holds: string[] = []
  let t = 0
  const v = new Voice({
    bridge,
    kv,
    backend: () => 'http://core:8787',
    sessionId: () => 's-1',
    sendHold: (g) => { holds.push(g); log.push(g) },
    makeWs: (u) => { if (opts.wsFail) throw new Error('socket blocked'); return new FakeWs(u) },
    now: () => t,
    preconsent: opts.preconsent,
  })
  const ws = () => FakeWs.all.at(-1)!
  const tick = async (ms = 0) => { t += ms; await vi.advanceTimersByTimeAsync(ms) }
  const pcm = (n: number) => new Uint8Array(n).fill(7)
  return { v, bridge, store, holds, log, ws, tick, pcm, release: (ok: boolean) => release?.(ok), setNow: (n: number) => { t = n } }
}

/** Invariant of every test: when we are done, the last mic call is a close and the mic is not considered open. */
function expectMicClosed(r: ReturnType<typeof rig>) {
  const mic = r.log.filter((l) => l.startsWith('mic:'))
  if (mic.length) expect(mic.at(-1)).toBe('mic:close')
  expect(r.v.micOpen).toBe(false)
}

beforeEach(() => { vi.useFakeTimers(); FakeWs.all = [] })
afterEach(() => vi.useRealTimers())

describe('voice.ts hold-to-ask', () => {
  it('builds the ws url from the backend and session', () => {
    expect(voiceWsUrl('http://core:8787/', 's-1')).toBe('ws://core:8787/ws/voice?session_id=s-1')
    expect(voiceWsUrl('https://x.ts.net', null)).toBe('wss://x.ts.net/ws/voice?session_id=')
  })

  it('flag off: createVoice is inert and never touches the bridge', () => {
    const r = rig()
    const v = createVoice(false)
    v.start(); v.stop(); v.onAudio(new Uint8Array(10)); void v.abort('x'); v.dispose()
    expect(v.enabled).toBe(false)
    expect(r.bridge.audioControl).not.toHaveBeenCalled()
  })

  it('mic stays closed and nothing is sent when no long press happens', async () => {
    const r = rig()
    r.v.onAudio(r.pcm(4000))
    await r.tick(5000)
    expect(r.bridge.audioControl).not.toHaveBeenCalled()
    expect(FakeWs.all).toHaveLength(0)
    expect(r.holds).toEqual([])
  })

  it('happy path: hold_start, mic open (Glasses), 100 ms binary batches, release -> mic close, end, hold_end in order', async () => {
    const r = rig()
    r.v.start()
    await r.tick()
    r.ws().open()
    expect(r.log).toEqual(['hold_start', 'mic:open:glasses'])
    expect(r.ws().ctl()).toEqual([{ type: 'start', consent: true }])
    for (let i = 0; i < 5; i++) r.v.onAudio(r.pcm(1600)) // 8000 bytes
    expect(r.ws().bin().map((b) => b.length)).toEqual([CHUNK_BYTES, CHUNK_BYTES])
    r.v.stop()
    await r.tick()
    expect(r.ws().bin().reduce((n, b) => n + b.length, 0)).toBe(8000) // tail flushed
    expect(r.log).toEqual(['hold_start', 'mic:open:glasses', 'mic:close', 'hold_end'])
    expect(r.ws().ctl().map((c) => c.type)).toEqual(['start', 'end'])
    expectMicClosed(r)
    r.ws().reply({ type: 'done' })
    expect(r.ws().closed).toBe(true)
  })

  it('audio arriving after the mic was closed is dropped', async () => {
    const r = rig()
    r.v.start(); await r.tick(); r.ws().open()
    r.v.onAudio(r.pcm(3200))
    r.v.stop(); await r.tick()
    const n = r.ws().bin().length
    r.v.onAudio(r.pcm(3200))
    expect(r.ws().bin().length).toBe(n)
  })

  it('audioControl(true) returns false: mic closed, abort + hold_end sent so core shows the fallback', async () => {
    const r = rig({ audio: 'false' })
    r.v.start(); await r.tick()
    expect(r.log).toEqual(['hold_start', 'mic:open:glasses', 'mic:close', 'hold_end'])
    expectMicClosed(r)
  })

  it('audioControl(true) throws: same clean abort', async () => {
    const r = rig({ audio: 'throw' })
    r.v.start(); await r.tick()
    expect(r.log).toEqual(['hold_start', 'mic:open:glasses', 'mic:close', 'hold_end'])
    expectMicClosed(r)
  })

  it('no audio frame within 1.5 s: abort, mic closed, hold_end', async () => {
    const r = rig()
    r.v.start(); await r.tick(); r.ws().open()
    await r.tick(FIRST_AUDIO_MS - 1)
    expect(r.holds).toEqual(['hold_start'])
    await r.tick(1)
    expect(r.holds).toEqual(['hold_start', 'hold_end'])
    expectMicClosed(r)
  })

  it('release with zero captured audio is an abort, not an empty end', async () => {
    const r = rig()
    r.v.start(); await r.tick(); r.ws().open()
    r.v.stop(); await r.tick()
    expect(r.holds).toEqual(['hold_start', 'hold_end'])
    expectMicClosed(r)
  })

  it('10 s safety cap ends the hold by itself', async () => {
    const r = rig()
    r.v.start(); await r.tick(); r.ws().open()
    r.v.onAudio(r.pcm(3200))
    await r.tick(CAP_MS)
    expect(r.ws().ctl().map((c) => c.type)).toEqual(['start', 'end'])
    expect(r.holds).toEqual(['hold_start', 'hold_end'])
    expectMicClosed(r)
  })

  it('foreground exit while recording closes the mic and tells core', async () => {
    const r = rig()
    r.v.start(); await r.tick(); r.ws().open()
    r.v.onAudio(r.pcm(3200))
    const sock = r.ws()
    await r.v.abort('foreground_exit')
    expect(sock.ctl().at(-1)).toMatchObject({ type: 'abort', reason: 'foreground_exit' })
    expect(r.holds).toEqual(['hold_start', 'hold_end'])
    expectMicClosed(r)
    await r.tick(CAP_MS * 2) // no stray timer fires afterwards
    expect(r.holds).toEqual(['hold_start', 'hold_end'])
  })

  it('dispose / disconnect while recording closes the mic', async () => {
    const r = rig()
    r.v.start(); await r.tick(); r.ws().open()
    r.v.dispose(); await r.tick()
    expectMicClosed(r)
    expect(r.holds).toEqual(['hold_start', 'hold_end'])
  })

  it('socket lost mid-recording aborts cleanly', async () => {
    const r = rig()
    r.v.start(); await r.tick(); r.ws().open()
    r.v.onAudio(r.pcm(3200))
    r.ws().drop(); await r.tick()
    expect(r.holds).toEqual(['hold_start', 'hold_end'])
    expectMicClosed(r)
  })

  it('server says unavailable: stop capturing, close the mic', async () => {
    const r = rig()
    r.v.start(); await r.tick(); r.ws().open()
    r.ws().reply({ type: 'unavailable' }); await r.tick()
    expect(r.holds).toEqual(['hold_start', 'hold_end'])
    expectMicClosed(r)
  })

  it('release while the mic is still opening: nothing captured, clean abort, mic closed', async () => {
    const r = rig({ audio: 'slow' })
    r.v.start(); await r.tick(); r.ws().open()
    r.v.stop()
    r.release(true); await r.tick()
    expect(r.holds).toEqual(['hold_start', 'hold_end'])
    expectMicClosed(r)
  })

  it('a second long press while one is in flight is ignored', async () => {
    const r = rig()
    r.v.start(); r.v.start(); await r.tick()
    expect(r.bridge.audioControl.mock.calls.filter((c) => c[0] === true)).toHaveLength(1)
    expect(FakeWs.all).toHaveLength(1)
  })

  it('same instance can do two full holds', async () => {
    const r = rig()
    for (let i = 0; i < 2; i++) {
      r.v.start(); await r.tick(); r.ws().open()
      r.v.onAudio(r.pcm(3200)); r.v.stop(); await r.tick()
    }
    expect(r.holds).toEqual(['hold_start', 'hold_end', 'hold_start', 'hold_end'])
    expectMicClosed(r)
  })
})

describe('consent gate', () => {
  it('first hold: no mic, no hold_start, asks core to show HOLD TO TALK; a second hold on that screen stores consent and records', async () => {
    const r = rig({ consent: false })
    r.v.start(); await r.tick()
    r.ws().open()
    expect(r.ws().ctl()).toEqual([{ type: 'start', consent: false }])
    r.ws().reply({ type: 'consent_required' }); await r.tick()
    expect(r.bridge.audioControl).not.toHaveBeenCalled()
    expect(r.holds).toEqual([])
    expect(r.store.get(CONSENT_KEY)).toBeUndefined()

    r.setNow(2000)
    r.v.start(); await r.tick()
    expect(r.store.get(CONSENT_KEY)).toBe('1')
    r.ws().open()
    expect(r.ws().ctl()).toEqual([{ type: 'start', consent: true }])
    expect(r.log).toEqual(['hold_start', 'mic:open:glasses'])
    r.v.onAudio(r.pcm(3200)); r.v.stop(); await r.tick()
    expectMicClosed(r)
  })

  it('preconsent (the welcome screen carries the audio notice): the very first hold records, no second hold needed', async () => {
    const r = rig({ consent: false, preconsent: true })
    r.v.start(); await r.tick()
    r.ws().open()
    expect(r.ws().ctl()).toEqual([{ type: 'start', consent: true }])
    expect(r.log).toEqual(['hold_start', 'mic:open:glasses'])
    r.v.onAudio(r.pcm(3200)); r.v.stop(); await r.tick()
    expectMicClosed(r)
  })

  it('a hold long after the consent screen has gone asks again instead of recording', async () => {
    const r = rig({ consent: false })
    r.v.start(); await r.tick(); r.ws().open(); r.ws().reply({ type: 'consent_required' }); await r.tick()
    r.setNow(60_000)
    r.v.start(); await r.tick(); r.ws().open()
    expect(r.ws().ctl()).toEqual([{ type: 'start', consent: false }])
    expect(r.bridge.audioControl).not.toHaveBeenCalled()
  })

  it('without core answering, consent is never assumed', async () => {
    const r = rig({ consent: false })
    r.v.start(); await r.tick(3500)
    r.v.start(); await r.tick(3500)
    expect(r.bridge.audioControl).not.toHaveBeenCalled()
    expect(r.store.get(CONSENT_KEY)).toBeUndefined()
  })
})


describe('voice cancellation regressions', () => {
  it('never opens the microphone after WebSocket construction fails', async () => {
    const r = rig({ wsFail: true })
    r.v.start(); await r.tick()
    expect(r.bridge.audioControl.mock.calls.some((c) => c[0])).toBe(false)
    expectMicClosed(r)
    expect(r.holds).toEqual(['hold_start', 'hold_end'])
  })

  it('backgrounding cancels the response still pending after release', async () => {
    const r = rig()
    r.v.start(); await r.tick(); r.ws().open()
    r.v.onAudio(r.pcm(3200)); r.v.stop(); await r.tick()
    const sock = r.ws()
    await r.v.abort('foreground_exit')
    expect(sock.closed).toBe(true)
    expect(sock.ctl().at(-1)).toEqual({ type: 'abort', reason: 'foreground_exit' })
    expectMicClosed(r)
  })
})
