import { beforeEach, describe, expect, it, vi } from 'vitest'
import apiClient from '@/api/client'
import { authService } from '@/api/services/authService'

vi.mock('@/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
  getErrorMessage: vi.fn(),
}))

describe('authService._syncUser', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('deduplicates concurrent syncs for the same access token', async () => {
    const user = {
      user_id: 'user-1',
      username: 'demo',
      email: 'demo@example.com',
      display_name: 'Demo',
      avatar_url: null,
      is_active: true,
      is_verified: true,
      role: 'child',
      membership_tier: 'free',
      referral_code: 'demo1234',
      created_at: '2026-04-12T00:00:00.000Z',
      last_login_at: null,
    }

    const getSpy = vi
      .mocked(apiClient.get)
      .mockResolvedValue({ data: user })

    const firstRequest = authService._syncUser('same-token')
    const secondRequest = authService._syncUser('same-token')

    await expect(firstRequest).resolves.toEqual(user)
    await expect(secondRequest).resolves.toEqual(user)
    expect(getSpy).toHaveBeenCalledTimes(1)
  })

  it('retries with a fresh request after a failed sync', async () => {
    const getSpy = vi
      .mocked(apiClient.get)
      .mockRejectedValueOnce(new Error('Unauthorized'))
      .mockResolvedValueOnce({
        data: {
          user_id: 'user-2',
          username: 'demo2',
          email: 'demo2@example.com',
          display_name: 'Demo 2',
          avatar_url: null,
          is_active: true,
          is_verified: true,
          role: 'child',
          membership_tier: 'free',
          referral_code: 'demo5678',
          created_at: '2026-04-12T00:00:00.000Z',
          last_login_at: null,
        },
      })

    await expect(authService._syncUser('retry-token')).rejects.toThrow('Unauthorized')
    await expect(authService._syncUser('retry-token')).resolves.toMatchObject({
      user_id: 'user-2',
    })
    expect(getSpy).toHaveBeenCalledTimes(2)
  })
})
