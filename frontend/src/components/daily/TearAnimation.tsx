import { useState, useRef } from 'react'
import { motion, useMotionValue, useTransform, useReducedMotion } from 'framer-motion'

interface TearAnimationProps {
  children: React.ReactNode
  onTearComplete: () => void
  disabled?: boolean
}

const TEAR_THRESHOLD = 0.6 // 60% of width to trigger

export default function TearAnimation({ children, onTearComplete, disabled }: TearAnimationProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [torn, setTorn] = useState(false)
  const prefersReduced = useReducedMotion()
  const dragX = useMotionValue(0)

  // Progress 0→1 as user drags
  const progress = useTransform(dragX, [0, 300], [0, 1])
  // Tear line clip-path: jagged edge moves left to right
  const clipPath = useTransform(progress, (p) => {
    const x = Math.min(p * 100, 100)
    // Jagged tear points
    return `polygon(${x}% 0%, ${x}% 15%, ${Math.max(0, x - 3)}% 25%, ${x}% 40%, ${Math.max(0, x - 4)}% 55%, ${x}% 70%, ${Math.max(0, x - 2)}% 85%, ${x}% 100%, 100% 100%, 100% 0%)`
  })

  const handleDragEnd = () => {
    if (torn || disabled) return
    const containerWidth = containerRef.current?.offsetWidth ?? 300
    const currentX = dragX.get()
    const pct = currentX / containerWidth

    if (pct >= TEAR_THRESHOLD) {
      setTorn(true)
      onTearComplete()
    }
  }

  if (prefersReduced) {
    return (
      <div
        className={`relative ${disabled ? 'pointer-events-none' : 'cursor-pointer'}`}
        onClick={!disabled && !torn ? () => { setTorn(true); onTearComplete() } : undefined}
      >
        {children}
      </div>
    )
  }

  if (torn) {
    return (
      <motion.div
        initial={{ opacity: 1, y: 0 }}
        animate={{ opacity: 0, y: -30, rotate: -5 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
      >
        {children}
      </motion.div>
    )
  }

  return (
    <div ref={containerRef} className="relative overflow-hidden">
      <motion.div
        drag="x"
        dragConstraints={{ left: 0, right: 300 }}
        dragElastic={0}
        dragMomentum={false}
        style={{ x: dragX }}
        onDragEnd={handleDragEnd}
        className={`relative ${disabled ? 'pointer-events-none' : 'cursor-grab active:cursor-grabbing'}`}
      >
        {/* Visible portion: shrinks as user drags right (paper being torn away) */}
        <motion.div style={{ clipPath }}>
          {children}
        </motion.div>
      </motion.div>

      {/* Revealed content underneath */}
      <div className="absolute inset-0 -z-10 flex items-center justify-center bg-accent/10 rounded-card">
        <span className="text-3xl">🌟</span>
      </div>
    </div>
  )
}
