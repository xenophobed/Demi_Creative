import { useEffect, type ReactNode } from 'react'
import axios from 'axios'
import type { Session } from '@supabase/supabase-js'
import { authService } from '@/api/services/authService'
import { hasAuthCallbackParams } from '@/api/authUtils'
import supabase, { isSupabaseEnabled } from '@/lib/supabase'
import useAuthStore from '@/store/useAuthStore'
import { performFullLogout } from '@/utils/logout'

// Track whether we arrived via an email confirmation redirect
const hadCallbackParams = hasAuthCallbackParams()

export async function recoverFromFailedBackendSync(error: unknown): Promise<void> {
  if (axios.isAxiosError(error) && error.response?.status === 401) {
    try {
      await supabase?.auth.signOut()
    } catch {
      // ignore
    }
    performFullLogout()
    return
  }
  useAuthStore.getState().setLoading(false)
}

async function syncAndRedirect(session: Session): Promise<void> {
  const store = useAuthStore.getState()
  store.setLoading(true)

  try {
    const user = await authService._syncUser(session.access_token)
    useAuthStore.getState().setAuth(user, session.access_token)

    // Redirect to home after email confirmation auto-login
    if (hadCallbackParams) {
      window.location.replace('/')
    }
  } catch (error) {
    console.error('[auth] Backend sync failed:', error)
    await recoverFromFailedBackendSync(error)
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    const client = supabase
    if (!isSupabaseEnabled() || !client) return

    const {
      data: { subscription },
    } = client.auth.onAuthStateChange((event, session) => {
      const store = useAuthStore.getState()

      // INITIAL_SESSION fires when the listener is registered.
      // If Supabase already exchanged the URL code before we mounted,
      // this is our chance to pick up the session.
      if (event === 'INITIAL_SESSION' && session) {
        if (!store.isAuthenticated || store.token !== session.access_token) {
          void syncAndRedirect(session)
        }
        return
      }

      // SIGNED_IN fires when the URL code exchange completes,
      // or when the user signs in via login form.
      if (event === 'SIGNED_IN' && session) {
        if (store.token !== session.access_token) {
          void syncAndRedirect(session)
        }
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
      subscription.unsubscribe()
    }
  }, [])

  return <>{children}</>
}
