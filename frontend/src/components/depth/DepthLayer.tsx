/**
 * DepthLayer Component
 * Wrapper component that applies parallax effects based on mouse/scroll position
 */

import { motion, useSpring, useTransform } from 'framer-motion'
import { useMemo, type ReactNode, type CSSProperties } from 'react'
import { useStreamVisualizationContext } from '@/providers/StreamVisualizationProvider'
import type { DepthConfig } from '@/types/streaming'

interface DepthLayerProps {
  children: ReactNode
  config?: Partial<DepthConfig>
  className?: string
  style?: CSSProperties
  as?: 'div' | 'section' | 'article' | 'main'
}

const layerDefaults: Record<DepthConfig['layer'], DepthConfig> = {
  background: {
    layer: 'background',
    parallaxFactor: 0.3,
    scale: 1.1,
    blur: 0,
    opacity: 0.8,
  },
  midground: {
    layer: 'midground',
    parallaxFactor: 0.5,
    scale: 1,
    blur: 0,
    opacity: 1,
  },
  foreground: {
    layer: 'foreground',
    parallaxFactor: 0.8,
    scale: 1,
    blur: 0,
    opacity: 1,
  },
}

export function DepthLayer({
  children,
  config,
  className = '',
  style,
  as: Component = 'div',
}: DepthLayerProps) {
  const { mousePosition, prefersReducedMotion } = useStreamVisualizationContext()

  // Merge config with defaults
  const finalConfig = useMemo(() => {
    const layer = config?.layer || 'midground'
    return { ...layerDefaults[layer], ...config }
  }, [config])

  // Create smooth spring values for mouse position
  const mouseXSpring = useSpring(mousePosition.x, { stiffness: 100, damping: 30 })
  const mouseYSpring = useSpring(mousePosition.y, { stiffness: 100, damping: 30 })

  // Transform mouse position to movement
  const maxMove = 20 * finalConfig.parallaxFactor
  const x = useTransform(mouseXSpring, [-1, 1], [-maxMove, maxMove])
  const y = useTransform(mouseYSpring, [-1, 1], [-maxMove, maxMove])

  // If reduced motion is preferred, render without parallax
  if (prefersReducedMotion) {
    const MotionComponent = motion[Component]
    return (
      <MotionComponent
        className={`${className}`}
        style={{
          ...style,
          opacity: finalConfig.opacity,
        }}
      >
        {children}
      </MotionComponent>
    )
  }

  const MotionComponent = motion[Component]

  return (
    <MotionComponent
      className={`preserve-3d gpu-accelerated ${className}`}
      style={{
        x,
        y,
        scale: finalConfig.scale,
        opacity: finalConfig.opacity,
        filter: finalConfig.blur ? `blur(${finalConfig.blur}px)` : undefined,
        ...style,
      }}
    >
      {children}
    </MotionComponent>
  )
}

export default DepthLayer
