import { useEffect, useState } from 'react'
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion'

interface StarFlyAnimationProps {
  active: boolean
  fromRef: React.RefObject<HTMLElement | null>
  toRef: React.RefObject<HTMLElement | null>
  onComplete: () => void
}

export default function StarFlyAnimation({ active, fromRef, toRef, onComplete }: StarFlyAnimationProps) {
  const prefersReduced = useReducedMotion()
  const [coords, setCoords] = useState<{ from: { x: number; y: number }; to: { x: number; y: number } } | null>(null)

  useEffect(() => {
    if (!active) {
      setCoords(null)
      return
    }

    if (prefersReduced) {
      onComplete()
      return
    }

    const fromEl = fromRef.current
    const toEl = toRef.current
    if (!fromEl || !toEl) {
      onComplete()
      return
    }

    const fromRect = fromEl.getBoundingClientRect()
    const toRect = toEl.getBoundingClientRect()
    setCoords({
      from: { x: fromRect.left + fromRect.width / 2, y: fromRect.top + fromRect.height / 2 },
      to: { x: toRect.left + toRect.width / 2, y: toRect.top + toRect.height / 2 },
    })
  }, [active, prefersReduced, fromRef, toRef, onComplete])

  if (!coords) return null

  const midX = (coords.from.x + coords.to.x) / 2
  const midY = Math.min(coords.from.y, coords.to.y) - 80 // arc peak above both points

  return (
    <AnimatePresence>
      {active && (
        <motion.div
          className="fixed z-50 pointer-events-none text-3xl"
          style={{ left: coords.from.x - 16, top: coords.from.y - 16 }}
          initial={{ scale: 0, opacity: 0 }}
          animate={{
            scale: [0, 1.3, 1, 0.8],
            opacity: [0, 1, 1, 0],
            left: [coords.from.x - 16, midX - 16, coords.to.x - 16],
            top: [coords.from.y - 16, midY - 16, coords.to.y - 16],
          }}
          transition={{
            duration: 0.9,
            ease: 'easeInOut',
            times: [0, 0.3, 0.7, 1],
          }}
          onAnimationComplete={onComplete}
        >
          🌟
        </motion.div>
      )}
    </AnimatePresence>
  )
}
