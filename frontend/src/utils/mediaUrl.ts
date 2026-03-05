const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

function backendOrigin(): string {
  if (API_BASE_URL.startsWith('http://') || API_BASE_URL.startsWith('https://')) {
    try {
      return new URL(API_BASE_URL).origin
    } catch {
      // fall through
    }
  }

  if (typeof window !== 'undefined') {
    return window.location.origin
  }

  return ''
}

export function resolveMediaUrl(url?: string | null): string | null {
  if (!url) return null
  const value = url.trim()
  if (!value) return null

  if (
    value.startsWith('http://') ||
    value.startsWith('https://') ||
    value.startsWith('data:') ||
    value.startsWith('blob:')
  ) {
    return value
  }

  const normalized = value.startsWith('./')
    ? value.slice(1)
    : value.startsWith('data/')
      ? `/${value}`
      : value.startsWith('/')
        ? value
        : `/${value}`

  return `${backendOrigin()}${normalized}`
}

