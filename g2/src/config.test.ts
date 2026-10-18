import { describe, expect, it } from 'vitest'
import { DEFAULT_BACKEND, normalizeBackend, readFlags, resolveBackend, resolveCenterCols, resolveGlyphTier, resolveSurface } from './config'
import { K, adoptSession, loadIdentity, makeStorage } from './session'

describe('config', () => {
  it('normalizes only http(s) origins', () => {
    expect(normalizeBackend('http://192.168.1.2:8787/')).toBe('http://192.168.1.2:8787')
    expect(normalizeBackend('https://x.ts.net/path?q=1')).toBe('https://x.ts.net')
    expect(normalizeBackend('ws://x')).toBeNull()
    expect(normalizeBackend('javascript:alert(1)')).toBeNull()
    expect(normalizeBackend('')).toBeNull()
    expect(normalizeBackend(null)).toBeNull()
  })
  it('priority: query > stored > env > default', () => {
    const env = { VITE_BACKEND_URL: 'http://env:1' }
    expect(resolveBackend('http://q:2', 'http://s:3', env)).toBe('http://q:2')
    expect(resolveBackend(null, 'http://s:3', env)).toBe('http://s:3')
    expect(resolveBackend(null, null, env)).toBe('http://env:1')
    expect(resolveBackend('garbage', 'also garbage', {})).toBe(DEFAULT_BACKEND)
  })
  it('flags default off', () => {
    expect(readFlags({}).voice).toBe(false)
    expect(readFlags({}).voicePreconsent).toBe(false)
    expect(readFlags({}).headShake).toBe(false)
    expect(readFlags({ VITE_FLAG_HEADSHAKE: '1' }).headShake).toBe(false) // needs voice
    expect(readFlags({ VITE_FLAG_VOICE: '1', VITE_FLAG_HEADSHAKE: '1' }).headShake).toBe(true)
    expect(readFlags({ VITE_VOICE_PRECONSENT: '1' }).voicePreconsent).toBe(true)
    expect(readFlags({ VITE_FLAG_VOICE: '0' }).voice).toBe(false)
    expect(readFlags({ VITE_FLAG_VOICE: '1' }).voice).toBe(true)
  })
  it('surface, glyphs, columns', () => {
    expect(resolveSurface('simulator')).toBe('simulator')
    expect(resolveSurface(null)).toBe('g2')
    expect(resolveSurface(null, 'S2001234567890')).toBe('simulator')
    expect(resolveSurface(null, 'SOMETHING')).toBe('g2')
    expect(resolveSurface('g2', 'S2001234567890')).toBe('g2')
    expect(resolveGlyphTier({ VITE_GLYPHS: 'ascii' })).toBe('ascii')
    expect(resolveGlyphTier({})).toBe('full')
    expect(resolveCenterCols({ VITE_CENTER_COLS: '36' })).toBe(36)
    expect(resolveCenterCols({ VITE_CENTER_COLS: '2' })).toBe(50)
  })
})

describe('session persistence', () => {
  const mem = () => {
    const m = new Map<string, string>()
    return { m, kv: { async get(k: string) { return m.get(k) ?? null }, async set(k: string, v: string) { m.set(k, v) } } }
  }
  it('creates a stable client_id once; session_id stays null until core assigns one', async () => {
    const { kv, m } = mem()
    const a = await loadIdentity(kv, () => 'abcd1234')
    expect(a).toEqual({ clientId: 'g2-abcd1234', sessionId: null })
    expect(m.has(K.sessionId)).toBe(false)
    const b = await loadIdentity(kv, () => 'zzzzzzzz')
    expect(b.clientId).toBe(a.clientId)
  })
  it('adopts the session id from a HudFrame, persists it, and restores it next launch', async () => {
    const { kv, m } = mem()
    expect(await adoptSession(kv, null, { type: 'hud', seq: 1, session_id: 's-core1' })).toBe('s-core1')
    expect(m.get(K.sessionId)).toBe('s-core1')
    expect((await loadIdentity(kv)).sessionId).toBe('s-core1')
    expect(await adoptSession(kv, 's-core1', { type: 'hud', seq: 2 })).toBe('s-core1')
    expect(await adoptSession(kv, 's-core1', { type: 'hud', seq: 3, session_id: 's-core2' })).toBe('s-core2')
    expect(await adoptSession(kv, 's-core1', { type: 'hud', seq: 4, session_id: null })).toBe('s-core1')
  })
  it('mirrors SDK storage and window.localStorage; survives either failing', async () => {
    const sdk = new Map<string, string>()
    const bridge = { getLocalStorage: async (k: string) => sdk.get(k) ?? '', setLocalStorage: async (k: string, v: string) => (sdk.set(k, v), true) }
    const win = new Map<string, string>()
    const store = { getItem: (k: string) => win.get(k) ?? null, setItem: (k: string, v: string) => void win.set(k, v) }
    const kv = makeStorage(bridge, store)
    await kv.set('a', '1')
    expect(sdk.get('a')).toBe('1')
    expect(win.get('a')).toBe('1')
    sdk.clear()
    expect(await kv.get('a')).toBe('1') // falls back to the mirror
    const broken = makeStorage({ getLocalStorage: async () => { throw new Error('x') }, setLocalStorage: async () => { throw new Error('y') } }, null)
    await broken.set('k', 'v')
    expect(await broken.get('k')).toBeNull()
  })
})
