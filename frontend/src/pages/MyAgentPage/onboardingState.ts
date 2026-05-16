/**
 * Pure helpers that drive the OnboardingModal's auto-open and step
 * sequencing. Extracted so they're unit-testable without mounting the
 * page tree (the project does not depend on @testing-library/react).
 *
 * Issue: #443 | Parent epic: #436
 */

import type { AgeGroup } from "@/types/api";

export interface AutoOpenInput {
  isAuthenticated: boolean;
  /** users.onboarded_at returned from /me. null/undefined = not yet. */
  onboardedAt: string | null | undefined;
  /** Existing agent for the active child (null if none yet). */
  hasExistingAgent: boolean;
}

export function shouldAutoOpenOnboarding(input: AutoOpenInput): boolean {
  if (!input.isAuthenticated) return false;
  if (input.onboardedAt) return false;
  // If a buddy already exists for this child, treat that as implicit
  // consent and skip the auto-open. Otherwise the modal stacks on top
  // of the live AgentChatPanel — the user sees their chat peeking
  // through the modal backdrop and the experience looks broken (#510
  // follow-up). Returning users without a buddy still see onboarding.
  if (input.hasExistingAgent) return false;
  return true;
}

export type OnboardingStepKey =
  | "greeting"
  | "name"
  | "avatar"
  | "title"
  | "consent";

/**
 * Per-PRD §3.11.2 the onboarding flow shrinks for younger children:
 *   3-5: avatar-only path with auto-named buddy
 *   6-8: name + avatar + curated title
 *   9-12: full flow with optional free-text title + nickname step
 *
 * The greeting and consent steps appear for all age groups.
 */
export function stepsForAge(age: AgeGroup | undefined | null): OnboardingStepKey[] {
  if (age === "3-5") {
    return ["greeting", "avatar", "consent"];
  }
  return ["greeting", "name", "avatar", "title", "consent"];
}

/**
 * For 3-5 we auto-suggest a buddy name so the child doesn't have to
 * type. The name skips the safety check on the server because it comes
 * from a curated server-vetted pool — but to keep things simple we
 * pull from a small client-side list and let the standard safety
 * pipeline run on it. None of these strings should fail the safety
 * gate.
 */
export const AUTO_NAME_SUGGESTIONS = [
  "Sunny",
  "Bubbles",
  "Rosie",
  "Pip",
  "Coco",
  "Toto",
  "Luna",
  "Dot",
] as const;
