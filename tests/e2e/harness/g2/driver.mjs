// Hosts the bundled G2 plugin in Node with browser-like globals, driven over stdin/stdout JSON lines.
//   node driver.mjs --bundle=<plugin.mjs> --core=http://127.0.0.1:PORT [--ws=normal|blocked]
// Network is real (Node fetch / WebSocket to the real core); only the Even SDK bridge is faked.
import readline from 'node:readline'
import { pathToFileURL } from 'node:url'

const args = Object.fromEntries(process.argv.slice(2).map((a) => {
  const [k, ...v] = a.replace(/^--/, '').split('=')
  return [k, v.join('=')]
}))

const H = (globalThis.__gbHarness = {
  shown: null, upgrades: [], statuses: [], listeners: [], shutdowns: [], audioControl: [],
  micMode: 'ok', fetches: [], polls: 0, wsCreated: 0, wsOpened: 0, wsSends: [], wsFrames: 0,
  rejections: [], netDown: false, sockets: new Set(),
})

// Browser: unhandled promise rejections are logged, not fatal. Record them instead of crashing Node.
process.on('unhandledRejection', (e) => H.rejections.push(String(e?.message ?? e)))

globalThis.location = new URL(`http://127.0.0.1:5173/?core=${encodeURIComponent(args.core)}`)
const phone = {
  set textContent(v) { H.statuses.push({ at: Date.now(), text: v }) },
  get textContent() { return H.statuses.at(-1)?.text ?? '' },
}
globalThis.document = { getElementById: (id) => (id === 'app' ? phone : null) }

const realFetch = globalThis.fetch
globalThis.fetch = async (url, init = {}) => {
  const u = String(url)
  if (u.endsWith('/state')) H.polls++
  else {
    const b = init.body
    H.fetches.push({ at: Date.now(), url: u.replace(args.core, ''), method: init.method ?? 'GET',
      bodyLen: b == null ? 0 : (b.length ?? b.byteLength ?? 0), body: typeof b === 'string' ? b : null })
  }
  if (H.netDown) throw new TypeError('fetch failed (harness: network down)')
  return realFetch(url, init)
}

const RealWS = globalThis.WebSocket
class HarnessWS {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3
  constructor(url) {
    H.wsCreated++
    this.readyState = 0
    this.onopen = this.onmessage = this.onclose = this.onerror = null
    if (args.ws === 'blocked' || H.netDown) {
      setTimeout(() => { this.readyState = 3; this.onclose?.({ code: 1006 }) }, 20)
      return
    }
    const ws = (this._ws = new RealWS(url))
    H.sockets.add(this)
    ws.onopen = () => { this.readyState = 1; H.wsOpened++; this.onopen?.({}) }
    ws.onmessage = (m) => { H.wsFrames++; this.onmessage?.({ data: m.data }) }
    const closed = () => {
      if (this.readyState === 3) return
      this.readyState = 3
      H.sockets.delete(this)
      this.onclose?.({ code: 1006 })
    }
    // Browsers always follow a failed connect's `error` with `close`; Node 22's WebSocket fires only `error`
    // on ECONNREFUSED and stays CONNECTING, which would fake a hang the WebView does not have.
    ws.onerror = closed
    ws.onclose = closed
  }
  send(d) { H.wsSends.push({ at: Date.now(), msg: JSON.parse(d) }); this._ws.send(d) }
  close() { this._ws?.close() }
}
globalThis.WebSocket = HarnessWS

function emit(event) { for (const cb of [...H.listeners]) cb(event) }

function pcm(bytes, enc) {
  const u8 = new Uint8Array(bytes)
  for (let i = 0; i < bytes; i++) u8[i] = (i * 37) & 0xff
  if (enc === 'array') return Array.from(u8)
  if (enc === 'base64') return Buffer.from(u8).toString('base64')
  return u8
}

function snapshot() {
  return {
    shown: H.shown, upgrades: H.upgrades, status: phone.textContent, statuses: H.statuses.map((s) => s.text),
    fetches: H.fetches, polls: H.polls, wsCreated: H.wsCreated, wsOpened: H.wsOpened, wsSends: H.wsSends,
    wsFrames: H.wsFrames, audioControl: H.audioControl, shutdowns: H.shutdowns, rejections: H.rejections,
    now: Date.now(),
  }
}

const ops = {
  snapshot: () => null,
  tap: () => emit({ sysEvent: {} }), // CLICK_EVENT = 0 is omitted by protobuf: eventType undefined
  text_tap: () => emit({ textEvent: { containerID: 1 } }),
  double_tap: () => emit({ sysEvent: { eventType: 3 } }),
  long_press: () => emit({ sysEvent: { eventType: 9 } }),
  release: () => emit({ sysEvent: { eventType: 10 } }),
  audio: (o) => emit({ audioEvent: { audioPcm: pcm(o.bytes, o.enc ?? 'u8') } }),
  mic: (o) => { H.micMode = o.mode },
  net: (o) => {
    H.netDown = !!o.down
    if (o.down) for (const s of [...H.sockets]) s.close()
  },
  drop_ws: () => { for (const s of [...H.sockets]) s.close() },
}

const rl = readline.createInterface({ input: process.stdin })
rl.on('line', async (line) => {
  const req = JSON.parse(line)
  let error = null
  try { await ops[req.op](req) } catch (e) { error = String(e?.stack ?? e) }
  process.stdout.write(JSON.stringify({ id: req.id, error, snap: snapshot() }) + '\n')
})

await import(pathToFileURL(args.bundle).href)
process.stdout.write(JSON.stringify({ id: 'ready', error: null, snap: snapshot() }) + '\n')
