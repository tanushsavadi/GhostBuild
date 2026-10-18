// Pure-logic tests for the CREAO additions in web/logic.js. Run: node --test web/tests/creao-logic.test.mjs
// (also run by knowledge/tests/test_web_creao_logic.py so `make test` covers it). Fixtures are MOCK data, not real CREAO output.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { readFileSync } from 'node:fs'

const L = createRequire(import.meta.url)('../logic.js')
const fx = (n) => JSON.parse(readFileSync(new URL(`../fixtures/${n}.json`, import.meta.url), 'utf8'))

test('nothing new is shown unless core says creao is enabled', () => {
  assert.equal(L.creaoEnabled(null), false)
  assert.equal(L.creaoEnabled({}), false)
  assert.equal(L.creaoEnabled({ enabled: 'true' }), false)
  assert.equal(L.creaoEnabled({ enabled: false, reason: 'GB_CREAO is not 1' }), false)
  assert.equal(L.creaoEnabled(fx('research_status_enabled')), true)
})

test('buildRunBody: goal required, http(s) links only, optional fields omitted when empty', () => {
  assert.equal(L.buildRunBody({ goal: '   ' }).ok, false)
  const bad = L.buildRunBody({ goal: 'x', docUrls: 'javascript:alert(1)\nhttps://ok.example/a' })
  assert.equal(bad.ok, false)
  assert.match(bad.errors.join(' '), /http\(s\)/)
  assert.equal(L.buildRunBody({ goal: 'x', videoUrls: 'ftp://v.example' }).ok, false)
  const ok = L.buildRunBody({ goal: ' replace a tube ', device: '', model: ' E5 ', intent: 'build', docUrls: 'https://a.example/x, https://b.example/y', videoUrls: '\nhttps://youtu.be/abc', followUp: ' ', sessionId: 's-1' })
  assert.deepEqual(ok.body, { goal: 'replace a tube', model: 'E5', intent: 'build', doc_urls: ['https://a.example/x', 'https://b.example/y'], video_urls: ['https://youtu.be/abc'], session_id: 's-1' })
  assert.equal(L.buildRunBody({ goal: 'x', docUrls: Array(6).fill('https://a.example').join(' ') }).ok, false)
})

test('run status chips: a draft is never shown as approved or available', () => {
  const runs = fx('research_runs').runs
  const by = Object.fromEntries(runs.map((r) => [r.run_id, L.runStatus(r)]))
  assert.match(by['r-demo1'].label, /DRAFT/)
  assert.doesNotMatch(by['r-demo1'].label, /APPROVED/)
  assert.equal(by['r-demo2'].kind, 'bad')
  assert.equal(by['r-demo3'].active, true)
  assert.equal(L.anyActive(runs), true)
  assert.equal(L.anyActive(runs.filter((r) => r.status !== 'running')), false)
  assert.match(L.runStatus({ status: 'draft_ready', approved_by: 'Ada' }).label, /APPROVED by Ada/)
  assert.equal(L.runStatus({ status: 'failed' }).kind, 'bad')
})

test('draft preview: steps, source kinds, timestamps, uncertainties', () => {
  const v = L.draftView(fx('research_run_r-demo1').draft)
  assert.equal(v.steps.length, 6)
  assert.ok(v.steps.every((s) => s.check === 'you confirm it'), 'manual steps by default')
  assert.deepEqual(v.sources.map((s) => s.kind), ['MANUFACTURER DOC', 'VIDEO TUTORIAL', 'WEB TUTORIAL'])
  assert.deepEqual(v.timestamps.map((t) => t.loc), ['t=00:04:20'])
  assert.match(v.timestamps[0].url, /t=260s$/)
  assert.ok(v.uncertainties.some((u) => u.startsWith('Hold time differs by model')))
  assert.equal(v.validationOk, true)
  assert.notEqual(v.provenance, 'AI-EXTRACTED · HUMAN-REVIEWED')
  assert.notEqual(v.provenance, 'AUTHORED DEMO METADATA')
  assert.equal(L.draftView(null), null)
})

