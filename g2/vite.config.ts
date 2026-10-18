import { defineConfig } from 'vite'

export default defineConfig({
  // /api goes to the laptop server (tools/open_palm_server.py), so the phone
  // only ever talks to this one port and no API key reaches the plugin.
  // allowedHosts: the https tunnel (cloudflared, see README) for phones that
  // can't reach the laptop's LAN address.
  server: {
    host: true,
    port: 5173,
    proxy: { '/api': 'http://127.0.0.1:8790' },
    allowedHosts: ['.trycloudflare.com'],
  },
  build: {
    target: 'esnext',
    rollupOptions: { input: { main: 'index.html', probe: 'probe.html', review: 'review.html' } },
  },
})
