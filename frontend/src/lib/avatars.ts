/**
 * Shared animal-emoji avatar whitelist for buddy / profile.
 * DO NOT EDIT WITHOUT UPDATING `backend/src/services/agent_constants.py`.
 * The drift contract test in
 * `backend/tests/contracts/test_avatar_whitelist_drift.py` will fail
 * if these two lists diverge.
 */
export const ANIMAL_EMOJIS = [
  "🐶",
  "🐱",
  "🐼",
  "🐨",
  "🦊",
  "🐰",
  "🐸",
  "🦁",
  "🐯",
  "🐮",
  "🐷",
  "🐵",
  "🐔",
  "🐧",
  "🦄",
  "🐲",
  "🐢",
  "🦋",
  "🐬",
  "🐙",
] as const;

export type AvatarEmoji = (typeof ANIMAL_EMOJIS)[number];

export const AVATAR_IDS: readonly string[] = ANIMAL_EMOJIS.map(
  (e) => `emoji:${e}`,
);
