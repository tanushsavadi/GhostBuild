// IMU glue: turn on the glasses' IMU stream, feed the head-shake detector, call back on a shake. SDK shapes verified against
// even_hub_sdk 0.0.16 index.d.ts: bridge.imuControl(isOpen, pace) and sysEvent { eventType: IMU_DATA_REPORT, imuData: {x,y,z} }.

import { ImuReportPace, OsEventTypeList } from '@evenrealities/even_hub_sdk'
import { HeadShakeDetector, type HeadShakeOptions } from './headshake'
import { log, warn } from './types'

export interface ImuBridge { imuControl(isOpen: boolean, reportFrq?: ImuReportPace): Promise<boolean> }

interface ImuEventLike { sysEvent?: { eventType?: number; imuData?: { x?: number; y?: number; z?: number } } | null }

export class HeadShakeTrigger {
  private on = false
  private samples = 0
  constructor(
    private readonly bridge: ImuBridge,
    private readonly onShake: () => void,
    private readonly detector = new HeadShakeDetector(),
    private readonly now: () => number = () => (typeof performance !== 'undefined' ? performance.now() : Date.now()),
  ) {}

  get running(): boolean { return this.on }

  async start(): Promise<boolean> {
    if (this.on) return true
    try {
      this.on = await this.bridge.imuControl(true, ImuReportPace.P100)
    } catch (e) {
      warn('imu: imuControl(true) threw', e)
      this.on = false
    }
    log(`imu: head-shake trigger ${this.on ? 'on' : 'unavailable'}`)
    return this.on
  }

  async stop(): Promise<void> {
    if (!this.on) return
    this.on = false
    this.detector.reset()
    try { await this.bridge.imuControl(false) } catch (e) { warn('imu: imuControl(false) threw', e) }
  }

  /** True when the event was an IMU report (consumed, never a gesture). */
  onEvent(event: ImuEventLike): boolean {
    const sys = event.sysEvent
    if (!sys || sys.eventType !== OsEventTypeList.IMU_DATA_REPORT || !sys.imuData) return false
    if (!this.on) return true
    const { x, y, z } = sys.imuData
    if (typeof x !== 'number' || typeof y !== 'number' || typeof z !== 'number') return true
    if (this.samples++ === 0) log('imu: first sample received')
    if (this.detector.push({ t: this.now(), x, y, z })) {
      log('imu: head shake detected')
      this.onShake()
    }
    return true
  }
}

export function detectorFromEnv(env: Record<string, string | undefined>): HeadShakeDetector {
  const num = (k: string): number | undefined => { const n = Number(env[k]); return Number.isFinite(n) && n > 0 ? n : undefined }
  const o: HeadShakeOptions = {}
  const rel = num('VITE_HEADSHAKE_SWING'); if (rel) o.relSwing = rel
  const dom = num('VITE_HEADSHAKE_DOMINANCE'); if (dom) o.dominance = dom
  return new HeadShakeDetector(o)
}
