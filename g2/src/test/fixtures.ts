import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import type { HudFrame } from '../types'

const here = dirname(fileURLToPath(import.meta.url))
export const example = (name: string): HudFrame =>
  JSON.parse(readFileSync(resolve(here, '../../../contracts/examples', `${name}.json`), 'utf8')) as HudFrame

export const frame = (over: Partial<HudFrame> & { seq: number }): HudFrame =>
  ({ type: 'hud', v: 2, mode: 'intervene', cue: { line1: 'CAMERA VIEW LOST', line2: 'CHECK CAMERA LENS' }, image: null, menu: null, cue_id: null, ttl_ms: null, source: 'pi_live', stale: false, ...over }) as HudFrame

/** Minimal valid 4-bit grey PNG header (IHDR only is enough for readPngInfo). */
export function fakePng(w: number, h: number): Uint8Array {
  const b = new Uint8Array(33)
  b.set([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])
  const dv = new DataView(b.buffer)
  dv.setUint32(8, 13)
  b.set([0x49, 0x48, 0x44, 0x52], 12)
  dv.setUint32(16, w)
  dv.setUint32(20, h)
  b[24] = 4
  b[25] = 0
  return b
}
