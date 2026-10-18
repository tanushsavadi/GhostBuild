const SIG = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]

export interface PngInfo {
  w: number
  h: number
  bitDepth: number
  colorType: number
}

/** Reads IHDR. Throws on anything that is not a PNG, so a bad body never reaches the glasses. */
export function readPngInfo(bytes: Uint8Array): PngInfo {
  if (bytes.length < 33) throw new Error('png: too short')
  for (let i = 0; i < 8; i++) if (bytes[i] !== SIG[i]) throw new Error('png: bad signature')
  const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  if (dv.getUint32(12) !== 0x49484452) throw new Error('png: IHDR missing')
  return { w: dv.getUint32(16), h: dv.getUint32(20), bitDepth: bytes[24], colorType: bytes[25] }
}

/** Image container limits from the SDK .d.ts: width 20-288, height 20-144. */
export const IMG_LIMITS = { minW: 20, maxW: 288, minH: 20, maxH: 144 } as const

export function sizeWithinLimits(w: number, h: number): boolean {
  return w >= IMG_LIMITS.minW && w <= IMG_LIMITS.maxW && h >= IMG_LIMITS.minH && h <= IMG_LIMITS.maxH
}
