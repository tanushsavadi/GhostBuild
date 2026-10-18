// Scripted HudFrames for the stub server. Every frame carries source "simulated" so the plugin shows the
// SIMULATED tag: stub output must never look like live data.
export const GUIDE = 'camera_lens'
export const VIEWS = ['where', 'how', 'correct']
const TITLES = { where: 'WHERE', how: 'HOW', correct: 'CORRECT' }
const FALLBACK = {
  where: { line1: 'WHERE: CAMERA LENS', line2: 'SWIPE FOR HOW' },
  how: { line1: 'HOW: LIFT THE COVER', line2: 'SWIPE FOR CORRECT' },
  correct: { line1: 'CORRECT: LENS CLEAR', line2: 'SWIPE UP TO GO BACK' },
}

const base = (seq) => ({ type: 'hud', v: 2, seq, image: null, menu: null, cue_id: null, ttl_ms: null, source: 'simulated', stale: false })

export const welcome = (seq) => ({ ...base(seq), mode: 'welcome', cue: { line1: 'GHOSTBUILD', line2: 'BUILD OR FIX?' }, ttl_ms: 2500 })
export const menu = (seq, selected = 0) => ({
  ...base(seq),
  mode: 'menu',
  cue: { line1: 'BUILD OR FIX?', line2: 'SWIPE · PRESS' },
  menu: { prompt: 'BUILD OR FIX?', options: ['FIX', 'BUILD'], selected },
})
export const intervene = (seq) => ({ ...base(seq), mode: 'intervene', cue: { line1: 'CAMERA VIEW LOST', line2: 'CHECK CAMERA LENS' }, cue_id: 'camera_view/0' })
export const visual = (seq, index = 0, sha256 = '0'.repeat(64)) => {
  const view = VIEWS[index]
  return {
    ...base(seq),
    mode: 'visual',
    cue: FALLBACK[view],
    image: {
      guide_id: GUIDE, view, index, count: VIEWS.length, title: TITLES[view],
      url: `/guides/${GUIDE}/${view}.png`, w: 288, h: 144, sha256,
      provenance: 'SIMULATED', step_id: `${GUIDE}.${view}`,
    },
    cue_id: 'camera_view/0',
  }
}
export const verified = (seq) => ({ ...base(seq), mode: 'verified', cue: { line1: '● CAMERA VIEW BACK', line2: '' }, ttl_ms: 3000 })
export const quiet = (seq) => ({ ...base(seq), mode: 'quiet', cue: null })
export const status = (seq) => ({ ...base(seq), mode: 'verified', cue: { line1: 'ALL TESTS PASSING', line2: '' }, ttl_ms: 3000 })