test('visual references are always reference-only; no picture is implied', () => {
  const v = L.draftView(fx('research_run_r-demo1').draft)
  assert.equal(v.hasPictures, false)
  assert.ok(v.references.length >= 2)
  assert.ok(v.references.every((r) => r.note === 'reference only — no picture on glasses'))
  assert.equal(L.REFERENCE_ONLY, 'reference only — no picture on glasses')
  // a non-http url is dropped, not linked
  const odd = L.draftView({ visual_references: [{ view: 'how', url: 'javascript:alert(1)', description: 'd' }], sources: [{ kind: 'WEB TUTORIAL', title: 't', url: 'javascript:x' }] })
  assert.equal(odd.references[0].url, null)
  assert.equal(odd.sources[0].url, null)
})

test('canApprove needs a validating draft, a reviewer and a token', () => {
  const rec = fx('research_run_r-demo1')
  assert.equal(L.canApprove(rec, '', 'tok').ok, false)
  assert.equal(L.canApprove(rec, 'Ada', '  ').ok, false)
  assert.equal(L.canApprove(rec, 'Ada', 'tok').ok, true)
  assert.equal(L.canApprove({ ...rec, approved_by: 'Bo' }, 'Ada', 'tok').ok, false)
  assert.equal(L.canApprove({ ...rec, status: 'invalid' }, 'Ada', 'tok').ok, false)
  assert.equal(L.canApprove({ ...rec, draft: { ...rec.draft, validation: { ok: false, errors: ['x'] } } }, 'Ada', 'tok').ok, false)
  assert.equal(L.canApprove(fx('research_run_r-demo2'), 'Ada', 'tok').ok, false)
})

test('error texts never claim success and never echo the token', () => {
  assert.match(L.runError(503, ''), /disabled/)
  assert.match(L.runError(429, '{"detail":"a research run is already active; wait for it to finish"}'), /already active/)
  assert.match(L.runError(0, ''), /Could not reach core/)
  assert.match(L.approveError(401, ''), /NOT APPROVED.*token/)
  assert.match(L.approveError(503, ''), /GB_ADMIN_TOKEN/)
  assert.match(L.approveError(409, '{"detail":"alias clash"}'), /alias clash/)
  assert.match(L.approveError(422, ''), /reviewer/)
  for (const s of [0, 401, 409, 422, 500, 503]) assert.match(L.approveError(s, 'x'), /^NOT APPROVED/)
})

test('fixtures are labelled MOCK and carry no secret-looking key', () => {
  for (const n of ['research_status_enabled', 'research_runs', 'research_run_r-demo1', 'research_run_r-demo2', 'research_run_r-demo3']) {
    const txt = readFileSync(new URL(`../fixtures/${n}.json`, import.meta.url), 'utf8')
    assert.ok(!/capi_[A-Za-z0-9]/.test(txt), n)
  }
  assert.match(JSON.stringify(fx('research_runs')), /MOCK data, not real CREAO output/)
})

test('build vs fix is inferred from the words, never asked', () => {
  assert.equal(L.inferMode('blink an LED on my Pi'), 'build')
  assert.equal(L.inferMode('fold a paper cup'), 'build')
  assert.equal(L.inferMode('my camera view is black'), 'fix')
  assert.equal(L.inferMode("the LED isn't lighting"), 'fix')
  assert.equal(L.inferMode(''), 'build')
})

test('wait text comes from the estimate and is honest when a run is slow', () => {
  assert.equal(L.waitText(null), 'Working on it')
  assert.equal(L.waitText({ remaining_s: 75, over: false }), 'About 75 seconds left')
  assert.equal(L.waitText({ remaining_s: 120, over: false }), 'About 2 minutes left')
  assert.equal(L.waitText({ remaining_s: 5, over: false }), 'Almost there')
  assert.match(L.waitText({ remaining_s: 0, over: true }), /longer than usual/)
})
