// Pure logic of the phone page (web/logic.js). Lives here so `make test` (vitest in g2/) covers it; web/ has no build tooling.
import { createRequire } from 'node:module'
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const L = createRequire(import.meta.url)('../../web/logic.js')
const fx = (n) => JSON.parse(readFileSync(new URL(`../../web/fixtures/${n}.json`, import.meta.url), 'utf8'))
const shelf = fx('card_flatpack_shelf')
const led = fx('card_led_breadboard')
const lens = fx('card_camera_lens')

describe('telemetry detection: the page works with no Pi', () => {
  it('manual playbook uses no telemetry; fault card and measured step do', () => {
    expect(L.cardUsesTelemetry(shelf)).toBe(false)
    expect(L.cardUsesTelemetry(led)).toBe(true) // last step has `verify`
    expect(L.cardUsesTelemetry(lens)).toBe(true) // tests
    expect(L.isPlaybookCard(shelf)).toBe(true)
    expect(L.isPlaybookCard(lens)).toBe(false)
  })
  it('manual playbook + pi_link down: no Pi banner, no Pi health row', () => {
    const st = fx('state_playbook_manual')
    expect(st.health.pi_link).toBe('down')
    expect(L.showPiBanners(st, shelf)).toBe(false)
    expect(L.showPiHealth(st, shelf)).toBe(false)
  })
  it('telemetry card + pi_link down keeps the Pi warning (measured steps cannot pass without it)', () => {
    const st = { ...fx('state_playbook_measured'), health: { ...fx('state_playbook_measured').health, pi_link: 'down' } }
    expect(L.showPiBanners(st, led)).toBe(true)
    expect(L.showPiHealth(st, led)).toBe(true)
    expect(L.showPiBanners(fx('state_pi_down'), lens)).toBe(true)
  })
  it('pi_link up shows Pi health even for a manual card, but never a banner', () => {
    const st = { ...fx('state_playbook_manual'), health: fx('state_playbook_measured').health }
    expect(L.showPiHealth(st, shelf)).toBe(true)
    expect(L.showPiBanners(st, shelf)).toBe(false)
  })
  it('before the card loads: PLAYBOOK engine is treated as no-telemetry, a fault engine as telemetry', () => {
    expect(L.usesTelemetry(fx('state_playbook_manual'), null)).toBe(false)
    expect(L.usesTelemetry(fx('state_pi_down'), null)).toBe(true)
  })
})

describe('playbook state', () => {
  it('current step index follows step_id when step_index disagrees', () => {
    const st = fx('state_playbook_manual')
    expect(L.currentStepIndex(st, shelf)).toBe(1)
    expect(L.currentStepIndex({ ...st, playbook: { ...st.playbook, step_index: 3 } }, shelf)).toBe(1)
    expect(L.currentStepIndex({ ...st, playbook: { ...st.playbook, step_index: 9, step_id: 'nope' } }, shelf)).toBe(3)
    expect(L.currentStepIndex({ ...st, playbook: null }, shelf)).toBe(-1)
  })
  it('badges: HUMAN CONFIRMED, MEASURED, pending (never anything stronger)', () => {
    const pb = { confirmed: ['frame'], verified: ['back'] }
    expect(L.stepStatus({ id: 'frame' }, pb)).toEqual({ kind: 'confirmed', label: 'HUMAN CONFIRMED' })
    expect(L.stepStatus({ id: 'back' }, pb)).toEqual({ kind: 'measured', label: 'MEASURED' })
    expect(L.stepStatus({ id: 'cams' }, pb)).toEqual({ kind: 'pending', label: 'pending' })
    expect(L.stepStatus({ id: 'x' }, null).kind).toBe('pending')
  })
  it('a measured step is described as evidence-only', () => {
    expect(L.stepRule(led.steps[2])).toMatch(/measured evidence/)
    expect(L.stepRule(led.steps[0])).toMatch(/you confirm/)
  })
  it('mirror counter equals the glasses counter (1-based, bullet for measured, OK when confirmed)', () => {
    const h = (o) => ({ step: { index: 2, count: 8, step_id: 'x', check: 'manual', confirmed: false, ...o } })
    expect(L.counterText(h({}))).toBe('3/8')
    expect(L.counterText(h({ check: 'measured' }))).toBe('● 3/8')
    expect(L.counterText(h({ confirmed: true }))).toBe('3/8 OK')
    expect(L.counterText({ step: null })).toBe('')
    expect(L.counterText(fx('state_playbook_completed').hud)).toBe('4/4 OK')
  })
})

