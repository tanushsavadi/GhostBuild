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
  | { kind: 'exit' } // DOUBLE press. Controller: system exit at root/offline, else Home. Never forwarded as a press.
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
 *  - DOUBLE_CLICK (3) in ANY envelope is checked first -> exit action (the controller exits at root, else sends Home).
 *  - sysEvent 0 -> press; textEvent 0 (undefined) -> press (SDK may route a text-container tap there).
 *  - textEvent SCROLL_BOTTOM (2) -> swipe_down; SCROLL_TOP (1) -> swipe_up (handle-input skill routing table).
 *  - LONG_PRESS (9) / RELEASE (10) arrive on sysEvent (device-apis doc) -> hold_start / hold_end.
 *  - lifecycle 4..7 from sysEvent (or textEvent).
 */
export function mapHubEvent(event: HubEventLike, opts: { forwardOnTop?: boolean } = {}): GestureAction {
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

  // swipe_down = forward (next), swipe_up = back. On the physical temple the wearer's forward swipe arrives as SCROLL_TOP
  // (operator report 2026-10-18), so the glasses map it with forwardOnTop; the simulator's Down key stays forward.
  const forward = opts.forwardOnTop ? OsEventTypeList.SCROLL_TOP_EVENT : OsEventTypeList.SCROLL_BOTTOM_EVENT
  const back = opts.forwardOnTop ? OsEventTypeList.SCROLL_BOTTOM_EVENT : OsEventTypeList.SCROLL_TOP_EVENT
  if (text === forward) return { kind: 'send', gesture: 'swipe_down' }
  if (text === back) return { kind: 'send', gesture: 'swipe_up' }

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
  private lastSwipe = -Infinity
  private pending: ReturnType<typeof setTimeout> | null = null
  /**
   * holdMs > 0 (the glasses): the temple reports the start of a swipe as a click, so a tap is held this long and dropped if
   * a swipe (or a double tap) follows; a tap just after a swipe is its tail. Held taps are delivered later through `emit`.
   */
  constructor(
    private readonly now: () => number = () => Date.now(),
    private readonly windowMs = 150,
    private readonly forwardOnTop = false,
    private readonly holdMs = 0,
  ) {}

  route(event: HubEventLike, emit?: (a: GestureAction) => void): GestureAction {
    const a = mapHubEvent(event, { forwardOnTop: this.forwardOnTop })
    const t = this.now()
    if (a.kind === 'exit' || (a.kind === 'send' && (a.gesture === 'swipe_up' || a.gesture === 'swipe_down'))) {
      if (a.kind === 'send') this.lastSwipe = t
      this.cancelPending() // the held tap was the start of this swipe / the first half of this double tap
      return a
    }
    if (a.kind === 'send' && a.gesture === 'press') {
      if (t - this.lastPress < this.windowMs) return { kind: 'ignore' }
      if (this.holdMs > 0 && t - this.lastSwipe < this.holdMs) return { kind: 'ignore' }
      this.lastPress = t
      if (this.holdMs > 0 && emit) {
        this.cancelPending()
        this.pending = setTimeout(() => { this.pending = null; emit(a) }, this.holdMs)
        return { kind: 'ignore' }
      }
    }
    return a
  }

  private cancelPending(): void {
    if (this.pending) clearTimeout(this.pending)
    this.pending = null
  }
}
