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
import useChildStore from './useChildStore'

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
        // Hydrate child store from server-side default_child_id so the
        // buddy persona binds to the same child profile across devices
        // (#455). No-op when the field is null/undefined or already
        // matches the local value.
        useChildStore.getState().setDefaultChildId(user.default_child_id)
      },

      // Update user profile
      setUser: (user) => {
        set({ user })
        useChildStore.getState().setDefaultChildId(user.default_child_id)
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

export default useAuthStore
