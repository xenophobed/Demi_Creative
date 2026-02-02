/**
 * Stream Visualization Provider
 * Global context for managing 2.5D animations and streaming visualization state
 */

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useMemo,
  type ReactNode,
} from 'react'
import type {
  AnimationPhase,
  IntensityLevel,
  StreamVisualizationContextValue,
  EffectTrigger,
} from '@/types/streaming'

// Create context with undefined default
const StreamVisualizationContext = createContext<StreamVisualizationContextValue | undefined>(
  undefined
)

// Effect queue for triggering animations
type EffectCallback = (effect: EffectTrigger) => void
const effectCallbacks = new Set<EffectCallback>()

export function registerEffectCallback(callback: EffectCallback): () => void {
  effectCallbacks.add(callback)
  return () => effectCallbacks.delete(callback)
}

function notifyEffectCallbacks(effect: EffectTrigger) {
  effectCallbacks.forEach((callback) => callback(effect))
}

interface StreamVisualizationProviderProps {
  children: ReactNode
}

export function StreamVisualizationProvider({ children }: StreamVisualizationProviderProps) {
  // Core state
  const [phase, setPhaseState] = useState<AnimationPhase>('idle')
  const [intensity, setIntensityState] = useState<IntensityLevel>('medium')
  const [isAnimating, setIsAnimating] = useState(false)
  const [message, setMessageState] = useState('')
  const [thinkingContent, setThinkingContentState] = useState('')
  const [currentTool, setCurrentToolState] = useState<string | null>(null)

  // Mouse/scroll tracking
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 })
  const [scrollPosition, setScrollPosition] = useState(0)

  // Reduced motion preference
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false)

  // Check for reduced motion preference
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
    setPrefersReducedMotion(mediaQuery.matches)

    const handler = (event: MediaQueryListEvent) => {
      setPrefersReducedMotion(event.matches)
    }

    mediaQuery.addEventListener('change', handler)
    return () => mediaQuery.removeEventListener('change', handler)
  }, [])

  // Mouse tracking (throttled)
  useEffect(() => {
    if (prefersReducedMotion) return

    let rafId: number
    let lastX = 0
    let lastY = 0

    const handleMouseMove = (event: MouseEvent) => {
      cancelAnimationFrame(rafId)
      rafId = requestAnimationFrame(() => {
        // Normalize to -1 to 1 range
        const x = (event.clientX / window.innerWidth) * 2 - 1
        const y = (event.clientY / window.innerHeight) * 2 - 1

        // Apply smoothing
        const smoothing = 0.1
        lastX += (x - lastX) * smoothing
        lastY += (y - lastY) * smoothing

        setMousePosition({ x: lastX, y: lastY })
      })
    }

    window.addEventListener('mousemove', handleMouseMove, { passive: true })
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      cancelAnimationFrame(rafId)
    }
  }, [prefersReducedMotion])

  // Scroll tracking (throttled)
  useEffect(() => {
    if (prefersReducedMotion) return

    let rafId: number
    let lastScroll = 0

    const handleScroll = () => {
      cancelAnimationFrame(rafId)
      rafId = requestAnimationFrame(() => {
        const scroll = window.scrollY
        const smoothing = 0.15
        lastScroll += (scroll - lastScroll) * smoothing
        setScrollPosition(lastScroll)
      })
    }

    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => {
      window.removeEventListener('scroll', handleScroll)
      cancelAnimationFrame(rafId)
    }
  }, [prefersReducedMotion])

  // Update animating state based on phase
  useEffect(() => {
    setIsAnimating(phase !== 'idle' && phase !== 'complete' && phase !== 'error')
  }, [phase])

  // Actions
  const setPhase = useCallback((newPhase: AnimationPhase) => {
    setPhaseState(newPhase)
  }, [])

  const setIntensity = useCallback((newIntensity: IntensityLevel) => {
    setIntensityState(newIntensity)
  }, [])

  const setMessage = useCallback((newMessage: string) => {
    setMessageState(newMessage)
  }, [])

  const setThinkingContent = useCallback((content: string) => {
    setThinkingContentState(content)
  }, [])

  const setCurrentTool = useCallback((tool: string | null) => {
    setCurrentToolState(tool)
  }, [])

  const triggerEffect = useCallback(
    (effect: 'confetti' | 'sparkles' | 'stars') => {
      if (prefersReducedMotion) return

      const effectTrigger: EffectTrigger = {
        type: effect === 'confetti' ? 'confetti' : effect === 'sparkles' ? 'sparkles' : 'stars',
        count: effect === 'confetti' ? 50 : 25,
        duration: effect === 'confetti' ? 4000 : 2000,
      }

      notifyEffectCallbacks(effectTrigger)
    },
    [prefersReducedMotion]
  )

  const reset = useCallback(() => {
    setPhaseState('idle')
    setIntensityState('medium')
    setMessageState('')
    setThinkingContentState('')
    setCurrentToolState(null)
    setIsAnimating(false)
  }, [])

  // Memoize context value
  const contextValue = useMemo<StreamVisualizationContextValue>(
    () => ({
      phase,
      intensity,
      isAnimating,
      message,
      thinkingContent,
      currentTool,
      mousePosition,
      scrollPosition,
      prefersReducedMotion,
      setPhase,
      setIntensity,
      setMessage,
      setThinkingContent,
      setCurrentTool,
      triggerEffect,
      reset,
    }),
    [
      phase,
      intensity,
      isAnimating,
      message,
      thinkingContent,
      currentTool,
      mousePosition,
      scrollPosition,
      prefersReducedMotion,
      setPhase,
      setIntensity,
      setMessage,
      setThinkingContent,
      setCurrentTool,
      triggerEffect,
      reset,
    ]
  )

  return (
    <StreamVisualizationContext.Provider value={contextValue}>
      {children}
    </StreamVisualizationContext.Provider>
  )
}

// Hook to use stream visualization context
export function useStreamVisualizationContext(): StreamVisualizationContextValue {
  const context = useContext(StreamVisualizationContext)
  if (!context) {
    throw new Error(
      'useStreamVisualizationContext must be used within a StreamVisualizationProvider'
    )
  }
  return context
}

export default StreamVisualizationProvider
