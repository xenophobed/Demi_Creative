import apiClient from '../client'
import type {
  ImageToStoryResponse,
  InteractiveStoryStartRequest,
  InteractiveStoryStartResponse,
  ChoiceRequest,
  ChoiceResponse,
  SessionStatusResponse,
  SessionResumeResponse,
  HealthCheckResponse,
  AgeGroup,
  VoiceType,
  StreamCallbacks,
  NewsToKidsRequest,
  NewsToKidsResponse,
} from '@/types/api'
import { consumeSSEStream } from '../utils/sseStream'

// API base URL
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

/**
 * Get auth token from localStorage for raw fetch() calls.
 * The axios client handles this via interceptors, but SSE streams use raw fetch.
 */
function getAuthToken(): string | null {
  try {
    const authStorage = localStorage.getItem('auth-storage')
    if (authStorage) {
      const { state } = JSON.parse(authStorage)
      return state?.token || null
    }
  } catch {
    // Ignore parsing errors
  }
  return null
}

function getAuthHeaders(): Record<string, string> {
  const token = getAuthToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/**
 * Story service API
 */
export const storyService = {
  /**
   * Generate story from drawing
   * @param image Image file
   * @param params Request parameters
   */
  async generateStoryFromImage(
    image: File,
    params: {
      childId: string
      ageGroup: AgeGroup
      interests?: string[]
      voice?: VoiceType
      enableAudio?: boolean
    }
  ): Promise<ImageToStoryResponse> {
    const formData = new FormData()
    formData.append('image', image)
    formData.append('child_id', params.childId)
    formData.append('age_group', params.ageGroup)

    if (params.interests && params.interests.length > 0) {
      formData.append('interests', params.interests.join(','))
    }
    if (params.voice) {
      formData.append('voice', params.voice)
    }
    if (params.enableAudio !== undefined) {
      formData.append('enable_audio', String(params.enableAudio))
    }

    const response = await apiClient.post<ImageToStoryResponse>(
      '/image-to-story',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 120000, // 2 minutes for image processing + story generation
      }
    )

    return response.data
  },

  /**
   * Generate story from drawing (streaming)
   * Uses Server-Sent Events for real-time progress
   */
  async generateStoryFromImageStream(
    image: File,
    params: {
      childId: string
      ageGroup: AgeGroup
      interests?: string[]
      voice?: VoiceType
      enableAudio?: boolean
    },
    callbacks: StreamCallbacks,
    signal?: AbortSignal
  ): Promise<void> {
    const formData = new FormData()
    formData.append('image', image)
    formData.append('child_id', params.childId)
    formData.append('age_group', params.ageGroup)

    if (params.interests && params.interests.length > 0) {
      formData.append('interests', params.interests.join(','))
    }
    if (params.voice) {
      formData.append('voice', params.voice)
    }
    if (params.enableAudio !== undefined) {
      formData.append('enable_audio', String(params.enableAudio))
    }

    const response = await fetch(`${API_BASE_URL}/image-to-story/stream`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData,
      signal,
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    await consumeSSEStream(response, callbacks)
  },

  /**
   * Start interactive story
   */
  async startInteractiveStory(
    params: InteractiveStoryStartRequest
  ): Promise<InteractiveStoryStartResponse> {
    const response = await apiClient.post<InteractiveStoryStartResponse>(
      '/story/interactive/start',
      params
    )
    return response.data
  },

  /**
   * Make a choice in interactive story
   */
  async makeChoice(
    sessionId: string,
    choice: ChoiceRequest
  ): Promise<ChoiceResponse> {
    const response = await apiClient.post<ChoiceResponse>(
      `/story/interactive/${sessionId}/choose`,
      choice
    )
    return response.data
  },

  /**
   * Get session status
   */
  async getSessionStatus(sessionId: string): Promise<SessionStatusResponse> {
    const response = await apiClient.get<SessionStatusResponse>(
      `/story/interactive/${sessionId}/status`
    )
    return response.data
  },

  /**
   * Resume an interactive story session (fetch full segment data)
   */
  async resumeSession(sessionId: string): Promise<SessionResumeResponse> {
    const response = await apiClient.get<SessionResumeResponse>(
      `/story/interactive/${sessionId}/resume`
    )
    return response.data
  },

  /**
   * Get story details
   */
  async getStory(storyId: string): Promise<ImageToStoryResponse> {
    const response = await apiClient.get<ImageToStoryResponse>(
      `/stories/${storyId}`
    )
    return response.data
  },

  /**
   * Get story history list
   */
  async getStoryHistory(childId: string): Promise<ImageToStoryResponse[]> {
    const response = await apiClient.get<ImageToStoryResponse[]>(
      `/stories/history/${childId}`
    )
    return response.data
  },

  /**
   * Save interactive story to My Stories
   */
  async saveInteractiveStory(
    sessionId: string
  ): Promise<{ story_id: string; session_id: string; message: string }> {
    const response = await apiClient.post(
      `/story/interactive/${sessionId}/save`
    )
    return response.data
  },

  /**
   * Health check
   */
  async healthCheck(): Promise<HealthCheckResponse> {
    const response = await fetch('/health')
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    return response.json() as Promise<HealthCheckResponse>
  },

  /**
   * Start interactive story (streaming)
   * Uses Server-Sent Events for real-time progress
   */
  async startInteractiveStoryStream(
    params: InteractiveStoryStartRequest,
    callbacks: StreamCallbacks
  ): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/story/interactive/start/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify(params),
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    await consumeSSEStream(response, callbacks)
  },

  /**
   * Convert news article to kid-friendly content
   */
  async convertNews(
    params: NewsToKidsRequest
  ): Promise<NewsToKidsResponse> {
    const response = await apiClient.post<NewsToKidsResponse>(
      '/news-to-kids/convert',
      params
    )
    return response.data
  },

  /**
   * Convert news to kids (streaming)
   */
  async convertNewsStream(
    params: NewsToKidsRequest,
    callbacks: StreamCallbacks
  ): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/news-to-kids/convert/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify(params),
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    await consumeSSEStream(response, callbacks)
  },

  /**
   * Get news conversion history
   */
  async getNewsHistory(childId: string): Promise<NewsToKidsResponse[]> {
    const response = await apiClient.get<NewsToKidsResponse[]>(
      `/news-to-kids/history/${childId}`
    )
    return response.data
  },

  /**
   * Make a choice in interactive story (streaming)
   */
  async makeChoiceStream(
    sessionId: string,
    choice: ChoiceRequest,
    callbacks: StreamCallbacks
  ): Promise<void> {
    const response = await fetch(
      `${API_BASE_URL}/story/interactive/${sessionId}/choose/stream`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(),
        },
        body: JSON.stringify(choice),
      }
    )

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    await consumeSSEStream(response, callbacks)
  },

  /**
   * Generate audio on-demand for an interactive story segment (10-12 age group)
   */
  async generateAudioOnDemand(
    sessionId: string,
    segmentId: number,
    voice?: string,
    speed?: number
  ): Promise<{ session_id: string; segment_id: number; audio_url: string; duration?: number }> {
    const response = await apiClient.post('/audio/generate', {
      session_id: sessionId,
      segment_id: segmentId,
      voice: voice || 'alloy',
      speed: speed || 1.1,
    })
    return response.data
  },

  /**
   * Generate audio on-demand for an image-to-story (10-12 age group)
   */
  async generateAudioForStory(
    storyId: string,
    voice?: string,
    speed?: number
  ): Promise<{ story_id: string; audio_url: string; duration?: number }> {
    const response = await apiClient.post('/audio/generate-for-story', {
      story_id: storyId,
      voice: voice || 'alloy',
      speed: speed || 1.1,
    })
    return response.data
  },
}

export default storyService
