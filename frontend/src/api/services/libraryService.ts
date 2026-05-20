/**
 * Library Service — API methods for the unified library (#61, #62, #63)
 */

import apiClient from '../client'

// ---- Types ----

export type LibraryItemType = 'art-story' | 'interactive' | 'kids-daily' | 'news' | 'morning-show' | 'kids-news'
export type LibrarySortOrder = 'newest' | 'oldest' | 'word_count' | 'favorite_first'

export interface LibraryItem {
  id: string
  type: LibraryItemType
  title: string
  preview: string
  image_url: string | null
  thumbnail_url?: string | null
  audio_url: string | null
  created_at: string
  is_favorited: boolean
  // Art-story
  safety_score?: number
  word_count?: number
  themes?: string[]
  // Interactive
  progress?: number
  status?: string
  // News
  category?: string
  // Kids Daily
  duration_seconds?: number
  is_new?: boolean
}

export interface LibraryResponse {
  items: LibraryItem[]
  total: number
  limit: number
  offset: number
}

export interface LibraryCountsResponse {
  art_story_count: number
  interactive_count: number
  news_count: number
  total: number
}

export interface FavoriteResponse {
  status: string
  item_id: string
  item_type: string
}

export type StatsGroupBy = 'week' | 'month'

export interface LibraryStatsPeriod {
  period: string
  count: number
}

export interface LibraryStatsResponse {
  periods: LibraryStatsPeriod[]
}

export interface RichStatsPeriod {
  period: string
  creation_count: number
  total_words: number
  unique_themes: number
  completion_rate: number
  story_type_breakdown: Record<string, number>
}

export interface RichStatsResponse {
  periods: RichStatsPeriod[]
  streak_days: number
}

export interface RichStatsOptions {
  childId?: string | null
  parentDashboard?: boolean
}

// ---- API ----

const LIBRARY_BASE = '/library'

export const libraryService = {
  /**
   * GET /api/v1/library — Unified library with pagination and type filter
   */
  async getLibrary(params?: {
    type?: LibraryItemType
    sort?: LibrarySortOrder
    limit?: number
    offset?: number
  }): Promise<LibraryResponse> {
    const response = await apiClient.get<LibraryResponse>(LIBRARY_BASE, { params })
    return response.data
  },

  /**
   * GET /api/v1/library/counts — Profile stat counts from library-visible data
   */
  async getCounts(): Promise<LibraryCountsResponse> {
    const response = await apiClient.get<LibraryCountsResponse>(`${LIBRARY_BASE}/counts`)
    return response.data
  },

  /**
   * GET /api/v1/library/search — Search across all library content
   */
  async searchLibrary(params: {
    q: string
    type?: LibraryItemType
    sort?: LibrarySortOrder
    limit?: number
    offset?: number
  }): Promise<LibraryResponse> {
    const response = await apiClient.get<LibraryResponse>(`${LIBRARY_BASE}/search`, { params })
    return response.data
  },

  /**
   * POST /api/v1/library/favorites — Add item to favorites
   */
  async addFavorite(itemId: string, itemType: LibraryItemType): Promise<FavoriteResponse> {
    const response = await apiClient.post<FavoriteResponse>(`${LIBRARY_BASE}/favorites`, {
      item_id: itemId,
      item_type: itemType,
    })
    return response.data
  },

  /**
   * GET /api/v1/library/stats — Creation counts grouped by week or month (#133)
   */
  async getStats(groupBy: StatsGroupBy = 'week'): Promise<LibraryStatsResponse> {
    const response = await apiClient.get<LibraryStatsResponse>(`${LIBRARY_BASE}/stats`, {
      params: { group_by: groupBy },
    })
    return response.data
  },

  /**
   * GET /api/v1/library/stats-rich — Rich growth dashboard metrics (#356)
   */
  async getRichStats(
    groupBy: StatsGroupBy = 'week',
    options: RichStatsOptions = {},
  ): Promise<RichStatsResponse> {
    const response = await apiClient.get<RichStatsResponse>(`${LIBRARY_BASE}/stats-rich`, {
      params: {
        group_by: groupBy,
        ...(options.childId ? { child_id: options.childId } : {}),
        ...(options.parentDashboard ? { parent_dashboard: true } : {}),
      },
    })
    return response.data
  },

  /**
   * DELETE /api/v1/library/favorites — Remove item from favorites
   */
  async removeFavorite(itemId: string, itemType: LibraryItemType): Promise<void> {
    await apiClient.delete(`${LIBRARY_BASE}/favorites`, {
      data: { item_id: itemId, item_type: itemType },
    })
  },
}
