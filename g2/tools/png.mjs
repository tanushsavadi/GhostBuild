// Dependency-free PNG encoder for the stub server: 4-bit greyscale (colour type 0, bit depth 4),
// i.e. the same shape as the G2-ready guide images. Stub images are SIMULATED test art, not real guides.
import { deflateSync } from 'node:zlib'

const CRC = (() => {
  const t = new Uint32Array(256)
  for (let n = 0; n < 256; n++) {
    let c = n
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
    t[n] = c >>> 0
  }
  return t
})()
const crc32 = (buf) => {
  let c = 0xffffffff
  for (const b of buf) c = CRC[(c ^ b) & 0xff] ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}
const chunk = (type, data) => {
  const len = Buffer.alloc(4)
  len.writeUInt32BE(data.length)
  const td = Buffer.concat([Buffer.from(type, 'ascii'), data])
  const crc = Buffer.alloc(4)
  crc.writeUInt32BE(crc32(td))
  return Buffer.concat([len, td, crc])
}

/** pixels: Uint8Array(w*h) with values 0..15 */
export function encodeGray4(w, h, pixels) {
  const stride = Math.ceil(w / 2)
  const raw = Buffer.alloc((stride + 1) * h)
  for (let y = 0; y < h; y++) {
    raw[y * (stride + 1)] = 0 // filter: none
    for (let x = 0; x < w; x++) {
      const v = pixels[y * w + x] & 15
      const i = y * (stride + 1) + 1 + (x >> 1)
      raw[i] |= x & 1 ? v : v << 4
    }
  }
  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(w, 0)
  ihdr.writeUInt32BE(h, 4)
  ihdr[8] = 4 // bit depth
  ihdr[9] = 0 // grey
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('IDAT', deflateSync(raw)),
    chunk('IEND', Buffer.alloc(0)),
  ])
}

const FONT = {
  A: '01110 10001 10001 11111 10001 10001 10001', B: '11110 10001 10001 11110 10001 10001 11110',
  C: '01110 10001 10000 10000 10000 10001 01110', D: '11110 10001 10001 10001 10001 10001 11110',
  E: '11111 10000 10000 11110 10000 10000 11111', H: '10001 10001 10001 11111 10001 10001 10001',
  I: '01110 00100 00100 00100 00100 00100 01110', L: '10000 10000 10000 10000 10000 10000 11111',
  M: '10001 11011 10101 10101 10001 10001 10001', O: '01110 10001 10001 10001 10001 10001 01110',
  R: '11110 10001 10001 11110 10100 10010 10001', S: '01111 10000 10000 01110 00001 00001 11110',
  T: '11111 00100 00100 00100 00100 00100 00100', U: '10001 10001 10001 10001 10001 10001 01110',
  W: '10001 10001 10001 10101 10101 11011 10001',
}

export class Canvas {
  constructor(w, h) {
    this.w = w
    this.h = h
    this.px = new Uint8Array(w * h)
  }
  set(x, y, v) {
    if (x >= 0 && y >= 0 && x < this.w && y < this.h) this.px[y * this.w + x] = v
  }
  rect(x, y, w, h, v, fill = true, t = 3) {
    for (let j = 0; j < h; j++)
      for (let i = 0; i < w; i++) {
        const edge = i < t || j < t || i >= w - t || j >= h - t
        if (fill || edge) this.set(x + i, y + j, v)
      }
  }
  circle(cx, cy, r, v, fill = true, t = 3) {
    for (let j = -r; j <= r; j++)
      for (let i = -r; i <= r; i++) {
        const d = Math.hypot(i, j)
        if (d <= r && (fill || d >= r - t)) this.set(cx + i, cy + j, v)
      }
  }
  line(x0, y0, x1, y1, v, t = 3) {
    const n = Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0))
    for (let s = 0; s <= n; s++) this.rect(Math.round(x0 + ((x1 - x0) * s) / n) - 1, Math.round(y0 + ((y1 - y0) * s) / n) - 1, t, t, v)
  }
  text(str, x, y, scale, v) {
    for (const ch of str) {
      const g = FONT[ch]
      if (g) g.split(' ').forEach((row, j) => [...row].forEach((bit, i) => bit === '1' && this.rect(x + i * scale, y + j * scale, scale, scale, v)))
      x += 6 * scale
    }
  }
}

/** Three stub "guide" pictures. They depict nothing real: they exist to exercise the 288x144 image path. */
export function stubGuidePng(view, w = 288, h = 144) {
  const c = new Canvas(w, h)
  c.rect(0, 0, w, h, 15, false, 2)
  c.rect(30, 36, 120, 80, 8, false, 4) // camera body
  c.circle(90, 76, 24, view === 'where' ? 15 : 10, false, 4) // lens
  if (view === 'where') {
    c.line(200, 30, 160, 62, 15, 4) // pointer at the lens
    c.rect(196, 26, 10, 10, 15)
  } else if (view === 'how') {
    c.circle(90, 76, 20, 6, true) // covered lens
    c.line(70, 56, 110, 96, 15, 4)
    c.line(110, 56, 70, 96, 15, 4)
  } else {
    c.circle(90, 76, 20, 12, true) // clear lens
    c.circle(90, 76, 7, 15, true)
  }
  c.text(view.toUpperCase(), 170, 70, 4, 15)
  c.text('SIMULATED', 150, 118, 2, 6)
  return encodeGray4(w, h, c.px)
}
