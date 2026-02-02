/**
 * useParallax Hook
 * Provides parallax motion values based on mouse and scroll position
 */

import { useSpring, useTransform, type MotionValue } from 'framer-motion'
import { useMemo } from 'react'
import { useStreamVisualizationContext } from '@/providers/StreamVisualizationProvider'
import { defaultParallaxConfig, defaultTiltConfig } from '@/config/animationPresets'
import type { ParallaxConfig, TiltConfig } from '@/types/streaming'

interface UseParallaxOptions {
  parallaxConfig?: Partial<ParallaxConfig>
  tiltConfig?: Partial<TiltConfig>
}

interface UseParallaxReturn {
  // Motion values for parallax movement
  x: MotionValue<number>
  y: MotionValue<number>

  // Motion values for tilt rotation
  rotateX: MotionValue<number>
  rotateY: MotionValue<number>

  // Scale for hover effect
  scale: MotionValue<number>

  // Computed style object for convenience
  style: {
    x: MotionValue<number>
    y: MotionValue<number>
    rotateX: MotionValue<number>
    rotateY: MotionValue<number>
  }

  // Whether effects are enabled
  isEnabled: boolean

  // Raw mouse position (-1 to 1)
  mousePosition: { x: number; y: number }

  // Scroll position
  scrollPosition: number
}

export function useParallax(options?: UseParallaxOptions): UseParallaxReturn {
  const { mousePosition, scrollPosition, prefersReducedMotion } =
    useStreamVisualizationContext()

  // Merge configs
  const parallaxConfig = useMemo(
    () => ({
      ...defaultParallaxConfig,
      ...options?.parallaxConfig,
    }),
    [options?.parallaxConfig]
  )

  const tiltConfig = useMemo(
    () => ({
      ...defaultTiltConfig,
      ...options?.tiltConfig,
    }),
    [options?.tiltConfig]
  )

  const isEnabled = !prefersReducedMotion && parallaxConfig.enabled

  // Spring config based on smoothing
  const springConfig = useMemo(
    () => ({
      stiffness: 150 * (1 - parallaxConfig.smoothing) + 50,
      damping: 20 + parallaxConfig.smoothing * 10,
    }),
    [parallaxConfig.smoothing]
  )

  // Create spring-smoothed mouse values
  const mouseXSpring = useSpring(isEnabled ? mousePosition.x : 0, springConfig)
  const mouseYSpring = useSpring(isEnabled ? mousePosition.y : 0, springConfig)

  // Transform to parallax movement
  const maxMove = parallaxConfig.maxTranslation * parallaxConfig.intensity
  const x = useTransform(mouseXSpring, [-1, 1], [-maxMove, maxMove])
  const y = useTransform(mouseYSpring, [-1, 1], [-maxMove, maxMove])

  // Transform to tilt rotation
  const maxTilt = tiltConfig.enabled ? tiltConfig.maxTilt : 0
  const rotateX = useTransform(mouseYSpring, [-1, 1], [maxTilt, -maxTilt])
  const rotateY = useTransform(mouseXSpring, [-1, 1], [-maxTilt, maxTilt])

  // Scale (static for now, can be animated on hover)
  const scale = useSpring(1, { stiffness: 300, damping: 30 })

  return {
    x,
    y,
    rotateX,
    rotateY,
    scale,
    style: {
      x,
      y,
      rotateX,
      rotateY,
    },
    isEnabled,
    mousePosition,
    scrollPosition,
  }
}

// Hook for element-specific tilt on hover
export function useTilt(config?: Partial<TiltConfig>) {
  const { prefersReducedMotion } = useStreamVisualizationContext()

  const tiltConfig = useMemo(
    () => ({
      ...defaultTiltConfig,
      ...config,
    }),
    [config]
  )

  const isEnabled = !prefersReducedMotion && tiltConfig.enabled

  // Spring values for rotation
  const rotateX = useSpring(0, { stiffness: 300, damping: 30 })
  const rotateY = useSpring(0, { stiffness: 300, damping: 30 })
  const scale = useSpring(1, { stiffness: 300, damping: 30 })

  const handleMouseMove = (event: React.MouseEvent<HTMLElement>) => {
    if (!isEnabled) return

    const rect = event.currentTarget.getBoundingClientRect()
    const centerX = rect.left + rect.width / 2
    const centerY = rect.top + rect.height / 2

    // Calculate position relative to center (-1 to 1)
    const x = (event.clientX - centerX) / (rect.width / 2)
    const y = (event.clientY - centerY) / (rect.height / 2)

    // Apply tilt
    rotateX.set(-y * tiltConfig.maxTilt)
    rotateY.set(x * tiltConfig.maxTilt)
  }

  const handleMouseEnter = () => {
    if (!isEnabled) return
    scale.set(tiltConfig.scale)
  }

  const handleMouseLeave = () => {
    rotateX.set(0)
    rotateY.set(0)
    scale.set(1)
  }

  return {
    rotateX,
    rotateY,
    scale,
    handlers: {
      onMouseMove: handleMouseMove,
      onMouseEnter: handleMouseEnter,
      onMouseLeave: handleMouseLeave,
    },
    style: {
      rotateX,
      rotateY,
      scale,
    },
    isEnabled,
  }
}

export default useParallax
