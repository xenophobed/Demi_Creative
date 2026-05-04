/**
 * Pure helper that decides whether the RequireOnboarded effect in
 * PageContainer should redirect the current request to /my-agent.
 *
 * Per PRD §3.11.2 onboarding is a SOFT gate. We do NOT redirect on
 * route navigation — that was annoying users who wanted to browse
 * Content Hub before crafting a buddy. Per-action affordances inside
 * /content-hub and the Share-to-Hub modal handle the actual gating
 * (create / join / post require an onboarded buddy; browsing does not).
 *
 * The function is kept (instead of being deleted outright) so that
 * future paths which truly REQUIRE onboarding can opt in by extending
 * the inner allowlist. Today no path requires it.
 *
 * Issue: #444 | Parent epic: #436
 */

export interface OnboardingGateInput {
  isAuthenticated: boolean;
  onboardedAt: string | null | undefined;
  pathname: string;
}

export function shouldRedirectToOnboarding(
  _input: OnboardingGateInput,
): boolean {
  // Intentionally always returns false. See header comment.
  return false;
}
