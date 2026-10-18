import { OsEventTypeList } from '@evenrealities/even_hub_sdk'
import type { Gesture } from './types'

/** The slice of EvenHubEvent we read (structural, so tests need no SDK instances). */
export interface HubEventLike {
  listEvent?: { eventType?: number } | null
  textEvent?: { eventType?: number } | null
  sysEvent?: { eventType?: number } | null
  audioEvent?: unknown
}

export type Lifecycle = 'foreground_enter' | 'foreground_exit' | 'abnormal_exit' | 'system_exit'

export type GestureAction =
  | { kind: 'send'; gesture: Gesture }
  | { kind: 'exit' } // DOUBLE press: shutDownPageContainer(1) locally. NEVER sent to the backend.
  | { kind: 'lifecycle'; event: Lifecycle }
  | { kind: 'ignore' }

/**
 * CLICK_EVENT is 0 and protobuf omits zero values, so a tap arrives as an envelope whose
 * eventType is undefined. The default is resolved INSIDE the envelope check: a missing envelope is
 * null (not a click), otherwise scroll/exit/audio events would fire the tap handler.
 */
export function eventTypeOf(envelope?: { eventType?: number } | null): number | null {
  if (!envelope) return null
  return envelope.eventType ?? OsEventTypeList.CLICK_EVENT
}

/**
 * Pure mapper from an SDK event to what the plugin should do.
 *  - DOUBLE_CLICK (3) in ANY envelope is checked first -> local exit, never forwarded, never hijacked.
 *  - sysEvent 0 -> press; textEvent 0 (undefined) -> press (SDK may route a text-container tap there).
 *  - textEvent SCROLL_BOTTOM (2) -> swipe_down; SCROLL_TOP (1) -> swipe_up (handle-input skill routing table).
 *  - LONG_PRESS (9) / RELEASE (10) arrive on sysEvent (device-apis doc) -> hold_start / hold_end.
 *  - lifecycle 4..7 from sysEvent (or textEvent).
 */
export function mapHubEvent(event: HubEventLike): GestureAction {
  const sys = eventTypeOf(event.sysEvent)
  const text = eventTypeOf(event.textEvent)
  const list = eventTypeOf(event.listEvent)

  if (sys === OsEventTypeList.DOUBLE_CLICK_EVENT || text === OsEventTypeList.DOUBLE_CLICK_EVENT || list === OsEventTypeList.DOUBLE_CLICK_EVENT) {
    return { kind: 'exit' }
  }

  for (const t of [sys, text]) {
    if (t === OsEventTypeList.FOREGROUND_ENTER_EVENT) return { kind: 'lifecycle', event: 'foreground_enter' }
    if (t === OsEventTypeList.FOREGROUND_EXIT_EVENT) return { kind: 'lifecycle', event: 'foreground_exit' }
    if (t === OsEventTypeList.ABNORMAL_EXIT_EVENT) return { kind: 'lifecycle', event: 'abnormal_exit' }
    if (t === OsEventTypeList.SYSTEM_EXIT_EVENT) return { kind: 'lifecycle', event: 'system_exit' }
  }

  if (sys === OsEventTypeList.LONG_PRESS_EVENT) return { kind: 'send', gesture: 'hold_start' }
  if (sys === OsEventTypeList.LONG_PRESS_RELEASE_EVENT) return { kind: 'send', gesture: 'hold_end' }

  if (text === OsEventTypeList.SCROLL_BOTTOM_EVENT) return { kind: 'send', gesture: 'swipe_down' }
  if (text === OsEventTypeList.SCROLL_TOP_EVENT) return { kind: 'send', gesture: 'swipe_up' }

  if (sys === OsEventTypeList.CLICK_EVENT || text === OsEventTypeList.CLICK_EVENT) return { kind: 'send', gesture: 'press' }

  return { kind: 'ignore' }
}

/**
 * Stateful wrapper: the SDK could surface one physical tap through both the sysEvent and the
 * textEvent envelope. A real second tap inside the debounce window is physically a DOUBLE press
 * (event 3), so identical presses closer than `windowMs` are one press.
 */
export class GestureRouter {
  private lastPress = -Infinity
  constructor(
    private readonly now: () => number = () => Date.now(),
    private readonly windowMs = 150,
  ) {}

  route(event: HubEventLike): GestureAction {
    const a = mapHubEvent(event)
    if (a.kind === 'send' && a.gesture === 'press') {
      const t = this.now()
      if (t - this.lastPress < this.windowMs) return { kind: 'ignore' }
      this.lastPress = t
    }
    return a
  }
}
