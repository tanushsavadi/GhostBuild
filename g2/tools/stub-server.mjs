#!/usr/bin/env node
// GhostBuild G2 stub backend: lets the plugin run in evenhub-simulator (or on the glasses) BEFORE core exists.
//   node tools/stub-server.mjs [--port 8787] [--fix-after-ms 0] [--flow repair|playbook]
// Serves: WS /ws?role=g2 · GET /hud?after=N · POST /hello · POST /input · GET /guides/<id>/<view>.png · GET /health
//         POST /admin/fix (physical-fix stand-in) · POST /admin/reset · POST /admin/frame (push a raw frame) · GET /admin/state
// Scripted flow: new session -> welcome (ttl 2.5 s) -> menu -> [press] intervene -> [press] picture WHERE ->
//   [swipe down] HOW -> CORRECT -> [swipe up/press] back ... -> /admin/fix -> verified (ttl 3 s) -> quiet.
// --flow playbook (generic sample task, no device facts): welcome -> menu (2) -> [press] chooser (3 options) -> [press] step 1/4 manual
//   -> [press] picture (WHERE, swipe for HOW, press/swipe up = back) -> [swipe down = confirm] step 2/4 -> [swipe down] measured step 3/4
//   -> [press = recheck] NOT MET YET -> [POST /admin/fix or stdin "f" = measured evidence] CHECK PASSED -> step 4/4 -> [swipe down]
//   completion (you confirmed) -> quiet. swipe up goes back one step.
// Every frame is source "simulated" and labelled so on screen. This is NOT hardware proof and NOT live data.
import http from 'node:http'
import { createHash } from 'node:crypto'
import { WebSocketServer } from 'ws'
import { stubGuidePng } from './png.mjs'
import * as F from './stub-frames.mjs'

const arg = (name, dflt) => {
  const i = process.argv.indexOf(`--${name}`)
  return i > 0 ? process.argv[i + 1] : dflt
}
const PORT = Number(arg('port', process.env.PORT ?? 8787))
const FIX_AFTER_MS = Number(arg('fix-after-ms', 0))
const FLOW = arg('flow', process.env.FLOW ?? 'repair')
if (!['repair', 'playbook'].includes(FLOW)) throw new Error(`unknown --flow ${FLOW}`)

const pngs = Object.fromEntries(F.VIEWS.map((v) => [v, stubGuidePng(v)]))
const shas = Object.fromEntries(F.VIEWS.map((v) => [v, createHash('sha256').update(pngs[v]).digest('hex')]))
const pbPngs = Object.fromEntries(F.PB_VIEWS.map((v) => [v, stubGuidePng(v)]))
const pbShas = Object.fromEntries(F.PB_VIEWS.map((v) => [v, createHash('sha256').update(pbPngs[v]).digest('hex')]))

let seq = 0
let current = null
let phase = 'none' // welcome | menu | intervene | visual | verified | quiet
let sid = null
let menuSel = 0
let viewIdx = 0
let stepIdx = 0
let chooserSel = 0
const sessions = new Set()
const clients = new Set()
const timers = new Set()
const log = (...a) => console.log(new Date().toISOString().slice(11, 23), ...a)

const later = (ms, fn) => {
  const t = setTimeout(() => { timers.delete(t); fn() }, ms)
  timers.add(t)
}
const clearTimers = () => { for (const t of timers) clearTimeout(t); timers.clear() }

function publish(make, nextPhase) {
  seq += 1
  current = { ...make(seq), session_id: sid }
  if (nextPhase) phase = nextPhase
  const json = JSON.stringify(current)
  log(`HUD  seq=${current.seq} mode=${current.mode} ${current.cue ? JSON.stringify(current.cue.line1) : '(blank)'}`)
  for (const ws of clients) if (ws.readyState === 1) ws.send(json)
}

function newSession() {
  clearTimers()
  menuSel = 0
  viewIdx = 0
  stepIdx = 0
  chooserSel = 0
  publish(F.welcome, 'welcome')
  later(2500, () => publish((s) => F.menu(s, menuSel), 'menu'))
}

const lastStep = F.PB_STEPS.length - 1
const showStep = (i) => { stepIdx = i; publish((q) => F.step(q, i), 'step') }

