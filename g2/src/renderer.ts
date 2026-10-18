import { ImageRawDataUpdate, TextContainerUpgrade } from '@evenrealities/even_hub_sdk'
import type { CreateStartUpPageContainer, RebuildPageContainer } from '@evenrealities/even_hub_sdk'
import type { ImageView, TextView, View } from './types'
import { log, warn } from './types'
import type { ImageLoader, LoadedImage } from './image'
import { CUE, IMG, TAG, textPageProps, toRebuild, toStartUp, visualPageProps } from './layout'

/** The subset of EvenAppBridge we call. Signatures checked against even_hub_sdk 0.0.16 index.d.ts. */
export interface BridgeLike {
  createStartUpPageContainer(c: CreateStartUpPageContainer): Promise<number>
  rebuildPageContainer(c: RebuildPageContainer): Promise<boolean>
  textContainerUpgrade(c: TextContainerUpgrade): Promise<boolean>
  updateImageRawData(d: ImageRawDataUpdate): Promise<string>
}

type Layout = { kind: 'text' } | { kind: 'visual'; w: number; h: number } | null

export interface ImageMetrics {
  url: string
  fetchMs: number
  rebuildMs: number
  sendMs: number
  totalMs: number
  bytes: number
  result: string
}

const IMAGE_OK = 'success' // ImageRawDataUpdateResult.success

/**
 * Applies Views to the glasses. Rules:
 *  - ALL bridge calls run through one pump, one at a time (image sends must never overlap).
 *  - latest-wins: while one View is being applied, newer ones overwrite the single pending slot.
 *  - text-only updates use textContainerUpgrade in place; the page is rebuilt ONLY when the layout
 *    changes (text <-> picture, or a different picture size), per docs "rebuild only when the layout changes".
 *  - an image failure at any step renders the frame's text fallback instead.
 */
export class Renderer {
  private layout: Layout = null
  private shownText: string | null = null
  private shownTag: string | null = null
  private shownImageKey: string | null = null
  private pending: View | null = null
  private pendingAt = 0
  private running: Promise<void> | null = null
  private lastView: View | null = null
  lastMetrics: ImageMetrics | null = null

  constructor(
    private readonly bridge: BridgeLike,
    private readonly loader: Pick<ImageLoader, 'load'>,
    private readonly now: () => number = () => Date.now(),
  ) {}

  /** createStartUpPageContainer is one-shot; everything after is rebuild/upgrade. */
  async init(first: TextView): Promise<boolean> {
    const r = await this.bridge.createStartUpPageContainer(toStartUp(textPageProps({ text: first.text, tag: first.tag })))
    if (r !== 0) {
      warn(`createStartUpPageContainer failed (code ${r}); will try rebuildPageContainer on next frame`)
      return false
    }
    this.layout = { kind: 'text' }
    this.shownText = first.text
    this.shownTag = first.tag
    this.lastView = first
    return true
  }

  render(view: View): Promise<void> {
    this.pending = view
    this.pendingAt = this.now()
    if (!this.running) this.running = this.pump()
    return this.running
  }

  /** Resolves when nothing is pending or in flight. */
  idle(): Promise<void> {
    return this.running ?? Promise.resolve()
  }

  /** Foreground restore: the glasses page may have been torn down, redraw from scratch. */
  forceRefresh(): Promise<void> {
    this.layout = null
    this.shownText = null
    this.shownTag = null
    this.shownImageKey = null
    return this.lastView ? this.render(this.lastView) : Promise.resolve()
  }

  private async pump(): Promise<void> {
    try {
      while (this.pending) {
        const view = this.pending
        const at = this.pendingAt
        this.pending = null
        this.lastView = view
        try {
          await this.apply(view, at)
        } catch (e) {
          warn('render failed', e)
          this.layout = null // force a rebuild next time
        }
      }
    } finally {
      this.running = null
    }
  }

  private async apply(view: View, requestedAt: number): Promise<void> {
    if (view.kind === 'text') return this.applyText(view)
    await this.applyImage(view, requestedAt)
  }

