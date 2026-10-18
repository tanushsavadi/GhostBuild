// Exercises the polling fallback against a REAL backend (core or stub): WebSocket is forced to fail.
//   npx vite-node tools/poll-check.mts [http://localhost:8787]
import { ConnectionManager } from '../src/conn'
import { Controller } from '../src/controller'

const backend = process.argv[2] ?? 'http://localhost:8787'
let session: string | null = null
const shown: string[] = []
const ctl = new Controller({
  render: (v) => shown.push(JSON.stringify(v.text)),
  sendInput: (i) => cm.sendInput(i),
  rehello: () => cm.sendHello(),
  exit: () => {},
  surface: () => 'simulator',
})
const cm = new ConnectionManager({
  backend: () => backend,
  clientId: () => 'poll-check',
  sessionId: () => session,
  surface: () => 'simulator',
  afterSeq: () => ctl.lastSeq,
  onMessage: (m) => { const s = (m as { session_id?: string }).session_id; if (s) session = s; ctl.onMessage(m) },
  onHealth: (h) => { console.log('health', h); ctl.onHealth(h) },
  onStatus: (s) => console.log('status', s),
  makeWs: () => { throw new Error('ws blocked (forced)') },
  wsFallbackMs: 4000,
})
ctl.boot()
cm.start()
const t0 = Date.now()
setTimeout(() => { console.log(`t+${Date.now() - t0}ms sending press`); cm.sendInput({ type: 'g2_input', v: 2, gesture: 'press', seq_seen: ctl.lastSeq, surface: 'simulator' }) }, 6500)
setTimeout(() => { console.log('rendered:', shown.join(' | ')); console.log('session', session, 'status', cm.status); cm.stop(); ctl.dispose(); process.exit(0) }, 9000)
