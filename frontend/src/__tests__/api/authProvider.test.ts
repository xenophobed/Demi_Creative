import { beforeEach, describe, expect, it, vi } from 'vitest'

const signOut = vi.fn()
const performFullLogout = vi.fn()
const setLoading = vi.fn()

vi.mock('@/lib/supabase', () => ({
  __esModule: true,
  default: {
    auth: {
      signOut,
    },
  },
  isSupabaseEnabled: vi.fn(() => true),
}))

vi.mock('@/utils/logout', () => ({
  performFullLogout,
}))

vi.mock('@/store/useAuthStore', () => ({
  __esModule: true,
  default: {
    getState: () => ({
      setLoading,
    }),
  },
}))

describe('recoverFromFailedBackendSync', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('signs out Supabase and clears app auth after a 401 backend sync failure', async () => {
    const { recoverFromFailedBackendSync } = await import('@/providers/AuthProvider')

    signOut.mockResolvedValue(undefined)

    await recoverFromFailedBackendSync({
      isAxiosError: true,
      response: { status: 401 },
    })

    expect(signOut).toHaveBeenCalledTimes(1)
    expect(performFullLogout).toHaveBeenCalledTimes(1)
    expect(setLoading).not.toHaveBeenCalled()
  })

  it('only clears the loading state for non-auth backend sync failures', async () => {
    const { recoverFromFailedBackendSync } = await import('@/providers/AuthProvider')

    await recoverFromFailedBackendSync({
      isAxiosError: true,
      response: { status: 500 },
    })

    expect(signOut).not.toHaveBeenCalled()
    expect(performFullLogout).not.toHaveBeenCalled()
    expect(setLoading).toHaveBeenCalledWith(false)
  })
})
