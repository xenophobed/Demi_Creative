/**
 * Auth Store - Manages authentication state with persistence.
 *
 * Works with both Supabase Auth and legacy custom tokens.
 * When Supabase is enabled, listens for token refresh events and
 * auto-updates the stored token.
 *
 * Issue: #318 | Parent Epic: #313
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User } from '@/types/auth'
import supabase, { isSupabaseEnabled } from '@/lib/supabase'
import apiClient from '@/api/client'

interface AuthState {
  // State
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean

  // Actions
  setAuth: (user: User, token: string) => void
  setUser: (user: User) => void
  setLoading: (loading: boolean) => void
  logout: () => void
  checkAuth: () => boolean
}

const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      // Initial state
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,

      // Set auth after login/register
      setAuth: (user, token) => {
        set({
          user,
          token,
          isAuthenticated: true,
          isLoading: false,
        })
      },

      // Update user profile
      setUser: (user) => {
        set({ user })
      },

      // Set loading state
      setLoading: (loading) => {
        set({ isLoading: loading })
      },

      // Logout and clear state
      logout: () => {
        set({
          user: null,
          token: null,
          isAuthenticated: false,
          isLoading: false,
        })
      },

      // Check if user is authenticated
      checkAuth: () => {
        const state = get()
        return state.isAuthenticated && !!state.token
      },
    }),
    {
      name: 'auth-storage', // localStorage key
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)

// Listen for Supabase auth state changes (token refresh, sign out, email confirm)
if (isSupabaseEnabled()) {
  supabase!.auth.onAuthStateChange(async (event, session) => {
    const store = useAuthStore.getState()

    if (event === 'SIGNED_IN' && session && !store.isAuthenticated) {
      // User confirmed email and was redirected back — sync to backend
      useAuthStore.getState().setLoading(true)
      try {
        const response = await apiClient.get<User>('/users/me', {
          headers: { Authorization: `Bearer ${session.access_token}` },
        })
        useAuthStore.getState().setAuth(response.data, session.access_token)
        // Navigate to home after successful auto-login (e.g. email confirmation)
        window.location.href = '/'
      } catch (err) {
        console.error('[auth] Backend sync after SIGNED_IN failed:', err)
        useAuthStore.getState().setLoading(false)
      }
    }

    if (event === 'TOKEN_REFRESHED' && session) {
      // Update the stored token so API calls use the fresh one
      if (store.isAuthenticated) {
        useAuthStore.setState({ token: session.access_token })
      }
    }

    if (event === 'SIGNED_OUT') {
      store.logout()
    }
  })
}

export default useAuthStore
