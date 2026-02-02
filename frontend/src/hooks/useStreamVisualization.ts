/**
 * useStreamVisualization Hook
 * Maps SSE events to animation phases and manages visualization state
 */

import { useCallback, useEffect, useRef } from 'react'
import { useStreamVisualizationContext } from '@/providers/StreamVisualizationProvider'
import type { AnimationPhase } from '@/types/streaming'
import type {
  SSEStatusData,
  SSEThinkingData,
  SSEToolUseData,
  StreamCallbacks,
} from '@/types/api'

interface UseStreamVisualizationReturn {
  // Current state
  phase: AnimationPhase
  isAnimating: boolean
  message: string
  thinkingContent: string
  currentTool: string | null
  prefersReducedMotion: boolean

  // Actions
  startVisualization: () => void
  stopVisualization: () => void
  triggerConfetti: () => void
  triggerSparkles: () => void

  // Stream callbacks that integrate with visualization
  createStreamCallbacks: (originalCallbacks?: StreamCallbacks) => StreamCallbacks
}

export function useStreamVisualization(): UseStreamVisualizationReturn {
  const context = useStreamVisualizationContext()
  const {
    phase,
    isAnimating,
    message,
    thinkingContent,
    currentTool,
    prefersReducedMotion,
    setPhase,
    setMessage,
    setThinkingContent,
    setCurrentTool,
    triggerEffect,
    reset,
  } = context

  // Track if visualization is active
  const isActiveRef = useRef(false)

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (isActiveRef.current) {
        reset()
      }
    }
  }, [reset])

  // Start visualization
  const startVisualization = useCallback(() => {
    isActiveRef.current = true
    setPhase('connecting')
    setMessage('Connecting...')
  }, [setPhase, setMessage])

  // Stop visualization
  const stopVisualization = useCallback(() => {
    isActiveRef.current = false
    reset()
  }, [reset])

  // Trigger effects
  const triggerConfetti = useCallback(() => {
    triggerEffect('confetti')
  }, [triggerEffect])

  const triggerSparkles = useCallback(() => {
    triggerEffect('sparkles')
  }, [triggerEffect])

  // Map SSE status to animation phase
  const mapStatusToPhase = useCallback((status: string): AnimationPhase => {
    switch (status) {
      case 'started':
        return 'connecting'
      case 'processing':
        return 'thinking'
      case 'completed':
        return 'complete'
      default:
        return 'thinking'
    }
  }, [])

  // Create stream callbacks that integrate with visualization
  const createStreamCallbacks = useCallback(
    (originalCallbacks?: StreamCallbacks): StreamCallbacks => {
      return {
        onStatus: (data: SSEStatusData) => {
          if (!isActiveRef.current) return

          const newPhase = mapStatusToPhase(data.status)
          setPhase(newPhase)
          setMessage(data.message)

          // Trigger celebration on complete
          if (data.status === 'completed') {
            triggerEffect('confetti')
          }

          // Call original callback
          originalCallbacks?.onStatus?.(data)
        },

        onThinking: (data: SSEThinkingData) => {
          if (!isActiveRef.current) return

          setPhase('thinking')
          setThinkingContent(data.content)

          // Trigger sparkles periodically during thinking
          if (data.turn % 2 === 0) {
            triggerEffect('sparkles')
          }

          originalCallbacks?.onThinking?.(data)
        },

        onToolUse: (data: SSEToolUseData) => {
          if (!isActiveRef.current) return

          setPhase('tool_executing')
          setCurrentTool(data.tool)
          setMessage(data.message)

          // Trigger stars when using tools
          triggerEffect('stars')

          originalCallbacks?.onToolUse?.(data)
        },

        onToolResult: (data) => {
          if (!isActiveRef.current) return

          setPhase('thinking')
          setCurrentTool(null)

          originalCallbacks?.onToolResult?.(data)
        },

        onSession: (data) => {
          originalCallbacks?.onSession?.(data)
        },

        onResult: (data) => {
          if (!isActiveRef.current) return

          setPhase('revealing')
          setMessage('Story is ready!')

          originalCallbacks?.onResult?.(data)
        },

        onComplete: (data) => {
          if (!isActiveRef.current) return

          setPhase('complete')
          setMessage('Complete!')
          triggerEffect('confetti')

          // Reset after delay
          setTimeout(() => {
            if (isActiveRef.current) {
              isActiveRef.current = false
              reset()
            }
          }, 3000)

          originalCallbacks?.onComplete?.(data)
        },

        onError: (data) => {
          if (!isActiveRef.current) return

          setPhase('error')
          setMessage(data.message)
          setCurrentTool(null)

          // Reset after delay
          setTimeout(() => {
            if (isActiveRef.current) {
              isActiveRef.current = false
              reset()
            }
          }, 2000)

          originalCallbacks?.onError?.(data)
        },
      }
    },
    [
      setPhase,
      setMessage,
      setThinkingContent,
      setCurrentTool,
      triggerEffect,
      reset,
      mapStatusToPhase,
    ]
  )

  return {
    phase,
    isAnimating,
    message,
    thinkingContent,
    currentTool,
    prefersReducedMotion,
    startVisualization,
    stopVisualization,
    triggerConfetti,
    triggerSparkles,
    createStreamCallbacks,
  }
}

export default useStreamVisualization
