import { motion } from 'framer-motion'
import type { StoryLengthMode } from '@/types/api'

interface ProgressIndicatorProps {
  current: number
  total: number
  choiceHistory: string[]
  storyLengthMode?: StoryLengthMode
  className?: string
}

function ProgressIndicator({
  current,
  total,
  choiceHistory,
  storyLengthMode = 'short',
  className = '',
}: ProgressIndicatorProps) {
  const isUnlimited = storyLengthMode === 'unlimited'

  // For unlimited mode, show chapter count instead of percentage
  const progressPercent = isUnlimited
    ? 0
    : total > 0
      ? Math.round((current / total) * 100)
      : 0

  return (
    <div className={`space-y-2 ${className}`}>
      {/* Chapter label */}
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-gray-600">
          Chapter {current + 1}
        </span>
        <span className="text-gray-400">
          {isUnlimited ? '∞ Endless Adventure' : `${progressPercent}%`}
        </span>
      </div>

      {/* Progress bar — hidden for unlimited mode */}
      {!isUnlimited && (
        <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-gradient-to-r from-primary via-secondary to-accent rounded-full"
            initial={{ width: 0 }}
            animate={{ width: `${progressPercent}%` }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
          />
        </div>
      )}

      {/* Segment dots (short/medium modes only, max 10 dots) */}
      {!isUnlimited && total <= 10 && total > 0 && (
        <div className="flex justify-center gap-2 pt-1">
          {Array.from({ length: total }).map((_, index) => (
            <motion.div
              key={index}
              className={`w-2 h-2 rounded-full ${
                index <= current
                  ? 'bg-primary'
                  : 'bg-gray-300'
              }`}
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ delay: index * 0.05 }}
            />
          ))}
        </div>
      )}

      {/* Choice history preview */}
      {choiceHistory.length > 0 && (
        <div className="flex flex-wrap gap-1 pt-2">
          {choiceHistory.slice(-5).map((choice, index) => (
            <motion.span
              key={index}
              className="text-xs px-2 py-0.5 bg-gray-100 text-gray-500 rounded-full"
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              {choice}
            </motion.span>
          ))}
        </div>
      )}
    </div>
  )
}

export default ProgressIndicator
