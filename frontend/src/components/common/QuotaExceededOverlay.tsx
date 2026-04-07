import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

interface QuotaExceededOverlayProps {
  show: boolean
  message: string
  onDismiss: () => void
  referralCode?: string
  membershipTier?: string
}

/**
 * Full-screen overlay shown when a user exceeds their daily generation quota.
 * Blurs the background and displays a friendly, child-appropriate message.
 */
export default function QuotaExceededOverlay({ show, message, onDismiss, referralCode, membershipTier }: QuotaExceededOverlayProps) {
  const [copied, setCopied] = useState(false)
  const shareUrl = referralCode ? `${window.location.origin}/login?ref=${referralCode}` : ''

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
            <p className="text-amber-700 mb-4 leading-relaxed">
              {message}
            </p>

            {/* Referral CTA */}
            {referralCode && membershipTier === 'plus' ? (
              <div className="mb-4 px-4 py-3 rounded-2xl bg-gradient-to-r from-amber-100 to-yellow-100 border border-amber-200">
                <p className="text-sm font-semibold text-amber-800">
                  You're a Plus member!
                </p>
              </div>
            ) : referralCode ? (
              <div className="mb-4 px-4 py-3 rounded-2xl bg-gradient-to-r from-purple-50 to-pink-50 border border-purple-200 space-y-2">
                <p className="text-sm font-semibold text-purple-800">
                  Want more? Share with friends!
                </p>
                <p className="text-xs text-purple-600">
                  Invite 10 friends to sign up and get 3x daily uses
                </p>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    readOnly
                    value={shareUrl}
                    className="flex-1 px-2 py-1.5 text-xs border border-purple-200 rounded-lg bg-white text-purple-700 truncate"
                  />
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(shareUrl)
                      setCopied(true)
                      setTimeout(() => setCopied(false), 2000)
                    }}
                    className="px-3 py-1.5 text-xs font-medium rounded-lg bg-purple-500 text-white hover:bg-purple-600 transition-colors whitespace-nowrap"
                  >
                    {copied ? "Copied!" : "Copy"}
                  </button>
                </div>
              </div>
            ) : null}

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
