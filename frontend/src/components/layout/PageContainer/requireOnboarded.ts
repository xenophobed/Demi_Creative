/**
 * Pure helper that decides whether the RequireOnboarded effect in
 * PageContainer should redirect the current request to /my-agent.
 *
 * Extracted so it's unit-testable without mounting the page tree
 * (the project does not depend on @testing-library/react).
 *
 * Issue: #444 | Parent epic: #436
 */

export interface OnboardingGateInput {
  isAuthenticated: boolean;
  onboardedAt: string | null | undefined;
  pathname: string;
}

export function shouldRedirectToOnboarding(
  input: OnboardingGateInput,
): boolean {
  const { isAuthenticated, onboardedAt, pathname } = input;
  if (!isAuthenticated) return false;
  if (onboardedAt) return false;
  if (pathname === "/my-agent") return false;
  if (pathname.startsWith("/login")) return false;
  if (pathname.startsWith("/register")) return false;
  return true;
}
