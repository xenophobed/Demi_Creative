/**
 * ThinkingBubble Component
 * Displays AI thinking content with animated bubble effect
 */

import { motion, AnimatePresence } from 'framer-motion'
import { memo } from 'react'
import { useStreamVisualizationContext } from '@/providers/StreamVisualizationProvider'
import { colors } from '@/config/animationPresets'

interface ThinkingBubbleProps {
  content?: string
  visible?: boolean
  className?: string
}

function ThinkingBubbleComponent({
  content: propContent,
  visible: propVisible,
  className = '',
}: ThinkingBubbleProps) {
  const context = useStreamVisualizationContext()
  const content = propContent ?? context.thinkingContent
  const visible = propVisible ?? (context.phase === 'thinking' && !!content)

  return (
    <AnimatePresence>
      {visible && content && (
        <motion.div
          className={`relative ${className}`}
          initial={{ opacity: 0, scale: 0.9, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: -5 }}
          transition={{ duration: 0.3, ease: 'easeOut' }}
        >
          {/* Main bubble */}
          <div
            className="relative rounded-2xl p-4 backdrop-blur-sm"
            style={{
              background: 'linear-gradient(135deg, #F5F3FF 0%, #FDF4FF 100%)',
              border: `2px solid ${colors.purple}30`,
              boxShadow: `0 4px 20px rgba(155, 89, 182, 0.15)`,
            }}
          >
            {/* Decorative thought icon */}
            <motion.span
              className="absolute -top-3 -left-2 text-2xl"
              animate={{
                y: [0, -3, 0],
                rotate: [0, 5, -5, 0],
              }}
              transition={{
                duration: 2,
                repeat: Infinity,
                ease: 'easeInOut',
              }}
            >
              💭
            </motion.span>

            {/* Content */}
            <div className="pl-4">
              <motion.p
                className="text-gray-600 italic text-sm leading-relaxed"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.1 }}
              >
                "{content}"
              </motion.p>
            </div>

            {/* Floating sparkles */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
              {[...Array(3)].map((_, i) => (
                <motion.div
                  key={i}
                  className="absolute w-2 h-2"
                  style={{
                    left: `${20 + i * 30}%`,
                    top: `${30 + i * 15}%`,
                  }}
                  animate={{
                    y: [0, -10, 0],
                    opacity: [0.3, 0.8, 0.3],
                    scale: [0.8, 1.2, 0.8],
                  }}
                  transition={{
                    duration: 2,
                    repeat: Infinity,
                    delay: i * 0.4,
                    ease: 'easeInOut',
                  }}
                >
                  <svg viewBox="0 0 24 24" fill={colors.purple} className="w-full h-full">
                    <path d="M12 0L14.59 9.41L24 12L14.59 14.59L12 24L9.41 14.59L0 12L9.41 9.41L12 0Z" />
                  </svg>
                </motion.div>
              ))}
            </div>
          </div>

          {/* Bubble tail dots */}
          <div className="flex items-center gap-1 ml-4 mt-1">
            {[0.6, 0.4, 0.25].map((size, i) => (
              <motion.div
                key={i}
                className="rounded-full"
                style={{
                  width: `${size}rem`,
                  height: `${size}rem`,
                  backgroundColor: `${colors.purple}60`,
                }}
                animate={{
                  scale: [1, 1.2, 1],
                  opacity: [0.6, 1, 0.6],
                }}
                transition={{
                  duration: 1.5,
                  repeat: Infinity,
                  delay: i * 0.2,
                }}
              />
            ))}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export const ThinkingBubble = memo(ThinkingBubbleComponent)

export default ThinkingBubble
