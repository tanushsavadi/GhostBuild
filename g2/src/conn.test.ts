import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ConnectionManager, extractFrames, wsUrl, type WsLike } from './conn'
import type { G2Input } from './types'

class FakeWs implements WsLike {
  static all: FakeWs[] = []
  readyState = 0
  sent: string[] = []
  onopen: WsLike['onopen'] = null
  onmessage: WsLike['onmessage'] = null
  onclose: WsLike['onclose'] = null
  onerror: WsLike['onerror'] = null
  constructor(public url: string) { FakeWs.all.push(this) }
  send(d: string) { this.sent.push(d) }
  close() { this.readyState = 3 }
  open() { this.readyState = 1; this.onopen?.() }
  msg(o: unknown) { this.onmessage?.({ data: JSON.stringify(o) }) }
  drop() { this.readyState = 3; this.onclose?.() }
}

const input: G2Input = { type: 'g2_input', v: 2, gesture: 'press', seq_seen: 3, surface: 'g2' }

function setup(fetchFn?: typeof fetch) {
  const messages: unknown[] = []
  const health: boolean[] = []
  const cm = new ConnectionManager({
    backend: () => 'http://core:8787',
    clientId: () => 'g2-test',
    sessionId: () => 's-1',
    surface: () => 'g2',
    afterSeq: () => 7,
    onMessage: (m) => messages.push(m),
    onHealth: (h) => health.push(h),
    makeWs: (u) => new FakeWs(u),
    fetchFn,
  })
  return { cm, messages, health }
}

beforeEach(() => { vi.useFakeTimers(); FakeWs.all = [] })
afterEach(() => { vi.useRealTimers() })

describe('ConnectionManager over WebSocket', () => {
  it('url mapping', () => {
    expect(wsUrl('http://h:8787')).toBe('ws://h:8787/ws?role=g2')
    expect(wsUrl('https://x.ts.net/')).toBe('wss://x.ts.net/ws?role=g2')
  })

  it('sends G2Hello first on open, then reports healthy only after the server answers', () => {
    const { cm, messages, health } = setup()
    cm.start()
    const ws = FakeWs.all[0]
    expect(ws.url).toBe('ws://core:8787/ws?role=g2')
    ws.open()
    expect(JSON.parse(ws.sent[0])).toEqual({ type: 'g2_hello', v: 2, client_id: 'g2-test', session_id: 's-1', surface: 'g2' })
    expect(health).toEqual([])
    ws.msg({ type: 'hud', seq: 1 })
    expect(health).toEqual([true])
    expect(messages).toHaveLength(1)
    cm.stop()
  })

  it('sends inputs as G2Input JSON; drops them when disconnected', () => {
    const { cm } = setup()
    cm.start()
    expect(cm.sendInput(input)).toBe(false)
    const ws = FakeWs.all[0]
    ws.open()
    expect(cm.sendInput(input)).toBe(true)
    expect(JSON.parse(ws.sent.at(-1)!)).toEqual(input)
    cm.stop()
  })

  it('reconnects with backoff and says hello again', () => {
    const { cm, health } = setup()
    cm.start()
    const a = FakeWs.all[0]
    a.open(); a.msg({ type: 'hud', seq: 1 })
    a.drop()
    expect(health.at(-1)).toBe(false)
    expect(FakeWs.all).toHaveLength(1)
    vi.advanceTimersByTime(500)
    expect(FakeWs.all).toHaveLength(2)
    FakeWs.all[1].drop() // fails again: next delay 1000
    vi.advanceTimersByTime(999)
    expect(FakeWs.all).toHaveLength(2)
    vi.advanceTimersByTime(1)
    expect(FakeWs.all).toHaveLength(3)
    FakeWs.all[2].open()
    expect(JSON.parse(FakeWs.all[2].sent[0]).type).toBe('g2_hello')
    cm.stop()
  })

  it('open but silent socket re-sends hello', () => {
    const { cm } = setup()
    cm.start()
    const ws = FakeWs.all[0]
    ws.open()
    vi.advanceTimersByTime(3000)
    expect(ws.sent.filter((s) => JSON.parse(s).type === 'g2_hello')).toHaveLength(2)
    cm.stop()
  })

  it('ignores non-JSON frames', () => {
    const { cm, messages } = setup()
    cm.start()
    const ws = FakeWs.all[0]
    ws.open()
    ws.onmessage?.({ data: 'not json' })
    ws.onmessage?.({ data: new ArrayBuffer(2) })
    expect(messages).toEqual([])
    cm.stop()
  })

  it('stop() closes and silences everything', () => {
    const { cm, health } = setup()
    cm.start()
    FakeWs.all[0].open()
    FakeWs.all[0].msg({ type: 'hud', seq: 1 })
    cm.stop()
    vi.advanceTimersByTime(20000)
    expect(FakeWs.all).toHaveLength(1)
    expect(health.at(-1)).toBe(false)
  })
})

