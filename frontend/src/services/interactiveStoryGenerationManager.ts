import { storyService } from '@/api/services/storyService'
import useInteractiveStoryStore from '@/store/useInteractiveStoryStore'
import type {
  ChoiceResponse,
  InteractiveStoryStartRequest,
  InteractiveStoryStartResponse,
  StreamCallbacks,
  EducationalValue,
} from '@/types/api'

type NavigateFn = (path: string) => void

let abortController: AbortController | null = null
let navigateFn: NavigateFn | null = null
let pendingNavigation: string | null = null

function queueNavigation(path: string) {
  if (navigateFn) {
    navigateFn(path)
  } else {
    pendingNavigation = path
  }
}

export const interactiveStoryGenerationManager = {
  registerNavigate(fn: NavigateFn) {
    navigateFn = fn
    if (pendingNavigation) {
      const path = pendingNavigation
      pendingNavigation = null
      fn(path)
    }
  },

  isGenerating(): boolean {
    return useInteractiveStoryStore.getState().streaming.isStreaming
  },

  async startStory(params: InteractiveStoryStartRequest): Promise<void> {
    const store = useInteractiveStoryStore.getState()

    if (store.streaming.isStreaming) {
      return
    }

    if (abortController) {
      abortController.abort()
    }
    abortController = new AbortController()

    store.setAgeGroup(params.age_group)
    store.startStreaming()

    const callbacks: StreamCallbacks = {
      onStatus: (data) => {
        useInteractiveStoryStore.getState().updateStreamStatus(data)
      },
      onThinking: (data) => {
        useInteractiveStoryStore.getState().updateThinking(data)
      },
      onToolUse: (data) => {
        useInteractiveStoryStore.getState().updateStreamStatus({
          status: 'processing',
          message: data.message,
        })
      },
      onResult: (data) => {
        const response = data as InteractiveStoryStartResponse
        const s = useInteractiveStoryStore.getState()
        s.setSession(response, params.age_group)
        queueNavigation(`/interactive?session=${response.session_id}`)
      },
      onComplete: () => {
        useInteractiveStoryStore.getState().stopStreaming()
      },
      onError: () => {
        useInteractiveStoryStore.getState().stopStreaming()
      },
    }

    try {
      await storyService.startInteractiveStoryStream(
        params,
        callbacks,
        abortController.signal
      )
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        return
      }
      useInteractiveStoryStore.getState().stopStreaming()
      throw err
    } finally {
      abortController = null
    }
  },

  async makeChoice(sessionId: string, choiceId: string): Promise<void> {
    const store = useInteractiveStoryStore.getState()

    if (store.streaming.isStreaming) {
      return
    }

    if (abortController) {
      abortController.abort()
    }
    abortController = new AbortController()

    store.startStreaming()

    const callbacks: StreamCallbacks = {
      onStatus: (data) => {
        useInteractiveStoryStore.getState().updateStreamStatus(data)
      },
      onThinking: (data) => {
        useInteractiveStoryStore.getState().updateThinking(data)
      },
      onToolUse: (data) => {
        useInteractiveStoryStore.getState().updateStreamStatus({
          status: 'processing',
          message: data.message,
        })
      },
      onResult: (data) => {
        const response = data as ChoiceResponse
        const s = useInteractiveStoryStore.getState()
        s.addSegment(response)

        if (response.next_segment.is_ending) {
          const extendedResponse = response as ChoiceResponse & {
            educational_summary?: EducationalValue
          }
          s.complete(
            extendedResponse.educational_summary || {
              themes: [],
              concepts: [],
              moral: undefined,
            }
          )
        }
        queueNavigation(`/interactive?session=${sessionId}`)
      },
      onComplete: () => {
        useInteractiveStoryStore.getState().stopStreaming()
      },
      onError: () => {
        useInteractiveStoryStore.getState().stopStreaming()
      },
    }

    try {
      await storyService.makeChoiceStream(
        sessionId,
        { choice_id: choiceId },
        callbacks,
        abortController.signal
      )
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        return
      }
      useInteractiveStoryStore.getState().stopStreaming()
      throw err
    } finally {
      abortController = null
    }
  },

  cancelGeneration() {
    if (abortController) {
      abortController.abort()
      abortController = null
    }
    useInteractiveStoryStore.getState().stopStreaming()
  },
}

export default interactiveStoryGenerationManager
