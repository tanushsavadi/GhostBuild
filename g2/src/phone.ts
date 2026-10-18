import type { ConnStatus } from './types'
import type { ImageMetrics } from './renderer'

export interface PhoneState {
  backend: string
  status: ConnStatus
  lastSeq: number
  offline: boolean
  metrics: ImageMetrics | null
  sessionId: string | null
  clientId: string
  surface: string
}

export interface PhoneUi {
  refresh(): void
}

/** Tiny phone-side companion screen: honest connection status + backend URL override. */
export function bindPhoneUi(h: { getState(): PhoneState; setBackend(raw: string): Promise<boolean> }): PhoneUi {
  const app = document.querySelector<HTMLDivElement>('#app')
  if (!app) return { refresh() {} }
  app.innerHTML = `
    <main class="gb">
      <h1>GhostBuild</h1>
      <p class="sub">Quiet guidance. Help when you need it.</p>
      <a id="gb-companion" class="primary" target="_blank" rel="noopener noreferrer">Open companion</a>
      <p class="sub">Enter a task, see sources, or ask a question on your phone.</p>
      <details><summary>Glasses controls</summary>
        <p>Press for a picture. Swipe to explore. Press again to return.</p>
        <p>On a manual step, swipe down deliberately to confirm. Measured checks need real evidence. Double press opens the system exit dialog.</p>
        <p>Optional hold-to-talk sends audio through your backend to ElevenLabs after consent. GhostBuild does not save recordings. Touch and phone text always work without a microphone.</p>
      </details>
      <details><summary>Connection settings</summary>
      <dl id="gb-stat"></dl>
      <form id="gb-form">
        <label for="gb-url">Backend</label>
        <input id="gb-url" inputmode="url" autocomplete="off" autocapitalize="off" spellcheck="false" />
        <button type="submit">Save and reconnect</button>
        <p id="gb-msg" class="msg"></p>
      </form>
      </details>
    </main>`
  const companion = app.querySelector<HTMLAnchorElement>('#gb-companion')!
  const stat = app.querySelector<HTMLElement>('#gb-stat')!
  const input = app.querySelector<HTMLInputElement>('#gb-url')!
  const msg = app.querySelector<HTMLElement>('#gb-msg')!
  input.value = h.getState().backend
  app.querySelector<HTMLFormElement>('#gb-form')!.addEventListener('submit', async (e) => {
    e.preventDefault()
    const ok = await h.setBackend(input.value)
    msg.textContent = ok ? 'Saved.' : 'Use a full http(s) URL, e.g. http://192.168.1.20:8787'
  })
  const row = (k: string, v: string) => `<dt>${k}</dt><dd>${v.replace(/[<>&]/g, '')}</dd>`
  return {
    refresh() {
      const s = h.getState()
      const m = s.metrics
      companion.href = `${s.backend.replace(/\/+$/, '')}/phone/`
      stat.innerHTML =
        row('Backend', s.backend) +
        row('Link', s.status === 'ws' ? 'websocket' : s.status === 'poll' ? 'polling' : s.status === 'down' ? 'DOWN' : 'connecting') +
        row('Glasses', s.offline ? 'GHOSTBUILD OFFLINE' : 'showing server frame') +
        row('Last frame seq', String(s.lastSeq)) +
        row('Surface', s.surface) +
        row('Session', s.sessionId ?? 'none yet') +
        row('Last picture', m ? `${m.result} ${m.totalMs} ms (fetch ${m.fetchMs}, send ${m.sendMs})` : 'none')
    },
  }
}