describe('polling fallback', () => {
  const okJson = (body: unknown, status = 200) => ({ ok: status < 400, status, text: async () => (body === undefined ? '' : JSON.stringify(body)) })

  it('starts polling after ~4 s without a WebSocket: POST /hello then GET /hud?after= every 300 ms', async () => {
    const calls: string[] = []
    const f = (async (u: string, init?: RequestInit) => {
      calls.push(`${init?.method} ${u.replace('http://core:8787', '')}`)
      if (u.endsWith('/hud?after=7')) return okJson({ type: 'hud', seq: 8 })
      return okJson(undefined, 204)
    }) as unknown as typeof fetch
    const { cm, messages, health } = setup(f)
    cm.start() // WS never opens
    await vi.advanceTimersByTimeAsync(3999)
    expect(calls).toEqual([])
    await vi.advanceTimersByTimeAsync(2)
    expect(calls[0]).toBe('POST /hello')
    expect(calls[1]).toBe('GET /hud?after=7')
    expect(messages).toEqual([{ type: 'hud', seq: 8 }])
    expect(health).toEqual([true])
    expect(cm.status).toBe('poll')
    await vi.advanceTimersByTimeAsync(300)
    expect(calls.filter((c) => c.startsWith('GET /hud')).length).toBe(2)
    cm.stop()
  })

  it('inputs go over POST /input in poll mode', async () => {
    const calls: Array<[string, string]> = []
    const f = (async (u: string, init?: RequestInit) => {
      calls.push([init?.method ?? '', u.replace('http://core:8787', '') + (init?.body ? ` ${init.body}` : '')])
      return okJson(undefined, 204)
    }) as unknown as typeof fetch
    const { cm } = setup(f)
    cm.start()
    await vi.advanceTimersByTimeAsync(4100)
    expect(cm.sendInput(input)).toBe(true)
    await vi.advanceTimersByTimeAsync(1)
    expect(calls.some(([m, u]) => m === 'POST' && u === `/input ${JSON.stringify(input)}`)).toBe(true)
    cm.stop()
  })

  it('poll failures flip health to false and re-hello on recovery', async () => {
    let fail = false
    const calls: string[] = []
    const f = (async (u: string, init?: RequestInit) => {
      calls.push(`${init?.method} ${u.replace('http://core:8787', '')}`)
      if (fail) throw new Error('net')
      return okJson(undefined, 204)
    }) as unknown as typeof fetch
    const { cm, health } = setup(f)
    cm.start()
    await vi.advanceTimersByTimeAsync(4100)
    expect(health.at(-1)).toBe(true)
    fail = true
    await vi.advanceTimersByTimeAsync(700)
    expect(health.at(-1)).toBe(false)
    fail = false
    calls.length = 0
    await vi.advanceTimersByTimeAsync(700)
    expect(calls[0]).toBe('POST /hello')
    expect(health.at(-1)).toBe(true)
    cm.stop()
  })

  it('a WebSocket that opens later takes over and polling stops', async () => {
    const calls: string[] = []
    const f = (async (u: string, init?: RequestInit) => { calls.push(`${init?.method} ${u}`); return okJson(undefined, 204) }) as unknown as typeof fetch
    const { cm } = setup(f)
    cm.start()
    await vi.advanceTimersByTimeAsync(4100)
    const before = calls.length
    // backoff reconnect created more sockets; open the newest one
    FakeWs.all.at(-1)!.open()
    await vi.advanceTimersByTimeAsync(2000)
    expect(calls.length).toBe(before)
    expect(cm.status).toBe('ws')
    cm.stop()
  })
})

