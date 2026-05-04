import { describe, expect, it } from "vitest";
import { shouldRedirectToOnboarding } from "./requireOnboarded";

describe("shouldRedirectToOnboarding", () => {
  it("does NOT redirect anonymous users", () => {
    expect(
      shouldRedirectToOnboarding({
        isAuthenticated: false,
        onboardedAt: null,
        pathname: "/library",
      }),
    ).toBe(false);
  });

  it("does NOT redirect users who have already onboarded", () => {
    expect(
      shouldRedirectToOnboarding({
        isAuthenticated: true,
        onboardedAt: "2026-01-01T00:00:00",
        pathname: "/library",
      }),
    ).toBe(false);
  });

  it("redirects authenticated, not-yet-onboarded users on a guarded path", () => {
    expect(
      shouldRedirectToOnboarding({
        isAuthenticated: true,
        onboardedAt: null,
        pathname: "/library",
      }),
    ).toBe(true);
  });

  it("does NOT redirect when already on /my-agent (avoids loops)", () => {
    expect(
      shouldRedirectToOnboarding({
        isAuthenticated: true,
        onboardedAt: null,
        pathname: "/my-agent",
      }),
    ).toBe(false);
  });

  it("does NOT redirect on /login or /register so the user can sign in / out", () => {
    expect(
      shouldRedirectToOnboarding({
        isAuthenticated: true,
        onboardedAt: null,
        pathname: "/login",
      }),
    ).toBe(false);
    expect(
      shouldRedirectToOnboarding({
        isAuthenticated: true,
        onboardedAt: null,
        pathname: "/register",
      }),
    ).toBe(false);
  });

  it("treats undefined onboardedAt the same as null (fresh user)", () => {
    expect(
      shouldRedirectToOnboarding({
        isAuthenticated: true,
        onboardedAt: undefined,
        pathname: "/upload",
      }),
    ).toBe(true);
  });
});
