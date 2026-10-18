#!/usr/bin/env node
// Simulator walk-through of the PLAYBOOK flow against the stub (--flow playbook). NOT hardware proof, NOT real core.
//   1. node tools/stub-server.mjs --flow playbook
//   2. npx vite --port 5173
//   3. npx evenhub-simulator "http://localhost:5173/?surface=simulator&backend=http://localhost:8787" --automation-port 9898
//   4. node tools/sim-playbook.mjs <out-dir>        (stub must be on a fresh session: restart it or POST /admin/reset first)
// Asserts the stub's phase after every input (the stub echoes the plugin's real G2Input) and saves a screenshot per frame.
import { mkdirSync, writeFileSync } from 'node:fs'

const SIM = process.env.SIM ?? 'http://127.0.0.1:9898'
const STUB = process.env.STUB ?? 'http://127.0.0.1:8787'
const out = process.argv[2] ?? 'sim-shots'
mkdirSync(out, { recursive: true })
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const input = (action) => fetch(`${SIM}/api/input`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action }) }).then((r) => r.text())
const state = () => fetch(`${STUB}/admin/state`).then((r) => r.json())
const consoleLog = async () => (await fetch(`${SIM}/api/console`).then((r) => r.json())).entries.map((e) => `${e.level}: ${e.message}`)
let failed = 0
async function shot(name, expectPhase, expectCue) {
  await sleep(900)
  const r = await fetch(`${SIM}/api/screenshot/glasses`)
  writeFileSync(`${out}/${name}.png`, Buffer.from(await r.arrayBuffer()))
  const st = await state()
  const ok = (!expectPhase || st.phase === expectPhase) && (!expectCue || (st.current?.cue?.line1 ?? '') === expectCue)
  if (!ok) failed++
  console.log(ok ? 'PASS' : 'FAIL', name, `phase=${st.phase} mode=${st.current?.mode} cue=${JSON.stringify(st.current?.cue?.line1)} step=${JSON.stringify(st.current?.step ?? null)}`, ok ? '' : `(expected phase=${expectPhase} cue=${expectCue})`)
}

console.log('ping', await fetch(`${SIM}/api/ping`).then((r) => r.text()))
for (let i = 0; i < 40 && !(await consoleLog()).some((l) => l.includes('[ghostbuild] ready')); i++) await sleep(250)
await sleep(1500)
await shot('01-menu-2-options', 'menu')
await input('click'); await shot('02-chooser-3-options', 'chooser')
await input('down'); await shot('03-chooser-second-selected', 'chooser')
await input('up')
await input('click'); await shot('04-step-1-of-4-manual', 'step', 'PREPARE THE PARTS')
await input('click'); await sleep(1200); await shot('05-step-1-picture-where', 'picture')
await input('down'); await sleep(1200); await shot('06-step-1-picture-how', 'picture')
await input('click'); await shot('07-back-to-step-1', 'step', 'PREPARE THE PARTS')
await input('down'); await shot('08-step-2-of-4-manual', 'step', 'PLACE PART ON BOARD')
await input('down'); await shot('09-step-3-of-4-measured', 'step', 'CHECK THE CONNECTION')
await input('down'); await shot('10-swipe-does-not-advance-measured', 'step', 'CHECK THE CONNECTION')
await input('click'); await shot('11-not-met-yet', 'step-notmet', 'NOT MET YET')
await sleep(2600)
await fetch(`${STUB}/admin/fix`, { method: 'POST' }); await shot('12-check-passed', 'step-passed', '● CHECK PASSED')
await sleep(2700); await shot('13-step-4-of-4', 'step', 'CLOSE THE COVER')
await input('down'); await shot('14-completion-you-confirmed', 'done')
await sleep(3300); await shot('15-quiet-blank', 'quiet')
console.log('--- plugin console (filtered) ---')
console.log((await consoleLog()).filter((l) => l.includes('ghostbuild') || l.startsWith('error')).join('\n'))
console.log(failed ? `${failed} FAILED` : 'ALL PHASES AS EXPECTED')
process.exit(failed ? 1 : 0)
