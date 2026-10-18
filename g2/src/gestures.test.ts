import { describe, expect, it } from 'vitest'
import { vi } from 'vitest'
import { GestureRouter, eventTypeOf, mapHubEvent } from './gestures'

describe('eventTypeOf', () => {
  it('missing envelope is null, never a click', () => {
    expect(eventTypeOf(undefined)).toBeNull()
    expect(eventTypeOf(null)).toBeNull()
  })
  it('present envelope with undefined eventType is CLICK (0)', () => {
    expect(eventTypeOf({})).toBe(0)
    expect(eventTypeOf({ eventType: 3 })).toBe(3)
  })
})

describe('mapHubEvent', () => {
  it('single press arrives as sysEvent with undefined eventType', () => {
    expect(mapHubEvent({ sysEvent: {} })).toEqual({ kind: 'send', gesture: 'press' })
    expect(mapHubEvent({ sysEvent: { eventType: 0 } })).toEqual({ kind: 'send', gesture: 'press' })
  })
  it('swipes come from textEvent: 2 = down, 1 = up', () => {
    expect(mapHubEvent({ textEvent: { eventType: 2 } })).toEqual({ kind: 'send', gesture: 'swipe_down' })
    expect(mapHubEvent({ textEvent: { eventType: 1 } })).toEqual({ kind: 'send', gesture: 'swipe_up' })
  })
  it('on the glasses the wearer\'s forward swipe (SCROLL_TOP) goes forward and the other way goes back', () => {
    expect(mapHubEvent({ textEvent: { eventType: 1 } }, { forwardOnTop: true })).toEqual({ kind: 'send', gesture: 'swipe_down' })
    expect(mapHubEvent({ textEvent: { eventType: 2 } }, { forwardOnTop: true })).toEqual({ kind: 'send', gesture: 'swipe_up' })
  })
  it('DOUBLE press is a local exit in every envelope and never a send', () => {
    for (const e of [{ sysEvent: { eventType: 3 } }, { textEvent: { eventType: 3 } }, { listEvent: { eventType: 3 } }]) {
      expect(mapHubEvent(e)).toEqual({ kind: 'exit' })
    }
  })
  it('double is checked before click even when both envelopes are present', () => {
    expect(mapHubEvent({ sysEvent: { eventType: 3 }, textEvent: {} })).toEqual({ kind: 'exit' })
  })
  it('long press pair maps to hold_start / hold_end (sysEvent)', () => {
    expect(mapHubEvent({ sysEvent: { eventType: 9 } })).toEqual({ kind: 'send', gesture: 'hold_start' })
    expect(mapHubEvent({ sysEvent: { eventType: 10 } })).toEqual({ kind: 'send', gesture: 'hold_end' })
  })
  it('lifecycle events', () => {
    expect(mapHubEvent({ sysEvent: { eventType: 4 } })).toEqual({ kind: 'lifecycle', event: 'foreground_enter' })
    expect(mapHubEvent({ sysEvent: { eventType: 5 } })).toEqual({ kind: 'lifecycle', event: 'foreground_exit' })
    expect(mapHubEvent({ sysEvent: { eventType: 6 } })).toEqual({ kind: 'lifecycle', event: 'abnormal_exit' })
    expect(mapHubEvent({ sysEvent: { eventType: 7 } })).toEqual({ kind: 'lifecycle', event: 'system_exit' })
  })
  it('audio, IMU and empty events never fire a press', () => {
    expect(mapHubEvent({ audioEvent: { audioPcm: new Uint8Array(4) } })).toEqual({ kind: 'ignore' })
    expect(mapHubEvent({ sysEvent: { eventType: 8 } })).toEqual({ kind: 'ignore' })
    expect(mapHubEvent({})).toEqual({ kind: 'ignore' })
  })
})

describe('GestureRouter', () => {
  it('suppresses a press echoed through two envelopes within the window', () => {
    let t = 1000
    const r = new GestureRouter(() => t, 150)
    expect(r.route({ sysEvent: {} })).toEqual({ kind: 'send', gesture: 'press' })
    t += 20
    expect(r.route({ textEvent: {} })).toEqual({ kind: 'ignore' })
    t += 500
    expect(r.route({ sysEvent: {} })).toEqual({ kind: 'send', gesture: 'press' })
  })
  it('never suppresses swipes or exit', () => {
    let t = 0
    const r = new GestureRouter(() => t, 150)
    expect(r.route({ textEvent: { eventType: 2 } }).kind).toBe('send')
    expect(r.route({ textEvent: { eventType: 2 } }).kind).toBe('send')
    expect(r.route({ sysEvent: { eventType: 3 } }).kind).toBe('exit')
    expect(r.route({ sysEvent: { eventType: 3 } }).kind).toBe('exit')
  })
})


describe('GestureRouter on the glasses: a swipe is never also a tap', () => {
  // Operator logs 2026-10-18: 11 taps landed 3-550 ms before a swipe; the temple reports the start of a swipe as a click.
  const setup = () => {
    vi.useFakeTimers()
    let t = 0
    const out: string[] = []
    const r = new GestureRouter(() => t, 150, true, 280)
    const go = (ev: unknown, dt = 0) => { t += dt; vi.advanceTimersByTime(dt); const a = r.route(ev as never, (x) => out.push(x.kind === 'send' ? x.gesture : x.kind)); if (a.kind !== 'ignore') out.push(a.kind === 'send' ? a.gesture : a.kind) }
    return { go, out, tick: (dt: number) => { t += dt; vi.advanceTimersByTime(dt) } }
  }
  it('a tap followed by a swipe within the hold is only the swipe', () => {
    const { go, out, tick } = setup()
    go({ sysEvent: {} })
    go({ textEvent: { eventType: 1 } }, 3)
    tick(500)
    expect(out).toEqual(['swipe_down'])
    vi.useRealTimers()
  })
  it('a lone tap still goes through after the hold', () => {
    const { go, out, tick } = setup()
    go({ sysEvent: {} })
    expect(out).toEqual([])
    tick(300)
    expect(out).toEqual(['press'])
    vi.useRealTimers()
  })
  it('a tap right after a swipe is its tail, not a select', () => {
    const { go, out, tick } = setup()
    go({ textEvent: { eventType: 2 } })
    go({ sysEvent: {} }, 100)
    tick(500)
    expect(out).toEqual(['swipe_up'])
    vi.useRealTimers()
  })
  it('a double tap is never preceded by its first tap', () => {
    const { go, out, tick } = setup()
    go({ sysEvent: {} })
    go({ sysEvent: { eventType: 3 } }, 120)
    tick(500)
    expect(out).toEqual(['exit'])
    vi.useRealTimers()
  })
})
