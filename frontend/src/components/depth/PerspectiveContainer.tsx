/**
 * PerspectiveContainer Component
 * Container that sets up 3D perspective for child elements
 */

import { motion, useSpring, useTransform } from 'framer-motion'
import { useMemo, type ReactNode, type CSSProperties } from 'react'
import { useStreamVisualizationContext } from '@/providers/StreamVisualizationProvider'
import { defaultParallaxConfig } from '@/config/animationPresets'
import type { ParallaxConfig } from '@/types/streaming'

interface PerspectiveContainerProps {
  children: ReactNode
  config?: Partial<ParallaxConfig>
  className?: string
  style?: CSSProperties
  enableTilt?: boolean
}

export function PerspectiveContainer({
  children,
  config,
  className = '',
  style,
  enableTilt = true,
}: PerspectiveContainerProps) {
  const { mousePosition, prefersReducedMotion } = useStreamVisualizationContext()

  // Merge config with defaults
  const finalConfig = useMemo(
    () => ({
      ...defaultParallaxConfig,
      ...config,
    }),
    [config]
  )

  // Create smooth spring values
  const springConfig = { stiffness: 150, damping: 20 }
  const mouseXSpring = useSpring(mousePosition.x, springConfig)
  const mouseYSpring = useSpring(mousePosition.y, springConfig)

  // Transform mouse position to rotation
  const rotateX = useTransform(
    mouseYSpring,
    [-1, 1],
    [finalConfig.maxRotation, -finalConfig.maxRotation]
  )
  const rotateY = useTransform(
    mouseXSpring,
    [-1, 1],
    [-finalConfig.maxRotation, finalConfig.maxRotation]
  )

  // If reduced motion or tilt disabled, render without effects
  if (prefersReducedMotion || !enableTilt || !finalConfig.enabled) {
    return (
      <div
        className={className}
        style={{
          perspective: `${finalConfig.perspective}px`,
          ...style,
        }}
      >
        {children}
      </div>
    )
  }

  return (
    <div
      className={`${className}`}
      style={{
        perspective: `${finalConfig.perspective}px`,
        ...style,
      }}
    >
      <motion.div
        className="preserve-3d gpu-accelerated w-full h-full"
        style={{
          rotateX,
          rotateY,
        }}
      >
        {children}
      </motion.div>
    </div>
  )
}

export default PerspectiveContainer