function pbVerified() {
  // Measured evidence for the measured step (the stub's stand-in for a real observation). Not a gesture result.
  if (phase !== 'step' && phase !== 'step-notmet') return
  if (F.PB_STEPS[stepIdx].check !== 'measured') return
  clearTimers()
  publish(F.stepPassed, 'step-passed')
  later(2500, () => showStep(stepIdx + 1))
}

function onPlaybookInput(msg) {
  const g = msg.gesture
  if (phase === 'menu') {
    if (g === 'swipe_down' || g === 'swipe_up') { menuSel = (menuSel + 1) % 2; publish((q) => F.menu(q, menuSel)) }
    else if (g === 'press') { chooserSel = 0; publish((q) => F.chooser(q, chooserSel), 'chooser') }
  } else if (phase === 'chooser') {
    const n = F.PB_TASKS.length
    if (g === 'swipe_down') { chooserSel = (chooserSel + 1) % n; publish((q) => F.chooser(q, chooserSel)) }
    else if (g === 'swipe_up') { chooserSel = (chooserSel + n - 1) % n; publish((q) => F.chooser(q, chooserSel)) }
    else if (g === 'press') showStep(0)
  } else if (phase === 'step' || phase === 'step-notmet') {
    const st = F.PB_STEPS[stepIdx]
    if (g === 'swipe_down') {
      if (st.check === 'manual') {
        if (stepIdx === lastStep) { clearTimers(); publish(F.completion, 'done'); later(3000, () => publish(F.quiet, 'quiet')) }
        else showStep(stepIdx + 1)
      } // a measured step never advances on a gesture
    } else if (g === 'swipe_up') { if (stepIdx > 0) showStep(stepIdx - 1) }
    else if (g === 'press') {
      if (st.check === 'measured') {
        publish((q) => F.stepNotMet(q, stepIdx), 'step-notmet') // recheck: evidence not met -> say so, never advance
        later(2500, () => { if (phase === 'step-notmet') showStep(stepIdx) })
      } else if (st.pictureOnPress) { viewIdx = 0; publish((q) => F.stepPicture(q, stepIdx, 0, pbShas.where), 'picture') }
    }
  } else if (phase === 'picture') {
    if (g === 'swipe_down' && viewIdx < F.PB_VIEWS.length - 1) { viewIdx++; publish((q) => F.stepPicture(q, stepIdx, viewIdx, pbShas[F.PB_VIEWS[viewIdx]])) }
    else if (g === 'swipe_up' && viewIdx > 0) { viewIdx--; publish((q) => F.stepPicture(q, stepIdx, viewIdx, pbShas[F.PB_VIEWS[viewIdx]])) }
    else if (g === 'press' || g === 'swipe_up') showStep(stepIdx)
  } else if (phase === 'quiet' && g === 'press') {
    publish(F.status)
    later(3000, () => publish(F.quiet, 'quiet'))
  }
}

function goVerified() {
  if (FLOW === 'playbook') return pbVerified()
  clearTimers()
  publish(F.verified, 'verified')
  later(3000, () => publish(F.quiet, 'quiet'))
}

function onInput(msg) {
  log(`IN   ${JSON.stringify(msg)}`)
  if (FLOW === 'playbook') return onPlaybookInput(msg)
  const g = msg.gesture
  if (phase === 'menu') {
    if (g === 'swipe_down' || g === 'swipe_up') { menuSel = (menuSel + 1) % 2; publish((s) => F.menu(s, menuSel)) }
    else if (g === 'press') {
      publish(F.intervene, 'intervene')
      if (FIX_AFTER_MS > 0) later(FIX_AFTER_MS, goVerified)
    }
  } else if (phase === 'intervene') {
    if (g === 'press') { viewIdx = 0; publish((s) => F.visual(s, 0, shas.where), 'visual') }
  } else if (phase === 'visual') {
    if (g === 'swipe_down' && viewIdx < F.VIEWS.length - 1) { viewIdx++; publish((s) => F.visual(s, viewIdx, shas[F.VIEWS[viewIdx]])) }
    else if (g === 'swipe_up' && viewIdx > 0) { viewIdx--; publish((s) => F.visual(s, viewIdx, shas[F.VIEWS[viewIdx]])) }
    else if (g === 'press' || g === 'swipe_up') publish(F.intervene, 'intervene')
  } else if (phase === 'quiet' && g === 'press') {
    publish(F.status)
    later(3000, () => publish(F.quiet, 'quiet'))
  }
}

