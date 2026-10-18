/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Core server origin, e.g. http://192.168.1.20:8787 . Also feeds the app.json network whitelist (see tools/gen-app-json.mjs). */
  readonly VITE_BACKEND_URL?: string
  /** '1' enables the hold-to-ask voice stub. Default off; the manifest ships without a microphone permission. */
  readonly VITE_FLAG_VOICE?: string
  /** "0" skips the launch intro (g2/src/intro.ts). */
  readonly VITE_FLAG_INTRO?: string
  /** 'ascii' = strict ASCII fallbacks for every non-ASCII glyph (use if the hardware glyph test fails). */
  readonly VITE_GLYPHS?: string
  /** Approx characters per line for space-padding centring (calibrate on hardware). */
  readonly VITE_CENTER_COLS?: string
}
interface ImportMeta {
  readonly env: ImportMetaEnv
}
