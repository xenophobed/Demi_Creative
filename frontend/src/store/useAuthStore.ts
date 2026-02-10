/**
 * Auth Store - Manages authentication state with persistence
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User } from '@/types/auth'

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

export default useAuthStore
