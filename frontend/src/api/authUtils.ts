import { AxiosHeaders, type InternalAxiosRequestConfig } from 'axios'
import supabase, { isSupabaseEnabled } from '@/lib/supabase'

/** Minimum seconds remaining before we proactively refresh the token. */
const REFRESH_BUFFER_SECONDS = 60

function readStoredToken(): string | null {
  try {
    const authStorage = localStorage.getItem('auth-storage')
    if (!authStorage) return null

    const { state } = JSON.parse(authStorage) as {
      state?: { token?: string | null }
    }
    return state?.token ?? null
  } catch {
    return null
  }
}

/**
 * Decode the `exp` claim from a JWT without verifying the signature.
 * Returns the expiry as a Unix timestamp (seconds), or null if unparseable.
 */
function getTokenExp(token: string): number | null {
  try {
    const payload = token.split('.')[1]
    if (!payload) return null
    const decoded = JSON.parse(atob(payload)) as { exp?: number }
    return decoded.exp ?? null
  } catch {
    return null
  }
}

/**
 * If the stored Supabase token is expiring soon, proactively refresh it
 * via `supabase.auth.getSession()` and update the Zustand auth store.
 * Returns the (possibly refreshed) token.
 */
async function ensureFreshToken(currentToken: string): Promise<string> {
  if (!isSupabaseEnabled() || !supabase) return currentToken

  const exp = getTokenExp(currentToken)
  if (exp === null) return currentToken

  const nowSeconds = Math.floor(Date.now() / 1000)
  if (exp - nowSeconds > REFRESH_BUFFER_SECONDS) return currentToken

  // Token is expiring soon or already expired — refresh it
  try {
    const { data } = await supabase.auth.getSession()
    const freshToken = data.session?.access_token
    if (freshToken && freshToken !== currentToken) {
      // Update the Zustand store so other requests pick up the new token
      const authStorage = localStorage.getItem('auth-storage')
      if (authStorage) {
        const parsed = JSON.parse(authStorage)
        if (parsed.state) {
          parsed.state.token = freshToken
          localStorage.setItem('auth-storage', JSON.stringify(parsed))
        }
      }
      return freshToken
    }
  } catch {
    // Refresh failed — use the current token and let the 401 handler deal with it
  }
  return currentToken
}

export async function applyStoredAuthHeader(
  config: InternalAxiosRequestConfig
): Promise<InternalAxiosRequestConfig> {
  const headers = AxiosHeaders.from(config.headers)

  if (!headers.get('Authorization')) {
    let token = readStoredToken()
    if (token) {
      token = await ensureFreshToken(token)
      headers.set('Authorization', `Bearer ${token}`)
    }
  }

  config.headers = headers
  return config
}

/**
 * Get a fresh auth header for raw fetch() calls (SSE streams).
 * Proactively refreshes the token if it's about to expire.
 */
export async function getFreshAuthHeaders(): Promise<Record<string, string>> {
  let token = readStoredToken()
  if (!token) return {}
  token = await ensureFreshToken(token)
  return { Authorization: `Bearer ${token}` }
}

export function hasAuthCallbackParams(
  locationLike: Pick<Location, 'hash' | 'search'> = window.location
): boolean {
  const hash = locationLike.hash || ''
  const search = locationLike.search || ''

  return (
    hash.includes('access_token=') ||
    hash.includes('refresh_token=') ||
    search.includes('code=') ||
    search.includes('token=') ||
    search.includes('type=signup') ||
    search.includes('type=recovery')
  )
}
