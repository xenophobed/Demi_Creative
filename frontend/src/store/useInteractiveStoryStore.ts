import { create } from 'zustand'
import type {
  StorySegment,
  EducationalValue,
  InteractiveStoryStartResponse,
  ChoiceResponse,
  SSEStatusData,
  SSEThinkingData,
} from '@/types/api'

type StoryStatus = 'idle' | 'playing' | 'completed'

interface StreamingState {
  isStreaming: boolean
  streamStatus: string
  streamMessage: string
  thinkingContent: string
  currentTurn: number
}

interface InteractiveStoryState {
  // Session state
  sessionId: string | null
  storyTitle: string
  currentSegment: StorySegment | null
  segments: StorySegment[]
  choiceHistory: string[]
  progress: number
  status: StoryStatus
  educationalSummary: EducationalValue | null

  // Streaming state
  streaming: StreamingState

  // Actions
  setSession: (response: InteractiveStoryStartResponse) => void
  addSegment: (response: ChoiceResponse) => void
  complete: (summary: EducationalValue) => void
  reset: () => void

  // Streaming actions
  startStreaming: () => void
  updateStreamStatus: (data: SSEStatusData) => void
  updateThinking: (data: SSEThinkingData) => void
  stopStreaming: () => void
}

const initialStreamingState: StreamingState = {
  isStreaming: false,
  streamStatus: '',
  streamMessage: '',
  thinkingContent: '',
  currentTurn: 0,
}

const initialState = {
  sessionId: null,
  storyTitle: '',
  currentSegment: null,
  segments: [],
  choiceHistory: [],
  progress: 0,
  status: 'idle' as StoryStatus,
  educationalSummary: null,
  streaming: initialStreamingState,
}

const useInteractiveStoryStore = create<InteractiveStoryState>((set) => ({
  ...initialState,

  setSession: (response) => {
    set({
      sessionId: response.session_id,
      storyTitle: response.story_title,
      currentSegment: response.opening,
      segments: [response.opening],
      choiceHistory: [],
      progress: 0,
      status: 'playing',
      educationalSummary: null,
      streaming: initialStreamingState,
    })
  },

  addSegment: (response) => {
    set((state) => ({
      currentSegment: response.next_segment,
      segments: [...state.segments, response.next_segment],
      choiceHistory: response.choice_history,
      progress: response.progress,
      streaming: initialStreamingState,
    }))
  },

  complete: (summary) => {
    set({
      status: 'completed',
      educationalSummary: summary,
      streaming: initialStreamingState,
    })
  },

  reset: () => {
    set(initialState)
  },

  // Streaming actions
  startStreaming: () => {
    set({
      streaming: {
        isStreaming: true,
        streamStatus: 'started',
        streamMessage: 'Creating story...',
        thinkingContent: '',
        currentTurn: 0,
      },
    })
  },

  updateStreamStatus: (data) => {
    set((state) => ({
      streaming: {
        ...state.streaming,
        streamStatus: data.status,
        streamMessage: data.message,
      },
    }))
  },

  updateThinking: (data) => {
    set((state) => ({
      streaming: {
        ...state.streaming,
        thinkingContent: data.content,
        currentTurn: data.turn,
      },
    }))
  },

  stopStreaming: () => {
    set((state) => ({
      streaming: {
        ...state.streaming,
        isStreaming: false,
      },
    }))
  },
}))

export default useInteractiveStoryStore
