import { useState, type ReactNode } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import AudioPlayer from '@/components/common/AudioPlayer'
import type { AgeGroup } from '@/types/api'

interface AgeAwareContentProps {
  ageGroup: AgeGroup | null
  textContent: ReactNode
  audioUrl: string | null | undefined
  onRequestAudio?: () => void
  isAudioLoading?: boolean
  autoPlayAudio?: boolean
  className?: string
}

function getDisplayMode(ageGroup: AgeGroup | null): 'audio' | 'both' | 'text' {
  switch (ageGroup) {
    case '3-5':
      return 'audio'
    case '10-12':
      return 'text'
    case '6-9':
    default:
      return 'both'
  }
}

function AgeAwareContent({
  ageGroup,
  textContent,
  audioUrl,
  onRequestAudio,
  isAudioLoading = false,
  autoPlayAudio = false,
  className = '',
}: AgeAwareContentProps) {
  const mode = getDisplayMode(ageGroup)
  const [showText, setShowText] = useState(false)
  const [audioRequested, setAudioRequested] = useState(false)

  const handleRequestAudio = () => {
    setAudioRequested(true)
    onRequestAudio?.()
  }

  // 3-5: Audio-first mode
  if (mode === 'audio') {
    return (
      <div className={className}>
        {/* Audio player - primary content */}
        {audioUrl ? (
          <AudioPlayer
            src={audioUrl}
            title="Listen to the Story"
            autoPlay={autoPlayAudio}
          />
        ) : (
          <div className="bg-gradient-to-r from-primary/10 to-secondary/10 rounded-card p-6 text-center">
            <motion.div
              animate={{ scale: [1, 1.1, 1] }}
              transition={{ duration: 2, repeat: Infinity }}
              className="text-4xl mb-2"
            >
              🔊
            </motion.div>
            <p className="text-gray-500 text-sm">Audio is loading...</p>
          </div>
        )}

        {/* Show Text toggle button */}
        <div className="mt-4">
          <motion.button
            className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl border-2 border-dashed border-gray-300 text-gray-500 hover:border-primary hover:text-primary transition-colors"
            onClick={() => setShowText(!showText)}
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.99 }}
          >
            <span>{showText ? '📖' : '👀'}</span>
            <span className="font-medium">
              {showText ? 'Hide Text' : 'Show Text'}
            </span>
          </motion.button>

          <AnimatePresence>
            {showText && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.3 }}
                className="overflow-hidden"
              >
                <div className="mt-4">{textContent}</div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    )
  }

  // 10-12: Text-first mode
  if (mode === 'text') {
    return (
      <div className={className}>
        {/* Text - primary content */}
        {textContent}

        {/* Listen button or audio player */}
        <div className="mt-4">
          {audioUrl ? (
            <AudioPlayer src={audioUrl} title="Story Narration" />
          ) : (
            <motion.button
              className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-gradient-to-r from-primary/10 to-secondary/10 text-gray-700 hover:from-primary/20 hover:to-secondary/20 transition-colors"
              onClick={handleRequestAudio}
              disabled={isAudioLoading}
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.99 }}
            >
              {isAudioLoading || audioRequested ? (
                <>
                  <motion.span
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                  >
                    ⏳
                  </motion.span>
                  <span className="font-medium">Generating audio...</span>
                </>
              ) : (
                <>
                  <span>🎧</span>
                  <span className="font-medium">Listen</span>
                </>
              )}
            </motion.button>
          )}
        </div>
      </div>
    )
  }

  // 6-9: Both mode (default)
  return (
    <div className={className}>
      {textContent}
      {audioUrl && (
        <div className="mt-4">
          <AudioPlayer src={audioUrl} title="Story Narration" autoPlay={autoPlayAudio} />
        </div>
      )}
    </div>
  )
}

export default AgeAwareContent
