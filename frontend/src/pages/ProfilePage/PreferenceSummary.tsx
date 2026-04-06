import { motion } from "framer-motion";
import Card from "@/components/common/Card";
import type { MemoryPreferenceCategory, PreferenceProfile } from "@/types/api";

interface PreferenceSummaryProps {
  preferences: PreferenceProfile | null;
  isLoading: boolean;
  isEditMode?: boolean;
  onDeletePreferenceItem?: (
    category: MemoryPreferenceCategory,
    label: string,
  ) => Promise<void> | void;
  deletingItemKey?: string | null;
}

const THEME_COLORS = [
  "bg-purple-200 text-purple-800",
  "bg-blue-200 text-blue-800",
  "bg-green-200 text-green-800",
  "bg-yellow-200 text-yellow-800",
  "bg-pink-200 text-pink-800",
];

const INTEREST_COLORS = [
  "bg-indigo-200 text-indigo-800",
  "bg-teal-200 text-teal-800",
  "bg-orange-200 text-orange-800",
  "bg-rose-200 text-rose-800",
  "bg-cyan-200 text-cyan-800",
];

/**
 * Extract the top N entries from a score map, sorted by score descending.
 */
function topEntries(
  scoreMap: Record<string, number>,
  limit: number,
): Array<{ label: string; score: number }> {
  return Object.entries(scoreMap)
    .sort(([, a], [, b]) => b - a)
    .slice(0, limit)
    .map(([label, score]) => ({ label, score }));
}

function PreferenceChip({
  label,
  className,
  delay,
  isEditMode,
  isDeleting,
  onDelete,
}: {
  label: string;
  className: string;
  delay: number;
  isEditMode: boolean;
  isDeleting: boolean;
  onDelete?: () => Promise<void> | void;
}) {
  return (
    <motion.span
      className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium ${className} ${isEditMode ? "pr-1.5" : ""}`}
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay }}
      whileHover={{ scale: 1.08 }}
    >
      <span>{label}</span>
      {isEditMode && (
        <button
          type="button"
          className="ml-2 h-5 w-5 rounded-full bg-white/80 text-gray-500 hover:text-red-500"
          aria-label={`Delete ${label}`}
          onClick={(e) => {
            e.stopPropagation();
            onDelete?.();
          }}
          disabled={isDeleting}
        >
          ×
        </button>
      )}
    </motion.span>
  );
}

function PreferenceSummary({
  preferences,
  isLoading,
  isEditMode = false,
  onDeletePreferenceItem,
  deletingItemKey = null,
}: PreferenceSummaryProps) {
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
    );
  }

  const themes = preferences ? topEntries(preferences.themes, 5) : [];
  const interests = preferences ? topEntries(preferences.interests, 5) : [];
  const concepts = preferences ? topEntries(preferences.concepts, 5) : [];
  const hasData =
    themes.length > 0 || interests.length > 0 || concepts.length > 0;

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
                  <PreferenceChip
                    key={entry.label}
                    label={entry.label}
                    className={THEME_COLORS[index % THEME_COLORS.length]}
                    delay={index * 0.05}
                    isEditMode={isEditMode}
                    isDeleting={deletingItemKey === `themes:${entry.label}`}
                    onDelete={() =>
                      onDeletePreferenceItem?.("themes", entry.label)
                    }
                  />
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
                  <PreferenceChip
                    key={entry.label}
                    label={entry.label}
                    className={INTEREST_COLORS[index % INTEREST_COLORS.length]}
                    delay={index * 0.05}
                    isEditMode={isEditMode}
                    isDeleting={deletingItemKey === `interests:${entry.label}`}
                    onDelete={() =>
                      onDeletePreferenceItem?.("interests", entry.label)
                    }
                  />
                ))}
              </div>
            </div>
          )}

          {concepts.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-600 mb-2">
                Things You Learned
              </h3>
              <div className="flex flex-wrap gap-2">
                {concepts.map((entry, index) => (
                  <PreferenceChip
                    key={entry.label}
                    label={entry.label}
                    className="bg-gray-200 text-gray-700"
                    delay={index * 0.05}
                    isEditMode={isEditMode}
                    isDeleting={deletingItemKey === `concepts:${entry.label}`}
                    onDelete={() =>
                      onDeletePreferenceItem?.("concepts", entry.label)
                    }
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

export default PreferenceSummary;
