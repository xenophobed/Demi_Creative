import { useEffect, type ReactNode } from 'react'
import type { Session } from '@supabase/supabase-js'
import { authService } from '@/api/services/authService'
import { hasAuthCallbackParams } from '@/api/authUtils'
import supabase, { isSupabaseEnabled } from '@/lib/supabase'
import useAuthStore from '@/store/useAuthStore'
import { performFullLogout } from '@/utils/logout'

async function syncSupabaseSession(
  session: Session,
  options?: { clearStaleAuth?: boolean; redirectOnSuccess?: boolean }
): Promise<void> {
  const { clearStaleAuth = false, redirectOnSuccess = false } = options ?? {}
  const store = useAuthStore.getState()

  if (clearStaleAuth) {
    store.logout()
  }

  store.setLoading(true)

  try {
    const user = await authService._syncUser(session.access_token)
    useAuthStore.getState().setAuth(user, session.access_token)

    if (redirectOnSuccess && hasAuthCallbackParams()) {
      window.location.replace('/')
    }
  } catch (error) {
    console.error('[auth] Backend sync after SIGNED_IN failed:', error)
    useAuthStore.getState().setLoading(false)
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    const client = supabase
    if (!isSupabaseEnabled() || !client) return

    let cancelled = false

    const initializeSession = async () => {
      const { data, error } = await client.auth.getSession()
      if (cancelled) return

      if (error) {
        console.error('[auth] Failed to restore Supabase session:', error)
        return
      }

      const store = useAuthStore.getState()
      if (!data.session) {
        if (store.isAuthenticated) {
          performFullLogout()
        }
        return
      }

      if (!store.isAuthenticated || store.token !== data.session.access_token) {
        await syncSupabaseSession(data.session, {
          redirectOnSuccess: hasAuthCallbackParams(),
        })
      }
    }

    void initializeSession()

    const {
      data: { subscription },
    } = client.auth.onAuthStateChange((event, session) => {
      const store = useAuthStore.getState()

      if (event === 'SIGNED_IN' && session && !store.isAuthenticated) {
        void syncSupabaseSession(session, {
          clearStaleAuth: true,
          redirectOnSuccess: hasAuthCallbackParams(),
        })
        return
      }

      if (event === 'TOKEN_REFRESHED' && session && store.isAuthenticated) {
        useAuthStore.setState({ token: session.access_token })
        return
      }

      if (event === 'SIGNED_OUT') {
        performFullLogout()
      }
    })

    return () => {
      cancelled = true
      subscription.unsubscribe()
    }
  }, [])

  return <>{children}</>
}
