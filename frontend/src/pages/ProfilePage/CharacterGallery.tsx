import { useRef } from "react";
import { motion } from "framer-motion";
import Card from "@/components/common/Card";
import type { MemoryCharacter } from "@/types/api";

interface CharacterGalleryProps {
  characters: MemoryCharacter[];
  mainCharacters?: MemoryCharacter[];
  otherCharacters?: MemoryCharacter[];
  isLoading: boolean;
  isEditMode?: boolean;
  onDeleteCharacter?: (name: string) => Promise<void> | void;
  deletingCharacterName?: string | null;
}

const CARD_COLORS = [
  "from-purple-100 to-purple-50 border-purple-200",
  "from-blue-100 to-blue-50 border-blue-200",
  "from-green-100 to-green-50 border-green-200",
  "from-yellow-100 to-yellow-50 border-yellow-200",
  "from-pink-100 to-pink-50 border-pink-200",
  "from-indigo-100 to-indigo-50 border-indigo-200",
  "from-teal-100 to-teal-50 border-teal-200",
  "from-orange-100 to-orange-50 border-orange-200",
];

function CharacterGallery({
  characters,
  mainCharacters = [],
  otherCharacters = [],
  isLoading,
  isEditMode = false,
  onDeleteCharacter,
  deletingCharacterName = null,
}: CharacterGalleryProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const hasGrouped = mainCharacters.length > 0 || otherCharacters.length > 0;
  const resolvedMainCharacters = hasGrouped
    ? mainCharacters
    : characters.filter(
        (c) =>
          Number(c.main_story_count || 0) > 0 || c.character_role === "main",
      );
  const resolvedOtherCharacters = hasGrouped
    ? otherCharacters
    : characters.filter(
        (c) =>
          !(Number(c.main_story_count || 0) > 0 || c.character_role === "main"),
      );

  const renderCharacterCards = (items: MemoryCharacter[], offset = 0) =>
    items.map((character, index) => (
      <motion.div
        key={character.name}
        className={`character-carousel-card relative rounded-xl border bg-gradient-to-br p-4 ${CARD_COLORS[(index + offset) % CARD_COLORS.length]}`}
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: index * 0.05 }}
        whileHover={{ scale: 1.03, y: -2 }}
      >
        {isEditMode && (
          <button
            type="button"
            className="absolute top-2 left-2 h-6 w-6 rounded-full bg-white/90 text-gray-500 hover:text-red-500 border border-white/90 shadow-sm"
            aria-label={`Delete ${character.name}`}
            onClick={(e) => {
              e.stopPropagation();
              onDeleteCharacter?.(character.name);
            }}
            disabled={deletingCharacterName === character.name}
          >
            ×
          </button>
        )}

        <span className="absolute top-2 right-2 bg-white/80 text-xs font-bold text-gray-600 rounded-full px-2 py-0.5 shadow-sm">
          x{character.appearance_count}
        </span>

        <h3
          className={`font-bold text-gray-800 text-sm truncate ${isEditMode ? "pl-8 pr-8" : "pr-8"}`}
        >
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
    ));

  if (isLoading) {
    return (
      <Card className="p-6">
        <h2 className="text-lg font-bold text-gray-800 mb-4">My Characters</h2>
        <div className="flex gap-3 overflow-hidden">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="h-32 w-40 flex-shrink-0 rounded-xl bg-gray-100 animate-pulse"
            />
          ))}
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-6 overflow-hidden">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-gray-800">My Characters</h2>
        {characters.length > 3 && (
          <span className="text-xs text-gray-400 italic">
            Swipe to see more →
          </span>
        )}
      </div>

      {characters.length === 0 ? (
        <div className="text-center py-8">
          <div className="text-4xl mb-3">🎨</div>
          <p className="text-gray-500 text-sm">
            Create your first story to meet your characters!
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          <div>
            <p className="text-sm font-semibold text-gray-700 mb-2">
              🌟 Main Characters ({resolvedMainCharacters.length})
            </p>
            {resolvedMainCharacters.length > 0 ? (
              <div ref={scrollRef} className="character-carousel">
                {renderCharacterCards(resolvedMainCharacters, 0)}
              </div>
            ) : (
              <p className="text-xs text-gray-500">No main characters yet.</p>
            )}
          </div>

          <div>
            <p className="text-sm font-semibold text-gray-700 mb-2">
              👥 Other Characters ({resolvedOtherCharacters.length})
            </p>
            {resolvedOtherCharacters.length > 0 ? (
              <div className="character-carousel">
                {renderCharacterCards(
                  resolvedOtherCharacters,
                  resolvedMainCharacters.length,
                )}
              </div>
            ) : (
              <p className="text-xs text-gray-500">No other characters yet.</p>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}

export default CharacterGallery;
