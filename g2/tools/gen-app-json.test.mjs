import { describe, expect, it } from 'vitest'
import { MIC_DESC, buildAppJson, origins } from './gen-app-json.mjs'

const base = { package_id: 'com.ghostbuild.ghostbuild', name: 'GhostBuild', permissions: [{ name: 'network', desc: 'x', whitelist: ['http://localhost:8787'] }] }

describe('gen-app-json', () => {
  it('lists http and ws origins, dedupes, strips paths', () => {
    expect(origins('http://192.168.1.20:8787/path, http://192.168.1.20:8787')).toEqual(['http://192.168.1.20:8787', 'ws://192.168.1.20:8787'])
    expect(origins('https://box.ts.net')).toEqual(['https://box.ts.net', 'wss://box.ts.net'])
  })
  it('rejects non-http(s) and empty input', () => {
    expect(() => origins('ftp://x')).toThrow()
    expect(() => buildAppJson(base, '')).toThrow(/no backend/)
  })
  it('adds g2-microphone ONLY for a voice build (and never phone-microphone)', () => {
    const on = buildAppJson(base, 'http://h:8787', { voice: true })
    expect(on.permissions.map((p) => p.name)).toEqual(['network', 'g2-microphone'])
    expect(on.permissions[1].desc).toBe(MIC_DESC)
    expect(MIC_DESC.length).toBeGreaterThanOrEqual(1)
    expect(MIC_DESC.length).toBeLessThanOrEqual(300)
    expect(buildAppJson(base, 'http://h:8787', { voice: false }).permissions.map((p) => p.name)).toEqual(['network'])
    expect(on.permissions.some((p) => p.name === 'phone-microphone')).toBe(false)
  })
  it('never adds a microphone permission by default', () => {
    const j = buildAppJson(base, 'http://h:8787')
    expect(j.permissions.map((p) => p.name)).toEqual(['network'])
    expect(j.permissions[0].whitelist).toContain('http://h:8787')
  })
})
