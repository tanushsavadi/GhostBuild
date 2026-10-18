// Launch intro: a few centred text frames, played once when the plugin starts (never on a reconnect), before the
// first backend frame. Text only, official glyphs (● ○), five small text updates over BLE. VITE_FLAG_INTRO=0 skips it.
import { sanitizeText } from './glyphs'
import type { TextView } from './types'
import { centerLine, textView, type ViewOptions } from './view'

export const WORDMARK = 'G H O S T B U I L D' // the backend welcome uses the same wordmark, so a new session continues seamlessly
const TAGLINE = 'HANDS BUSY. MIND CLEAR.'
const REVEAL = [3, 9, 13, WORDMARK.length] // characters shown per frame: G H / G H O S T / G H O S T B U / all
const FILL = [1, 2, 4, 5] // ● of 5 in the bar, per frame

export interface IntroFrame { view: TextView; ms: number }

export function introFrames(opts: ViewOptions): IntroFrame[] {
  const line = (s: string) => centerLine(sanitizeText(s, opts.glyphTier), opts.centerCols)
  const bar = (n: number) => '●'.repeat(n) + '○'.repeat(5 - n)
  const frames = REVEAL.map((n, i) => ({
    view: textView([line(WORDMARK.slice(0, n).padEnd(WORDMARK.length)), line(bar(FILL[i]))]),
    ms: 280,
  }))
  frames.push({ view: textView([line(WORDMARK), line(TAGLINE)]), ms: 1500 })
  return frames
}

export async function playIntro(render: (v: TextView) => Promise<void>, frames: IntroFrame[]): Promise<void> {
  for (const f of frames) {
    const t0 = Date.now()
    await render(f.view)
    const rest = f.ms - (Date.now() - t0)
    if (rest > 0) await new Promise((r) => setTimeout(r, rest))
  }
}
