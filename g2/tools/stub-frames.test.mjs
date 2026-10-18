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

describe('playbook stub frames are valid HudFrames', () => {
  const frames = {
    chooser: F.chooser(1, 2), step0: F.step(2, 0), step2: F.step(3, 2), notMet: F.stepNotMet(4, 2),
    picture0: F.stepPicture(5, 0, 0), picture1: F.stepPicture(6, 0, 1), passed: F.stepPassed(7), completion: F.completion(8),
  }
  for (const [name, f] of Object.entries(frames)) {
    it(name, () => {
      expect(validate(f), JSON.stringify(validate.errors)).toBe(true)
      expect(f.source).toBe('simulated')
      // models.py _shape rules the JSON schema cannot express
      if (f.mode === 'step') expect(f.step).toBeTruthy()
      if (f.mode === 'menu') expect(f.menu).toBeTruthy()
      if (f.image) expect(f.mode).toBe('visual')
    })
  }
  it('chooser has three options; step indices are 0-based and in range', () => {
    expect(F.chooser(1).menu.options).toHaveLength(3)
    for (let i = 0; i < F.PB_STEPS.length; i++) expect(F.step(1, i).step.index).toBeLessThan(F.step(1, i).step.count)
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