describe('extractFrames', () => {
  it('handles the plausible reply shapes', () => {
    const f = { type: 'hud', seq: 1 }
    expect(extractFrames(f)).toEqual([f])
    expect(extractFrames([f, f])).toEqual([f, f])
    expect(extractFrames({ frame: f })).toEqual([f])
    expect(extractFrames({ frames: [f] })).toEqual([f])
    expect(extractFrames(null)).toEqual([])
    expect(extractFrames({})).toEqual([])
    expect(extractFrames(undefined)).toEqual([])
  })
})

describe('transport handover regressions', () => {
  const response = (body: unknown) => ({ ok: true, status: 200, text: async () => JSON.stringify(body) }) as Response

  it('manual reconnect becomes unhealthy until the new socket answers, resetting the sequence gate', () => {
    const { cm, health } = setup()
    cm.start()
    FakeWs.all[0].open()
    FakeWs.all[0].msg({ type: 'hud', seq: 900 })
    cm.reconnectNow()
    expect(health).toEqual([true, false])
    FakeWs.all[1].open()
    FakeWs.all[1].msg({ type: 'hud', seq: 1 })
    expect(health).toEqual([true, false, true])
    cm.stop()
  })

  it('poll hello resets health before delivering the restarted server frame', async () => {
    const order: string[] = []
    const cm = new ConnectionManager({
      backend: () => 'http://core:8787', clientId: () => 'c', sessionId: () => 's', surface: () => 'g2', afterSeq: () => 900,
      onMessage: () => order.push('frame'), onHealth: (ok) => order.push(`health:${ok}`), makeWs: (u) => new FakeWs(u),
      fetchFn: (async () => response({ type: 'hud', seq: 1 })) as typeof fetch,
    })
    cm.start()
    await vi.advanceTimersByTimeAsync(4001)
    expect(order.slice(0, 2)).toEqual(['health:true', 'frame'])
    cm.stop()
  })

  it('ignores a delayed HTTP hello after WebSocket takeover', async () => {
    let release!: (r: Response) => void
    const deferred = new Promise<Response>((resolve) => { release = resolve })
    const { cm, messages, health } = setup((async () => deferred) as typeof fetch)
    cm.start()
    await vi.advanceTimersByTimeAsync(4001)
    const ws = FakeWs.all.at(-1)!
    ws.open()
    ws.msg({ type: 'hud', seq: 20 })
    release(response({ type: 'hud', seq: 99, session_id: 'obsolete' }))
    await vi.advanceTimersByTimeAsync(1)
    expect(messages).toEqual([{ type: 'hud', seq: 20 }])
    expect(health.at(-1)).toBe(true)
    expect(cm.status).toBe('ws')
    cm.stop()
  })

  it('ignores a delayed HTTP reply after stop', async () => {
    let release!: (r: Response) => void
    const deferred = new Promise<Response>((resolve) => { release = resolve })
    const { cm, messages, health } = setup((async () => deferred) as typeof fetch)
    cm.start()
    await vi.advanceTimersByTimeAsync(4001)
    cm.stop()
    release(response({ type: 'hud', seq: 99 }))
    await vi.advanceTimersByTimeAsync(1)
    expect(messages).toEqual([])
    expect(health).toEqual([])
  })
})
