import {
  CreateStartUpPageContainer,
  ImageContainerProperty,
  RebuildPageContainer,
  TextContainerProperty,
} from '@evenrealities/even_hub_sdk'

// Container identity. textContainerUpgrade needs matching containerID + containerName (mismatch silently no-ops).
export const CUE = { id: 1, name: 'cue' } as const
export const TAG = { id: 2, name: 'tag' } as const
export const IMG = { id: 3, name: 'img' } as const

export const CANVAS = { w: 576, h: 288 } as const

/** Text-only page: one event-capture cue container (+ small non-capture tag line). */
const TEXT_CUE = { x: 16, y: 72, w: 544, h: 168 }
/** Visual page: picture on top, caption (still the single event-capture container) under it, tag line last. */
const VISUAL_TOP = 8
const CAPTION_GAP = 8
const TAG_BOX = { x: 16, y: 248, w: 544, h: 36 }

export interface TextBlocks {
  text: string
  tag: string
}

function cueContainer(box: { x: number; y: number; w: number; h: number }, content: string) {
  return new TextContainerProperty({
    xPosition: box.x,
    yPosition: box.y,
    width: box.w,
    height: box.h,
    borderWidth: 0,
    borderColor: 0,
    paddingLength: 4,
    containerID: CUE.id,
    containerName: CUE.name,
    content,
    isEventCapture: 1,
  })
}

function tagContainer(content: string) {
  return new TextContainerProperty({
    xPosition: TAG_BOX.x,
    yPosition: TAG_BOX.y,
    width: TAG_BOX.w,
    height: TAG_BOX.h,
    borderWidth: 0,
    borderColor: 0,
    paddingLength: 4,
    containerID: TAG.id,
    containerName: TAG.name,
    content,
    isEventCapture: 0,
    textColor: 2, // dimmer than the cue (SDK >= 0.0.14, levels 0-4). Legibility at 2 is a hardware check.
  })
}

export function textPageProps(b: TextBlocks) {
  return {
    containerTotalNum: 2,
    textObject: [cueContainer(TEXT_CUE, b.text), tagContainer(b.tag)],
  }
}

export function imageGeometry(w: number, h: number) {
  const x = Math.round((CANVAS.w - w) / 2)
  const capY = VISUAL_TOP + h + CAPTION_GAP
  return {
    image: { x, y: VISUAL_TOP, w, h },
    caption: { x: 16, y: capY, w: 544, h: Math.max(40, TAG_BOX.y - capY - 4) },
  }
}

export function visualPageProps(b: TextBlocks, w: number, h: number) {
  const g = imageGeometry(w, h)
  return {
    containerTotalNum: 3,
    textObject: [cueContainer(g.caption, b.text), tagContainer(b.tag)],
    imageObject: [
      new ImageContainerProperty({
        xPosition: g.image.x,
        yPosition: g.image.y,
        width: w,
        height: h,
        containerID: IMG.id,
        containerName: IMG.name,
      }),
    ],
  }
}

export const toStartUp = (p: ReturnType<typeof textPageProps>) => new CreateStartUpPageContainer(p)
export const toRebuild = (p: ReturnType<typeof textPageProps> | ReturnType<typeof visualPageProps>) => new RebuildPageContainer(p)
