export interface Flags {
  voice: boolean
}

export interface RuntimeEnv {
  VITE_BACKEND_URL?: string
  VITE_FLAG_VOICE?: string
  VITE_GLYPHS?: string
  VITE_CENTER_COLS?: string
}

export const DEFAULT_BACKEND = 'http://localhost:8787'

/** Accept only http(s) origins; strip path and trailing slash. Returns null for anything else. */
export function normalizeBackend(raw: string | null | undefined): string | null {
  if (!raw) return null
  const s = raw.trim()
  if (!/^https?:\/\//i.test(s)) return null
  try {
    const u = new URL(s)
    return `${u.protocol}//${u.host}`
  } catch {
    return null
  }
}

/** Priority: ?backend= query > stored setting > VITE_BACKEND_URL > default. */
export function resolveBackend(query: string | null, stored: string | null, env: RuntimeEnv): string {
  return normalizeBackend(query) ?? normalizeBackend(stored) ?? normalizeBackend(env.VITE_BACKEND_URL) ?? DEFAULT_BACKEND
}

export function readFlags(env: RuntimeEnv): Flags {
  return { voice: env.VITE_FLAG_VOICE === '1' }
}

export function resolveSurface(query: string | null): 'g2' | 'simulator' {
  return query === 'simulator' ? 'simulator' : 'g2'
}

export function resolveGlyphTier(env: RuntimeEnv): 'full' | 'ascii' {
  return env.VITE_GLYPHS === 'ascii' ? 'ascii' : 'full'
}

export function resolveCenterCols(env: RuntimeEnv): number {
  const n = Number(env.VITE_CENTER_COLS)
  return Number.isFinite(n) && n >= 10 && n <= 60 ? Math.floor(n) : 30
}
