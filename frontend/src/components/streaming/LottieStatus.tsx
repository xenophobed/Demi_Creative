/**
 * LottieStatus Component
 * Lightweight Lottie-based status indicators
 */

import { memo, useMemo } from 'react'
import { motion } from 'framer-motion'
import Lottie from 'lottie-react'
import { useStreamVisualizationContext } from '@/providers/StreamVisualizationProvider'
import type { AnimationPhase } from '@/types/streaming'

// Inline Lottie animation data for common states
// These are simplified animations to avoid external dependencies

const loadingDots = {
  v: '5.7.4',
  fr: 30,
  ip: 0,
  op: 60,
  w: 100,
  h: 40,
  layers: [
    {
      ty: 4,
      nm: 'Dot 1',
      sr: 1,
      ks: {
        o: { a: 1, k: [{ t: 0, s: [30] }, { t: 15, s: [100] }, { t: 30, s: [30] }] },
        p: { a: 0, k: [20, 20] },
        s: { a: 1, k: [{ t: 0, s: [80, 80] }, { t: 15, s: [100, 100] }, { t: 30, s: [80, 80] }] },
      },
      shapes: [{ ty: 'el', s: { a: 0, k: [16, 16] }, p: { a: 0, k: [0, 0] } }, { ty: 'fl', c: { a: 0, k: [1, 0.42, 0.42] } }],
    },
    {
      ty: 4,
      nm: 'Dot 2',
      sr: 1,
      ks: {
        o: { a: 1, k: [{ t: 10, s: [30] }, { t: 25, s: [100] }, { t: 40, s: [30] }] },
        p: { a: 0, k: [50, 20] },
        s: { a: 1, k: [{ t: 10, s: [80, 80] }, { t: 25, s: [100, 100] }, { t: 40, s: [80, 80] }] },
      },
      shapes: [{ ty: 'el', s: { a: 0, k: [16, 16] }, p: { a: 0, k: [0, 0] } }, { ty: 'fl', c: { a: 0, k: [0.31, 0.8, 0.77] } }],
    },
    {
      ty: 4,
      nm: 'Dot 3',
      sr: 1,
      ks: {
        o: { a: 1, k: [{ t: 20, s: [30] }, { t: 35, s: [100] }, { t: 50, s: [30] }] },
        p: { a: 0, k: [80, 20] },
        s: { a: 1, k: [{ t: 20, s: [80, 80] }, { t: 35, s: [100, 100] }, { t: 50, s: [80, 80] }] },
      },
      shapes: [{ ty: 'el', s: { a: 0, k: [16, 16] }, p: { a: 0, k: [0, 0] } }, { ty: 'fl', c: { a: 0, k: [1, 0.9, 0.43] } }],
    },
  ],
}

const checkmark = {
  v: '5.7.4',
  fr: 30,
  ip: 0,
  op: 30,
  w: 100,
  h: 100,
  layers: [
    {
      ty: 4,
      nm: 'Check',
      sr: 1,
      ks: {
        o: { a: 0, k: 100 },
        p: { a: 0, k: [50, 50] },
      },
      shapes: [
        {
          ty: 'sh',
          ks: {
            a: 1,
            k: [
              { t: 0, s: [{ c: false, v: [[20, 50], [20, 50], [20, 50]] }] },
              { t: 15, s: [{ c: false, v: [[20, 50], [40, 70], [40, 70]] }] },
              { t: 30, s: [{ c: false, v: [[20, 50], [40, 70], [80, 30]] }] },
            ],
          },
        },
        { ty: 'st', c: { a: 0, k: [0.18, 0.8, 0.44] }, w: { a: 0, k: 8 }, lc: 2, lj: 2 },
      ],
    },
  ],
}

interface LottieStatusProps {
  phase?: AnimationPhase
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

function LottieStatusComponent({ phase: propPhase, size = 'md', className = '' }: LottieStatusProps) {
  const { phase: contextPhase, prefersReducedMotion } = useStreamVisualizationContext()
  const phase = propPhase ?? contextPhase

  const sizeStyles = useMemo(() => {
    switch (size) {
      case 'sm':
        return { width: 40, height: 20 }
      case 'lg':
        return { width: 100, height: 50 }
      default:
        return { width: 60, height: 30 }
    }
  }, [size])

  // Select animation based on phase
  const animationData = useMemo(() => {
    switch (phase) {
      case 'complete':
        return checkmark
      case 'connecting':
      case 'thinking':
      case 'tool_executing':
      case 'revealing':
        return loadingDots
      default:
        return null
    }
  }, [phase])

  // If reduced motion or no animation, show static indicator
  if (prefersReducedMotion || !animationData) {
    if (phase === 'complete') {
      return (
        <span className={`text-green-500 ${className}`} style={{ fontSize: sizeStyles.height }}>
          ✓
        </span>
      )
    }
    if (phase === 'error') {
      return (
        <span className={`text-red-500 ${className}`} style={{ fontSize: sizeStyles.height }}>
          ✗
        </span>
      )
    }
    return null
  }

  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.8 }}
    >
      <Lottie
        animationData={animationData}
        loop={phase !== 'complete'}
        autoplay
        style={sizeStyles}
      />
    </motion.div>
  )
}

export const LottieStatus = memo(LottieStatusComponent)

export default LottieStatus
