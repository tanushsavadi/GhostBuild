import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Controller } from './controller'
import type { G2Input, View } from './types'
import { example, frame } from './test/fixtures'

function setup() {
  const rendered: View[] = []
  const sent: G2Input[] = []
  const exits: number[] = []
  let rehellos = 0
  const voice = { start: vi.fn(), stop: vi.fn() }
  const c = new Controller({
    render: (v) => rendered.push(v),
    sendInput: (i) => { sent.push(i); return true },
    rehello: () => { rehellos++ },
    exit: () => exits.push(1),
    surface: () => 'g2',
    voice,
  })
  return { c, rendered, sent, exits, voice, rehellos: () => rehellos }
}
const text = (v: View | undefined) => (v as { text: string } | undefined)?.text.replace(/\s+/g, ' ').trim()

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

describe('frames', () => {
  it('renders each new frame and never re-renders an identical one', () => {
    const { c, rendered } = setup()
    c.onMessage(frame({ seq: 1 }))
    c.onMessage(frame({ seq: 2 })) // same content, newer seq
    expect(rendered).toHaveLength(1)
    c.onMessage(frame({ seq: 3, cue: { line1: 'OTHER' } }))
    expect(rendered).toHaveLength(2)
  })

  it('never goes backwards in seq', () => {
    const { c, rendered } = setup()
    c.onMessage(frame({ seq: 5, cue: { line1: 'NEW' } }))
    c.onMessage(frame({ seq: 4, cue: { line1: 'OLD' } }))
    c.onMessage(frame({ seq: 5, cue: { line1: 'DUP' } }))
    expect(rendered.map(text)).toEqual(['NEW'])
  })

  it('drops malformed frames without throwing and ignores non-HUD chatter', () => {
    const { c, rendered } = setup()
    c.onMessage({ type: 'hud', seq: 'x' })
    c.onMessage({ type: 'pong' })
    c.onMessage(null)
    expect(rendered).toEqual([])
  })

  it('ttl_ms clears locally to blank as a fallback', () => {
    const { c, rendered } = setup()
    c.onMessage(example('hud_verified')) // ttl 3000
    expect(text(rendered[0])).toContain('CAMERA VIEW BACK')
    vi.advanceTimersByTime(2999)
    expect(rendered).toHaveLength(1)
    vi.advanceTimersByTime(1)
    expect(rendered).toHaveLength(2)
    expect((rendered[1] as { text: string }).text).toBe(' ')
  })

  it('a newer frame cancels the pending ttl clear', () => {
    const { c, rendered } = setup()
    c.onMessage({ ...example('hud_verified'), seq: 10 })
    c.onMessage(frame({ seq: 11, cue: { line1: 'NEXT' } }))
    vi.advanceTimersByTime(10000)
    expect(rendered.map(text)).toEqual(['● CAMERA VIEW BACK', 'NEXT'])
  })

  it('a ttl-cleared frame replayed by a reconnect does not come back', () => {
    const { c, rendered } = setup()
    c.onMessage(example('hud_verified'))
    vi.advanceTimersByTime(3000)
    c.onHealth(true) // reconnect resets the gate
    c.onMessage(example('hud_verified')) // server replays the current frame
    expect(rendered).toHaveLength(2)
    expect((rendered[1] as { text: string }).text).toBe(' ')
  })

  it('seq_seen in inputs is the last rendered frame seq', () => {
    const { c, sent } = setup()
    c.onMessage(frame({ seq: 8 }))
    c.onAction({ kind: 'send', gesture: 'press' })
    expect(sent[0]).toEqual({ type: 'g2_input', v: 2, gesture: 'press', seq_seen: 8, surface: 'g2' })
  })
})

