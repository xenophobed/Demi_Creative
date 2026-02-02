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
  SSEEventType,
} from '@/types/api'

// API 基础 URL
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

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
    callbacks: StreamCallbacks
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
      body: formData,
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('No response body')
    }

    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        let eventType: SSEEventType | null = null

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim() as SSEEventType
          } else if (line.startsWith('data: ') && eventType) {
            const data = JSON.parse(line.slice(6))

            switch (eventType) {
              case 'status':
                callbacks.onStatus?.(data)
                break
              case 'thinking':
                callbacks.onThinking?.(data)
                break
              case 'tool_use':
                callbacks.onToolUse?.(data)
                break
              case 'tool_result':
                callbacks.onToolResult?.(data)
                break
              case 'result':
                callbacks.onResult?.(data)
                break
              case 'complete':
                callbacks.onComplete?.(data)
                break
              case 'error':
                callbacks.onError?.(data)
                break
            }
            eventType = null
          }
        }
      }
    } finally {
      reader.releaseLock()
    }
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
      },
      body: JSON.stringify(params),
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('No response body')
    }

    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // 解析 SSE 事件
        const lines = buffer.split('\n')
        buffer = lines.pop() || '' // 保留不完整的行

        let eventType: SSEEventType | null = null

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim() as SSEEventType
          } else if (line.startsWith('data: ') && eventType) {
            const data = JSON.parse(line.slice(6))

            switch (eventType) {
              case 'status':
                callbacks.onStatus?.(data)
                break
              case 'thinking':
                callbacks.onThinking?.(data)
                break
              case 'tool_use':
                callbacks.onToolUse?.(data)
                break
              case 'tool_result':
                callbacks.onToolResult?.(data)
                break
              case 'session':
                callbacks.onSession?.(data)
                break
              case 'result':
                callbacks.onResult?.(data)
                break
              case 'complete':
                callbacks.onComplete?.(data)
                break
              case 'error':
                callbacks.onError?.(data)
                break
            }
            eventType = null
          }
        }
      }
    } finally {
      reader.releaseLock()
    }
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
        },
        body: JSON.stringify(choice),
      }
    )

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('No response body')
    }

    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        let eventType: SSEEventType | null = null

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim() as SSEEventType
          } else if (line.startsWith('data: ') && eventType) {
            const data = JSON.parse(line.slice(6))

            switch (eventType) {
              case 'status':
                callbacks.onStatus?.(data)
                break
              case 'thinking':
                callbacks.onThinking?.(data)
                break
              case 'tool_use':
                callbacks.onToolUse?.(data)
                break
              case 'tool_result':
                callbacks.onToolResult?.(data)
                break
              case 'result':
                callbacks.onResult?.(data)
                break
              case 'complete':
                callbacks.onComplete?.(data)
                break
              case 'error':
                callbacks.onError?.(data)
                break
            }
            eventType = null
          }
        }
      }
    } finally {
      reader.releaseLock()
    }
  },
}

export default storyService
