import { storyService } from '@/api/services/storyService'
import useStoryStore from '@/store/useStoryStore'
import useChildStore from '@/store/useChildStore'
import type { AgeGroup, ImageToStoryResponse, StreamCallbacks } from '@/types/api'

type NavigateFn = (path: string) => void

let abortController: AbortController | null = null
let navigateFn: NavigateFn | null = null
let pendingNavigation: string | null = null

export const storyGenerationManager = {
  registerNavigate(fn: NavigateFn) {
    navigateFn = fn
    // If generation completed while navigate wasn't registered, navigate now
    if (pendingNavigation) {
      const path = pendingNavigation
      pendingNavigation = null
      fn(path)
    }
  },

  isGenerating(): boolean {
    return useStoryStore.getState().generationInProgress
  },

  startGeneration(ageGroup: AgeGroup, interests?: string[]) {
    const store = useStoryStore.getState()

    // Prevent duplicate runs
    if (store.generationInProgress) {
      return
    }

    const { selectedImage, selectedVoice, enableAudio } = store
    if (!selectedImage) {
      store.setUploadError('Please select an image first')
      return
    }

    // Abort any previous controller
    if (abortController) {
      abortController.abort()
    }
    abortController = new AbortController()

    const childStore = useChildStore.getState()
    const childId = childStore.currentChild?.child_id || childStore.defaultChildId

    store.setUploadStatus('uploading')
    store.setUploadError(null)
    store.startStreaming()

    const callbacks: StreamCallbacks = {
      onStatus: (data) => {
        const s = useStoryStore.getState()
        s.updateStreamStatus(data)
        if (data.status === 'started') {
          s.setUploadStatus('processing')
        }
      },
      onThinking: (data) => {
        useStoryStore.getState().updateThinking(data)
      },
      onToolUse: (data) => {
        useStoryStore.getState().setStreamMessage(data.message)
      },
      onResult: (data) => {
        const storyData = data as ImageToStoryResponse
        const s = useStoryStore.getState()
        s.setUploadStatus('success')
        s.setCurrentStory(storyData)
        s.stopStreaming()

        const path = `/story/${storyData.story_id}`
        if (navigateFn) {
          navigateFn(path)
        } else {
          pendingNavigation = path
        }
      },
      onComplete: () => {
        useStoryStore.getState().stopStreaming()
      },
      onError: (data) => {
        const s = useStoryStore.getState()
        s.setUploadStatus('error')
        s.setUploadError(data.message)
        s.setGenerationError(data.message)
      },
    }

    storyService
      .generateStoryFromImageStream(
        selectedImage,
        {
          childId,
          ageGroup,
          interests,
          voice: selectedVoice,
          enableAudio,
        },
        callbacks,
        abortController.signal
      )
      .catch((err) => {
        // Ignore abort errors
        if (err instanceof DOMException && err.name === 'AbortError') {
          return
        }
        const s = useStoryStore.getState()
        s.setUploadStatus('error')
        s.setUploadError(err.message || 'Generation failed')
        s.setGenerationError(err.message || 'Generation failed')
      })
  },

  cancelGeneration() {
    if (abortController) {
      abortController.abort()
      abortController = null
    }
    const s = useStoryStore.getState()
    s.setUploadStatus('idle')
    s.resetStreaming()
  },
}

export default storyGenerationManager
