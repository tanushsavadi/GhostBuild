import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import Ajv from 'ajv'
import * as F from './stub-frames.mjs'
import { stubGuidePng } from './png.mjs'

// Validate every scripted frame against the generated JSON Schema from contracts/models.py.
const schema = JSON.parse(readFileSync(new URL('../../contracts/schema/hud.json', import.meta.url), 'utf8'))
const ajv = new Ajv({ strict: false })
const validate = ajv.compile(schema)

describe('stub frames are valid HudFrames', () => {
  const frames = {
    welcome: F.welcome(1), menu: F.menu(2, 1), intervene: F.intervene(3),
    visual0: F.visual(4, 0), visual1: F.visual(5, 1), visual2: F.visual(6, 2),
    verified: F.verified(7), quiet: F.quiet(8), status: F.status(9),
  }
  for (const [name, f] of Object.entries(frames)) {
    it(name, () => { expect(validate(f), JSON.stringify(validate.errors)).toBe(true) })
  }
  it('all are labelled simulated', () => {
    for (const f of Object.values(frames)) expect(f.source).toBe('simulated')
  })
  it('valid with a session_id too', () => {
    expect(validate({ ...F.menu(2), session_id: 's-abc' }), JSON.stringify(validate.errors)).toBe(true)
  })
})

describe('stub png', () => {
  it('is a 288x144 4-bit grey PNG', () => {
    const p = stubGuidePng('where')
    expect([...p.subarray(0, 8)]).toEqual([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])
    expect(p.readUInt32BE(16)).toBe(288)
    expect(p.readUInt32BE(20)).toBe(144)
    expect(p[24]).toBe(4)
    expect(p[25]).toBe(0)
  })
})
