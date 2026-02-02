/**
 * ToolIndicator Component
 * Shows which tool is currently being used with animated icon
 */

import { motion, AnimatePresence } from 'framer-motion'
import { memo } from 'react'
import { useStreamVisualizationContext } from '@/providers/StreamVisualizationProvider'
import { getToolIcon, colors } from '@/config/animationPresets'

interface ToolIndicatorProps {
  tool?: string | null
  message?: string
  visible?: boolean
  className?: string
}

function ToolIndicatorComponent({
  tool: propTool,
  message: propMessage,
  visible: propVisible,
  className = '',
}: ToolIndicatorProps) {
  const context = useStreamVisualizationContext()
  const tool = propTool ?? context.currentTool
  const message = propMessage ?? context.message
  const visible = propVisible ?? (context.phase === 'tool_executing' && !!tool)

  const icon = tool ? getToolIcon(tool) : '⚙️'

  return (
    <AnimatePresence>
      {visible && tool && (
        <motion.div
          className={`relative ${className}`}
          initial={{ opacity: 0, scale: 0.8, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.9, y: -5 }}
          transition={{
            type: 'spring',
            stiffness: 300,
            damping: 20,
          }}
        >
          <div
            className="flex items-center gap-3 rounded-2xl p-3 backdrop-blur-sm"
            style={{
              background: 'linear-gradient(135deg, #FFFBEB 0%, #FEF3C7 100%)',
              border: `2px solid ${colors.yellow}40`,
              boxShadow: `0 4px 20px rgba(241, 196, 15, 0.2)`,
            }}
          >
            {/* Animated tool icon */}
            <motion.div
              className="relative"
              animate={{
                scale: [1, 1.15, 1],
                rotate: [0, 5, -5, 0],
              }}
              transition={{
                duration: 0.8,
                repeat: Infinity,
                ease: 'easeInOut',
              }}
            >
              <span className="text-3xl block">{icon}</span>

              {/* Radiating stars */}
              {[...Array(4)].map((_, i) => (
                <motion.div
                  key={i}
                  className="absolute w-3 h-3"
                  style={{
                    top: '50%',
                    left: '50%',
                  }}
                  animate={{
                    x: [0, Math.cos((i * Math.PI) / 2) * 25],
                    y: [0, Math.sin((i * Math.PI) / 2) * 25],
                    opacity: [0, 1, 0],
                    scale: [0.5, 1, 0.5],
                  }}
                  transition={{
                    duration: 1,
                    repeat: Infinity,
                    delay: i * 0.15,
                    ease: 'easeOut',
                  }}
                >
                  <svg viewBox="0 0 24 24" fill={colors.yellow} className="w-full h-full">
                    <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
                  </svg>
                </motion.div>
              ))}
            </motion.div>

            {/* Tool info */}
            <div className="flex-1 min-w-0">
              <motion.p
                className="font-medium text-sm"
                style={{ color: colors.yellow }}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
              >
                Using Tool
              </motion.p>
              {message && (
                <motion.p
                  className="text-gray-600 text-sm truncate"
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.1 }}
                >
                  {message}
                </motion.p>
              )}
            </div>

            {/* Activity indicator */}
            <motion.div
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: colors.yellow }}
              animate={{
                scale: [1, 1.5, 1],
                opacity: [1, 0.5, 1],
              }}
              transition={{
                duration: 0.5,
                repeat: Infinity,
              }}
            />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export const ToolIndicator = memo(ToolIndicatorComponent)

export default ToolIndicator
