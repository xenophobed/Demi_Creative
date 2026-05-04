/**
 * Onboarding Service — wrapper for POST /me/onboarding/complete (#440).
 * Returns the full UserResponse so the auth store can sync onboarded_at
 * and parent_consent_at without a second round-trip.
 */

import apiClient from "../client";
import type { User } from "@/types/auth";

export interface CompleteOnboardingPayload {
  parent_consent: boolean;
  child_id: string;
}

export async function completeOnboarding(
  payload: CompleteOnboardingPayload,
): Promise<User> {
  const r = await apiClient.post<User>("/me/onboarding/complete", payload);
  return r.data;
}

export const onboardingService = { completeOnboarding };
