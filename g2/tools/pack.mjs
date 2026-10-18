// Build and pack Open Palm for the Even Hub (Beta / Release upload).
//
// The packaged app runs from the Even app, so it reaches the laptop server at a
// fixed https address: https://$NGROK_DOMAIN (from ../.env). That address is
// baked into the build (VITE_API_BASE) and added to the app.json network
// whitelist, which must list exact origins (no wildcards). Without NGROK_DOMAIN
// the package still works for typing, cards and prepared sentences; speech,
// live AI order and new prep then need the dev (QR) version.
//
// Run from g2/:  npm run pack     ->  open-palm.ehpk
import { execSync } from 'node:child_process'
import { existsSync, readFileSync, writeFileSync } from 'node:fs'

const env = {}
if (existsSync('../.env')) {
  for (const line of readFileSync('../.env', 'utf8').split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$/)
    if (m && !line.trimStart().startsWith('#')) env[m[1]] = m[2].replace(/^["']|["']$/g, '')
  }
}
const domain = (process.env.NGROK_DOMAIN || env.NGROK_DOMAIN || '').replace(/^https?:\/\//, '').replace(/\/$/, '')
const base = domain ? `https://${domain}` : ''

const app = JSON.parse(readFileSync('app.json', 'utf8'))
if (base) {
  app.permissions = [
    ...app.permissions.filter(p => p.name !== 'network'),
    { name: 'network', desc: 'Talks to the Open Palm laptop server for speech, word order and conversation prep.', whitelist: [base] },
  ]
}
writeFileSync('app.pack.json', JSON.stringify(app, null, 2) + '\n') // git-ignored
console.log(base ? `server address: ${base} (whitelisted)` : 'no NGROK_DOMAIN in ../.env: packing without a server address')

const run = cmd => execSync(cmd, { stdio: 'inherit', env: { ...process.env, VITE_API_BASE: base } })
run('npx tsc --noEmit')
run('npx vite build')
run('npx evenhub pack app.pack.json dist -o open-palm.ehpk --sdk-ver 0.0.16')
