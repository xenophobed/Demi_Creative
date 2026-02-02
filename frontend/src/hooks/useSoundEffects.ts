/**
 * useSoundEffects Hook
 * Manages sound effects for animation phases and interactions
 */

import { useCallback, useEffect, useRef } from 'react'
import { Howl, Howler } from 'howler'
import { useStreamVisualizationContext } from '@/providers/StreamVisualizationProvider'
import type { AnimationPhase } from '@/types/streaming'

// Sound effect URLs - using data URIs for simple sounds to avoid external dependencies
// In production, these would be actual audio file paths
const soundConfig = {
  connecting: {
    // Gentle chime
    src: 'data:audio/wav;base64,UklGRl9vT19LV0NQAGZpbHRlcl9ub25lAA==',
    volume: 0.3,
  },
  thinking: {
    // Soft bubble
    src: 'data:audio/wav;base64,UklGRl9vT19LV0NQAGZpbHRlcl9ub25lAA==',
    volume: 0.2,
  },
  tool_executing: {
    // Quick ping
    src: 'data:audio/wav;base64,UklGRl9vT19LV0NQAGZpbHRlcl9ub25lAA==',
    volume: 0.25,
  },
  revealing: {
    // Sparkle
    src: 'data:audio/wav;base64,UklGRl9vT19LV0NQAGZpbHRlcl9ub25lAA==',
    volume: 0.3,
  },
  complete: {
    // Celebration
    src: 'data:audio/wav;base64,UklGRl9vT19LV0NQAGZpbHRlcl9ub25lAA==',
    volume: 0.4,
  },
  error: {
    // Gentle error
    src: 'data:audio/wav;base64,UklGRl9vT19LV0NQAGZpbHRlcl9ub25lAA==',
    volume: 0.2,
  },
}

interface UseSoundEffectsOptions {
  enabled?: boolean
  volume?: number
}

interface UseSoundEffectsReturn {
  playSound: (phase: AnimationPhase) => void
  setVolume: (volume: number) => void
  mute: () => void
  unmute: () => void
  isMuted: boolean
}

export function useSoundEffects(options: UseSoundEffectsOptions = {}): UseSoundEffectsReturn {
  const { enabled = true, volume: defaultVolume = 0.5 } = options
  const { phase, prefersReducedMotion } = useStreamVisualizationContext()

  const soundsRef = useRef<Map<AnimationPhase, Howl>>(new Map())
  const previousPhaseRef = useRef<AnimationPhase>('idle')
  const isMutedRef = useRef(false)

  // Initialize sounds
  useEffect(() => {
    if (!enabled || prefersReducedMotion) return

    // Pre-load sounds
    Object.entries(soundConfig).forEach(([phaseName, config]) => {
      const sound = new Howl({
        src: [config.src],
        volume: config.volume * defaultVolume,
        preload: true,
      })
      soundsRef.current.set(phaseName as AnimationPhase, sound)
    })

    // Cleanup
    return () => {
      soundsRef.current.forEach((sound) => sound.unload())
      soundsRef.current.clear()
    }
  }, [enabled, prefersReducedMotion, defaultVolume])

  // Play sound on phase change
  useEffect(() => {
    if (!enabled || prefersReducedMotion || isMutedRef.current) return
    if (phase === previousPhaseRef.current) return
    if (phase === 'idle') return

    const sound = soundsRef.current.get(phase)
    if (sound) {
      sound.play()
    }

    previousPhaseRef.current = phase
  }, [phase, enabled, prefersReducedMotion])

  // Manual play function
  const playSound = useCallback(
    (soundPhase: AnimationPhase) => {
      if (!enabled || prefersReducedMotion || isMutedRef.current) return
      const sound = soundsRef.current.get(soundPhase)
      if (sound) {
        sound.play()
      }
    },
    [enabled, prefersReducedMotion]
  )

  // Volume control
  const setVolume = useCallback((newVolume: number) => {
    Howler.volume(Math.max(0, Math.min(1, newVolume)))
  }, [])

  // Mute/unmute
  const mute = useCallback(() => {
    Howler.mute(true)
    isMutedRef.current = true
  }, [])

  const unmute = useCallback(() => {
    Howler.mute(false)
    isMutedRef.current = false
  }, [])

  return {
    playSound,
    setVolume,
    mute,
    unmute,
    isMuted: isMutedRef.current,
  }
}

export default useSoundEffects
