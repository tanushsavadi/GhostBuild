// Wire types come from the generated contract (contracts/models.py -> contracts/ts/index.ts).
// Never hand-copy the schema here.
import type { Gesture, G2Hello, G2Input, HudFrame, ImageRef } from '../../contracts/ts/index'

export type { Gesture, G2Hello, G2Input, HudFrame, ImageRef }

/** What the renderer is asked to show. Produced only by view.ts. */
export type View = TextView | ImageView

export interface TextView {
  kind: 'text'
  /** Text for the single event-capture container. `' '` means blank (quiet). */
  text: string
  /** Small non-capture line (source label such as SIMULATED/REPLAY). `' '` when empty. */
  tag: string
  /** Stable identity used for de-duplication. */
  key: string
}

export interface ImageView {
  kind: 'image'
  /** Caption shown under the picture (cue text). */
  text: string
  tag: string
  image: ImageRef
  /** Text-only rendering used when the image cannot be shown. */
  fallback: TextView
  key: string
}

export type ConnStatus = 'connecting' | 'ws' | 'poll' | 'down'

export const log = (...a: unknown[]): void => console.log('[ghostbuild]', ...a)
export const warn = (...a: unknown[]): void => console.warn('[ghostbuild]', ...a)
