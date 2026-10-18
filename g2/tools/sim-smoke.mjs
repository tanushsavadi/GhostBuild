#!/usr/bin/env node
// Simulator walk-through against the stub backend. NOT hardware proof.
//   1. node tools/stub-server.mjs
//   2. npx vite --port 5173
//   3. npx evenhub-simulator "http://localhost:5173/?surface=simulator&backend=http://localhost:8787" --automation-port 9898
//   4. node tools/sim-smoke.mjs <out-dir>        (stub must be on a fresh session: restart it or POST /admin/reset first)
import { mkdirSync, writeFileSync } from 'node:fs'

const SIM = process.env.SIM ?? 'http://127.0.0.1:9898'
const STUB = process.env.STUB ?? 'http://127.0.0.1:8787'
const out = process.argv[2] ?? 'sim-shots'
mkdirSync(out, { recursive: true })
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const input = (action) => fetch(`${SIM}/api/input`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action }) }).then((r) => r.text())
const state = () => fetch(`${STUB}/admin/state`).then((r) => r.json())
const shot = async (name) => {
  const r = await fetch(`${SIM}/api/screenshot/glasses`)
  writeFileSync(`${out}/${name}.png`, Buffer.from(await r.arrayBuffer()))
  console.log('shot', name, (await state()).phase)
}
const consoleLog = async () => (await fetch(`${SIM}/api/console`).then((r) => r.json())).entries.map((e) => `${e.level}: ${e.message}`)

console.log('ping', await fetch(`${SIM}/api/ping`).then((r) => r.text()))
for (let i = 0; i < 40 && !(await consoleLog()).some((l) => l.includes('[ghostbuild] ready')); i++) await sleep(250)
await sleep(1500)
await shot('01-menu')
await input('down'); await sleep(600); await shot('02-menu-build-selected')
await input('up'); await sleep(600)
await input('click'); await sleep(800); await shot('03-intervene')
await input('click'); await sleep(1500); await shot('04-visual-where')
await input('down'); await sleep(1500); await shot('05-visual-how')
await input('down'); await sleep(1500); await shot('06-visual-correct')
await input('click'); await sleep(1000); await shot('07-back-to-cue')
await fetch(`${STUB}/admin/fix`, { method: 'POST' }); await sleep(700); await shot('08-verified')
await sleep(3500); await shot('09-quiet-blank')
console.log('--- plugin console ---')
console.log((await consoleLog()).filter((l) => l.includes('ghostbuild') || l.startsWith('error')).join('\n'))
