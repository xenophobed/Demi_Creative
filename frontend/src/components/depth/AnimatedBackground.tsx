/**
 * AnimatedBackground Component
 * Multi-layer parallax background with floating decorative elements
 */

import { motion } from 'framer-motion'
import { memo, useMemo } from 'react'
import { useStreamVisualizationContext } from '@/providers/StreamVisualizationProvider'
import { DepthLayer } from './DepthLayer'
import { colors } from '@/config/animationPresets'

interface AnimatedBackgroundProps {
  className?: string
  variant?: 'default' | 'playful' | 'calm'
}

// Floating decorative elements
const floatingElements = [
  { emoji: '🌟', x: 10, y: 15, delay: 0, size: 'text-2xl' },
  { emoji: '🎈', x: 85, y: 20, delay: 0.5, size: 'text-3xl' },
  { emoji: '🌈', x: 75, y: 75, delay: 1, size: 'text-2xl' },
  { emoji: '✨', x: 20, y: 80, delay: 1.5, size: 'text-xl' },
  { emoji: '🦋', x: 90, y: 50, delay: 2, size: 'text-2xl' },
  { emoji: '🌸', x: 5, y: 45, delay: 2.5, size: 'text-xl' },
  { emoji: '🎨', x: 50, y: 10, delay: 3, size: 'text-2xl' },
  { emoji: '📚', x: 60, y: 85, delay: 3.5, size: 'text-xl' },
]

// Gradient orbs for background
const gradientOrbs = [
  {
    color: colors.primary,
    x: 20,
    y: 30,
    size: 300,
    opacity: 0.15,
    blur: 80,
  },
  {
    color: colors.secondary,
    x: 70,
    y: 60,
    size: 250,
    opacity: 0.12,
    blur: 70,
  },
  {
    color: colors.accent,
    x: 40,
    y: 80,
    size: 200,
    opacity: 0.1,
    blur: 60,
  },
]

function AnimatedBackgroundComponent({
  className = '',
  variant = 'default',
}: AnimatedBackgroundProps) {
  const { prefersReducedMotion, phase } = useStreamVisualizationContext()

  // Adjust animation intensity based on phase
  const animationIntensity = useMemo(() => {
    switch (phase) {
      case 'thinking':
      case 'tool_executing':
        return 1.5
      case 'complete':
        return 2
      default:
        return 1
    }
  }, [phase])

  // Variant-specific styling
  const variantStyles = useMemo(() => {
    switch (variant) {
      case 'playful':
        return {
          showEmojis: true,
          orbOpacityMultiplier: 1.2,
          animationSpeed: 0.8,
        }
      case 'calm':
        return {
          showEmojis: false,
          orbOpacityMultiplier: 0.7,
          animationSpeed: 1.5,
        }
      default:
        return {
          showEmojis: true,
          orbOpacityMultiplier: 1,
          animationSpeed: 1,
        }
    }
  }, [variant])

  return (
    <div
      className={`fixed inset-0 overflow-hidden pointer-events-none z-0 ${className}`}
      aria-hidden="true"
    >
      {/* Background gradient layer */}
      <DepthLayer config={{ layer: 'background', parallaxFactor: 0.2 }}>
        <div className="absolute inset-0 gradient-bg" />

        {/* Gradient orbs */}
        {gradientOrbs.map((orb, i) => (
          <motion.div
            key={i}
            className="absolute rounded-full"
            style={{
              left: `${orb.x}%`,
              top: `${orb.y}%`,
              width: orb.size,
              height: orb.size,
              background: `radial-gradient(circle, ${orb.color} 0%, transparent 70%)`,
              opacity: orb.opacity * variantStyles.orbOpacityMultiplier,
              filter: `blur(${orb.blur}px)`,
              transform: 'translate(-50%, -50%)',
            }}
            animate={
              prefersReducedMotion
                ? {}
                : {
                    x: [0, 30 * animationIntensity, 0],
                    y: [0, -20 * animationIntensity, 0],
                    scale: [1, 1.1, 1],
                  }
            }
            transition={{
              duration: (8 + i * 2) * variantStyles.animationSpeed,
              repeat: Infinity,
              ease: 'easeInOut',
            }}
          />
        ))}
      </DepthLayer>

      {/* Midground decorative layer */}
      <DepthLayer config={{ layer: 'midground', parallaxFactor: 0.4 }}>
        {/* Subtle pattern overlay */}
        <div
          className="absolute inset-0 opacity-[0.02]"
          style={{
            backgroundImage: `radial-gradient(circle at 25px 25px, ${colors.primary} 2px, transparent 0)`,
            backgroundSize: '50px 50px',
          }}
        />
      </DepthLayer>

      {/* Foreground floating elements */}
      {variantStyles.showEmojis && (
        <DepthLayer config={{ layer: 'foreground', parallaxFactor: 0.7 }}>
          {floatingElements.map((element, i) => (
            <motion.div
              key={i}
              className={`absolute ${element.size} select-none`}
              style={{
                left: `${element.x}%`,
                top: `${element.y}%`,
              }}
              animate={
                prefersReducedMotion
                  ? {}
                  : {
                      y: [0, -15 * animationIntensity, 0],
                      rotate: [0, 10, -10, 0],
                      scale: [1, 1.05, 1],
                    }
              }
              transition={{
                duration: (4 + i * 0.5) * variantStyles.animationSpeed,
                repeat: Infinity,
                delay: element.delay,
                ease: 'easeInOut',
              }}
            >
              <span className="opacity-30">{element.emoji}</span>
            </motion.div>
          ))}
        </DepthLayer>
      )}

      {/* Phase-specific accent */}
      {phase !== 'idle' && (
        <motion.div
          className="absolute inset-0"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          style={{
            background:
              phase === 'thinking'
                ? 'radial-gradient(circle at 50% 50%, rgba(155, 89, 182, 0.05) 0%, transparent 50%)'
                : phase === 'tool_executing'
                  ? 'radial-gradient(circle at 50% 50%, rgba(241, 196, 15, 0.05) 0%, transparent 50%)'
                  : phase === 'complete'
                    ? 'radial-gradient(circle at 50% 50%, rgba(46, 204, 113, 0.05) 0%, transparent 50%)'
                    : 'none',
          }}
        />
      )}
    </div>
  )
}

export const AnimatedBackground = memo(AnimatedBackgroundComponent)

export default AnimatedBackground
