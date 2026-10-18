import { describe, expect, it, vi } from 'vitest'
import { ImuReportPace, OsEventTypeList } from '@evenrealities/even_hub_sdk'
import { HeadShakeDetector } from './headshake'
import { HeadShakeTrigger } from './imu'

const imuEvent = (x: number, y: number, z: number) => ({ sysEvent: { eventType: OsEventTypeList.IMU_DATA_REPORT, imuData: { x, y, z } } })

describe('HeadShakeTrigger', () => {
  it('turns the IMU on with the documented call and off again', async () => {
    const bridge = { imuControl: vi.fn(async () => true) }
    const t = new HeadShakeTrigger(bridge, () => {})
    expect(await t.start()).toBe(true)
    expect(bridge.imuControl).toHaveBeenCalledWith(true, ImuReportPace.P100)
    await t.stop()
    expect(bridge.imuControl).toHaveBeenLastCalledWith(false)
    expect(t.running).toBe(false)
  })

  it('is unavailable (and harmless) when the host refuses or throws', async () => {
    expect(await new HeadShakeTrigger({ imuControl: vi.fn(async () => false) }, () => {}).start()).toBe(false)
    expect(await new HeadShakeTrigger({ imuControl: vi.fn(async () => { throw new Error('no imu') }) }, () => {}).start()).toBe(false)
  })

  it('consumes IMU reports (never a gesture), ignores other events, and fires on a shake', async () => {
    let clock = 0
    const onShake = vi.fn()
    const t = new HeadShakeTrigger({ imuControl: vi.fn(async () => true) }, onShake, new HeadShakeDetector(), () => clock)
    await t.start()
    expect(t.onEvent({ sysEvent: { eventType: OsEventTypeList.CLICK_EVENT } })).toBe(false)
    expect(t.onEvent({})).toBe(false)
    for (; clock < 1500; clock += 33) expect(t.onEvent(imuEvent(0.001, 0.002, 0.001))).toBe(true)
    for (let k = 0; k < 50; k++, clock += 33) t.onEvent(imuEvent(0, Math.sin((2 * Math.PI * 3 * k * 33) / 1000), 0))
    expect(onShake).toHaveBeenCalledTimes(1)
  })

  it('does nothing while stopped', async () => {
    const onShake = vi.fn()
    const t = new HeadShakeTrigger({ imuControl: vi.fn(async () => true) }, onShake)
    expect(t.onEvent(imuEvent(1, 2, 3))).toBe(true) // still an IMU report, but not processed
    expect(onShake).not.toHaveBeenCalled()
  })
})
