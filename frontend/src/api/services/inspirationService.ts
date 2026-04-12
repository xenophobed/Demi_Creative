/**
 * Inspiration Daily Service — API methods for daily creative inspiration (#405, #409)
 */

import apiClient from '../client'
import type { DailyContent } from '@/components/daily/InspirationDaily'

export interface InspirationCardResponse {
  card: {
    id: string
    title: string
    summary: string
    source_hint: string
    creative_prompt: string
    category: string
    illustration_emoji: string
    cta_type: 'draw' | 'story' | 'explore'
    cta_route: string
    age_adaptations: Record<string, { summary: string; creative_prompt: string }>
  }
  age_group: string
  adapted_summary: string
  adapted_prompt: string
}

/**
 * Fetch today's inspiration card from the API.
 * Returns null if the request fails (caller should fall back to seed bank).
 */
export async function fetchDailyInspiration(
  ageGroup: string = '6-8',
): Promise<InspirationCardResponse | null> {
  try {
    const { data } = await apiClient.get<InspirationCardResponse>(
      '/inspiration-daily',
      { params: { age_group: ageGroup }, timeout: 5000 },
    )
    return data
  } catch {
    return null
  }
}

/**
 * Convert an API InspirationCardResponse into the DailyContent shape
 * used by the InspirationDaily component.
 */
export function toDailyContent(resp: InspirationCardResponse): DailyContent {
  const card = resp.card
  return {
    headline: card.title,
    body: resp.adapted_summary,
    illustration: card.illustration_emoji,
    weather: card.source_hint,
    weatherEmoji: '🌍',
    miniAd: `Category: ${card.category.replace('_', ' ')}`,
    cta_type: card.cta_type,
    cta_route: card.cta_route as DailyContent['cta_route'],
    creative_prompt: resp.adapted_prompt,
  }
}
