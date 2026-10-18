#!/usr/bin/env node
// Writes an app.json whose network whitelist comes from the environment, so the packaged plugin may reach core.
//   VITE_BACKEND_URL=http://192.168.1.20:8787 node tools/gen-app-json.mjs app.local.json
//   GB_BACKEND_URLS=http://192.168.1.20:8787,https://box.tail1234.ts.net node tools/gen-app-json.mjs app.local.json
// The same VITE_BACKEND_URL also becomes the plugin's default backend at build time, so one variable drives both.
// Each origin is listed as http(s) AND ws(s): whether the host app needs the ws:// origin for WebSockets is UNVERIFIED
// (docs only say "one entry per origin"); evenhub-cli 0.1.14 packs either way.
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

export function origins(raw) {
  const out = []
  for (const part of String(raw ?? '').split(',').map((s) => s.trim()).filter(Boolean)) {
    let u
    try { u = new URL(part) } catch { throw new Error(`not a URL: ${part}`) }
    if (u.protocol !== 'http:' && u.protocol !== 'https:') throw new Error(`only http(s) origins: ${part}`)
    const secure = u.protocol === 'https:'
    for (const o of [`${u.protocol}//${u.host}`, `${secure ? 'wss' : 'ws'}://${u.host}`]) if (!out.includes(o)) out.push(o)
  }
  return out
}

export const MIC_DESC =
  'Hold-to-ask voice: the glasses microphone is opened only while you hold a long press, and the audio is sent to your GhostBuild server on your network for transcription. It is never stored.'

export function buildAppJson(base, urls, { voice = false } = {}) {
  const whitelist = origins(urls)
  if (whitelist.length === 0) throw new Error('no backend URL: set VITE_BACKEND_URL or GB_BACKEND_URLS')
  const net = { name: 'network', desc: base.permissions.find((p) => p.name === 'network')?.desc ?? 'Talks to the GhostBuild bench server.', whitelist }
  // g2-microphone (docs: Packaging, valid names) is declared ONLY for a VITE_FLAG_VOICE=1 build; unused permissions are flagged at review.
  const mic = voice ? [{ name: 'g2-microphone', desc: MIC_DESC }] : []
  return { ...base, permissions: [net, ...mic, ...base.permissions.filter((p) => p.name !== 'network' && p.name !== 'g2-microphone')] }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const out = process.argv[2] ?? 'app.local.json'
  const base = JSON.parse(readFileSync(new URL('../app.json', import.meta.url), 'utf8'))
  const json = buildAppJson(base, process.env.GB_BACKEND_URLS ?? process.env.VITE_BACKEND_URL, { voice: process.env.VITE_FLAG_VOICE === '1' })
  writeFileSync(out, JSON.stringify(json, null, 2) + '\n')
  console.log(`wrote ${out}: whitelist ${JSON.stringify(json.permissions[0].whitelist)}; microphone permission ${json.permissions.some((p) => p.name === 'g2-microphone') ? 'DECLARED (voice build)' : 'not declared'}`)
}
