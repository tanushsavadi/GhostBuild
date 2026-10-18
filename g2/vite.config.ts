import { defineConfig } from 'vite'

export default defineConfig({
  // Relative paths: a packaged .ehpk is not served from the site root.
  base: './',
  // /api goes to the laptop server (tools/open_palm_server.py), so the phone
  // only ever talks to this one port and no API key reaches the plugin.
  // allowedHosts: the https tunnels (ngrok fixed domain, cloudflared) that
  // phones use to reach this laptop.
  // cors: a packaged .ehpk calls /api from the Even app's own origin through the
  // ngrok domain; Vite only allows localhost origins by default.
  server: {
    host: true,
    port: 5173,
    proxy: { '/api': 'http://127.0.0.1:8790' },
    allowedHosts: ['.trycloudflare.com', '.ngrok-free.dev', '.ngrok-free.app'],
    cors: true,
  },
  build: {
    target: 'esnext',
    rollupOptions: { input: { main: 'index.html', probe: 'probe.html', review: 'review.html' } },
  },
})
