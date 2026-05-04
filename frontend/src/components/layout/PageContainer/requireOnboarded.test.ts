import { describe, expect, it } from "vitest";
import { shouldRedirectToOnboarding } from "./requireOnboarded";

/**
 * Per PRD §3.11.2 onboarding is a soft gate. The route-level helper
 * never redirects; per-action affordances inside Content Hub and the
 * Share-to-Hub modal do the actual gating.
 *
 * These cases lock that contract so a future regression that re-enables
 * the redirect (e.g. by adding paths back) flips the test red.
 */
describe("shouldRedirectToOnboarding (soft gate, no route redirect)", () => {
  const matrix = [
    { isAuthenticated: false, onboardedAt: null, pathname: "/content-hub" },
    { isAuthenticated: true, onboardedAt: null, pathname: "/content-hub" },
    {
      isAuthenticated: true,
      onboardedAt: null,
      pathname: "/content-hub/dragons",
    },
    {
      isAuthenticated: true,
      onboardedAt: "2026-01-01T00:00:00",
      pathname: "/content-hub",
    },
    { isAuthenticated: true, onboardedAt: null, pathname: "/library" },
    { isAuthenticated: true, onboardedAt: null, pathname: "/upload" },
    { isAuthenticated: true, onboardedAt: null, pathname: "/my-agent" },
    { isAuthenticated: true, onboardedAt: null, pathname: "/login" },
  ];

  for (const input of matrix) {
    it(`does NOT redirect: ${JSON.stringify(input)}`, () => {
      expect(shouldRedirectToOnboarding(input)).toBe(false);
    });
  }
});
