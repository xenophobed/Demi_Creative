import { motion } from 'framer-motion'
import Card from '@/components/common/Card'
import type { PreferenceProfile } from '@/types/api'

interface PreferenceSummaryProps {
  preferences: PreferenceProfile | null
  isLoading: boolean
}

const THEME_COLORS = [
  'bg-purple-200 text-purple-800',
  'bg-blue-200 text-blue-800',
  'bg-green-200 text-green-800',
  'bg-yellow-200 text-yellow-800',
  'bg-pink-200 text-pink-800',
]

const INTEREST_COLORS = [
  'bg-indigo-200 text-indigo-800',
  'bg-teal-200 text-teal-800',
  'bg-orange-200 text-orange-800',
  'bg-rose-200 text-rose-800',
  'bg-cyan-200 text-cyan-800',
]

/**
 * Extract the top N entries from a score map, sorted by score descending.
 */
function topEntries(
  scoreMap: Record<string, number>,
  limit: number
): Array<{ label: string; score: number }> {
  return Object.entries(scoreMap)
    .sort(([, a], [, b]) => b - a)
    .slice(0, limit)
    .map(([label, score]) => ({ label, score }))
}

function PreferenceSummary({ preferences, isLoading }: PreferenceSummaryProps) {
  if (isLoading) {
    return (
      <Card className="p-6">
        <h2 className="text-lg font-bold text-gray-800 mb-4">
          Favorite Themes and Interests
        </h2>
        <div className="flex flex-wrap gap-2">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-7 w-20 rounded-full bg-gray-100 animate-pulse"
            />
          ))}
        </div>
      </Card>
    )
  }

  const themes = preferences ? topEntries(preferences.themes, 5) : []
  const interests = preferences ? topEntries(preferences.interests, 5) : []
  const hasData = themes.length > 0 || interests.length > 0

  return (
    <Card className="p-6">
      <h2 className="text-lg font-bold text-gray-800 mb-4">
        Favorite Themes and Interests
      </h2>

      {!hasData ? (
        <div className="text-center py-6">
          <div className="text-4xl mb-3">🌈</div>
          <p className="text-gray-500 text-sm">
            Your favorite themes will appear here as you explore stories!
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {themes.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-600 mb-2">
                Themes
              </h3>
              <div className="flex flex-wrap gap-2">
                {themes.map((entry, index) => (
                  <motion.span
                    key={entry.label}
                    className={`inline-block rounded-full px-3 py-1 text-sm font-medium ${THEME_COLORS[index % THEME_COLORS.length]}`}
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: index * 0.05 }}
                    whileHover={{ scale: 1.08 }}
                  >
                    {entry.label}
                  </motion.span>
                ))}
              </div>
            </div>
          )}

          {interests.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-600 mb-2">
                Interests
              </h3>
              <div className="flex flex-wrap gap-2">
                {interests.map((entry, index) => (
                  <motion.span
                    key={entry.label}
                    className={`inline-block rounded-full px-3 py-1 text-sm font-medium ${INTEREST_COLORS[index % INTEREST_COLORS.length]}`}
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: index * 0.05 }}
                    whileHover={{ scale: 1.08 }}
                  >
                    {entry.label}
                  </motion.span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  )
}

export default PreferenceSummary
