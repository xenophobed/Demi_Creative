import type { MemoryCharacter } from "@/types/api";

// "Main characters" = the most frequently appearing characters. Keep this rule
// in sync with get_characters_grouped + MAIN_CHARACTER_LIMIT in
// backend/src/services/database/character_repository.py.
export const MAIN_CHARACTER_LIMIT = 5;

/**
 * Split characters into main/other by appearance frequency.
 *
 * - More than MAIN_CHARACTER_LIMIT characters: the top N by appearance_count
 *   are main; the rest are other.
 * - MAIN_CHARACTER_LIMIT or fewer: only the most-frequent character(s) — those
 *   tied at the highest appearance_count — are main, so a small cast still
 *   divides instead of all landing in main. If every character appears equally
 *   often (including a single character), they are all main.
 */
export function splitByAppearanceFrequency(characters: MemoryCharacter[]): {
  main: MemoryCharacter[];
  other: MemoryCharacter[];
} {
  const ranked = [...characters].sort(
    (a, b) => Number(b.appearance_count || 0) - Number(a.appearance_count || 0),
  );
  if (ranked.length === 0) return { main: [], other: [] };

  if (ranked.length > MAIN_CHARACTER_LIMIT) {
    return {
      main: ranked.slice(0, MAIN_CHARACTER_LIMIT),
      other: ranked.slice(MAIN_CHARACTER_LIMIT),
    };
  }

  const topCount = Number(ranked[0].appearance_count || 0);
  return {
    main: ranked.filter((c) => Number(c.appearance_count || 0) === topCount),
    other: ranked.filter((c) => Number(c.appearance_count || 0) !== topCount),
  };
}
