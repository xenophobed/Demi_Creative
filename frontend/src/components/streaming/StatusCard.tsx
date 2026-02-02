/**
 * StatusCard Component
 * Displays current streaming status with phase-appropriate styling
 */

import { motion, AnimatePresence } from 'framer-motion'
import { memo } from 'react'
import { useStreamVisualizationContext } from '@/providers/StreamVisualizationProvider'
import { getPhaseTheme, getAnimationPreset } from '@/config/animationPresets'
import type { AnimationPhase } from '@/types/streaming'

interface StatusCardProps {
  phase?: AnimationPhase
  message?: string
  className?: string
}

function StatusCardComponent({ phase: propPhase, message: propMessage, className = '' }: StatusCardProps) {
  const context = useStreamVisualizationContext()
  const phase = propPhase ?? context.phase
  const message = propMessage ?? context.message

  const theme = getPhaseTheme(phase)
  const preset = getAnimationPreset(phase)

  // Don't render in idle state
  if (phase === 'idle' && !message) {
    return null
  }

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={phase}
        className={`
          rounded-2xl p-4 backdrop-blur-sm
          border-2 shadow-lg
          ${className}
        `}
        style={{
          background: theme.colors.background,
          borderColor: `${theme.colors.primary}40`,
          boxShadow: `0 4px 20px ${theme.colors.glow}`,
        }}
        initial={preset.enter}
        animate={preset.animate}
        exit={preset.exit}
      >
        <div className="flex items-center gap-3">
          {/* Animated icon */}
          <motion.span
            className="text-3xl"
            animate={
              phase === 'thinking' || phase === 'connecting'
                ? { scale: [1, 1.1, 1], rotate: [0, 5, -5, 0] }
                : phase === 'tool_executing'
                  ? { scale: [1, 1.2, 1] }
                  : phase === 'error'
                    ? { x: [-2, 2, -2, 0] }
                    : {}
            }
            transition={{
              duration: phase === 'error' ? 0.3 : 1.5,
              repeat: phase === 'error' ? 2 : Infinity,
              ease: 'easeInOut',
            }}
          >
            {theme.icon}
          </motion.span>

          {/* Status content */}
          <div className="flex-1 min-w-0">
            <motion.p
              className="font-medium text-sm"
              style={{ color: theme.colors.primary }}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              {theme.label}
            </motion.p>
            {message && (
              <motion.p
                className="text-gray-600 text-sm truncate"
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
              >
                {message}
              </motion.p>
            )}
          </div>

          {/* Loading indicator for active phases */}
          {(phase === 'connecting' || phase === 'thinking' || phase === 'tool_executing') && (
            <div className="flex gap-1">
              {[0, 1, 2].map((i) => (
                <motion.div
                  key={i}
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: theme.colors.primary }}
                  animate={{
                    scale: [1, 1.3, 1],
                    opacity: [0.5, 1, 0.5],
                  }}
                  transition={{
                    duration: 0.8,
                    repeat: Infinity,
                    delay: i * 0.15,
                  }}
                />
              ))}
            </div>
          )}
        </div>
      </motion.div>
    </AnimatePresence>
  )
}

export const StatusCard = memo(StatusCardComponent)

export default StatusCard
