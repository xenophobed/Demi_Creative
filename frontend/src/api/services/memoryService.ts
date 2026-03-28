/**
 * Memory Service - API methods for character gallery and preference data
 */

import apiClient from '../client'
import type {
  MemoryCharactersResponse,
  MemoryPreferencesResponse,
  MemoryDeleteResponse,
} from '@/types/api'

const MEMORY_BASE = '/memory'

export const memoryService = {
  /**
   * Get all characters for a child, sorted by appearance count
   */
  async getCharacters(childId: string): Promise<MemoryCharactersResponse> {
    const response = await apiClient.get<MemoryCharactersResponse>(
      `${MEMORY_BASE}/characters/${childId}`
    )
    return response.data
  },

  /**
   * Get preference profile for a child
   */
  async getPreferences(childId: string): Promise<MemoryPreferencesResponse> {
    const response = await apiClient.get<MemoryPreferencesResponse>(
      `${MEMORY_BASE}/preferences/${childId}`
    )
    return response.data
  },

  /**
   * Delete all preference and vector data for a child (COPPA compliance)
   */
  async deletePreferences(childId: string): Promise<MemoryDeleteResponse> {
    const response = await apiClient.delete<MemoryDeleteResponse>(
      `${MEMORY_BASE}/preferences/${childId}`
    )
    return response.data
  },

  /**
   * Get user's primary child_id from story history
   */
  async getChildId(): Promise<{ child_id: string | null }> {
    const response = await apiClient.get<{ child_id: string | null }>(
      `${MEMORY_BASE}/child-id`
    )
    return response.data
  },

  /**
   * Get personalised theme recommendations based on preference history (#292)
   */
  async getRecommendations(
    childId: string,
    limit: number = 5
  ): Promise<{ child_id: string; recommendations: string[] }> {
    const response = await apiClient.get<{
      child_id: string
      recommendations: string[]
    }>(`${MEMORY_BASE}/recommendations/${childId}`, { params: { limit } })
    return response.data
  },
}

export default memoryService
