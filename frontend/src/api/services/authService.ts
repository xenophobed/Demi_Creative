/**
 * Auth Service - API methods for authentication
 */

import apiClient from '../client'
import type {
  LoginRequest,
  RegisterRequest,
  AuthResponse,
  User,
  UserWithStats,
  UpdateProfileRequest,
  ChangePasswordRequest,
  PaginatedStories,
  PaginatedSessions,
} from '@/types/auth'

// API base URL for auth endpoints
const AUTH_BASE = '/users'

export const authService = {
  /**
   * Login with username/email and password
   */
  async login(data: LoginRequest): Promise<AuthResponse> {
    const response = await apiClient.post<AuthResponse>(`${AUTH_BASE}/login`, data)
    return response.data
  },

  /**
   * Register a new user
   */
  async register(data: RegisterRequest): Promise<AuthResponse> {
    const response = await apiClient.post<AuthResponse>(`${AUTH_BASE}/register`, data)
    return response.data
  },

  /**
   * Get current user profile
   */
  async getCurrentUser(): Promise<User> {
    const response = await apiClient.get<User>(`${AUTH_BASE}/me`)
    return response.data
  },

  /**
   * Update current user profile
   */
  async updateProfile(data: UpdateProfileRequest): Promise<User> {
    const response = await apiClient.put<User>(`${AUTH_BASE}/me`, data)
    return response.data
  },

  /**
   * Change password
   */
  async changePassword(data: ChangePasswordRequest): Promise<{ message: string }> {
    const response = await apiClient.post<{ message: string }>(
      `${AUTH_BASE}/me/change-password`,
      data
    )
    return response.data
  },

  /**
   * Logout current user
   */
  async logout(): Promise<void> {
    await apiClient.post(`${AUTH_BASE}/logout`)
  },

  /**
   * Get user by ID
   */
  async getUserById(userId: string): Promise<User> {
    const response = await apiClient.get<User>(`${AUTH_BASE}/${userId}`)
    return response.data
  },

  /**
   * Get current user stats (story count, session count)
   */
  async getUserStats(): Promise<UserWithStats> {
    const response = await apiClient.get<UserWithStats>(`${AUTH_BASE}/me/stats`)
    return response.data
  },

  /**
   * Get current user's stories (paginated)
   */
  async getMyStories(params?: { limit?: number; offset?: number }): Promise<PaginatedStories> {
    const response = await apiClient.get<PaginatedStories>(`${AUTH_BASE}/me/stories`, { params })
    return response.data
  },

  /**
   * Get current user's interactive sessions (paginated)
   */
  async getMySessions(params?: { status?: string; limit?: number; offset?: number }): Promise<PaginatedSessions> {
    const response = await apiClient.get<PaginatedSessions>(`${AUTH_BASE}/me/sessions`, { params })
    return response.data
  },
}

export default authService
