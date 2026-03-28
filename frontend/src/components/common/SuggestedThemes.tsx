/**
 * SuggestedThemes - displays personalised theme recommendation chips (#292).
 *
 * Fetches recommendations from GET /api/v1/memory/recommendations/{child_id}
 * and renders them as clickable chips.  When clicked, the caller receives the
 * theme string via `onSelect`.
 */

import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { memoryService } from '@/api/services/memoryService'
import useChildStore from '@/store/useChildStore'
import useAuthStore from '@/store/useAuthStore'

interface SuggestedThemesProps {
  /** Called when the user clicks a theme chip */
  onSelect: (theme: string) => void
  /** Maximum chips to show (default 5) */
  limit?: number
}

export default function SuggestedThemes({ onSelect, limit = 5 }: SuggestedThemesProps) {
  const { isAuthenticated } = useAuthStore()
  const { defaultChildId } = useChildStore()
  const [themes, setThemes] = useState<string[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!isAuthenticated || !defaultChildId) return

    let cancelled = false
    setLoading(true)

    memoryService
      .getRecommendations(defaultChildId, limit)
      .then((res) => {
        if (!cancelled) setThemes(res.recommendations)
      })
      .catch(() => {
        // Silently fail — recommendations are a nice-to-have
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [isAuthenticated, defaultChildId, limit])

  if (loading || themes.length === 0) return null

  return (
    <div className="space-y-2">
      <p className="text-sm text-gray-500 font-medium">Suggested for you</p>
      <div className="flex flex-wrap gap-2">
        <AnimatePresence>
          {themes.map((theme, i) => (
            <motion.button
              key={theme}
              className="px-3 py-1.5 rounded-full text-sm font-medium bg-purple-50 text-purple-700 border border-purple-200 hover:bg-purple-100 transition-colors"
              onClick={() => onSelect(theme)}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              transition={{ delay: i * 0.05 }}
              whileHover={{ scale: 1.08 }}
              whileTap={{ scale: 0.95 }}
            >
              {theme}
            </motion.button>
          ))}
        </AnimatePresence>
      </div>
    </div>
  )
}
