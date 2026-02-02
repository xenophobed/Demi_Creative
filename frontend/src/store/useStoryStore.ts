import { create } from 'zustand'
import type { ImageToStoryResponse, UploadStatus, VoiceType } from '@/types/api'

interface StoryState {
  // 当前故事
  currentStory: ImageToStoryResponse | null

  // 上传状态
  uploadStatus: UploadStatus
  uploadProgress: number
  uploadError: string | null

  // 选中的图片
  selectedImage: File | null
  imagePreviewUrl: string | null

  // 语音设置
  selectedVoice: VoiceType
  enableAudio: boolean

  // 故事历史（本地缓存）
  storyHistory: ImageToStoryResponse[]

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
    // 释放预览 URL
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
    })
  },
}))

export default useStoryStore
