import { useState, useRef, useCallback, useEffect } from 'react'
import { motion, useMotionValue, useTransform, useReducedMotion, animate } from 'framer-motion'

interface TearAnimationProps {
  children: React.ReactNode
  onTearComplete: () => void
  disabled?: boolean
}

const TEAR_THRESHOLD = 0.50 // 50% of width to trigger

export default function TearAnimation({ children, onTearComplete, disabled }: TearAnimationProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [torn, setTorn] = useState(false)
  const [animationDone, setAnimationDone] = useState(false)
  const [containerWidth, setContainerWidth] = useState(300)
  const prefersReduced = useReducedMotion()
  const dragX = useMotionValue(0)

  // Measure container on mount and resize
  useEffect(() => {
    const measure = () => {
      if (containerRef.current) setContainerWidth(containerRef.current.offsetWidth)
    }
    measure()
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [])

  // Progress 0→1 as user drags
  const progress = useTransform(dragX, [0, containerWidth], [0, 1])

  // Jagged tear clip-path that moves left to right
  const clipPath = useTransform(progress, (p) => {
    const x = Math.min(Math.max(p, 0) * 100, 100)
    return `polygon(${x}% 0%, ${x}% 15%, ${Math.max(0, x - 3)}% 25%, ${x}% 40%, ${Math.max(0, x - 4)}% 55%, ${x}% 70%, ${Math.max(0, x - 2)}% 85%, ${x}% 100%, 100% 100%, 100% 0%)`
  })

  const handleDragEnd = useCallback(() => {
    if (torn || disabled) return
    const pct = dragX.get() / containerWidth

    if (pct >= TEAR_THRESHOLD) {
      setTorn(true)
      onTearComplete()
    } else {
      // Snap back
      animate(dragX, 0, { type: 'spring', stiffness: 300, damping: 25 })
    }
  }, [torn, disabled, dragX, containerWidth, onTearComplete])

  if (prefersReduced) {
    return (
      <div
        className={`relative ${disabled ? 'pointer-events-none' : 'cursor-pointer'}`}
        onClick={!disabled && !torn ? () => { setTorn(true); setAnimationDone(true); onTearComplete() } : undefined}
      >
        {children}
      </div>
    )
  }

  // After tear-out animation finishes, render children directly
  // so InspirationDaily's built-in "claimed" state shows through
  if (animationDone) {
    return <>{children}</>
  }

  if (torn) {
    return (
      <motion.div
        initial={{ opacity: 1, y: 0 }}
        animate={{ opacity: 0, y: -30, rotate: -5 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        onAnimationComplete={() => setAnimationDone(true)}
      >
        {children}
      </motion.div>
    )
  }

  return (
    <div ref={containerRef} className="relative overflow-hidden">
      <motion.div
        drag="x"
        dragConstraints={{ left: 0, right: containerWidth }}
        dragElastic={0}
        dragMomentum={false}
        style={{ x: dragX }}
        onDragEnd={handleDragEnd}
        className={`relative ${disabled ? 'pointer-events-none' : 'cursor-grab active:cursor-grabbing'}`}
      >
        {/* Visible portion: shrinks as user drags right */}
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
