import { describe, expect, it } from 'vitest'
import { Renderer, type BridgeLike } from './renderer'
import { ImageLoader } from './image'
import { blankView, frameToView, textView } from './view'
import { example, fakePng } from './test/fixtures'
import type { ImageView, View } from './types'

function fakeBridge(opts: { imageResult?: string; rebuild?: boolean; delayImage?: number } = {}) {
  const calls: string[] = []
  let inFlightImages = 0
  let maxInFlight = 0
  const b: BridgeLike & { calls: string[]; maxInFlight: () => number } = {
    calls,
    maxInFlight: () => maxInFlight,
    async createStartUpPageContainer() { calls.push('create'); return 0 },
    async rebuildPageContainer(c) {
      const n = (c as unknown as { imageObject?: unknown[] }).imageObject?.length ?? 0
      calls.push(n ? 'rebuild:visual' : 'rebuild:text')
      return opts.rebuild ?? true
    },
    async textContainerUpgrade(c) { calls.push(`upgrade:${c.containerName}:${JSON.stringify(c.content)}`); return true },
    async updateImageRawData(d) {
      inFlightImages++
      maxInFlight = Math.max(maxInFlight, inFlightImages)
      calls.push(`image:${d.containerName}:${(d.imageData as Uint8Array).length}`)
      await new Promise((r) => setTimeout(r, opts.delayImage ?? 5))
      inFlightImages--
      return opts.imageResult ?? 'success'
    },
  }
  return b
}

const okLoader = (w = 288, h = 144) => ({ load: async () => ({ bytes: fakePng(w, h), w, h, fetchMs: 3, cached: false }) })
const failLoader = { load: async () => { throw new Error('boom') } }

const visual = (idx = 0, sha = 'a'.repeat(64)): ImageView => {
  const f = example('hud_visual')
  return frameToView({ ...f, image: { ...f.image!, index: idx, sha256: sha } }) as ImageView
}

