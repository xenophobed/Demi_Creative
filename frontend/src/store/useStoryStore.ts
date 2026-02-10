import { create } from 'zustand'
import type { ImageToStoryResponse, UploadStatus, VoiceType, SSEStatusData, SSEThinkingData } from '@/types/api'

export interface StreamingState {
  isStreaming: boolean
  streamStatus: string
  streamMessage: string
  thinkingContent: string
  currentTurn: number
}

export const initialStreamingState: StreamingState = {
  isStreaming: false,
  streamStatus: '',
  streamMessage: '',
  thinkingContent: '',
  currentTurn: 0,
}

interface StoryState {
  // Current story
  currentStory: ImageToStoryResponse | null

  // Upload status
  uploadStatus: UploadStatus
  uploadProgress: number
  uploadError: string | null

  // Selected image
  selectedImage: File | null
  imagePreviewUrl: string | null

  // Voice settings
  selectedVoice: VoiceType
  enableAudio: boolean

  // Story history (local cache)
  storyHistory: ImageToStoryResponse[]

  // Streaming state (persisted across navigation)
  streaming: StreamingState
  generationInProgress: boolean
  generationError: string | null

  // Actions
  setCurrentStory: (story: ImageToStoryResponse | null) => void
  setUploadStatus: (status: UploadStatus) => void
  setUploadProgress: (progress: number) => void
  setUploadError: (error: string | null) => void
  setSelectedImage: (file: File | null) => void
  setSelectedVoice: (voice: VoiceType) => void
  setEnableAudio: (enable: boolean) => void
  addToHistory: (story: ImageToStoryResponse) => void
  clearHistory: () => void
  reset: () => void

  // Streaming actions
  startStreaming: () => void
  updateStreamStatus: (data: SSEStatusData) => void
  updateThinking: (data: SSEThinkingData) => void
  setStreamMessage: (message: string) => void
  stopStreaming: () => void
  setGenerationError: (error: string | null) => void
  resetStreaming: () => void
}

const useStoryStore = create<StoryState>((set, get) => ({
  currentStory: null,
  uploadStatus: 'idle',
  uploadProgress: 0,
  uploadError: null,
  selectedImage: null,
  imagePreviewUrl: null,
  selectedVoice: 'nova',
  enableAudio: true,
  storyHistory: [],
  streaming: initialStreamingState,
  generationInProgress: false,
  generationError: null,

  setCurrentStory: (story) => {
    set({ currentStory: story })
    // 自动添加到历史
    if (story) {
      get().addToHistory(story)
    }
  },

  setUploadStatus: (status) => set({ uploadStatus: status }),

  setUploadProgress: (progress) => set({ uploadProgress: progress }),

  setUploadError: (error) => set({ uploadError: error }),

  setSelectedImage: (file) => {
    // 释放旧的预览 URL
    const oldUrl = get().imagePreviewUrl
    if (oldUrl) {
      URL.revokeObjectURL(oldUrl)
    }

    if (file) {
      const previewUrl = URL.createObjectURL(file)
      set({
        selectedImage: file,
        imagePreviewUrl: previewUrl,
        uploadStatus: 'idle',
        uploadError: null,
      })
    } else {
      set({
        selectedImage: null,
        imagePreviewUrl: null,
        uploadStatus: 'idle',
        uploadError: null,
      })
    }
  },

  setSelectedVoice: (voice) => set({ selectedVoice: voice }),

  setEnableAudio: (enable) => set({ enableAudio: enable }),

  addToHistory: (story) => {
    const history = get().storyHistory
    // 避免重复
    if (!history.find(s => s.story_id === story.story_id)) {
      set({
        storyHistory: [story, ...history].slice(0, 50), // 保留最近50个
      })
    }
  },

  clearHistory: () => set({ storyHistory: [] }),

  reset: () => {
    const oldUrl = get().imagePreviewUrl
    if (oldUrl) {
      URL.revokeObjectURL(oldUrl)
    }

    set({
      currentStory: null,
      uploadStatus: 'idle',
      uploadProgress: 0,
      uploadError: null,
      selectedImage: null,
      imagePreviewUrl: null,
      streaming: initialStreamingState,
      generationInProgress: false,
      generationError: null,
    })
  },

  // Streaming actions
  startStreaming: () => {
    set({
      streaming: {
        isStreaming: true,
        streamStatus: 'started',
        streamMessage: 'Uploading image...',
        thinkingContent: '',
        currentTurn: 0,
      },
      generationInProgress: true,
      generationError: null,
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

  setStreamMessage: (message) => {
    set((state) => ({
      streaming: {
        ...state.streaming,
        streamMessage: message,
      },
    }))
  },

  stopStreaming: () => {
    set({
      streaming: initialStreamingState,
      generationInProgress: false,
    })
  },

  setGenerationError: (error) => {
    set({
      generationError: error,
      generationInProgress: false,
      streaming: initialStreamingState,
    })
  },

  resetStreaming: () => {
    set({
      streaming: initialStreamingState,
      generationInProgress: false,
      generationError: null,
    })
  },
}))

export default useStoryStore
