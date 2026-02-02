import { useState, useCallback } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { storyService } from '@/api/services/storyService'
import { getErrorMessage } from '@/api/client'
import useStoryStore from '@/store/useStoryStore'
import useChildStore from '@/store/useChildStore'
import type { AgeGroup, VoiceType, ImageToStoryResponse, StreamCallbacks } from '@/types/api'

interface StreamingState {
  isStreaming: boolean
  streamStatus: string
  streamMessage: string
  thinkingContent: string
  currentTurn: number
}

interface UseStoryGenerationOptions {
  onSuccess?: () => void
  onError?: (error: string) => void
}

const initialStreamingState: StreamingState = {
  isStreaming: false,
  streamStatus: '',
  streamMessage: '',
  thinkingContent: '',
  currentTurn: 0,
}

export function useStoryGeneration(options?: UseStoryGenerationOptions) {
  const navigate = useNavigate()
  const [streaming, setStreaming] = useState<StreamingState>(initialStreamingState)

  const {
    selectedImage,
    selectedVoice,
    enableAudio,
    setUploadStatus,
    setUploadError,
    setCurrentStory,
    reset,
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

  // Streaming generate
  const generateStream = useCallback(
    async (ageGroup: AgeGroup, interests?: string[]) => {
      if (!selectedImage) {
        setUploadError('Please select an image first')
        return
      }

      setUploadStatus('uploading')
      setUploadError(null)
      setStreaming({
        isStreaming: true,
        streamStatus: 'started',
        streamMessage: 'Uploading image...',
        thinkingContent: '',
        currentTurn: 0,
      })

      const childId = currentChild?.child_id || defaultChildId

      const callbacks: StreamCallbacks = {
        onStatus: (data) => {
          setStreaming((prev) => ({
            ...prev,
            streamStatus: data.status,
            streamMessage: data.message,
          }))
          if (data.status === 'started') {
            setUploadStatus('processing')
          }
        },
        onThinking: (data) => {
          setStreaming((prev) => ({
            ...prev,
            thinkingContent: data.content,
            currentTurn: data.turn,
          }))
        },
        onToolUse: (data) => {
          setStreaming((prev) => ({
            ...prev,
            streamMessage: data.message,
          }))
        },
        onResult: (data) => {
          const storyData = data as ImageToStoryResponse
          setUploadStatus('success')
          setCurrentStory(storyData)
          options?.onSuccess?.()
          navigate(`/story/${storyData.story_id}`)
        },
        onComplete: () => {
          setStreaming(initialStreamingState)
        },
        onError: (data) => {
          setUploadStatus('error')
          setUploadError(data.message)
          setStreaming(initialStreamingState)
          options?.onError?.(data.message)
        },
      }

      try {
        await storyService.generateStoryFromImageStream(
          selectedImage,
          {
            childId,
            ageGroup,
            interests,
            voice: selectedVoice,
            enableAudio,
          },
          callbacks
        )
      } catch (err) {
        const message = getErrorMessage(err)
        setUploadStatus('error')
        setUploadError(message)
        setStreaming(initialStreamingState)
        options?.onError?.(message)
      }
    },
    [
      selectedImage,
      selectedVoice,
      enableAudio,
      currentChild,
      defaultChildId,
      setUploadStatus,
      setUploadError,
      setCurrentStory,
      navigate,
      options,
    ]
  )

  const resetAll = () => {
    reset()
    mutation.reset()
    setStreaming(initialStreamingState)
  }

  return {
    generate,
    generateStream,
    reset: resetAll,
    isLoading: mutation.isPending || streaming.isStreaming,
    isError: mutation.isError,
    isSuccess: mutation.isSuccess,
    error: mutation.error ? getErrorMessage(mutation.error) : null,
    data: mutation.data,
    streaming,
  }
}

export default useStoryGeneration
