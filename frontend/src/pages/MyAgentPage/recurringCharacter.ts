/**
 * Recurring character chip selector (#560).
 *
 * Pure helper extracted so the chip-selection rule can be unit-tested
 * without a DOM — the project does not ship @testing-library/react, so
 * UI logic that lives in components is exercised through a pure
 * function instead.
 *
 * Rule: a character is chip-worthy only if it has appeared at least
 * twice. Among chip-worthy characters, the one with the most
 * appearances wins. Ties broken by `last_seen_at` (most-recent first)
 * so a tied "favourite" feels current to the child.
 *
 * The 2-appearance floor is deliberate: a one-off character isn't a
 * pattern, and the chip is meant to surface continuity, not noise.
 */

import type { MemoryCharacter } from "@/types/api";

const RECURRING_THRESHOLD = 2;

export function pickRecurringCharacter(
  characters: readonly MemoryCharacter[] | null | undefined,
): MemoryCharacter | null {
  if (!characters || characters.length === 0) return null;
  const recurring = characters.filter(
    (c) => (c.appearance_count ?? 0) >= RECURRING_THRESHOLD && Boolean(c.name),
  );
  if (recurring.length === 0) return null;

  // Sort by appearance_count desc, then last_seen_at desc.
  const sorted = [...recurring].sort((a, b) => {
    const byCount = (b.appearance_count ?? 0) - (a.appearance_count ?? 0);
    if (byCount !== 0) return byCount;
    return (b.last_seen_at ?? "").localeCompare(a.last_seen_at ?? "");
  });
  return sorted[0] ?? null;
}

export function chipPrefillForCharacter(name: string): string {
  return `Tell me more about ${name}`;
}
