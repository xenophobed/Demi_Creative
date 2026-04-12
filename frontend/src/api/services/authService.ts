/**
 * Auth Service - authentication via Supabase (primary) or legacy API (fallback).
 *
 * When VITE_SUPABASE_URL is set, signUp/signIn/signOut use the Supabase JS
 * client. The Supabase access token is then passed to the backend as a Bearer
 * token — the backend validates it via SUPABASE_JWT_SECRET.
 *
 * When Supabase is not configured, falls back to the existing custom-token
 * endpoints (/users/register, /users/login, etc.).
 *
 * Issue: #318 | Parent Epic: #313
 */

import apiClient from '../client'
import supabase, { isSupabaseEnabled } from '@/lib/supabase'
import type {
  LoginRequest,
  RegisterRequest,
  AuthResponse,
  PendingConfirmation,
  User,
  UserWithStats,
  UpdateProfileRequest,
  ChangePasswordRequest,
  PaginatedStories,
  PaginatedSessions,
  ReferralStatus,
} from '@/types/auth'

const AUTH_BASE = '/users'

export const authService = {
  /**
   * Login with email and password.
   */
  async login(data: LoginRequest): Promise<AuthResponse> {
    if (isSupabaseEnabled()) {
      const { data: authData, error } = await supabase!.auth.signInWithPassword({
        email: data.username_or_email,
        password: data.password,
      })
      if (error) throw new Error(error.message)
      if (!authData.session) throw new Error('No session returned')

      // Sync user to backend (auto-creates local row if needed)
      const user = await authService._syncUser(authData.session.access_token)

      return {
        user,
        token: {
          access_token: authData.session.access_token,
          token_type: 'bearer',
          expires_in: authData.session.expires_in ?? 3600,
        },
      }
    }

    // Legacy flow
    const response = await apiClient.post<AuthResponse>(`${AUTH_BASE}/login`, data)
    return response.data
  },

  /**
   * Register a new user with email + password.
   */
  async register(data: RegisterRequest): Promise<AuthResponse | PendingConfirmation> {
    if (isSupabaseEnabled()) {
      const { data: authData, error } = await supabase!.auth.signUp({
        email: data.email,
        password: data.password,
        options: {
          emailRedirectTo: window.location.origin,
          data: {
            display_name: data.display_name || data.username,
            username: data.username,
          },
        },
      })
      if (error) throw new Error(error.message)
      if (!authData.session) {
        // Email confirmation required — Supabase doesn't return a session
        return { pendingConfirmation: true, email: data.email }
      }

      const user = await authService._syncUser(authData.session.access_token)

      return {
        user,
        token: {
          access_token: authData.session.access_token,
          token_type: 'bearer',
          expires_in: authData.session.expires_in ?? 3600,
        },
      }
    }

    // Legacy flow
    const response = await apiClient.post<AuthResponse>(`${AUTH_BASE}/register`, data)
    return response.data
  },

  /**
   * Resend Supabase email confirmation.
   */
  async resendConfirmation(email: string): Promise<void> {
    if (!isSupabaseEnabled()) return

    const { error } = await supabase!.auth.resend({
      type: 'signup',
      email,
      options: {
        emailRedirectTo: window.location.origin,
      },
    })

    if (error) throw new Error(error.message)
  },

  /**
   * Sync Supabase user to backend — calls GET /users/me which auto-creates
   * the local user row via get_current_user dep.
   */
  async _syncUser(accessToken: string): Promise<User> {
    const response = await apiClient.get<User>(`${AUTH_BASE}/me`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    return response.data
  },

  /**
   * Get current user profile.
   */
  async getCurrentUser(): Promise<User> {
    const response = await apiClient.get<User>(`${AUTH_BASE}/me`)
    return response.data
  },

  /**
   * Update current user profile.
   */
  async updateProfile(data: UpdateProfileRequest): Promise<User> {
    const response = await apiClient.put<User>(`${AUTH_BASE}/me`, data)
    return response.data
  },

  /**
   * Change password.
   */
  async changePassword(data: ChangePasswordRequest): Promise<{ message: string }> {
    if (isSupabaseEnabled()) {
      const { error } = await supabase!.auth.updateUser({
        password: data.new_password,
      })
      if (error) throw new Error(error.message)
      return { message: 'Password updated' }
    }

    const response = await apiClient.post<{ message: string }>(
      `${AUTH_BASE}/me/change-password`,
      data
    )
    return response.data
  },

  /**
   * Logout current user.
   */
  async logout(): Promise<void> {
    if (isSupabaseEnabled()) {
      await supabase!.auth.signOut()
      return
    }
    await apiClient.post(`${AUTH_BASE}/logout`)
  },

  /**
   * Get user by ID.
   */
  async getUserById(userId: string): Promise<User> {
    const response = await apiClient.get<User>(`${AUTH_BASE}/${userId}`)
    return response.data
  },

  /**
   * Get current user stats.
   */
  async getUserStats(): Promise<UserWithStats> {
    const response = await apiClient.get<UserWithStats>(`${AUTH_BASE}/me/stats`)
    return response.data
  },

  /**
   * Get current user's stories (paginated).
   */
  async getMyStories(params?: { limit?: number; offset?: number }): Promise<PaginatedStories> {
    const response = await apiClient.get<PaginatedStories>(`${AUTH_BASE}/me/stories`, { params })
    return response.data
  },

  /**
   * Get referral status for current user.
   */
  async fetchReferralStatus(): Promise<ReferralStatus> {
    const response = await apiClient.get<ReferralStatus>(`${AUTH_BASE}/me/referrals`)
    return response.data
  },

  /**
   * Get current user's interactive sessions (paginated).
   */
  async getMySessions(params?: { status?: string; status_filter?: string; limit?: number; offset?: number }): Promise<PaginatedSessions> {
    const normalizedParams = params
      ? {
          status_filter: params.status_filter ?? params.status,
          limit: params.limit,
          offset: params.offset,
        }
      : undefined

    const response = await apiClient.get<PaginatedSessions>(`${AUTH_BASE}/me/sessions`, {
      params: normalizedParams,
    })
    return response.data
  },
}

export default authService
