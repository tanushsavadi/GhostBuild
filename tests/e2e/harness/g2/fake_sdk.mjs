// Stand-in for @evenrealities/even_hub_sdk 0.0.16, ONLY the surface g2/src/main.ts uses.
// Enum values copied from node_modules/@evenrealities/even_hub_sdk/dist/index.d.ts (0.0.16).
// It records every call into globalThis.__gbHarness. It proves nothing about real G2 rendering, BLE, or mic.
const H = () => globalThis.__gbHarness

export const OsEventTypeList = {
  CLICK_EVENT: 0, SCROLL_TOP_EVENT: 1, SCROLL_BOTTOM_EVENT: 2, DOUBLE_CLICK_EVENT: 3,
  FOREGROUND_ENTER_EVENT: 4, FOREGROUND_EXIT_EVENT: 5, ABNORMAL_EXIT_EVENT: 6, SYSTEM_EXIT_EVENT: 7,
  IMU_DATA_REPORT: 8, LONG_PRESS_EVENT: 9, LONG_PRESS_RELEASE_EVENT: 10,
}
export const AudioInputSource = { Glasses: 'glasses', Phone: 'phone' }

export class TextContainerProperty { constructor(o) { Object.assign(this, o) } }
export class CreateStartUpPageContainer { constructor(o) { Object.assign(this, o) } }
export class TextContainerUpgrade { constructor(o) { Object.assign(this, o) } }

const bridge = {
  async createStartUpPageContainer(c) {
    const content = c.textObject?.[0]?.content ?? ''
    H().shown = content
    H().upgrades.push({ at: Date.now(), content })
    return 0
  },
  textContainerUpgrade(u) {
    H().shown = u.content
    H().upgrades.push({ at: Date.now(), content: u.content })
    return Promise.resolve(true)
  },
  onEvenHubEvent(cb) {
    H().listeners.push(cb)
    return () => { H().listeners = H().listeners.filter((x) => x !== cb) }
  },
  shutDownPageContainer(n) { H().shutdowns.push(n) },
  async audioControl(on, source) {
    H().audioControl.push({ at: Date.now(), on, source: source ?? null })
    const mode = H().micMode
    if (on && mode === 'throw') throw new Error('mic unavailable (harness)')
    if (on && mode === 'fail') return false
    return true
  },
}

export async function waitForEvenAppBridge() { return bridge }