describe('Renderer', () => {
  it('init creates the startup page once, then text updates are in-place upgrades (no rebuild)', async () => {
    const b = fakeBridge()
    const r = new Renderer(b, okLoader())
    expect(await r.init(blankView())).toBe(true)
    await r.render(textView(['CHECK A']))
    await r.render(textView(['CHECK B']))
    expect(b.calls[0]).toBe('create')
    expect(b.calls.filter((c) => c.startsWith('rebuild'))).toEqual([])
    expect(b.calls.filter((c) => c.startsWith('upgrade:cue'))).toHaveLength(2)
  })

  it('does not call the bridge for unchanged text', async () => {
    const b = fakeBridge()
    const r = new Renderer(b, okLoader())
    await r.init(blankView())
    await r.render(textView(['X']))
    const n = b.calls.length
    await r.render(textView(['X']))
    expect(b.calls.length).toBe(n)
  })

  it('text -> picture rebuilds once, sends the PNG, picture -> picture is in place, picture -> text rebuilds back', async () => {
    const b = fakeBridge()
    const r = new Renderer(b, okLoader())
    await r.init(blankView())
    await r.render(visual(0, 'a'.repeat(64)))
    await r.render(visual(1, 'b'.repeat(64)))
    await r.render(textView(['BACK TO CUE']))
    expect(b.calls.filter((c) => c === 'rebuild:visual')).toHaveLength(1)
    expect(b.calls.filter((c) => c.startsWith('image:'))).toHaveLength(2)
    expect(b.calls.at(-1)).toBe('rebuild:text')
    expect(r.lastMetrics?.result).toBe('success')
  })

  it('a different picture size rebuilds the visual page', async () => {
    const b = fakeBridge()
    let w = 288
    const loader = { load: async () => ({ bytes: fakePng(w, 100), w, h: 100, fetchMs: 1, cached: false }) }
    const r = new Renderer(b, loader)
    await r.init(blankView())
    await r.render(visual(0, 'a'.repeat(64)))
    w = 200
    await r.render(visual(1, 'b'.repeat(64)))
    expect(b.calls.filter((c) => c === 'rebuild:visual')).toHaveLength(2)
  })

  it('image load failure renders the text cue fallback', async () => {
    const b = fakeBridge()
    const r = new Renderer(b, failLoader)
    await r.init(blankView())
    await r.render(visual())
    expect(b.calls.some((c) => c.startsWith('image:'))).toBe(false)
    expect(b.calls.some((c) => c.includes('WHERE: CAMERA LENS'))).toBe(true)
  })

  it('image send failure falls back to text after the picture page was built', async () => {
    const b = fakeBridge({ imageResult: 'imageToGray4Failed' })
    const r = new Renderer(b, okLoader())
    await r.init(blankView())
    await r.render(visual())
    expect(b.calls.at(-1)).toBe('rebuild:text')
    expect(r.lastMetrics?.result).toBe('imageToGray4Failed')
  })

  it('rebuild failure for the visual page falls back to text', async () => {
    const b = fakeBridge()
    let n = 0
    b.rebuildPageContainer = async (c) => {
      const isVisual = ((c as unknown as { imageObject?: unknown[] }).imageObject?.length ?? 0) > 0
      b.calls.push(isVisual ? 'rebuild:visual' : 'rebuild:text')
      n++
      return !isVisual
    }
    const r = new Renderer(b, okLoader())
    await r.init(blankView())
    await r.render(visual())
    expect(n).toBe(2)
    expect(b.calls.at(-1)).toBe('rebuild:text')
  })

  it('never runs two image sends at once and is latest-wins', async () => {
    const b = fakeBridge({ delayImage: 20 })
    const r = new Renderer(b, okLoader())
    await r.init(blankView())
    const seen: View[] = []
    void seen
    r.render(visual(0, '1'.repeat(64)))
    await new Promise((res) => setTimeout(res, 10)) // first picture is now mid-send
    r.render(visual(1, '2'.repeat(64)))
    r.render(visual(2, '3'.repeat(64)))
    r.render(textView(['FINAL']))
    await r.idle()
    expect(b.maxInFlight()).toBe(1)
    expect(b.calls.at(-1)?.includes('FINAL') || b.calls.at(-1) === 'rebuild:text').toBe(true)
    // the middle frames were skipped, not queued: at most the first one reached the glasses
    expect(b.calls.filter((c) => c.startsWith('image:')).length).toBeLessThanOrEqual(1)
  })

  it('forceRefresh redraws the current view from scratch', async () => {
    const b = fakeBridge()
    const r = new Renderer(b, okLoader())
    await r.init(blankView())
    await r.render(textView(['HELLO']))
    b.calls.length = 0
    await r.forceRefresh()
    expect(b.calls).toEqual(['rebuild:text'])
  })

  it('a failed init is retried via rebuild on the next frame', async () => {
    const b = fakeBridge()
    b.createStartUpPageContainer = async () => 1
    const r = new Renderer(b, okLoader())
    expect(await r.init(blankView())).toBe(false)
    await r.render(textView(['X']))
    expect(b.calls).toEqual(['rebuild:text'])
  })

  it('same picture again is not resent (real sha) but IS resent when the hash is the zero placeholder', async () => {
    const b = fakeBridge()
    const r = new Renderer(b, okLoader())
    await r.init(blankView())
    await r.render(visual(0, 'c'.repeat(64)))
    await r.render(textView(['x']))
    await r.render(visual(0, 'c'.repeat(64)))
    expect(b.calls.filter((c) => c.startsWith('image:'))).toHaveLength(2) // rebuild reset the shown key
    const b2 = fakeBridge()
    const r2 = new Renderer(b2, okLoader())
    await r2.init(blankView())
    await r2.render(visual(0, '0'.repeat(64)))
    await r2.render(visual(1, '0'.repeat(64)))
    expect(b2.calls.filter((c) => c.startsWith('image:'))).toHaveLength(2)
  })
})

