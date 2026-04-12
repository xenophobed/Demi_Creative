import { AxiosHeaders, type InternalAxiosRequestConfig } from 'axios'

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

export function applyStoredAuthHeader(
  config: InternalAxiosRequestConfig
): InternalAxiosRequestConfig {
  const headers = AxiosHeaders.from(config.headers)

  if (!headers.get('Authorization')) {
    const token = readStoredToken()
    if (token) {
      headers.set('Authorization', `Bearer ${token}`)
    }
  }

  config.headers = headers
  return config
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
