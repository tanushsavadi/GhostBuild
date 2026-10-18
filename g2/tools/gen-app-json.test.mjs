import { describe, expect, it } from 'vitest'
import { buildAppJson, origins } from './gen-app-json.mjs'

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
  it('never adds a microphone permission', () => {
    const j = buildAppJson(base, 'http://h:8787')
    expect(j.permissions.map((p) => p.name)).toEqual(['network'])
    expect(j.permissions[0].whitelist).toContain('http://h:8787')
  })
})
