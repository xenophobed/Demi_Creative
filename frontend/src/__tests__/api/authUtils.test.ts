import { AxiosHeaders } from 'axios'
import { beforeEach, describe, expect, it } from 'vitest'
import { applyStoredAuthHeader, hasAuthCallbackParams } from '@/api/authUtils'

describe('authUtils', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('preserves an explicit Authorization header', async () => {
    localStorage.setItem(
      'auth-storage',
      JSON.stringify({
        state: {
          token: 'stale-token',
        },
      })
    )

    const config = await applyStoredAuthHeader({
      headers: AxiosHeaders.from({
        Authorization: 'Bearer fresh-token',
      }),
    } as never)

    expect(AxiosHeaders.from(config.headers).get('Authorization')).toBe('Bearer fresh-token')
  })

  it('uses the persisted token when the request has no auth header', async () => {
    localStorage.setItem(
      'auth-storage',
      JSON.stringify({
        state: {
          token: 'persisted-token',
        },
      })
    )

    const config = await applyStoredAuthHeader({
      headers: AxiosHeaders.from({}),
    } as never)

    expect(AxiosHeaders.from(config.headers).get('Authorization')).toBe('Bearer persisted-token')
  })

  it('detects auth callback params in the URL', () => {
    expect(
      hasAuthCallbackParams({
        hash: '#access_token=abc&refresh_token=def',
        search: '',
      })
    ).toBe(true)

    expect(
      hasAuthCallbackParams({
        hash: '',
        search: '?code=123&type=signup',
      })
    ).toBe(true)

    expect(
      hasAuthCallbackParams({
        hash: '',
        search: '?tab=profile',
      })
    ).toBe(false)
  })
})
