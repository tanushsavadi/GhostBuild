import type { ImageRef } from './types'
import { log, warn } from './types'
import { readPngInfo, sizeWithinLimits } from './png'

export interface LoadedImage {
  bytes: Uint8Array
  w: number
  h: number
  fetchMs: number
  cached: boolean
}

export interface ImageLoaderOptions {
  backend: () => string
  fetchFn?: typeof fetch
  timeoutMs?: number
  now?: () => number
}

const ZERO_SHA = /^0+$/

/**
 * Fetches `${backend}${ref.url}` as PNG bytes. The SDK's updateImageRawData takes ENCODED image
 * bytes (PNG) as a Uint8Array and converts to 4-bit grey itself (official `image` template;
 * the result code imageToGray4Failed confirms host-side conversion). We only validate that it is a
 * real PNG that fits an image container. Any failure throws; the caller renders the text cue instead.
 */
export class ImageLoader {
  private cache = new Map<string, LoadedImage>()
  private readonly fetchFn: typeof fetch
  private readonly timeoutMs: number
  private readonly now: () => number

  constructor(private readonly o: ImageLoaderOptions) {
    this.fetchFn = o.fetchFn ?? ((...a) => globalThis.fetch(...a))
    this.timeoutMs = o.timeoutMs ?? 4000
    this.now = o.now ?? (() => Date.now())
  }

  /** Only cache when the contract hash is real (the all-zero example hash would go stale). */
  private cacheKey(ref: ImageRef): string | null {
    return ref.sha256 && !ZERO_SHA.test(ref.sha256) ? `${ref.url}|${ref.sha256}` : null
  }

  async load(ref: ImageRef): Promise<LoadedImage> {
    const ck = this.cacheKey(ref)
    if (ck) {
      const hit = this.cache.get(ck)
      if (hit) return { ...hit, fetchMs: 0, cached: true }
    }
    const url = `${this.o.backend()}${ref.url.startsWith('/') ? '' : '/'}${ref.url}`
    const t0 = this.now()
    const ctl = typeof AbortController !== 'undefined' ? new AbortController() : null
    const timer = ctl ? setTimeout(() => ctl.abort(), this.timeoutMs) : null
    try {
      const res = await this.fetchFn(url, { signal: ctl?.signal, cache: 'no-store' })
      if (!res.ok) throw new Error(`image fetch ${res.status}`)
      const bytes = new Uint8Array(await res.arrayBuffer())
      const info = readPngInfo(bytes)
      if (!sizeWithinLimits(info.w, info.h)) throw new Error(`image ${info.w}x${info.h} outside container limits`)
      if (info.w !== ref.w || info.h !== ref.h) warn(`image dims ${info.w}x${info.h} differ from frame ref ${ref.w}x${ref.h}; using PNG dims`)
      const loaded: LoadedImage = { bytes, w: info.w, h: info.h, fetchMs: this.now() - t0, cached: false }
      log(`image fetched ${ref.url} ${bytes.length}B ${info.w}x${info.h} in ${loaded.fetchMs}ms`)
      if (ck) {
        this.cache.set(ck, loaded)
        if (this.cache.size > 6) this.cache.delete(this.cache.keys().next().value as string)
      }
      return loaded
    } finally {
      if (timer) clearTimeout(timer)
    }
  }
}
