/**
 * Authentication Types
 */

// Login request
export interface LoginRequest {
  username_or_email: string  // Can be username or email
  password: string
}

// Register request
export interface RegisterRequest {
  username: string
  email: string
  password: string
  display_name?: string
}

// User profile returned from API
export interface User {
  user_id: string
  username: string
  email: string
  display_name: string | null
  avatar_url: string | null
  is_active: boolean
  is_verified: boolean
  created_at: string
  last_login_at: string | null
}

// Token response from API
export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
}

// Auth response from login/register
export interface AuthResponse {
  user: User
  token: TokenResponse
}

// Profile update request
export interface UpdateProfileRequest {
  display_name?: string
  avatar_url?: string
}

// Change password request
export interface ChangePasswordRequest {
  current_password: string
  new_password: string
}

// User with content statistics
export interface UserWithStats extends User {
  story_count: number
  session_count: number
}

// Story summary for user's story list
export interface UserStorySummary {
  story_id: string
  child_id: string
  age_group: string
  story_preview: string
  word_count: number
  themes: string[]
  image_url: string | null
  audio_url: string | null
  created_at: string
}

// Session summary for user's session list
export interface UserSessionSummary {
  session_id: string
  story_title: string
  child_id: string
  age_group: string
  theme: string | null
  current_segment: number
  total_segments: number
  status: string
  created_at: string
  updated_at: string
}

// Paginated stories response
export interface PaginatedStories {
  user: { user_id: string; username: string; display_name: string | null; avatar_url: string | null; created_at: string }
  stories: UserStorySummary[]
  total: number
  limit: number
  offset: number
}

// Paginated sessions response
export interface PaginatedSessions {
  user: { user_id: string; username: string; display_name: string | null; avatar_url: string | null }
  sessions: UserSessionSummary[]
  total: number
  limit: number
  offset: number
}
