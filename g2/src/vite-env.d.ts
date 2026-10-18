/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Laptop server address for a packaged build, e.g. https://name.ngrok-free.app. Empty in dev (Vite proxies /api). */
  readonly VITE_API_BASE?: string
}
