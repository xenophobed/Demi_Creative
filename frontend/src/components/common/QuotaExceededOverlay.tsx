import { motion, AnimatePresence } from 'framer-motion'

interface QuotaExceededOverlayProps {
  show: boolean
  message: string
  onDismiss: () => void
}

/**
 * Full-screen overlay shown when a user exceeds their daily generation quota.
 * Blurs the background and displays a friendly, child-appropriate message.
 */
export default function QuotaExceededOverlay({ show, message, onDismiss }: QuotaExceededOverlayProps) {
  return (
    <AnimatePresence>
      {show && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center p-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          {/* Blurred backdrop */}
          <div
            className="absolute inset-0 bg-black/30 backdrop-blur-sm"
            onClick={onDismiss}
          />

          {/* Modal card */}
          <motion.div
            className="relative w-full max-w-md rounded-3xl bg-gradient-to-b from-amber-50 to-orange-50 border border-amber-200 shadow-2xl p-8 text-center"
            initial={{ opacity: 0, scale: 0.85, y: 30 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            transition={{ type: 'spring', damping: 22, stiffness: 260 }}
          >
            <div className="text-5xl mb-4">🌙</div>
            <h2 className="text-xl font-bold text-amber-800 mb-2">
              今天的创作次数用完啦！
            </h2>
            <p className="text-amber-700 mb-6 leading-relaxed">
              {message}
            </p>
            <button
              onClick={onDismiss}
              className="px-6 py-2.5 rounded-full bg-amber-400 hover:bg-amber-500 text-white font-semibold shadow-md transition-colors"
            >
              知道了
            </button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

/** Check whether an error message is a quota-exceeded error */
export function isQuotaError(msg: string | null | undefined): boolean {
  return !!msg && msg.includes('创作次数用完')
}
