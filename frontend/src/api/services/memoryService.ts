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
}

export default memoryService
