/**
 * Pure helper that decides whether the RequireOnboarded effect in
 * PageContainer should redirect the current request to /my-agent.
 *
 * Extracted so it's unit-testable without mounting the page tree
 * (the project does not depend on @testing-library/react).
 *
 * Per PRD §3.11.2: onboarding is a SOFT gate. The "Not now" path lets
 * the child use the rest of the app but blocks Content Hub posting
 * until consent is given. So this helper only fires on /content-hub
 * paths (and the share-to-hub flow that lives there) — never on the
 * entire app.
 *
 * Issue: #444 | Parent epic: #436
 */

export interface OnboardingGateInput {
  isAuthenticated: boolean;
  onboardedAt: string | null | undefined;
  pathname: string;
}

/**
 * Paths that REQUIRE onboarding to access. Everything else is open
 * to authenticated users regardless of onboarding state.
 */
function requiresOnboarding(pathname: string): boolean {
  // Content Hub is the public-sharing surface; posting / browsing
  // private groups requires the buddy persona to exist. Public
  // landing reads are still open to onboarded-or-not via the page's
  // own guest-empty state, but the gate itself only fires here.
  return pathname.startsWith("/content-hub");
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
  // Soft gate: only block paths that genuinely need a buddy persona.
  if (!requiresOnboarding(pathname)) return false;
  return true;
}
