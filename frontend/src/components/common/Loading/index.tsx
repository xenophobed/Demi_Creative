import { motion } from 'framer-motion'
import { getPhaseTheme } from '@/config/animationPresets'
import type { AnimationPhase } from '@/types/streaming'

interface LoadingProps {
  size?: 'sm' | 'md' | 'lg'
  message?: string
  fullScreen?: boolean
  phase?: AnimationPhase
}

function Loading({ size = 'md', message, fullScreen = false, phase }: LoadingProps) {
  const sizes = {
    sm: 'w-8 h-8',
    md: 'w-16 h-16',
    lg: 'w-24 h-24',
  }

  // Get phase-specific colors if phase is provided
  const theme = phase ? getPhaseTheme(phase) : null
  const primaryColor = theme?.colors.primary || '#FF6B6B'
  const accentColor = theme?.colors.accent || '#FFE66D'

  const content = (
    <div className="flex flex-col items-center justify-center gap-4">
      {/* Cute loading animation */}
      <div className="relative">
        {/* Rotating stars */}
        <motion.div
          className={`${sizes[size]} relative`}
          animate={{ rotate: 360 }}
          transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
        >
          {[0, 1, 2, 3].map((i) => (
            <motion.div
              key={i}
              className="absolute"
              style={{
                top: '50%',
                left: '50%',
                transformOrigin: 'center',
              }}
              initial={{
                x: '-50%',
                y: '-50%',
                rotate: i * 90,
              }}
            >
              <Star
                color={i % 2 === 0 ? primaryColor : accentColor}
                style={{
                  transform: `translateY(-${size === 'sm' ? 10 : size === 'md' ? 20 : 30}px)`,
                }}
              />
            </motion.div>
          ))}
        </motion.div>

        {/* Center circle */}
        <motion.div
          className={`absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2
            ${size === 'sm' ? 'w-4 h-4' : size === 'md' ? 'w-8 h-8' : 'w-12 h-12'}
            rounded-full bg-gradient-to-br from-primary to-secondary`}
          animate={{ scale: [1, 1.2, 1] }}
          transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
        />
      </div>

      {/* Loading text */}
      {message && (
        <motion.p
          className="text-gray-600 font-medium"
          animate={{ opacity: [1, 0.5, 1] }}
          transition={{ duration: 1.5, repeat: Infinity }}
        >
          {message}
        </motion.p>
      )}
    </div>
  )

  if (fullScreen) {
    return (
      <div className="fixed inset-0 bg-warm flex items-center justify-center z-50">
        {content}
      </div>
    )
  }

  return content
}

// Star SVG
function Star({ color = 'currentColor', style = {} }: { color?: string; style?: React.CSSProperties }) {
  return (
    <svg
      className="w-4 h-4"
      style={{ fill: color, ...style }}
      viewBox="0 0 24 24"
    >
      <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
    </svg>
  )
}

// Simple pulse loading indicator
export function PulseLoader({ className = '' }: { className?: string }) {
  return (
    <div className={`flex gap-2 items-center justify-center ${className}`}>
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          className="w-3 h-3 rounded-full bg-primary"
          animate={{ scale: [1, 1.3, 1], opacity: [1, 0.5, 1] }}
          transition={{
            duration: 0.8,
            repeat: Infinity,
            delay: i * 0.2,
          }}
        />
      ))}
    </div>
  )
}

// Skeleton loading
export function Skeleton({
  className = '',
  variant = 'rect',
}: {
  className?: string
  variant?: 'rect' | 'circle' | 'text'
}) {
  const baseStyles = 'animate-pulse bg-gray-200'

  const variants = {
    rect: 'rounded-lg',
    circle: 'rounded-full',
    text: 'rounded h-4',
  }

  return <div className={`${baseStyles} ${variants[variant]} ${className}`} />
}

export default Loading
