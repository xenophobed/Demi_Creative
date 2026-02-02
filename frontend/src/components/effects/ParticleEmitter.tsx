/**
 * ParticleEmitter Component
 * Renders animated particles based on configuration
 */

import { motion, AnimatePresence } from 'framer-motion'
import { useState, useEffect, useMemo, memo } from 'react'
import { useStreamVisualizationContext } from '@/providers/StreamVisualizationProvider'
import type { ParticleConfig, ParticleType } from '@/types/streaming'

interface Particle {
  id: number
  x: number
  y: number
  size: number
  color: string
  rotation: number
  delay: number
}

interface ParticleEmitterProps {
  config: ParticleConfig
  active?: boolean
  origin?: { x: number; y: number }
  className?: string
}

// Particle shape renderers
const ParticleShapes: Record<ParticleType, React.FC<{ size: number; color: string }>> = {
  sparkle: ({ size, color }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={color}>
      <path d="M12 0L14.59 9.41L24 12L14.59 14.59L12 24L9.41 14.59L0 12L9.41 9.41L12 0Z" />
    </svg>
  ),
  star: ({ size, color }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={color}>
      <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
    </svg>
  ),
  bubble: ({ size, color }) => (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        background: `radial-gradient(circle at 30% 30%, ${color}, transparent)`,
        border: `2px solid ${color}`,
        opacity: 0.7,
      }}
    />
  ),
  confetti: ({ size, color }) => (
    <div
      style={{
        width: size,
        height: size * 0.4,
        backgroundColor: color,
        borderRadius: 2,
      }}
    />
  ),
}

// Generate random number in range
function random(min: number, max: number): number {
  return Math.random() * (max - min) + min
}

// Generate particles
function generateParticles(config: ParticleConfig, origin?: { x: number; y: number }): Particle[] {
  const particles: Particle[] = []
  const { count, colors, size, spread } = config

  for (let i = 0; i < count; i++) {
    // Calculate spread angle
    const angle = random(-spread / 2, spread / 2) * (Math.PI / 180)

    // Random position within container (or from origin)
    const startX = origin?.x ?? random(10, 90)
    const startY = origin?.y ?? random(10, 90)

    particles.push({
      id: Date.now() + i,
      x: startX + Math.sin(angle) * random(0, 30),
      y: startY,
      size: random(size.min, size.max),
      color: colors[Math.floor(Math.random() * colors.length)],
      rotation: random(0, 360),
      delay: random(0, 0.5),
    })
  }

  return particles
}

// Get animation based on behavior
function getAnimation(config: ParticleConfig, particle: Particle) {
  const { behavior, speed, lifetime } = config
  const duration = lifetime / 1000

  const baseAnimation = {
    opacity: [0, 1, 1, 0],
    scale: [0, 1, 1, 0],
  }

  switch (behavior) {
    case 'rise':
      return {
        ...baseAnimation,
        y: [0, -random(100, 200)],
        x: [0, random(-30, 30)],
        rotate: [0, random(-180, 180)],
        transition: {
          duration: duration * random(speed.min, speed.max),
          delay: particle.delay,
          ease: 'easeOut',
        },
      }

    case 'fall':
      return {
        ...baseAnimation,
        y: [0, random(100, 200)],
        x: [0, random(-50, 50)],
        rotate: [0, random(-360, 360)],
        transition: {
          duration: duration * random(speed.min, speed.max),
          delay: particle.delay,
          ease: [0.25, 0.46, 0.45, 0.94],
        },
      }

    case 'drift':
      return {
        ...baseAnimation,
        y: [0, random(-50, 50)],
        x: [0, random(-80, 80)],
        rotate: [0, random(-180, 180)],
        transition: {
          duration: duration * random(speed.min, speed.max),
          delay: particle.delay,
          ease: 'easeInOut',
        },
      }

    case 'burst':
      const angle = random(0, 360) * (Math.PI / 180)
      const distance = random(50, 150)
      return {
        ...baseAnimation,
        x: [0, Math.cos(angle) * distance],
        y: [0, Math.sin(angle) * distance],
        rotate: [0, random(-360, 360)],
        transition: {
          duration: duration * random(speed.min, speed.max) * 0.5,
          delay: particle.delay,
          ease: 'easeOut',
        },
      }

    case 'float':
    default:
      return {
        ...baseAnimation,
        y: [0, random(-20, -50), random(-30, -80)],
        x: [0, random(-20, 20), random(-30, 30)],
        rotate: [0, random(-90, 90)],
        transition: {
          duration: duration * random(speed.min, speed.max),
          delay: particle.delay,
          ease: 'easeInOut',
          repeat: Infinity,
          repeatType: 'reverse' as const,
        },
      }
  }
}

function ParticleEmitterComponent({
  config,
  active = true,
  origin,
  className = '',
}: ParticleEmitterProps) {
  const { prefersReducedMotion } = useStreamVisualizationContext()
  const [particles, setParticles] = useState<Particle[]>([])

  // Generate particles when active
  useEffect(() => {
    if (!active || prefersReducedMotion) {
      setParticles([])
      return
    }

    // Initial particles
    setParticles(generateParticles(config, origin))

    // Regenerate particles periodically for continuous effects
    if (config.behavior === 'float' || config.behavior === 'rise') {
      const interval = setInterval(() => {
        setParticles(generateParticles(config, origin))
      }, config.lifetime * 0.8)

      return () => clearInterval(interval)
    }
  }, [active, config, origin, prefersReducedMotion])

  // Cleanup when inactive
  useEffect(() => {
    if (!active) {
      const timeout = setTimeout(() => setParticles([]), config.lifetime)
      return () => clearTimeout(timeout)
    }
  }, [active, config.lifetime])

  const ParticleShape = useMemo(() => ParticleShapes[config.type], [config.type])

  if (prefersReducedMotion || particles.length === 0) {
    return null
  }

  return (
    <div
      className={`pointer-events-none fixed inset-0 overflow-hidden z-50 ${className}`}
      aria-hidden="true"
    >
      <AnimatePresence>
        {particles.map((particle) => (
          <motion.div
            key={particle.id}
            className="absolute"
            style={{
              left: `${particle.x}%`,
              top: `${particle.y}%`,
              rotate: particle.rotation,
            }}
            initial={{ opacity: 0, scale: 0 }}
            animate={getAnimation(config, particle)}
            exit={{ opacity: 0, scale: 0 }}
          >
            <ParticleShape size={particle.size} color={particle.color} />
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}

export const ParticleEmitter = memo(ParticleEmitterComponent)

export default ParticleEmitter