describe('ImageLoader', () => {
  const ref = example('hud_visual').image!
  const mkFetch = (body: Uint8Array | null, status = 200) =>
    (async () => ({ ok: status < 400, status, arrayBuffer: async () => (body ?? new Uint8Array()).buffer.slice((body ?? new Uint8Array()).byteOffset, (body ?? new Uint8Array()).byteOffset + (body ?? new Uint8Array()).byteLength) })) as unknown as typeof fetch

  it('fetches backend + url and validates the PNG', async () => {
    let got = ''
    const f = (async (u: string) => { got = u; return { ok: true, status: 200, arrayBuffer: async () => fakePng(288, 144).buffer } }) as unknown as typeof fetch
    const l = new ImageLoader({ backend: () => 'http://h:8787', fetchFn: f })
    const img = await l.load(ref)
    expect(got).toBe('http://h:8787/guides/camera_lens/where.png')
    expect(img).toMatchObject({ w: 288, h: 144, cached: false })
  })
  it('throws on HTTP error, non-PNG and oversize', async () => {
    await expect(new ImageLoader({ backend: () => 'http://h', fetchFn: mkFetch(null, 404) }).load(ref)).rejects.toThrow(/404/)
    await expect(new ImageLoader({ backend: () => 'http://h', fetchFn: mkFetch(new Uint8Array(64)) }).load(ref)).rejects.toThrow(/png/)
    await expect(new ImageLoader({ backend: () => 'http://h', fetchFn: mkFetch(fakePng(400, 300)) }).load(ref)).rejects.toThrow(/limits/)
  })
  it('caches only when the hash is real', async () => {
    let n = 0
    const f = (async () => { n++; return { ok: true, status: 200, arrayBuffer: async () => fakePng(288, 144).buffer } }) as unknown as typeof fetch
    const l = new ImageLoader({ backend: () => 'http://h', fetchFn: f })
    await l.load(ref) // zero sha: no cache
    await l.load(ref)
    expect(n).toBe(2)
    const real = { ...ref, sha256: 'd'.repeat(64) }
    await l.load(real)
    const hit = await l.load(real)
    expect(n).toBe(3)
    expect(hit.cached).toBe(true)
  })
})

describe('renderer recovery regressions', () => {
  it('rebuilds the same cue immediately when a text update fails', async () => {
    const b = fakeBridge()
    b.textContainerUpgrade = async () => false
    const r = new Renderer(b, okLoader())
    await r.init(blankView())
    await r.render(textView(['DO THIS NOW'], 'SIMULATED'))
    expect(b.calls.at(-1)).toBe('rebuild:text')
  })

  it('rebuilds immediately when the evidence tag update fails', async () => {
    const b = fakeBridge()
    b.textContainerUpgrade = async (c) => c.containerID !== 2
    const r = new Renderer(b, okLoader())
    await r.init(blankView())
    await r.render(textView(['ACTION'], 'SIMULATED'))
    expect(b.calls.at(-1)).toBe('rebuild:text')
  })

  it('shows the text fallback when the image SDK call throws', async () => {
    const b = fakeBridge()
    b.updateImageRawData = async () => { throw new Error('BLE image transfer failed') }
    const r = new Renderer(b, okLoader())
    await r.init(blankView())
    await r.render(visual())
    expect(b.calls.at(-1)).toBe('rebuild:text')
  })

  it('foreground refresh preserves the newest pending frame during a transfer', async () => {
    const b = fakeBridge({ delayImage: 20 })
    const texts: string[] = []
    const original = b.rebuildPageContainer
    b.rebuildPageContainer = async (p) => { texts.push(p.textObject?.[0]?.content ?? ''); return original(p) }
    const r = new Renderer(b, okLoader())
    await r.init(blankView())
    void r.render(visual())
    await new Promise((resolve) => setTimeout(resolve, 5))
    void r.render(textView(['NEWEST']))
    await r.forceRefresh()
    expect(texts.at(-1)).toBe('NEWEST')
    expect(b.maxInFlight()).toBe(1)
  })
})
