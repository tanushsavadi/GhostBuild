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
      <p class="sub">Look at the glasses. This screen is only status.</p>
      <dl id="gb-stat"></dl>
      <form id="gb-form">
        <label for="gb-url">Backend</label>
        <input id="gb-url" inputmode="url" autocomplete="off" autocapitalize="off" spellcheck="false" />
        <button type="submit">Save and reconnect</button>
        <p id="gb-msg" class="msg"></p>
      </form>
    </main>`
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
