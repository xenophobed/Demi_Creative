/**
 * Curated buddy titles. Mirror of backend/src/services/agent_constants.py
 * CURATED_TITLES (PRD §3.11.3). Order matters and must match the backend
 * exactly so the curated-bypass safety check on the server agrees with
 * the in-app picker.
 *
 * Free-text titles outside this list are allowed only for the 9-12 age
 * group, and are safety-checked server-side before persistence.
 */
export const CURATED_TITLES = [
  "Story Wizard",
  "Brave Lion",
  "Galaxy Explorer",
  "Dragon Friend",
  "Magic Painter",
  "Forest Guardian",
  "Ocean Adventurer",
  "Star Dreamer",
  "Dance Captain",
  "Inventor",
  "Riddle Master",
  "Cloud Surfer",
  "Tiny Hero",
  "Silly Scientist",
  "Music Maker",
  "Treasure Hunter",
  "Kindness Knight",
  "Robot Buddy",
  "Time Traveler",
  "Sunshine Maker",
] as const;

export type CuratedTitle = (typeof CURATED_TITLES)[number];

import type { AgeGroup } from "@/types/api";

/**
 * Free-text custom titles are allowed only in the 9-12 age tier per PRD §3.11.2.
 * Younger tiers stay constrained to the curated list.
 */
export function customTitleAllowed(age: AgeGroup | undefined | null): boolean {
  return age === "9-12";
}