describe('sources and provenance', () => {
  it('collects cites per source with location, deep link and the step they belong to', () => {
    const c = L.collectCites(shelf)
    expect(c.video[0]).toMatchObject({ loc: 't=00:12:34', url: 'https://example.com/watch?v=FIXTURE&t=754s', stepId: 'cams' })
    expect(L.isTimestampLoc(c.video[0].loc)).toBe(true)
    expect(L.isTimestampLoc('page 3, figure 2')).toBe(false)
    expect(c.leaflet[0].loc).toBe('page 3, figure 2')
    expect(c.repo[0].url).toMatch(/#L10-L18$/)
    expect(Object.keys(L.collectCites(lens)).sort()).toEqual(['picam_docs', 'station_spec'])
  })
  it('every source kind in the fixtures is a contract EvidenceLabel the badge knows', () => {
    const kinds = new Set([...shelf.sources, ...led.sources].map((s) => s.kind))
    expect([...kinds].sort()).toEqual(['AUTHORED PROJECT SPEC', 'GITHUB SOURCE', 'MANUFACTURER DOC', 'VIDEO TUTORIAL', 'WEB TUTORIAL'])
  })
  it('provenance wording keeps AUTHORED and AI-EXTRACTED distinct', () => {
    expect(L.provenanceNote('AI-EXTRACTED · HUMAN-REVIEWED')).toMatch(/AI.*reviewed by a human/)
    expect(L.provenanceNote('AUTHORED DEMO METADATA')).toMatch(/not extracted/)
    expect(shelf.provenance).toBe('AI-EXTRACTED · HUMAN-REVIEWED')
    expect(led.provenance).toBe('AUTHORED DEMO METADATA')
  })
})

describe('/ask', () => {
  it('accepts the contract shape, with or without a glasses answer', () => {
    expect(L.normalizeAsk({ answer: { line1: 'QUARTER TURN', line2: '' }, text: 'A quarter turn is enough.', intent: 'faq' })).toEqual({ ok: true, answer: { line1: 'QUARTER TURN', line2: '' }, text: 'A quarter turn is enough.', intent: 'faq' })
    expect(L.normalizeAsk({ answer: null, text: 'Not in this card.', intent: 'unknown' })).toMatchObject({ ok: true, answer: null })
  })
  it('rejects malformed bodies instead of inventing an answer', () => {
    expect(L.normalizeAsk(null).ok).toBe(false)
    expect(L.normalizeAsk({ answer: null }).ok).toBe(false)
    expect(L.normalizeAsk({ answer: 'x', text: 'y' }).ok).toBe(false)
  })
  it('404 is reported as not available, never as an answer', () => {
    expect(L.askError(404)).toMatch(/NOT AVAILABLE.*no POST \/ask.*Nothing was answered/)
    expect(L.askError(500, 'boom')).toMatch(/HTTP 500 boom/)
    expect(L.askError(0)).toMatch(/could not reach core/)
  })
})

describe('/research/request', () => {
  const base = { v: 2, session_id: 's', status: 'unsupported', mode: 'build', cue: { line1: 'NOT SUPPORTED YET' }, detail: '', alternatives: [] }
  it('queued request says saved for async research, not available now', () => {
    const o = L.researchOutcome({ ...base, research_queued: true })
    expect(o.kind).toBe('queued')
    expect(o.headline).toBe('saved for async research — not available now')
    expect(o.headline).toBe(L.NOT_AVAILABLE)
  })
  it('never implies availability: not queued and supported are distinct and honest', () => {
    expect(L.researchOutcome({ ...base, research_queued: false }).headline).toMatch(/not available now/)
    const s = L.researchOutcome({ ...base, status: 'supported', card_id: 'c', task_title: 'T' })
    expect(s.kind).toBe('supported')
    expect(L.researchOutcome(null).kind).toBe('error')
  })
  it('404 on the endpoint is reported honestly', () => {
    expect(L.researchError(404)).toMatch(/NOT AVAILABLE.*Nothing was saved/)
  })
  it('the fixture resolutions are queued/unsupported as advertised', () => {
    expect(L.researchOutcome(fx('goal_resolution_unsupported_research')).kind).toBe('queued')
    expect(fx('goal_resolution_unsupported_research').alternatives.length).toBeGreaterThan(0)
  })
})
