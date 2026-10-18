#!/usr/bin/env node
// Official simulator + actual core integration. Use an ISOLATED core: this changes its active task.
// Start core --port 8791, Vite --port 5174, simulator backend=http://localhost:8791 on automation :9899.
// CORE=http://localhost:8791 SIM=http://localhost:9899 npm run sim:core
// No physical task is performed. Confirmations are simulator inputs; no sensor or provider is faked.
import { mkdirSync, writeFileSync } from 'node:fs'

const core = process.env.CORE ?? 'http://127.0.0.1:8791'
const sim = process.env.SIM ?? 'http://127.0.0.1:9899'
const dir = process.env.OUT ?? 'sim-shots/final-real-core'
const scope = 'Official simulator + actual core; no Pi telemetry, provider calls, or physical glasses'
const startedAt = Date.now()
const report = []
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
mkdirSync(dir, { recursive: true })
const result = (data) => writeFileSync(`${dir}/result.json`, JSON.stringify({ scope, startedAt, core, sim, ...data, report }, null, 2))
result({ status: 'RUNNING' })

async function get(path) {
  const res = await fetch(`${core}${path}`)
  if (!res.ok) throw new Error(`${path}: ${res.status}`)
  return res.json()
}
async function post(path, body) {
  const res = await fetch(`${core}${path}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${path}: ${res.status} ${await res.text()}`)
  return res.json()
}
async function input(action) {
  const res = await fetch(`${sim}/api/input`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action }),
  })
  if (!res.ok) throw new Error(`simulator input: ${res.status}`)
}
async function check(name, predicate) {
  // Let the current frame settle before the next deliberate gesture.
  await wait(1800)
  const hud = await get('/hud')
  if (!predicate(hud)) throw new Error(`${name}: ${JSON.stringify(hud)}`)
  const image = await fetch(`${sim}/api/screenshot/glasses`)
  if (!image.ok) throw new Error(`screenshot: ${image.status}`)
  writeFileSync(`${dir}/${name}.png`, Buffer.from(await image.arrayBuffer()))
  report.push({ name, mode: hud.mode, cue: hud.cue, step: hud.step, source: hud.source })
  console.log('PASS', name, hud.mode, hud.cue?.line1)
}

try {
  let session = await get('/session')
  for (let i = 0; session.id === 'none' && i < 40; i++) {
    await wait(250)
    session = await get('/session')
  }
  if (session.id === 'none') throw new Error('simulator not connected; launch it with the same CORE backend')
  const request = (text) => post('/session/goal', { session_id: session.id, mode: 'build', via: 'phone_text', text })
  const first = await request('fold a paper cup')
  if (first.status !== 'supported') throw new Error(`first task: ${JSON.stringify(first)}`)
  await wait(3000)
  await check('01-generic-manual-step', (h) => h.mode === 'step' && h.step?.index === 0 && h.source === 'manual')
  await input('down')
  await check('02-manual-confirm-next', (h) => h.step?.index === 1)
  await input('click')
  await check('03-source-image-where', (h) => h.mode === 'visual' && h.image?.index === 0)
  await input('click')
  await check('04-source-image-how', (h) => h.mode === 'visual' && h.image?.index === 1)
  await input('click')
  await check('05-source-image-correct', (h) => h.mode === 'visual' && h.image?.index === 2)
  await input('click')
  await check('06-return-keeps-step', (h) => h.mode === 'step' && h.step?.index === 1)
  const answer = await post('/ask', { session_id: session.id, text: 'why does this matter' })
  if (!answer.answer || answer.intent !== 'why') throw new Error(`contextual answer: ${JSON.stringify(answer)}`)
  await wait(2600)

  const second = await request('light an led')
  if (second.status !== 'supported' || second.card_id === first.card_id) throw new Error('second distinct generic task did not resolve')
  await wait(3000)
  await check('07-second-generic-task', (h) => h.mode === 'step' && h.step?.index === 0 && h.source === 'manual')
  const stepCount = (await get('/hud')).step.count
  for (let index = 0; index < stepCount; index++) {
    await input('down')
    await check(`08-second-task-confirm-${index + 1}`, (h) => index === stepCount - 1
      ? h.source === 'manual' && /YOU CONFIRMED/.test(h.cue?.line2 ?? '') && !/VERIFIED/.test(h.cue?.line1 ?? '')
      : h.step?.index === index + 1)
  }
  await wait(3300)
  await check('09-completion-becomes-quiet', (h) => h.mode === 'quiet')
  const entries = (await fetch(`${sim}/api/console`).then((r) => r.json())).entries.filter((e) => e.ts >= startedAt)
  const images = entries.filter((e) => e.message.includes('image shown ') && e.message.includes('result=success'))
  if (images.length < 3) throw new Error('expected three actual successful SDK image sends in this run')
  writeFileSync(`${dir}/console.json`, JSON.stringify(entries, null, 2))
  result({ status: 'PASS', first, second, answer, images })
  console.log('PASS: two actual playbooks, three SDK images, contextual answer, manual completion, quiet')
} catch (error) {
  result({ status: 'FAIL', error: String(error) })
  console.error(error)
  process.exitCode = 1
}
