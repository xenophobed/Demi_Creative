/**
 * StreamingVisualizer Component
 * Main component that orchestrates all streaming visualization elements
 */

import { motion, AnimatePresence } from 'framer-motion'
import { memo, useMemo } from 'react'
import { useStreamVisualizationContext } from '@/providers/StreamVisualizationProvider'
import { getPhaseTheme, getParticleConfig } from '@/config/animationPresets'
import { ParticleEmitter } from '@/components/effects/ParticleEmitter'
import { Sparkles } from '@/components/effects/Sparkles'
import { StatusCard } from './StatusCard'
import { ThinkingBubble } from './ThinkingBubble'
import { ToolIndicator } from './ToolIndicator'
import type { AnimationPhase } from '@/types/streaming'

interface StreamingVisualizerProps {
  // Override phase from props (otherwise uses context)
  phase?: AnimationPhase
  message?: string
  thinkingContent?: string
  currentTool?: string | null

  // Layout options
  layout?: 'card' | 'overlay' | 'inline'
  showParticles?: boolean
  showSparkles?: boolean
  showStatus?: boolean
  showThinking?: boolean
  showTool?: boolean

  // Styling
  className?: string
}

function StreamingVisualizerComponent({
  phase: propPhase,
  message: propMessage,
  thinkingContent: propThinkingContent,
  currentTool: propCurrentTool,
  layout = 'card',
  showParticles = true,
  showSparkles = true,
  showStatus = true,
  showThinking = true,
  showTool = true,
  className = '',
}: StreamingVisualizerProps) {
  const context = useStreamVisualizationContext()

  // Use props or context values
  const phase = propPhase ?? context.phase
  const message = propMessage ?? context.message
  const thinkingContent = propThinkingContent ?? context.thinkingContent
  const currentTool = propCurrentTool ?? context.currentTool
  const { prefersReducedMotion } = context

  // Get theme and particles for current phase
  const theme = useMemo(() => getPhaseTheme(phase), [phase])
  const particleConfig = useMemo(() => getParticleConfig(phase), [phase])

  // Determine visibility
  const isActive = phase !== 'idle'
  const showThinkingBubble = showThinking && phase === 'thinking' && thinkingContent
  const showToolIndicator = showTool && phase === 'tool_executing' && currentTool

  // Don't render if idle and no overrides
  if (!isActive && !propPhase) {
    return null
  }

  // Overlay layout - fixed position full screen
  if (layout === 'overlay') {
    return (
      <>
        {/* Particle effects */}
        {showParticles && particleConfig && !prefersReducedMotion && (
          <ParticleEmitter config={particleConfig} active={isActive} />
        )}

        {/* Overlay container */}
        <AnimatePresence>
          {isActive && (
            <motion.div
              className={`fixed inset-0 z-40 flex items-center justify-center pointer-events-none ${className}`}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              {/* Semi-transparent backdrop */}
              <motion.div
                className="absolute inset-0 bg-white/60 backdrop-blur-sm"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              />

              {/* Content */}
              <div className="relative z-10 max-w-md w-full mx-4 space-y-4">
                {showStatus && <StatusCard phase={phase} message={message} />}
                {showThinkingBubble && <ThinkingBubble content={thinkingContent} visible />}
                {showToolIndicator && (
                  <ToolIndicator tool={currentTool} message={message} visible />
                )}
              </div>

              {/* Sparkles around content */}
              {showSparkles && !prefersReducedMotion && (
                <Sparkles
                  active={phase === 'thinking' || phase === 'revealing'}
                  spread="center"
                  count={10}
                />
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </>
    )
  }

  // Inline layout - just the components
  if (layout === 'inline') {
    return (
      <div className={`relative ${className}`}>
        {/* Sparkle background */}
        {showSparkles && !prefersReducedMotion && (
          <Sparkles
            active={phase === 'thinking' || phase === 'tool_executing'}
            spread="full"
            count={8}
          />
        )}

        <div className="relative z-10 space-y-3">
          {showStatus && <StatusCard phase={phase} message={message} />}
          {showThinkingBubble && <ThinkingBubble content={thinkingContent} visible />}
          {showToolIndicator && <ToolIndicator tool={currentTool} message={message} visible />}
        </div>
      </div>
    )
  }

  // Card layout (default) - contained within a card
  return (
    <AnimatePresence>
      {isActive && (
        <motion.div
          className={`relative overflow-hidden rounded-2xl ${className}`}
          style={{
            background: theme.colors.background,
            boxShadow: `0 4px 20px ${theme.colors.glow}`,
          }}
          initial={{ opacity: 0, y: 20, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -10, scale: 0.98 }}
          transition={{ duration: 0.3 }}
        >
          {/* Sparkle overlay */}
          {showSparkles && !prefersReducedMotion && (
            <Sparkles
              active={phase === 'thinking' || phase === 'tool_executing'}
              spread="full"
              count={6}
            />
          )}

          {/* Content */}
          <div className="relative z-10 p-4 space-y-3">
            {showStatus && <StatusCard phase={phase} message={message} className="!shadow-none !border-0 !bg-transparent !p-0" />}
            {showThinkingBubble && <ThinkingBubble content={thinkingContent} visible />}
            {showToolIndicator && <ToolIndicator tool={currentTool} message={message} visible />}
          </div>

          {/* Decorative elements */}
          <motion.div
            className="absolute -bottom-2 -right-2 text-6xl opacity-10"
            animate={{ rotate: [0, 10, -10, 0] }}
            transition={{ duration: 4, repeat: Infinity }}
          >
            {theme.icon}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export const StreamingVisualizer = memo(StreamingVisualizerComponent)

export default StreamingVisualizer
