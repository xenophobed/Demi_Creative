import { motion } from 'framer-motion'

interface SafetyBadgeProps {
  score: number
  showDetails?: boolean
  className?: string
}

function SafetyBadge({ score, showDetails = false, className = '' }: SafetyBadgeProps) {
  // Convert 0-1 score to percentage
  const percentage = Math.round(score * 100)

  // Determine level and color based on score
  const getLevel = () => {
    if (score >= 0.8) {
      return {
        label: 'Very Safe',
        emoji: '🛡️',
        color: 'green',
        bgClass: 'bg-green-100',
        textClass: 'text-green-700',
        borderClass: 'border-green-200',
      }
    } else if (score >= 0.6) {
      return {
        label: 'Kid Friendly',
        emoji: '✅',
        color: 'blue',
        bgClass: 'bg-blue-100',
        textClass: 'text-blue-700',
        borderClass: 'border-blue-200',
      }
    } else if (score >= 0.4) {
      return {
        label: 'Parental Guidance',
        emoji: '👀',
        color: 'yellow',
        bgClass: 'bg-yellow-100',
        textClass: 'text-yellow-700',
        borderClass: 'border-yellow-200',
      }
    } else {
      return {
        label: 'Not Suitable',
        emoji: '⚠️',
        color: 'red',
        bgClass: 'bg-red-100',
        textClass: 'text-red-700',
        borderClass: 'border-red-200',
      }
    }
  }

  const level = getLevel()

  if (!showDetails) {
    // Compact badge
    return (
      <motion.div
        className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full
          ${level.bgClass} ${level.textClass} border ${level.borderClass} ${className}`}
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ type: 'spring', stiffness: 500, damping: 30 }}
      >
        <span>{level.emoji}</span>
        <span className="font-semibold text-sm">{level.label}</span>
      </motion.div>
    )
  }

  // Detailed badge
  return (
    <motion.div
      className={`${level.bgClass} ${level.textClass} rounded-card p-4 border ${level.borderClass} ${className}`}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{level.emoji}</span>
          <span className="font-bold">Content Safety Rating</span>
        </div>
        <span className="text-2xl font-bold">{percentage}%</span>
      </div>

      {/* Progress bar */}
      <div className="relative h-3 bg-white/50 rounded-full overflow-hidden">
        <motion.div
          className={`absolute inset-y-0 left-0 rounded-full ${
            level.color === 'green'
              ? 'bg-green-500'
              : level.color === 'blue'
              ? 'bg-blue-500'
              : level.color === 'yellow'
              ? 'bg-yellow-500'
              : 'bg-red-500'
          }`}
          initial={{ width: 0 }}
          animate={{ width: `${percentage}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        />
      </div>

      <p className="text-sm mt-2 opacity-80">{level.label}</p>
    </motion.div>
  )
}

export default SafetyBadge
