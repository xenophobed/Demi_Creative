import { useEffect, type ReactNode } from 'react'
import axios from 'axios'
import type { Session } from '@supabase/supabase-js'
import { authService } from '@/api/services/authService'
import { hasAuthCallbackParams } from '@/api/authUtils'
import supabase, { isSupabaseEnabled } from '@/lib/supabase'
import useAuthStore from '@/store/useAuthStore'
import { performFullLogout } from '@/utils/logout'

export async function recoverFromFailedBackendSync(error: unknown): Promise<void> {
  if (axios.isAxiosError(error) && error.response?.status === 401) {
    try {
      await supabase?.auth.signOut()
    } catch (signOutError) {
      console.error('[auth] Failed to clear invalid Supabase session:', signOutError)
    }

    performFullLogout()
    return
  }

  useAuthStore.getState().setLoading(false)
}

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
    await recoverFromFailedBackendSync(error)
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    const client = supabase
    if (!isSupabaseEnabled() || !client) return

    let cancelled = false

    // Set up the listener FIRST so we never miss a SIGNED_IN event
    const {
      data: { subscription },
    } = client.auth.onAuthStateChange((event, session) => {
      const store = useAuthStore.getState()

      if (event === 'SIGNED_IN' && session && store.token !== session.access_token) {
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

    // Now that the listener is active, initialize the session.
    // If the URL contains auth callback params (email confirmation redirect),
    // exchange the code/token — onAuthStateChange will fire SIGNED_IN.
    const initializeSession = async () => {
      if (hasAuthCallbackParams()) {
        // Exchange the code/token from the URL — triggers SIGNED_IN above
        const { error } = await client.auth.exchangeCodeForSession(
          new URLSearchParams(window.location.search).get('code') ?? ''
        )
        if (error) {
          // Fallback: try getSession which also detects hash fragments
          await client.auth.getSession()
        }
        return
      }

      // Normal page load — restore existing session
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
          redirectOnSuccess: false,
        })
      }
    }

    void initializeSession()

    return () => {
      cancelled = true
      subscription.unsubscribe()
    }
  }, [])

  return <>{children}</>
}