  private async applyText(v: TextView): Promise<void> {
    if (this.layout?.kind !== 'text') {
      const ok = await this.bridge.rebuildPageContainer(toRebuild(textPageProps({ text: v.text, tag: v.tag })))
      if (!ok) {
        warn('rebuildPageContainer(text) returned false')
        this.layout = null
        return
      }
      this.layout = { kind: 'text' }
      this.shownText = v.text
      this.shownTag = v.tag
      this.shownImageKey = null
      return
    }
    await this.upgradeTexts(v.text, v.tag)
  }

  private async upgradeTexts(text: string, tag: string): Promise<void> {
    if (text !== this.shownText) {
      const ok = await this.bridge.textContainerUpgrade(
        new TextContainerUpgrade({ containerID: CUE.id, containerName: CUE.name, content: text }),
      )
      if (!ok) {
        warn('textContainerUpgrade(cue) returned false; rebuilding next time')
        this.layout = null
        return
      }
      this.shownText = text
    }
    if (tag !== this.shownTag) {
      const ok = await this.bridge.textContainerUpgrade(
        new TextContainerUpgrade({ containerID: TAG.id, containerName: TAG.name, content: tag }),
      )
      if (ok) this.shownTag = tag
      else warn('textContainerUpgrade(tag) returned false')
    }
  }

  private async applyImage(v: ImageView, requestedAt: number): Promise<void> {
    let loaded: LoadedImage
    try {
      loaded = await this.loader.load(v.image)
    } catch (e) {
      warn(`image load failed (${(e as Error).message}); showing text cue`)
      return this.applyText(v.fallback)
    }
    if (this.pending) return // a newer view is waiting: latest wins, do not touch the screen for a stale one

    const m: ImageMetrics = { url: v.image.url, fetchMs: loaded.fetchMs, rebuildMs: 0, sendMs: 0, totalMs: 0, bytes: loaded.bytes.length, result: '' }
    const sameLayout = this.layout?.kind === 'visual' && this.layout.w === loaded.w && this.layout.h === loaded.h

    if (!sameLayout) {
      const r0 = this.now()
      const ok = await this.bridge.rebuildPageContainer(toRebuild(visualPageProps({ text: v.text, tag: v.tag }, loaded.w, loaded.h)))
      m.rebuildMs = this.now() - r0
      if (!ok) {
        warn('rebuildPageContainer(visual) returned false; showing text cue')
        this.layout = null
        m.result = 'rebuildFailed'
        this.finishMetrics(m, requestedAt)
        return this.applyText(v.fallback)
      }
      this.layout = { kind: 'visual', w: loaded.w, h: loaded.h }
      this.shownText = v.text
      this.shownTag = v.tag
      this.shownImageKey = null
    } else {
      await this.upgradeTexts(v.text, v.tag)
      if (this.layout === null) return this.applyText(v.fallback)
    }

    if (this.pending) {
      m.result = 'superseded'
      return
    }
    const key = /^0+$/.test(v.image.sha256) ? null : `${v.image.url}|${v.image.sha256}`
    if (key === null || key !== this.shownImageKey) {
      const s0 = this.now()
      const res = await this.bridge.updateImageRawData(
        new ImageRawDataUpdate({ containerID: IMG.id, containerName: IMG.name, imageData: loaded.bytes }),
      )
      m.sendMs = this.now() - s0
      m.result = res
      if (res !== IMAGE_OK) {
        warn(`updateImageRawData -> ${res}; showing text cue`)
        this.finishMetrics(m, requestedAt)
        this.shownImageKey = null
        return this.applyText(v.fallback)
      }
      this.shownImageKey = key
    } else {
      m.result = 'unchanged'
    }
    this.finishMetrics(m, requestedAt)
  }

  private finishMetrics(m: ImageMetrics, requestedAt: number): void {
    m.totalMs = this.now() - requestedAt
    this.lastMetrics = m
    log(`image shown ${m.url} result=${m.result} fetch=${m.fetchMs}ms rebuild=${m.rebuildMs}ms send=${m.sendMs}ms total=${m.totalMs}ms bytes=${m.bytes}`)
  }
}
