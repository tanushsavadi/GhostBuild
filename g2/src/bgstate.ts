import * as sdk from '@evenrealities/even_hub_sdk'
import { log } from './types'

/**
 * setBackgroundState / onBackgroundRestore are documented by the everything-evenhub background-state skill but are NOT
 * exported by @evenrealities/even_hub_sdk 0.0.16 (not in index.d.ts or index.js). We feature-detect so a later SDK
 * picks them up without code changes; today persistence relies on setLocalStorage (see session.ts) plus a re-hello on
 * FOREGROUND_ENTER, which matches the official Background & Lifecycle page ("persist anything important to localStorage").
 */
type Maybe = {
  setBackgroundState?: (key: string, exporter: () => Record<string, unknown>) => void
  onBackgroundRestore?: (key: string, restorer: (saved: Record<string, unknown>) => void) => void
}

export function registerBackgroundState(
  key: string,
  exporter: () => Record<string, unknown>,
  restorer: (saved: Record<string, unknown>) => void,
): boolean {
  const m = sdk as unknown as Maybe
  if (typeof m.setBackgroundState !== 'function' || typeof m.onBackgroundRestore !== 'function') {
    log('setBackgroundState not in this SDK build; relying on setLocalStorage + re-hello')
    return false
  }
  m.setBackgroundState(key, exporter)
  m.onBackgroundRestore(key, restorer)
  return true
}
