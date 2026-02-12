import { create } from 'zustand'
import type {
  AgeGroup,
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
  ageGroup: AgeGroup | null
  currentSegment: StorySegment | null
  segments: StorySegment[]
  choiceHistory: string[]
  progress: number
  status: StoryStatus
  educationalSummary: EducationalValue | null

  // Streaming state
  streaming: StreamingState

  // Actions
  setSession: (response: InteractiveStoryStartResponse, ageGroup?: AgeGroup) => void
  addSegment: (response: ChoiceResponse) => void
  complete: (summary: EducationalValue) => void
  setAgeGroup: (ageGroup: AgeGroup) => void
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
  ageGroup: null as AgeGroup | null,
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

  setSession: (response, ageGroup) => {
    set((state) => ({
      sessionId: response.session_id,
      storyTitle: response.story_title,
      ageGroup: ageGroup || state.ageGroup,
      currentSegment: response.opening,
      segments: [response.opening],
      choiceHistory: [],
      progress: 0,
      status: 'playing',
      educationalSummary: null,
      streaming: initialStreamingState,
    }))
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

  setAgeGroup: (ageGroup) => {
    set({ ageGroup })
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