function onHello(msg) {
  log(`HELLO ${JSON.stringify(msg)}`)
  if (!msg.session_id || !sessions.has(msg.session_id)) {
    // like core: null/unknown session id -> core creates a session (welcome, then menu) and tells the plugin its id
    // in HudFrame.session_id. A known id resumes the current frame (no welcome).
    sid = 's-' + Math.random().toString(16).slice(2, 10)
    sessions.add(sid)
    newSession()
  }
  return current
}

// -------------------------------------------------------------------------------- HTTP
const cors = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Access-Control-Allow-Private-Network': 'true',
  'Access-Control-Max-Age': '600',
}
const readBody = (req) => new Promise((res) => { let b = ''; req.on('data', (c) => (b += c)); req.on('end', () => res(b)) })
const send = (res, status, body, type = 'application/json') => {
  res.writeHead(status, { ...cors, 'Content-Type': type, 'Cache-Control': 'no-store' })
  res.end(body)
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://x')
  if (req.method === 'OPTIONS') return send(res, 204, '')
  if (url.pathname === '/health') return send(res, 200, JSON.stringify({ ok: true, stub: true, source: 'simulated', g2_clients: clients.size }))
  if (url.pathname === '/hud') {
    const after = Number(url.searchParams.get('after') ?? -1)
    return current && current.seq > after ? send(res, 200, JSON.stringify(current)) : send(res, 204, '')
  }
  if (url.pathname === '/hello' && req.method === 'POST') {
    const f = onHello(JSON.parse((await readBody(req)) || '{}'))
    return f ? send(res, 200, JSON.stringify(f)) : send(res, 204, '')
  }
  if (url.pathname === '/input' && req.method === 'POST') {
    onInput(JSON.parse((await readBody(req)) || '{}'))
    return send(res, 204, '')
  }
  const m = url.pathname.match(/^\/guides\/camera_lens\/(where|how|correct)\.png$/)
  if (m) return send(res, 200, pngs[m[1]], 'image/png')
  const pm = url.pathname.match(new RegExp(`^/guides/${F.PB_GUIDE}/(where|how)\\.png$`))
  if (pm) return send(res, 200, pbPngs[pm[1]], 'image/png')
  if (url.pathname === '/admin/fix' && req.method === 'POST') { goVerified(); return send(res, 204, '') }
  if (url.pathname === '/admin/reset' && req.method === 'POST') { sessions.clear(); sid = null; current = null; phase = 'none'; clearTimers(); return send(res, 204, '') }
  if (url.pathname === '/admin/frame' && req.method === 'POST') { const f = JSON.parse(await readBody(req)); seq = Math.max(seq, f.seq ?? 0); current = f; for (const ws of clients) ws.send(JSON.stringify(f)); return send(res, 204, '') }
  if (url.pathname === '/admin/state') return send(res, 200, JSON.stringify({ phase, seq, current, sessions: [...sessions] }))
  send(res, 404, '{"error":"not found"}')
})

// -------------------------------------------------------------------------------- WebSocket
const wss = new WebSocketServer({ noServer: true })
server.on('upgrade', (req, socket, head) => {
  const u = new URL(req.url, 'http://x')
  if (u.pathname !== '/ws' || u.searchParams.get('role') !== 'g2') return socket.destroy()
  wss.handleUpgrade(req, socket, head, (ws) => wss.emit('connection', ws))
})
wss.on('connection', (ws) => {
  clients.add(ws)
  log(`WS   client connected (${clients.size})`)
  ws.on('message', (data) => {
    let msg
    try { msg = JSON.parse(String(data)) } catch { return log('WS   bad json') }
    if (msg.type === 'g2_hello') {
      const f = onHello(msg)
      if (f && ws.readyState === 1) ws.send(JSON.stringify(f)) // server replies with the current frame
    } else if (msg.type === 'g2_input') onInput(msg)
  })
  ws.on('close', () => { clients.delete(ws); log(`WS   client closed (${clients.size})`) })
})

process.stdin.on('data', (d) => { if (String(d).trim() === 'f') { log('stdin: fix'); goVerified() } })
server.listen(PORT, '0.0.0.0', () => log(`GhostBuild G2 STUB (simulated data, flow ${FLOW}) on :${PORT}  [stdin "f" = physical fix]`))
