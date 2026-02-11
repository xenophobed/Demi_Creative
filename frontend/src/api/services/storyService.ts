import apiClient from '../client'
import type {
  ImageToStoryResponse,
  InteractiveStoryStartRequest,
  InteractiveStoryStartResponse,
  ChoiceRequest,
  ChoiceResponse,
  SessionStatusResponse,
  HealthCheckResponse,
  AgeGroup,
  VoiceType,
  StreamCallbacks,
} from '@/types/api'
import { consumeSSEStream } from '../utils/sseStream'

// API 基础 URL
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
 * 故事服务 API
 */
export const storyService = {
  /**
   * 画作转故事
   * @param image 图片文件
   * @param params 请求参数
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
   * 画作转故事（流式）
   * 使用 Server-Sent Events 获取实时进度
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
   * 开始互动故事
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
   * 选择互动故事分支
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
   * 获取会话状态
   */
  async getSessionStatus(sessionId: string): Promise<SessionStatusResponse> {
    const response = await apiClient.get<SessionStatusResponse>(
      `/story/interactive/${sessionId}/status`
    )
    return response.data
  },

  /**
   * 获取故事详情
   */
  async getStory(storyId: string): Promise<ImageToStoryResponse> {
    const response = await apiClient.get<ImageToStoryResponse>(
      `/stories/${storyId}`
    )
    return response.data
  },

  /**
   * 获取故事历史列表
   */
  async getStoryHistory(childId: string): Promise<ImageToStoryResponse[]> {
    const response = await apiClient.get<ImageToStoryResponse[]>(
      `/stories/history/${childId}`
    )
    return response.data
  },

  /**
   * 健康检查
   */
  async healthCheck(): Promise<HealthCheckResponse> {
    const response = await apiClient.get<HealthCheckResponse>('/health')
    return response.data
  },

  /**
   * 开始互动故事（流式）
   * 使用 Server-Sent Events 获取实时进度
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
   * 选择互动故事分支（流式）
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
}

export default storyService
