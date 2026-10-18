import { defineConfig } from 'vite'

// base './' keeps asset URLs relative so the packaged .ehpk works regardless of the WebView's origin/path.
export default defineConfig({
  base: './',
  server: { host: true, port: 5173 },
  build: { target: 'esnext' },
})
