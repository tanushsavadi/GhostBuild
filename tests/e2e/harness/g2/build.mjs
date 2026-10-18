// Bundle the REAL g2/src/main.ts with the SDK import swapped for fake_sdk.mjs. Usage: node build.mjs <out.mjs>
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const g2 = path.resolve(here, '../../../../g2')
const esbuild = createRequire(path.join(g2, 'package.json'))('esbuild')

await esbuild.build({
  entryPoints: [path.join(g2, 'src/main.ts')],
  outfile: process.argv[2],
  bundle: true,
  format: 'esm',
  platform: 'neutral',
  target: 'es2022',
  logLevel: 'error',
  plugins: [{
    name: 'fake-even-sdk',
    setup(b) {
      b.onResolve({ filter: /^@evenrealities\/even_hub_sdk$/ }, () => ({ path: path.join(here, 'fake_sdk.mjs') }))
    },
  }],
})
