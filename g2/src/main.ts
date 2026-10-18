import { waitForEvenAppBridge } from '@evenrealities/even_hub_sdk'
import { Controller } from './controller'
import { ConnectionManager } from './conn'
import { GestureRouter } from './gestures'
import { ImageLoader } from './image'
import { Renderer } from './renderer'
import { createVoice } from './voice'
import { registerBackgroundState } from './bgstate'
import { K, adoptSession, loadIdentity, makeStorage } from './session'
import { normalizeBackend, readFlags, resolveBackend, resolveCenterCols, resolveGlyphTier, resolveSurface } from './config'
import { blankView } from './view'
import { bindPhoneUi } from './phone'
import { log, type ConnStatus } from './types'

const bridge = await waitForEvenAppBridge()

const env = import.meta.env
const params = new URLSearchParams(location.search)
let win: Storage | null = null
try { win = window.localStorage } catch { win = null }
const kv = makeStorage(bridge, win)

// --- configuration -------------------------------------------------------------------------------------------
const queryBackend = normalizeBackend(params.get('backend'))
if (queryBackend) await kv.set(K.backend, queryBackend)
let backend = resolveBackend(params.get('backend'), await kv.get(K.backend), env)
const flags = readFlags(env)
const surface = resolveSurface(params.get('surface'))
const identity = await loadIdentity(kv)
let sessionId = identity.sessionId
log(`backend=${backend} surface=${surface} client=${identity.clientId} session=${sessionId} voice=${flags.voice}`)

// --- pieces --------------------------------------------------------------------------------------------------
const loader = new ImageLoader({ backend: () => backend })
const renderer = new Renderer(bridge, loader)
const voice = createVoice(flags.voice)
let status: ConnStatus = 'connecting'

const controller: Controller = new Controller({
  render: (v) => void renderer.render(v),
  sendInput: (i) => conn.sendInput(i),
  rehello: () => conn.sendHello(),
  exit: () => void bridge.shutDownPageContainer(1), // double press: system exit dialog. Never sent to the backend.
  surface: () => surface,
  voice: flags.voice ? voice : undefined,
  viewOptions: { centerCols: resolveCenterCols(env), glyphTier: resolveGlyphTier(env) },
  onFrameRendered: () => ui.refresh(),
})

const conn: ConnectionManager = new ConnectionManager({
  backend: () => backend,
  clientId: () => identity.clientId,
  sessionId: () => sessionId,
  surface: () => surface,
  afterSeq: () => controller.lastSeq,
  onMessage: (m) => {
    void adoptSession(kv, sessionId, m).then((id) => { sessionId = id })
    controller.onMessage(m)
  },
  onHealth: (ok) => { controller.onHealth(ok); ui.refresh() },
  onStatus: (s) => { status = s; ui.refresh() },
})

const ui = bindPhoneUi({
  getState: () => ({ backend, status, lastSeq: controller.lastSeq, offline: controller.isOfflineShown, metrics: renderer.lastMetrics, sessionId, clientId: identity.clientId, surface }),
  setBackend: async (raw) => {
    const n = normalizeBackend(raw)
    if (!n) return false
    backend = n
    await kv.set(K.backend, n)
    conn.reconnectNow()
    ui.refresh()
    return true
  },
})

// Background/foreground: relies on setLocalStorage (see session.ts); the host-snapshot API is not in SDK 0.0.16.
registerBackgroundState('hud', () => ({ sessionId, backend }), (saved) => {
  if (typeof saved.sessionId === 'string') sessionId = saved.sessionId
  if (typeof saved.backend === 'string' && normalizeBackend(saved.backend)) backend = saved.backend
})

// --- glasses page + events -----------------------------------------------------------------------------------
const ok = await renderer.init(blankView())
log(`page created: ${ok ? 'success' : 'FAILED'}`)

const router = new GestureRouter()
let cleaned = false
function cleanup(): void {
  if (cleaned) return
  cleaned = true
  unsubscribe()
  conn.stop()
  controller.dispose()
}

const unsubscribe = bridge.onEvenHubEvent((event) => {
  const a = router.route(event)
  if (a.kind === 'lifecycle') {
    switch (a.event) {
      case 'foreground_enter':
        void renderer.forceRefresh()
        conn.reconnectNow() // re-hello with the stored session id
        break
      case 'foreground_exit':
        void kv.set(K.sessionId, sessionId)
        break
      default: // abnormal_exit | system_exit
        cleanup()
    }
    return
  }
  controller.onAction(a)
})

window.addEventListener('beforeunload', cleanup)

controller.boot()
conn.start()

;(window as unknown as Record<string, unknown>).__ghostbuild = { controller, conn, renderer }
log('ready') // marker for simulator automation (poll /api/console for this line)
