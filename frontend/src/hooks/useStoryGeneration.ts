import { useCallback } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { storyService } from '@/api/services/storyService'
import { getErrorMessage } from '@/api/client'
import useStoryStore from '@/store/useStoryStore'
import useChildStore from '@/store/useChildStore'
import { storyGenerationManager } from '@/services/storyGenerationManager'
import type { AgeGroup, VoiceType } from '@/types/api'

interface UseStoryGenerationOptions {
  onSuccess?: () => void
  onError?: (error: string) => void
}

export function useStoryGeneration(options?: UseStoryGenerationOptions) {
  const navigate = useNavigate()

  const {
    selectedImage,
    selectedVoice,
    enableAudio,
    uploadStatus,
    streaming,
    generationInProgress,
    setUploadStatus,
    setUploadError,
    setCurrentStory,
    reset,
    resetStreaming,
  } = useStoryStore()

  const { currentChild, defaultChildId } = useChildStore()

  // Non-streaming mutation (legacy)
  const mutation = useMutation({
    mutationFn: async (params: {
      image: File
      ageGroup: AgeGroup
      interests?: string[]
      voice?: VoiceType
      enableAudio?: boolean
    }) => {
      setUploadStatus('uploading')
      setUploadError(null)

      const childId = currentChild?.child_id || defaultChildId

      return storyService.generateStoryFromImage(params.image, {
        childId,
        ageGroup: params.ageGroup,
        interests: params.interests,
        voice: params.voice || selectedVoice,
        enableAudio: params.enableAudio ?? enableAudio,
      })
    },
    onMutate: () => {
      setUploadStatus('processing')
    },
    onSuccess: (data) => {
      setUploadStatus('success')
      setCurrentStory(data)
      options?.onSuccess?.()
      navigate(`/story/${data.story_id}`)
    },
    onError: (error) => {
      const message = getErrorMessage(error)
      setUploadStatus('error')
      setUploadError(message)
      options?.onError?.(message)
    },
  })

  // Non-streaming generate
  const generate = (ageGroup: AgeGroup, interests?: string[]) => {
    if (!selectedImage) {
      setUploadError('Please select an image first')
      return
    }

    mutation.mutate({
      image: selectedImage,
      ageGroup,
      interests,
      voice: selectedVoice,
      enableAudio,
    })
  }

  // Streaming generate — delegates to the singleton manager
  const generateStream = useCallback(
    (ageGroup: AgeGroup, interests?: string[]) => {
      storyGenerationManager.startGeneration(ageGroup, interests)
    },
    []
  )

  const cancel = useCallback(() => {
    storyGenerationManager.cancelGeneration()
  }, [])

  const resetAll = () => {
    reset()
    mutation.reset()
    resetStreaming()
  }

  return {
    generate,
    generateStream,
    cancel,
    reset: resetAll,
    isLoading: mutation.isPending || streaming.isStreaming,
    isGenerating: generationInProgress,
    isError: mutation.isError,
    isSuccess: mutation.isSuccess,
    error: mutation.error ? getErrorMessage(mutation.error) : null,
    data: mutation.data,
    streaming,
    uploadStatus,
  }
}

export default useStoryGeneration
