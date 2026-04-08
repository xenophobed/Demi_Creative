import { motion, useAnimation, useReducedMotion } from 'framer-motion'
import { useCallback, useEffect, useImperativeHandle, forwardRef } from 'react'
import useDailyTaskStore from '@/store/useDailyTaskStore'

export interface StarPiggyBankHandle {
  onStarReceived: () => void
}

interface StarPiggyBankProps {
  className?: string
}

function StarSlot({ filled, index }: { filled: boolean; index: number }) {
  return (
    <motion.span
      className={`text-base sm:text-lg leading-none select-none ${
        filled
          ? 'drop-shadow-[0_0_4px_rgba(255,230,109,0.8)]'
          : 'opacity-30 grayscale'
      }`}
      initial={{ scale: 0.8, opacity: 0 }}
      animate={{ scale: 1, opacity: filled ? 1 : 0.3 }}
      transition={{ delay: index * 0.05, type: 'spring', stiffness: 400, damping: 20 }}
      aria-hidden="true"
    >
      ⭐
    </motion.span>
  )
}

const StarPiggyBank = forwardRef<StarPiggyBankHandle, StarPiggyBankProps>(
  function StarPiggyBank({ className = '' }, ref) {
    const { claimed, target } = useDailyTaskStore((s) => s.getWeekProgress())
    const streak = useDailyTaskStore((s) => s.getStreak())
    const prefersReduced = useReducedMotion()
    const shakeControls = useAnimation()

    const triggerShake = useCallback(async () => {
      if (prefersReduced) return
      await shakeControls.start({
        rotate: [0, -6, 6, -4, 4, -2, 2, 0],
        scale: [1, 1.08, 1.08, 1.04, 1.04, 1, 1, 1],
        transition: { duration: 0.6, ease: 'easeInOut' },
      })
    }, [prefersReduced, shakeControls])

    useImperativeHandle(ref, () => ({ onStarReceived: triggerShake }), [triggerShake])

    useEffect(() => {
      if (claimed > 0) {
        triggerShake()
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [claimed])

    return (
      <motion.div
        className={`inline-flex items-center gap-1.5 sm:gap-2 px-3 py-1.5 rounded-full
          bg-warm-100 border border-accent/30 shadow-card font-rounded ${className}`}
        animate={shakeControls}
        aria-label={`Weekly star progress: ${claimed} of ${target} stars collected`}
        role="status"
      >
        <span className="text-lg sm:text-xl leading-none select-none" aria-hidden="true">
          🫙
        </span>

        <span className="inline-flex items-center gap-0.5">
          {Array.from({ length: target }, (_, i) => (
            <StarSlot key={i} index={i} filled={i < claimed} />
          ))}
        </span>

        <span className="text-xs sm:text-sm font-semibold text-accent-dark whitespace-nowrap">
          {claimed}/{target}
        </span>

        {streak >= 2 && (
          <motion.span
            className="ml-0.5 text-xs font-bold text-primary bg-primary/10 px-1.5 py-0.5 rounded-full"
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', stiffness: 500, damping: 25 }}
          >
            🔥{streak}
          </motion.span>
        )}
      </motion.div>
    )
  },
)

export default StarPiggyBank
