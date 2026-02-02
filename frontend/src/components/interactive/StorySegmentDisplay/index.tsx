import { motion } from 'framer-motion'
import { Sparkles } from '@/components/effects/Sparkles'
import { revealAnimation, staggerChildren, staggerItem } from '@/config/animationPresets'
import type { StorySegment } from '@/types/api'

interface StorySegmentDisplayProps {
  segment: StorySegment
  title?: string
  segmentIndex: number
  className?: string
  isRevealing?: boolean
}

function StorySegmentDisplay({
  segment,
  title,
  segmentIndex,
  className = '',
  isRevealing = false,
}: StorySegmentDisplayProps) {
  // Split text into paragraphs
  const paragraphs = segment.text.split('\n').filter((p) => p.trim())

  return (
    <motion.div
      className={`relative ${className}`}
      initial="hidden"
      animate="visible"
      variants={revealAnimation}
    >
      {/* Reveal sparkles */}
      {isRevealing && (
        <Sparkles active count={12} spread="full" duration={2500} />
      )}
      {/* Title (for opening segment) */}
      {title && segmentIndex === 0 && (
        <motion.div
          className="text-center mb-6"
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <motion.span
            className="text-4xl inline-block mb-2"
            animate={{ rotate: [0, -5, 5, 0] }}
            transition={{ duration: 3, repeat: Infinity }}
          >
            ✨
          </motion.span>
          <h2 className="text-2xl md:text-3xl font-bold text-gradient">
            {title}
          </h2>
          <div className="mt-3 flex justify-center gap-2">
            {['🌟', '📖', '🌟'].map((emoji, i) => (
              <motion.span
                key={i}
                className="text-lg"
                animate={{ scale: [1, 1.2, 1] }}
                transition={{ duration: 2, repeat: Infinity, delay: i * 0.3 }}
              >
                {emoji}
              </motion.span>
            ))}
          </div>
        </motion.div>
      )}

      {/* Story content */}
      <div className="bg-white rounded-card p-6 md:p-8 shadow-card">
        {/* Segment indicator for non-opening segments */}
        {segmentIndex > 0 && (
          <motion.div
            className="flex items-center gap-2 mb-4 text-sm text-gray-500"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
          >
            <span className="w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold">
              {segmentIndex + 1}
            </span>
            <span>Story continues...</span>
          </motion.div>
        )}

        {/* Paragraphs with staggered animation */}
        <motion.div
          className="space-y-4 text-gray-700 leading-relaxed"
          variants={staggerChildren}
          initial="hidden"
          animate="visible"
        >
          {paragraphs.map((paragraph, index) => (
            <motion.p
              key={index}
              className={`${
                index === 0 && segmentIndex === 0
                  ? 'first-letter:text-4xl first-letter:font-bold first-letter:text-primary first-letter:float-left first-letter:mr-2 first-letter:mt-1'
                  : ''
              }`}
              variants={staggerItem}
            >
              {paragraph}
            </motion.p>
          ))}
        </motion.div>

        {/* Ending indicator */}
        {segment.is_ending && (
          <motion.div
            className="mt-6 pt-4 border-t border-gray-200 text-center"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.8 }}
          >
            <span className="text-2xl">🎉</span>
            <p className="text-gray-500 mt-1 font-medium">~ The End ~</p>
          </motion.div>
        )}

        {/* Decorative bottom border */}
        <motion.div
          className="mt-6 h-1 bg-gradient-to-r from-primary via-secondary to-accent rounded-full"
          initial={{ scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={{ delay: 0.5, duration: 0.5 }}
        />
      </div>
    </motion.div>
  )
}

export default StorySegmentDisplay
