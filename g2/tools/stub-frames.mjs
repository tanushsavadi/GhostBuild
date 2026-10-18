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

// ---------------------------------------------------------------------------- PLAYBOOK flow (generic sample task)
// Deliberately device-agnostic: the plugin only renders frames. Step text here is placeholder sample data, not a real task.
export const PB_GUIDE = 'sample_task'
export const PB_VIEWS = ['where', 'how']
export const PB_STEPS = [
  { id: 'prepare', check: 'manual', cue: { line1: 'PREPARE THE PARTS', line2: 'SWIPE DOWN WHEN DONE' }, pictureOnPress: true },
  { id: 'place', check: 'manual', cue: { line1: 'PLACE PART ON BOARD', line2: 'SWIPE DOWN WHEN DONE' } },
  { id: 'measure', check: 'measured', cue: { line1: 'CHECK THE CONNECTION', line2: 'WAITING FOR EVIDENCE' } },
  { id: 'finish', check: 'manual', cue: { line1: 'CLOSE THE COVER', line2: 'SWIPE DOWN WHEN DONE' } },
]
const PB_FALLBACK = {
  where: { line1: 'WHERE: SEE PICTURE', line2: 'SWIPE FOR HOW' },
  how: { line1: 'HOW: SEE PICTURE', line2: 'PRESS TO GO BACK' },
}
export const PB_TASKS = ['SAMPLE TASK A', 'SAMPLE TASK B', 'SAMPLE TASK C']

export const chooser = (seq, selected = 0) => ({
  ...base(seq),
  mode: 'menu',
  cue: { line1: 'PICK A TASK', line2: 'SWIPE · PRESS' },
  menu: { prompt: 'PICK A TASK', options: PB_TASKS, selected },
})
export const stepRef = (i, confirmed = false) => ({
  index: i, count: PB_STEPS.length, step_id: PB_STEPS[i].id, check: PB_STEPS[i].check, confirmed,
})
export const step = (seq, i, over = {}) => ({
  ...base(seq), mode: 'step', cue: PB_STEPS[i].cue, step: stepRef(i), cue_id: `sample/${PB_STEPS[i].id}`, ...over,
})
export const stepNotMet = (seq, i) => ({
  ...step(seq, i), cue: { line1: 'NOT MET YET', line2: 'CHECK THE STEP, RECHECK' }, ttl_ms: null,
})
export const stepPicture = (seq, i, view = 0, sha256 = '0'.repeat(64)) => {
  const name = PB_VIEWS[view]
  return {
    ...base(seq), mode: 'visual', cue: PB_FALLBACK[name],
    image: {
      guide_id: PB_GUIDE, view: name, index: view, count: PB_VIEWS.length, title: TITLES[name] ?? name.toUpperCase(),
      url: `/guides/${PB_GUIDE}/${name}.png`, w: 288, h: 144, sha256, provenance: 'SIMULATED', step_id: `${PB_STEPS[i].id}.${name}`,
    },
    step: stepRef(i), cue_id: `sample/${PB_STEPS[i].id}`,
  }
}
export const stepPassed = (seq) => ({ ...base(seq), mode: 'verified', cue: { line1: '● CHECK PASSED', line2: '' }, ttl_ms: 2500 })
export const completion = (seq) => ({
  ...step(seq, PB_STEPS.length - 1, { cue: { line1: '✓ DONE (YOU CONFIRMED)', line2: '' }, ttl_ms: 3000 }),
  step: stepRef(PB_STEPS.length - 1, true),
})
