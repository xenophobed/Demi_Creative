import { motion } from 'framer-motion'
import Card from '@/components/common/Card'
import type { MemoryCharacter } from '@/types/api'

interface CharacterGalleryProps {
  characters: MemoryCharacter[]
  isLoading: boolean
}

const CARD_COLORS = [
  'from-purple-100 to-purple-50 border-purple-200',
  'from-blue-100 to-blue-50 border-blue-200',
  'from-green-100 to-green-50 border-green-200',
  'from-yellow-100 to-yellow-50 border-yellow-200',
  'from-pink-100 to-pink-50 border-pink-200',
  'from-indigo-100 to-indigo-50 border-indigo-200',
  'from-teal-100 to-teal-50 border-teal-200',
  'from-orange-100 to-orange-50 border-orange-200',
]

function CharacterGallery({ characters, isLoading }: CharacterGalleryProps) {
  if (isLoading) {
    return (
      <Card className="p-6">
        <h2 className="text-lg font-bold text-gray-800 mb-4">My Characters</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="h-32 rounded-xl bg-gray-100 animate-pulse"
            />
          ))}
        </div>
      </Card>
    )
  }

  return (
    <Card className="p-6">
      <h2 className="text-lg font-bold text-gray-800 mb-4">My Characters</h2>

      {characters.length === 0 ? (
        <div className="text-center py-8">
          <div className="text-4xl mb-3">🎨</div>
          <p className="text-gray-500 text-sm">
            Create your first story to meet your characters!
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {characters.map((character, index) => (
            <motion.div
              key={character.name}
              className={`relative rounded-xl border bg-gradient-to-br p-4 ${CARD_COLORS[index % CARD_COLORS.length]}`}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: index * 0.05 }}
              whileHover={{ scale: 1.03, y: -2 }}
            >
              {/* Appearance count badge */}
              <span className="absolute top-2 right-2 bg-white/80 text-xs font-bold text-gray-600 rounded-full px-2 py-0.5 shadow-sm">
                x{character.appearance_count}
              </span>

              <h3 className="font-bold text-gray-800 text-sm truncate pr-8">
                {character.name}
              </h3>

              {character.description && (
                <p className="text-gray-600 text-xs mt-1 line-clamp-2">
                  {character.description}
                </p>
              )}

              {character.traits && character.traits.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {character.traits.slice(0, 3).map((trait) => (
                    <span
                      key={trait}
                      className="bg-white/60 text-gray-600 text-[10px] rounded-full px-2 py-0.5"
                    >
                      {trait}
                    </span>
                  ))}
                </div>
              )}
            </motion.div>
          ))}
        </div>
      )}
    </Card>
  )
}

export default CharacterGallery