describe('gestures', () => {
  it('double press exits locally and is NEVER sent to the backend', () => {
    const { c, sent, exits } = setup()
    c.onAction({ kind: 'exit' })
    expect(exits).toHaveLength(1)
    expect(sent).toEqual([])
  })
  it('ignore/lifecycle actions send nothing', () => {
    const { c, sent } = setup()
    c.onAction({ kind: 'ignore' })
    c.onAction({ kind: 'lifecycle', event: 'foreground_enter' })
    expect(sent).toEqual([])
  })
  it('voice stub only on hold start/release, never on press', () => {
    const { c, voice } = setup()
    c.onAction({ kind: 'send', gesture: 'press' })
    expect(voice.start).not.toHaveBeenCalled()
    c.onAction({ kind: 'send', gesture: 'hold_start' })
    c.onAction({ kind: 'send', gesture: 'hold_end' })
    expect(voice.start).toHaveBeenCalledTimes(1)
    expect(voice.stop).toHaveBeenCalledTimes(1)
  })
})

describe('offline honesty', () => {
  it('shows GHOSTBUILD OFFLINE / RECONNECTING after 3 s unhealthy, never earlier', () => {
    const { c, rendered } = setup()
    c.onMessage(example('hud_verified'))
    c.onHealth(false)
    vi.advanceTimersByTime(2999)
    expect(rendered).toHaveLength(1)
    vi.advanceTimersByTime(1)
    expect(text(rendered.at(-1))).toBe('GHOSTBUILD OFFLINE RECONNECTING')
    expect(c.isOfflineShown).toBe(true)
  })

  it('never leaves an old success on screen: offline replaces it, and the ttl timer no longer matters', () => {
    const { c, rendered } = setup()
    c.onMessage({ ...example('hud_verified'), ttl_ms: 60000 })
    c.onHealth(false)
    vi.advanceTimersByTime(3000)
    expect(text(rendered.at(-1))).toContain('OFFLINE')
    vi.advanceTimersByTime(60000)
    expect(text(rendered.at(-1))).toContain('OFFLINE')
  })

  it('a quick reconnect (< 3 s) never shows OFFLINE', () => {
    const { c, rendered } = setup()
    c.onMessage(frame({ seq: 1 }))
    c.onHealth(false)
    vi.advanceTimersByTime(2000)
    c.onHealth(true)
    c.onMessage(frame({ seq: 1 })) // server restate after reconnect
    vi.advanceTimersByTime(10000)
    expect(rendered).toHaveLength(1)
  })

  it('on reconnect the server frame replaces the offline view even with a lower seq (server restarted)', () => {
    const { c, rendered } = setup()
    c.onMessage(frame({ seq: 90, cue: { line1: 'BEFORE' } }))
    c.onHealth(false)
    vi.advanceTimersByTime(3000)
    c.onHealth(true)
    c.onMessage(frame({ seq: 1, mode: 'quiet', cue: null }))
    expect((rendered.at(-1) as { text: string }).text).toBe(' ')
    expect(c.isOfflineShown).toBe(false)
  })

  it('does not invent a welcome: while offline-and-connected it only re-hellos until a frame arrives', () => {
    const { c, rendered, rehellos } = setup()
    c.boot()
    vi.advanceTimersByTime(3000) // offline shown from boot
    c.onHealth(true)
    vi.advanceTimersByTime(2000)
    expect(rehellos()).toBe(1)
    expect(rendered.map(text)).toEqual(['GHOSTBUILD OFFLINE RECONNECTING'])
    c.onMessage(example('hud_welcome')) // server decides about the welcome
    expect(text(rendered.at(-1))).toContain('GHOSTBUILD BUILD OR FIX?')
    vi.advanceTimersByTime(10000)
    expect(rehellos()).toBe(1)
  })

  it('boot: if the backend never answers, offline appears at 3 s from start', () => {
    const { c, rendered } = setup()
    c.boot()
    expect(rendered).toEqual([])
    vi.advanceTimersByTime(3000)
    expect(text(rendered[0])).toContain('OFFLINE')
  })
})
