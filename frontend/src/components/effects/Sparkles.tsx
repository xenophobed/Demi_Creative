/**
 * Sparkles Component
 * Lightweight sparkle effect overlay
 */

import { motion, AnimatePresence } from 'framer-motion'
import { useState, useEffect, memo } from 'react'
import { useStreamVisualizationContext } from '@/providers/StreamVisualizationProvider'
import { colors } from '@/config/animationPresets'

interface Sparkle {
  id: number
  x: number
  y: number
  size: number
  color: string
  delay: number
}

interface SparklesProps {
  active?: boolean
  count?: number
  colors?: string[]
  duration?: number
  spread?: 'full' | 'center' | 'edges'
  className?: string
}

// Sparkle SVG shape
function SparkleShape({ size, color }: { size: number; color: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 160 160" fill="none">
      <path
        d="M80 0C80 0 84.2846 41.2925 101.496 58.504C118.707 75.7154 160 80 160 80C160 80 118.707 84.2846 101.496 101.496C84.2846 118.707 80 160 80 160C80 160 75.7154 118.707 58.504 101.496C41.2925 84.2846 0 80 0 80C0 80 41.2925 75.7154 58.504 58.504C75.7154 41.2925 80 0 80 0Z"
        fill={color}
      />
    </svg>
  )
}

// Generate random sparkles
function generateSparkles(
  count: number,
  colorOptions: string[],
  spread: 'full' | 'center' | 'edges'
): Sparkle[] {
  const sparkles: Sparkle[] = []

  for (let i = 0; i < count; i++) {
    let x: number, y: number

    switch (spread) {
      case 'center':
        x = 30 + Math.random() * 40
        y = 30 + Math.random() * 40
        break
      case 'edges':
        if (Math.random() > 0.5) {
          x = Math.random() > 0.5 ? Math.random() * 20 : 80 + Math.random() * 20
          y = Math.random() * 100
        } else {
          x = Math.random() * 100
          y = Math.random() > 0.5 ? Math.random() * 20 : 80 + Math.random() * 20
        }
        break
      case 'full':
      default:
        x = Math.random() * 100
        y = Math.random() * 100
    }

    sparkles.push({
      id: Date.now() + i,
      x,
      y,
      size: 8 + Math.random() * 16,
      color: colorOptions[Math.floor(Math.random() * colorOptions.length)],
      delay: Math.random() * 0.8,
    })
  }

  return sparkles
}

const defaultColors = [colors.accent, colors.primary, colors.secondary, '#FFF']

function SparklesComponent({
  active = true,
  count = 15,
  colors: colorOptions = defaultColors,
  duration = 2000,
  spread = 'full',
  className = '',
}: SparklesProps) {
  const { prefersReducedMotion } = useStreamVisualizationContext()
  const [sparkles, setSparkles] = useState<Sparkle[]>([])

  useEffect(() => {
    if (!active || prefersReducedMotion) {
      setSparkles([])
      return
    }

    // Generate initial sparkles
    setSparkles(generateSparkles(count, colorOptions, spread))

    // Regenerate sparkles periodically
    const interval = setInterval(() => {
      setSparkles(generateSparkles(count, colorOptions, spread))
    }, duration * 0.75)

    return () => clearInterval(interval)
  }, [active, count, colorOptions, duration, spread, prefersReducedMotion])

  if (prefersReducedMotion || !active) {
    return null
  }

  return (
    <div
      className={`pointer-events-none absolute inset-0 overflow-hidden ${className}`}
      aria-hidden="true"
    >
      <AnimatePresence mode="popLayout">
        {sparkles.map((sparkle) => (
          <motion.div
            key={sparkle.id}
            className="absolute"
            style={{
              left: `${sparkle.x}%`,
              top: `${sparkle.y}%`,
            }}
            initial={{ opacity: 0, scale: 0, rotate: 0 }}
            animate={{
              opacity: [0, 1, 1, 0],
              scale: [0, 1, 1.2, 0],
              rotate: [0, 180],
            }}
            exit={{ opacity: 0, scale: 0 }}
            transition={{
              duration: duration / 1000,
              delay: sparkle.delay,
              ease: 'easeInOut',
            }}
          >
            <SparkleShape size={sparkle.size} color={sparkle.color} />
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}

export const Sparkles = memo(SparklesComponent)

// Export a quick burst variant
interface SparkBurstProps {
  trigger?: boolean
  origin?: { x: number; y: number }
  count?: number
  colors?: string[]
  onComplete?: () => void
}

export function SparkBurst({
  trigger = false,
  origin = { x: 50, y: 50 },
  count = 8,
  colors: colorOptions = defaultColors,
  onComplete,
}: SparkBurstProps) {
  const { prefersReducedMotion } = useStreamVisualizationContext()
  const [sparkles, setSparkles] = useState<Sparkle[]>([])

  useEffect(() => {
    if (!trigger || prefersReducedMotion) return

    const newSparkles: Sparkle[] = []
    for (let i = 0; i < count; i++) {
      newSparkles.push({
        id: Date.now() + i,
        x: origin.x,
        y: origin.y,
        size: 10 + Math.random() * 12,
        color: colorOptions[i % colorOptions.length],
        delay: i * 0.02,
      })
    }

    setSparkles(newSparkles)

    const timeout = setTimeout(() => {
      setSparkles([])
      onComplete?.()
    }, 1000)

    return () => clearTimeout(timeout)
  }, [trigger, origin, count, colorOptions, onComplete, prefersReducedMotion])

  if (prefersReducedMotion || sparkles.length === 0) {
    return null
  }

  return (
    <div className="pointer-events-none fixed inset-0 overflow-hidden z-50" aria-hidden="true">
      <AnimatePresence>
        {sparkles.map((sparkle, i) => {
          const burstAngle = (i / sparkles.length) * Math.PI * 2
          const distance = 60 + Math.random() * 40

          return (
            <motion.div
              key={sparkle.id}
              className="absolute"
              style={{
                left: `${sparkle.x}%`,
                top: `${sparkle.y}%`,
              }}
              initial={{ opacity: 0, scale: 0, x: 0, y: 0 }}
              animate={{
                opacity: [0, 1, 1, 0],
                scale: [0, 1.5, 1, 0],
                x: Math.cos(burstAngle) * distance,
                y: Math.sin(burstAngle) * distance,
                rotate: [0, 360],
              }}
              transition={{
                duration: 0.8,
                delay: sparkle.delay,
                ease: 'easeOut',
              }}
            >
              <SparkleShape size={sparkle.size} color={sparkle.color} />
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}

export default Sparkles
