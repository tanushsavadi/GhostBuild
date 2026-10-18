import { defineConfig } from 'vite'

export default defineConfig({
  // /api goes to the laptop server (tools/open_palm_server.py), so the phone
  // only ever talks to this one port and no API key reaches the plugin.
  server: { host: true, port: 5173, proxy: { '/api': 'http://127.0.0.1:8790' } },
  build: {
    target: 'esnext',
    rollupOptions: { input: { main: 'index.html', probe: 'probe.html', review: 'review.html' } },
  },
})
