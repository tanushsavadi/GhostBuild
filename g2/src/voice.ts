import { log } from './types'

/**
 * Hold-to-ask stub. VITE_FLAG_VOICE=0 (default): nothing here is ever called and the manifest has NO microphone
 * permission. Design for later: capture starts ONLY on an intentional hold (LONG_PRESS_EVENT -> hold_start) and
 * stops on release (LONG_PRESS_RELEASE_EVENT -> hold_end), never on a plain press. To enable, in a later change:
 *  1. add {"name":"g2-microphone","desc":"..."} to app.json permissions,
 *  2. call bridge.audioControl(true, AudioInputSource.Glasses) in start() and audioControl(false) in stop()
 *     (requires createStartUpPageContainer to have succeeded first),
 *  3. forward audioEvent.audioPcm to the backend ASR path (never treat audio frames as taps).
 */
export interface VoiceCapture {
  readonly enabled: boolean
  start(): void
  stop(): void
}

export function createVoice(enabled: boolean): VoiceCapture {
  return {
    enabled,
    start() {
      if (!enabled) return
      log('voice: hold started (capture NOT implemented in this build)')
    },
    stop() {
      if (!enabled) return
      log('voice: hold released')
    },
  }
}
