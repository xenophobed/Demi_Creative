import { useState, useCallback } from 'react'
import { storyService } from '@/api/services/storyService'
import useInteractiveStoryStore from '@/store/useInteractiveStoryStore'
import type {
  AgeGroup,
  InteractiveStoryStartRequest,
  InteractiveStoryStartResponse,
  ChoiceResponse,
  StorySegment,
  EducationalValue,
  StreamCallbacks,
} from '@/types/api'

interface StreamingState {
  isStreaming: boolean
  streamStatus: string
  streamMessage: string
  thinkingContent: string
  currentTurn: number
}

interface UseInteractiveStoryReturn {
  // State
  sessionId: string | null
  storyTitle: string
  ageGroup: AgeGroup | null
  currentSegment: StorySegment | null
  choiceHistory: string[]
  progress: number
  isLoading: boolean
  error: string | null
  isCompleted: boolean
  educationalSummary: EducationalValue | null

  // Streaming state
  streaming: StreamingState

  // Actions
  startStory: (params: InteractiveStoryStartRequest) => Promise<void>
  startStoryStream: (params: InteractiveStoryStartRequest) => Promise<void>
  makeChoice: (choiceId: string) => Promise<void>
  makeChoiceStream: (choiceId: string) => Promise<void>
  resumeSession: (sessionId: string) => Promise<void>
  reset: () => void
}

export function useInteractiveStory(): UseInteractiveStoryReturn {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const {
    sessionId,
    storyTitle,
    ageGroup,
    currentSegment,
    choiceHistory,
    progress,
    status,
    educationalSummary,
    streaming,
    setSession,
    addSegment,
    restoreSession,
    complete,
    setAgeGroup,
    reset: resetStore,
    startStreaming,
    updateStreamStatus,
    updateThinking,
    stopStreaming,
  } = useInteractiveStoryStore()

  const startStory = useCallback(
    async (params: InteractiveStoryStartRequest) => {
      setIsLoading(true)
      setError(null)
      setAgeGroup(params.age_group)

      try {
        const response = await storyService.startInteractiveStory(params)
        setSession(response, params.age_group)
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Failed to start story, please try again'
        setError(message)
        throw err
      } finally {
        setIsLoading(false)
      }
    },
    [setSession, setAgeGroup]
  )

  const startStoryStream = useCallback(
    async (params: InteractiveStoryStartRequest) => {
      setIsLoading(true)
      setError(null)
      setAgeGroup(params.age_group)
      startStreaming()

      const callbacks: StreamCallbacks = {
        onStatus: (data) => {
          updateStreamStatus(data)
        },
        onThinking: (data) => {
          updateThinking(data)
        },
        onToolUse: (data) => {
          updateStreamStatus({
            status: 'processing',
            message: data.message,
          })
        },
        onResult: (data) => {
          // Cast to InteractiveStoryStartResponse
          const response = data as InteractiveStoryStartResponse
          setSession(response, params.age_group)
        },
        onComplete: () => {
          stopStreaming()
          setIsLoading(false)
        },
        onError: (data) => {
          setError(data.message)
          stopStreaming()
          setIsLoading(false)
        },
      }

      try {
        await storyService.startInteractiveStoryStream(params, callbacks)
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Failed to start story, please try again'
        setError(message)
        stopStreaming()
        setIsLoading(false)
        throw err
      }
    },
    [setSession, setAgeGroup, startStreaming, updateStreamStatus, updateThinking, stopStreaming]
  )

  const makeChoice = useCallback(
    async (choiceId: string) => {
      if (!sessionId) {
        setError('Session not found')
        return
      }

      setIsLoading(true)
      setError(null)

      try {
        const response = await storyService.makeChoice(sessionId, {
          choice_id: choiceId,
        })

        addSegment(response)

        // Check if this is the ending
        if (response.next_segment.is_ending) {
          // Fetch educational summary from session status
          try {
            const statusResponse =
              await storyService.getSessionStatus(sessionId)
            if (statusResponse.educational_summary) {
              complete(statusResponse.educational_summary)
            } else {
              // Create a default summary if none provided
              complete({
                themes: [],
                concepts: [],
                moral: undefined,
              })
            }
          } catch {
            // Complete without summary if status fetch fails
            complete({
              themes: [],
              concepts: [],
              moral: undefined,
            })
          }
        }
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Choice failed, please try again'
        setError(message)
        throw err
      } finally {
        setIsLoading(false)
      }
    },
    [sessionId, addSegment, complete]
  )

  const makeChoiceStream = useCallback(
    async (choiceId: string) => {
      if (!sessionId) {
        setError('Session not found')
        return
      }

      setIsLoading(true)
      setError(null)
      startStreaming()

      const callbacks: StreamCallbacks = {
        onStatus: (data) => {
          updateStreamStatus(data)
        },
        onThinking: (data) => {
          updateThinking(data)
        },
        onToolUse: (data) => {
          updateStreamStatus({
            status: 'processing',
            message: data.message,
          })
        },
        onResult: (data) => {
          const response = data as ChoiceResponse
          addSegment(response)

          // Check if this is the ending
          if (response.next_segment.is_ending) {
            const extendedResponse = response as ChoiceResponse & {
              educational_summary?: EducationalValue
            }
            if (extendedResponse.educational_summary) {
              complete(extendedResponse.educational_summary)
            } else {
              complete({
                themes: [],
                concepts: [],
                moral: undefined,
              })
            }
          }
        },
        onComplete: () => {
          stopStreaming()
          setIsLoading(false)
        },
        onError: (data) => {
          setError(data.message)
          stopStreaming()
          setIsLoading(false)
        },
      }

      try {
        await storyService.makeChoiceStream(
          sessionId,
          { choice_id: choiceId },
          callbacks
        )
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Choice failed, please try again'
        setError(message)
        stopStreaming()
        setIsLoading(false)
        throw err
      }
    },
    [sessionId, addSegment, complete, startStreaming, updateStreamStatus, updateThinking, stopStreaming]
  )

  const resumeSession = useCallback(
    async (resumeSessionId: string) => {
      setIsLoading(true)
      setError(null)

      try {
        const response = await storyService.resumeSession(resumeSessionId)
        restoreSession(response)
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Failed to resume story'
        setError(message)
        throw err
      } finally {
        setIsLoading(false)
      }
    },
    [restoreSession]
  )

  const reset = useCallback(() => {
    resetStore()
    setError(null)
  }, [resetStore])

  return {
    sessionId,
    storyTitle,
    ageGroup,
    currentSegment,
    choiceHistory,
    progress,
    isLoading,
    error,
    isCompleted: status === 'completed',
    educationalSummary,
    streaming,
    startStory,
    startStoryStream,
    makeChoice,
    makeChoiceStream,
    resumeSession,
    reset,
  }
}

export default useInteractiveStory
