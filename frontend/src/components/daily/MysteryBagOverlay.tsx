/**
 * MysteryBagOverlay — fullscreen gamification overlay (#387)
 *
 * Flow: select 1 of 3 bags → tear open → confetti → reveal random tool emoji → CTA
 * Parent Epic: #384
 */

import { useState, useCallback, useRef } from 'react'
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion'
import { createPortal } from 'react-dom'
import Confetti from '@/components/effects/Confetti'
import Button from '@/components/common/Button'

const TOOL_EMOJIS = ['✏️', '🖍️', '🖌️', '✒️', '🎨', '🩹', '✂️', '📏', '🧶']

const BAG_COLORS = [
  { bg: 'bg-blue-400', border: 'border-blue-500', shadow: 'shadow-blue-300/50', label: 'Blue' },
  { bg: 'bg-pink-400', border: 'border-pink-500', shadow: 'shadow-pink-300/50', label: 'Pink' },
  { bg: 'bg-amber-400', border: 'border-amber-500', shadow: 'shadow-amber-300/50', label: 'Yellow' },
]

type Phase = 'select' | 'tear' | 'reveal'

interface MysteryBagOverlayProps {
  onItemCollected: (emoji: string, element: HTMLElement | null) => void
  onClose: () => void
}

export default function MysteryBagOverlay({ onItemCollected, onClose }: MysteryBagOverlayProps) {
  const prefersReduced = useReducedMotion()
  const [phase, setPhase] = useState<Phase>('select')
  const [selectedBag, setSelectedBag] = useState<number | null>(null)
  const [revealedEmoji, setRevealedEmoji] = useState<string | null>(null)
  const [showConfetti, setShowConfetti] = useState(false)
  const ctaRef = useRef<HTMLButtonElement>(null)

  const handleSelectBag = useCallback((index: number) => {
    if (phase !== 'select') return
    setSelectedBag(index)
    setPhase('tear')
  }, [phase])

  const handleTear = useCallback(() => {
    if (phase !== 'tear') return
    const emoji = TOOL_EMOJIS[Math.floor(Math.random() * TOOL_EMOJIS.length)]
    setRevealedEmoji(emoji)
    setShowConfetti(true)
    setPhase('reveal')

    // Reset confetti after animation
    setTimeout(() => setShowConfetti(false), 3000)
  }, [phase])

  const handleCollect = useCallback(() => {
    if (!revealedEmoji) return
    onItemCollected(revealedEmoji, ctaRef.current)
  }, [revealedEmoji, onItemCollected])

  const handleBackdropClick = useCallback(() => {
    // Only allow closing before selection
    if (phase === 'select') {
      onClose()
    }
  }, [phase, onClose])

  const overlay = (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        {/* Backdrop */}
        <motion.div
          className="absolute inset-0 bg-black/50 backdrop-blur-sm"
          onClick={handleBackdropClick}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        />

        {/* Content */}
        <motion.div
          className="relative z-10 w-full max-w-lg"
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: 'spring', damping: 20, stiffness: 200 }}
        >
          {/* Title */}
          <motion.h2
            className="text-center text-2xl font-bold text-white mb-8 drop-shadow-lg"
            initial={{ y: -20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.2 }}
          >
            {phase === 'select' && 'Pick a Mystery Bag!'}
            {phase === 'tear' && 'Tear it open!'}
            {phase === 'reveal' && 'You got a new tool!'}
          </motion.h2>

          {/* === SELECT PHASE === */}
          {phase === 'select' && (
            <div className="flex justify-center gap-6">
              {BAG_COLORS.map((bag, index) => (
                <motion.button
                  key={bag.label}
                  className={`
                    relative w-24 h-32 rounded-2xl border-2 ${bag.bg} ${bag.border}
                    shadow-lg ${bag.shadow} cursor-pointer
                    flex flex-col items-center justify-center gap-1
                  `}
                  initial={{ opacity: 0, y: 30 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.1, type: 'spring' }}
                  whileHover={prefersReduced ? {} : { rotate: [-2, 2, -2, 0], scale: 1.08 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={() => handleSelectBag(index)}
                >
                  <span className="text-3xl">🎒</span>
                  <span className="text-xs font-bold text-white/90">{bag.label}</span>
                  {/* Dashed line at top — hint for tear */}
                  <div className="absolute top-2 left-3 right-3 border-t-2 border-dashed border-white/50" />
                </motion.button>
              ))}
            </div>
          )}

          {/* === TEAR PHASE === */}
          {phase === 'tear' && selectedBag !== null && (
            <div className="flex justify-center">
              <motion.button
                className={`
                  relative w-36 h-44 rounded-2xl border-2
                  ${BAG_COLORS[selectedBag].bg} ${BAG_COLORS[selectedBag].border}
                  shadow-xl ${BAG_COLORS[selectedBag].shadow}
                  cursor-pointer flex flex-col items-center justify-center gap-2
                `}
                initial={{ scale: 0.5, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ type: 'spring', damping: 15 }}
                whileHover={prefersReduced ? {} : { scale: 1.05 }}
                whileTap={{ scale: 0.9 }}
                onClick={handleTear}
              >
                <span className="text-5xl">🎒</span>
                {/* Animated dashed tear line */}
                <motion.div
                  className="absolute top-3 left-4 right-4 border-t-2 border-dashed border-white"
                  animate={{ opacity: [0.5, 1, 0.5] }}
                  transition={{ duration: 1, repeat: Infinity }}
                />
                <span className="text-sm font-bold text-white/90 mt-2">Tap to open!</span>
              </motion.button>
            </div>
          )}

          {/* === REVEAL PHASE === */}
          {phase === 'reveal' && revealedEmoji && (
            <motion.div
              className="flex flex-col items-center gap-6"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              {/* Revealed emoji */}
              <motion.div
                className="text-7xl"
                initial={{ scale: 0, rotate: -180 }}
                animate={{ scale: 1, rotate: 0 }}
                transition={{
                  type: 'spring',
                  damping: 8,
                  stiffness: 100,
                  delay: 0.2,
                }}
              >
                {revealedEmoji}
              </motion.div>

              {/* CTA Button */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.6 }}
              >
                <Button
                  ref={ctaRef}
                  variant="primary"
                  size="lg"
                  onClick={handleCollect}
                  leftIcon={<span>📦</span>}
                >
                  放入百宝箱
                </Button>
              </motion.div>
            </motion.div>
          )}
        </motion.div>

        {/* Confetti */}
        <Confetti
          active={showConfetti}
          count={60}
          origin={{ x: 50, y: 40 }}
          duration={3000}
        />
      </motion.div>
    </AnimatePresence>
  )

  return createPortal(overlay, document.body)
}
