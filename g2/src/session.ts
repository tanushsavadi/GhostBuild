import { warn } from './types'

/** Storage that is mirrored: the SDK's phone-side store (setLocalStorage/getLocalStorage) AND window.localStorage. */
export interface KeyValue {
  get(key: string): Promise<string | null>
  set(key: string, value: string): Promise<void>
}

export const K = {
  clientId: 'gb.client_id',
  sessionId: 'gb.session_id',
  backend: 'gb.backend',
} as const

export interface BridgeStorage {
  getLocalStorage(key: string): Promise<string>
  setLocalStorage(key: string, value: string): Promise<boolean>
}

/** SDK store first (survives WebView recreation per docs), window.localStorage as a mirror/fallback. All wrapped in try/catch. */
export function makeStorage(bridge: BridgeStorage | null, win: Pick<Storage, 'getItem' | 'setItem'> | null): KeyValue {
  return {
    async get(key) {
      try {
        if (bridge) {
          const v = await bridge.getLocalStorage(key) // returns '' for a missing key
          if (v) return v
        }
      } catch (e) {
        warn('bridge.getLocalStorage failed', e)
      }
      try {
        return win?.getItem(key) || null
      } catch {
        return null
      }
    },
    async set(key, value) {
      try {
        win?.setItem(key, value)
      } catch { /* private mode etc. */ }
      try {
        if (bridge) await bridge.setLocalStorage(key, value)
      } catch (e) {
        warn('bridge.setLocalStorage failed', e)
      }
    },
  }
}

const randomHex = (n: number): string =>
  Array.from({ length: n }, () => Math.floor(Math.random() * 16).toString(16)).join('')

export interface Identity {
  clientId: string
  sessionId: string
}

/**
 * client_id: stable per install (g2-xxxxxxxx). session_id: restored from storage; if none, generated once
 * and persisted. NOTE: contract v2 has no inbound message that assigns a session id, so the plugin owns it;
 * `adoptSession` lets core override later (any inbound object with a string `session_id`).
 */
export async function loadIdentity(kv: KeyValue, rand: (n: number) => string = randomHex): Promise<Identity> {
  let clientId = await kv.get(K.clientId)
  if (!clientId) {
    clientId = `g2-${rand(8)}`
    await kv.set(K.clientId, clientId)
  }
  let sessionId = await kv.get(K.sessionId)
  if (!sessionId) {
    sessionId = `s-${rand(10)}`
    await kv.set(K.sessionId, sessionId)
  }
  return { clientId, sessionId }
}

export async function adoptSession(kv: KeyValue, current: string, msg: unknown): Promise<string> {
  const id = (msg as { session_id?: unknown } | null)?.session_id
  if (typeof id === 'string' && id.length > 0 && id !== current) {
    await kv.set(K.sessionId, id)
    return id
  }
  return current
}
