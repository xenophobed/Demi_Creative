/**
 * Library Service — API methods for the unified library (#61, #62, #63)
 */

import apiClient from '../client'

// ---- Types ----

export type LibraryItemType = 'art-story' | 'interactive' | 'news'
export type LibrarySortOrder = 'newest' | 'oldest' | 'word_count'

export interface LibraryItem {
  id: string
  type: LibraryItemType
  title: string
  preview: string
  image_url: string | null
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
}

export interface LibraryResponse {
  items: LibraryItem[]
  total: number
  limit: number
  offset: number
}

export interface FavoriteResponse {
  status: string
  item_id: string
  item_type: string
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
   * DELETE /api/v1/library/favorites — Remove item from favorites
   */
  async removeFavorite(itemId: string, itemType: LibraryItemType): Promise<void> {
    await apiClient.delete(`${LIBRARY_BASE}/favorites`, {
      data: { item_id: itemId, item_type: itemType },
    })
  },
}
