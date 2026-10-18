import type { HudFrame, ImageRef, TextView, View } from './types'
import { sanitizeLine, type GlyphTier } from './glyphs'

export interface ViewOptions {
  /** Approximate characters that fit a line; used to centre by space padding (no text-align on G2). */
  centerCols: number
  glyphTier: GlyphTier
}

/**
 * The font is proportional and a space is roughly half an average capital's width. Measured in the 0.9.5 simulator:
 * ~10.5 px per capital, ~5 px per space, 536 px inner width -> about 50 average characters per line.
 * Hardware metrics may differ: calibrate VITE_CENTER_COLS on the glasses (see README).
 */
export const DEFAULT_VIEW_OPTIONS: ViewOptions = { centerCols: 50, glyphTier: 'full' }
const SPACE_RATIO = 0.5

function padFor(width: number, cols: number): number {
  return Math.max(0, Math.round((cols - width) / 2 / SPACE_RATIO))
}

/** The G2 has no text alignment: "centering" is space padding (docs: Display & UI System). */
export function centerLine(line: string, cols: number): string {
  return ' '.repeat(padFor(line.length, cols)) + line
}

/** Centre a block of lines as one unit so column markers (`> `) stay aligned. */
export function centerBlock(lines: string[], cols: number): string[] {
  const width = lines.reduce((m, l) => Math.max(m, l.length), 0)
  const pad = ' '.repeat(padFor(width, cols))
  return lines.map((l) => pad + l)
}

export function textView(lines: string[], tag = ' '): TextView {
  const text = lines.length ? lines.join('\n') : ' '
  return { kind: 'text', text, tag: tag || ' ', key: `t|${text}|${tag}` }
}

export function blankView(tag = ' '): TextView {
  return textView([], tag)
}

/** Honest transport state. Never carries a success claim. */
export function offlineView(opts: ViewOptions = DEFAULT_VIEW_OPTIONS): TextView {
  return textView(
    [centerLine('GHOSTBUILD OFFLINE', opts.centerCols), centerLine('RECONNECTING', opts.centerCols)],
  )
}

export function sourceTag(source: HudFrame['source']): string {
  return source === 'pi_live' ? '' : source.toUpperCase()
}

function joinTag(...parts: string[]): string {
  const t = parts.filter(Boolean).join('  ')
  return t || ' '
}

function menuLines(frame: HudFrame, opts: ViewOptions): string[] | null {
  const m = frame.menu
  const options = m?.options as string[] | undefined
  if (!m || !Array.isArray(options) || options.length === 0) return null
  const sel = Math.min(Math.max(0, m.selected ?? 0), options.length - 1)
  const rows = options.map((o, i) => `${i === sel ? '> ' : '  '}${sanitizeLine(String(o), opts.glyphTier)}`)
  const lines = [sanitizeLine(m.prompt ?? '', opts.glyphTier), ...rows]
  // Hint line only when it still fits the container (prompt + 2 options + hint = 4 lines).
  const hint = sanitizeLine(frame.cue?.line2 ?? '', opts.glyphTier)
  if (hint && options.length <= 2) lines.push(hint)
  return centerBlock(lines.filter((l) => l.trim().length > 0), opts.centerCols)
}

function cueLines(frame: HudFrame, opts: ViewOptions): string[] {
  const l1 = sanitizeLine(frame.cue?.line1 ?? '', opts.glyphTier)
  const l2 = sanitizeLine(frame.cue?.line2 ?? '', opts.glyphTier)
  return [l1, l2].filter(Boolean).map((l) => centerLine(l, opts.centerCols))
}

/**
 * HudFrame -> render plan. Pure. Rules:
 *  - quiet            -> blank `" "`
 *  - stale            -> honest STALE DATA (contract: "plugin shows ERROR instead"), never the old cue
 *  - menu             -> prompt + options, selected marked `> `, others `  `
 *  - visual + image   -> image with cue as caption; `fallback` is the text-only rendering
 *  - everything else  -> up to 2 centred lines
 * Non-live sources (replay, simulated) always add a visible tag.
 */
export function frameToView(frame: HudFrame, opts: ViewOptions = DEFAULT_VIEW_OPTIONS): View {
  const tag = sourceTag(frame.source)

  if (frame.stale) {
    return textView([centerLine('STALE DATA', opts.centerCols), centerLine('CHECK LINK', opts.centerCols)], joinTag(tag))
  }
  if (frame.mode === 'quiet') return blankView(joinTag(tag))

  if (frame.mode === 'menu') {
    const lines = menuLines(frame, opts)
    if (lines && lines.length) return textView(lines, joinTag(tag))
    // fall through to the cue fallback
  }

  let lines = cueLines(frame, opts)
  if (lines.length === 0) lines = [centerLine('NO CUE TEXT', opts.centerCols)]
  const fallback = textView(lines, joinTag(tag))

  if (frame.mode === 'visual' && frame.image) {
    const img: ImageRef = frame.image
    const idx = img.count > 1 ? `${img.index + 1}/${img.count}` : ''
    const t = joinTag(idx, tag)
    return {
      kind: 'image',
      text: lines.join('\n'),
      tag: t,
      image: img,
      fallback,
      key: `i|${img.url}|${img.sha256}|${img.index}|${lines.join('\n')}|${t}`,
    }
  }
  return fallback
}
