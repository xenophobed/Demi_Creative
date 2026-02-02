/**
 * Confetti Component
 * Celebration confetti effect
 */

import { motion, AnimatePresence } from 'framer-motion'
import { useState, useEffect, useCallback, memo } from 'react'
import { useStreamVisualizationContext, registerEffectCallback } from '@/providers/StreamVisualizationProvider'
import { colors } from '@/config/animationPresets'
import type { EffectTrigger } from '@/types/streaming'

interface ConfettiPiece {
  id: number
  x: number
  y: number
  color: string
  size: number
  rotation: number
  shape: 'rect' | 'circle' | 'triangle'
  delay: number
}

interface ConfettiProps {
  active?: boolean
  count?: number
  colors?: string[]
  duration?: number
  spread?: number
  origin?: { x: number; y: number }
  className?: string
}

const defaultConfettiColors = [
  colors.primary,
  colors.secondary,
  colors.accent,
  colors.purple,
  colors.green,
  colors.blue,
  '#FFF',
]

// Confetti shape components
function RectShape({ size, color }: { size: number; color: string }) {
  return (
    <div
      style={{
        width: size,
        height: size * 0.4,
        backgroundColor: color,
        borderRadius: 2,
      }}
    />
  )
}

function CircleShape({ size, color }: { size: number; color: string }) {
  return (
    <div
      style={{
        width: size * 0.6,
        height: size * 0.6,
        backgroundColor: color,
        borderRadius: '50%',
      }}
    />
  )
}

function TriangleShape({ size, color }: { size: number; color: string }) {
  return (
    <div
      style={{
        width: 0,
        height: 0,
        borderLeft: `${size * 0.4}px solid transparent`,
        borderRight: `${size * 0.4}px solid transparent`,
        borderBottom: `${size * 0.7}px solid ${color}`,
      }}
    />
  )
}

const shapes = ['rect', 'circle', 'triangle'] as const

// Generate confetti pieces
function generateConfetti(
  count: number,
  colorOptions: string[],
  origin: { x: number; y: number },
  spread: number
): ConfettiPiece[] {
  const pieces: ConfettiPiece[] = []

  for (let i = 0; i < count; i++) {
    // Spread from origin
    const angle = (Math.random() - 0.5) * spread * (Math.PI / 180)
    const offsetX = Math.sin(angle) * Math.random() * 30

    pieces.push({
      id: Date.now() + i + Math.random(),
      x: origin.x + offsetX,
      y: origin.y - 10,
      color: colorOptions[Math.floor(Math.random() * colorOptions.length)],
      size: 8 + Math.random() * 10,
      rotation: Math.random() * 360,
      shape: shapes[Math.floor(Math.random() * shapes.length)],
      delay: Math.random() * 0.3,
    })
  }

  return pieces
}

function ConfettiComponent({
  active = false,
  count = 50,
  colors: colorOptions = defaultConfettiColors,
  duration = 4000,
  spread = 120,
  origin = { x: 50, y: 30 },
  className = '',
}: ConfettiProps) {
  const { prefersReducedMotion } = useStreamVisualizationContext()
  const [confetti, setConfetti] = useState<ConfettiPiece[]>([])

  // Trigger confetti
  const triggerConfetti = useCallback(() => {
    if (prefersReducedMotion) return

    setConfetti(generateConfetti(count, colorOptions, origin, spread))

    // Clear after duration
    setTimeout(() => {
      setConfetti([])
    }, duration)
  }, [count, colorOptions, origin, spread, duration, prefersReducedMotion])

  // Handle active prop changes
  useEffect(() => {
    if (active) {
      triggerConfetti()
    }
  }, [active, triggerConfetti])

  if (prefersReducedMotion || confetti.length === 0) {
    return null
  }

  return (
    <div
      className={`pointer-events-none fixed inset-0 overflow-hidden z-50 ${className}`}
      aria-hidden="true"
    >
      <AnimatePresence>
        {confetti.map((piece) => {
          // Random end position
          const endX = (Math.random() - 0.5) * 100
          const endY = 120 + Math.random() * 30
          const rotations = 2 + Math.random() * 4

          return (
            <motion.div
              key={piece.id}
              className="absolute"
              style={{
                left: `${piece.x}%`,
                top: `${piece.y}%`,
              }}
              initial={{
                opacity: 0,
                scale: 0,
                rotate: piece.rotation,
                x: 0,
                y: 0,
              }}
              animate={{
                opacity: [0, 1, 1, 0.8, 0],
                scale: [0, 1, 1, 0.8, 0.5],
                rotate: [piece.rotation, piece.rotation + 360 * rotations],
                x: [0, endX * 0.3, endX * 0.6, endX],
                y: [0, -30, endY * 0.5, endY],
              }}
              transition={{
                duration: duration / 1000,
                delay: piece.delay,
                ease: [0.25, 0.46, 0.45, 0.94],
              }}
            >
              {piece.shape === 'rect' && <RectShape size={piece.size} color={piece.color} />}
              {piece.shape === 'circle' && <CircleShape size={piece.size} color={piece.color} />}
              {piece.shape === 'triangle' && (
                <TriangleShape size={piece.size} color={piece.color} />
              )}
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}

export const Confetti = memo(ConfettiComponent)

// Global confetti controller that responds to effect triggers
export function ConfettiController() {
  const { prefersReducedMotion } = useStreamVisualizationContext()
  const [isActive, setIsActive] = useState(false)
  const [config, setConfig] = useState<Partial<ConfettiProps>>({})

  useEffect(() => {
    if (prefersReducedMotion) return

    const unregister = registerEffectCallback((effect: EffectTrigger) => {
      if (effect.type === 'confetti') {
        setConfig({
          count: effect.count || 50,
          duration: effect.duration || 4000,
          colors: effect.colors,
          origin: effect.origin ? { x: effect.origin.x, y: effect.origin.y } : undefined,
        })
        setIsActive(true)

        // Reset after animation
        setTimeout(() => {
          setIsActive(false)
        }, (effect.duration || 4000) + 100)
      }
    })

    return unregister
  }, [prefersReducedMotion])

  if (prefersReducedMotion) return null

  return <Confetti active={isActive} {...config} />
}

export default Confetti
