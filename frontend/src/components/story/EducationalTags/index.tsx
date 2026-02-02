import { motion } from 'framer-motion'
import type { EducationalValue } from '@/types/api'

interface EducationalTagsProps {
  value: EducationalValue
  className?: string
}

function EducationalTags({ value, className = '' }: EducationalTagsProps) {
  const { themes, concepts, moral } = value

  // Theme colors and icons
  const themeStyles: Record<string, { emoji: string; bgColor: string; textColor: string }> = {
    Friendship: { emoji: '🤝', bgColor: 'bg-pink-100', textColor: 'text-pink-700' },
    Courage: { emoji: '🦁', bgColor: 'bg-orange-100', textColor: 'text-orange-700' },
    Love: { emoji: '💕', bgColor: 'bg-red-100', textColor: 'text-red-700' },
    Honesty: { emoji: '✨', bgColor: 'bg-yellow-100', textColor: 'text-yellow-700' },
    Kindness: { emoji: '🌸', bgColor: 'bg-purple-100', textColor: 'text-purple-700' },
    Exploration: { emoji: '🔍', bgColor: 'bg-blue-100', textColor: 'text-blue-700' },
    Growth: { emoji: '🌱', bgColor: 'bg-green-100', textColor: 'text-green-700' },
    Teamwork: { emoji: '👥', bgColor: 'bg-indigo-100', textColor: 'text-indigo-700' },
    Creativity: { emoji: '💡', bgColor: 'bg-amber-100', textColor: 'text-amber-700' },
    Adventure: { emoji: '🗺️', bgColor: 'bg-teal-100', textColor: 'text-teal-700' },
    default: { emoji: '🏷️', bgColor: 'bg-gray-100', textColor: 'text-gray-700' },
  }

  // Concept colors and icons
  const conceptStyles: Record<string, { emoji: string; bgColor: string; textColor: string }> = {
    Colors: { emoji: '🎨', bgColor: 'bg-rainbow', textColor: 'text-purple-700' },
    Numbers: { emoji: '🔢', bgColor: 'bg-blue-50', textColor: 'text-blue-700' },
    Shapes: { emoji: '⬡', bgColor: 'bg-green-50', textColor: 'text-green-700' },
    Animals: { emoji: '🐾', bgColor: 'bg-amber-50', textColor: 'text-amber-700' },
    Nature: { emoji: '🌿', bgColor: 'bg-emerald-50', textColor: 'text-emerald-700' },
    Science: { emoji: '🔬', bgColor: 'bg-cyan-50', textColor: 'text-cyan-700' },
    Art: { emoji: '🖼️', bgColor: 'bg-rose-50', textColor: 'text-rose-700' },
    Music: { emoji: '🎵', bgColor: 'bg-violet-50', textColor: 'text-violet-700' },
    default: { emoji: '📚', bgColor: 'bg-gray-50', textColor: 'text-gray-700' },
  }

  const getThemeStyle = (theme: string) => themeStyles[theme] || themeStyles.default
  const getConceptStyle = (concept: string) => conceptStyles[concept] || conceptStyles.default

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Theme tags */}
      {themes.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-lg">🎯</span>
            <span className="text-sm font-semibold text-gray-600">Story Themes</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {themes.map((theme, index) => {
              const style = getThemeStyle(theme)
              return (
                <motion.span
                  key={theme}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium
                    ${style.bgColor} ${style.textColor}`}
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: index * 0.1 }}
                  whileHover={{ scale: 1.05 }}
                >
                  <span>{style.emoji}</span>
                  <span>{theme}</span>
                </motion.span>
              )
            })}
          </div>
        </div>
      )}

      {/* Concept tags */}
      {concepts.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-lg">💡</span>
            <span className="text-sm font-semibold text-gray-600">Learning Concepts</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {concepts.map((concept, index) => {
              const style = getConceptStyle(concept)
              return (
                <motion.span
                  key={concept}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium
                    ${style.bgColor} ${style.textColor}`}
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: index * 0.1 + 0.2 }}
                  whileHover={{ scale: 1.05 }}
                >
                  <span>{style.emoji}</span>
                  <span>{concept}</span>
                </motion.span>
              )
            })}
          </div>
        </div>
      )}

      {/* Moral lesson */}
      {moral && (
        <motion.div
          className="bg-gradient-to-r from-amber-50 to-orange-50 rounded-card p-4 border border-amber-200"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
        >
          <div className="flex items-start gap-3">
            <span className="text-2xl flex-shrink-0">💝</span>
            <div>
              <span className="text-sm font-semibold text-amber-700 block mb-1">
                Story Moral
              </span>
              <p className="text-amber-800">{moral}</p>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  )
}

export default EducationalTags
