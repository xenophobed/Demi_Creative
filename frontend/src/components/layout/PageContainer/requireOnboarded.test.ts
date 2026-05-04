import { describe, expect, it } from "vitest";
import { shouldRedirectToOnboarding } from "./requireOnboarded";

describe("shouldRedirectToOnboarding (soft gate per PRD §3.11.2)", () => {
  it("does NOT redirect anonymous users", () => {
    expect(
      shouldRedirectToOnboarding({
        isAuthenticated: false,
        onboardedAt: null,
        pathname: "/content-hub",
      }),
    ).toBe(false);
  });

  it("does NOT redirect users who have already onboarded", () => {
    expect(
      shouldRedirectToOnboarding({
        isAuthenticated: true,
        onboardedAt: "2026-01-01T00:00:00",
        pathname: "/content-hub",
      }),
    ).toBe(false);
  });

  it("redirects only when an authenticated, not-yet-onboarded user hits Content Hub", () => {
    expect(
      shouldRedirectToOnboarding({
        isAuthenticated: true,
        onboardedAt: null,
        pathname: "/content-hub",
      }),
    ).toBe(true);
    expect(
      shouldRedirectToOnboarding({
        isAuthenticated: true,
        onboardedAt: null,
        pathname: "/content-hub/dragons",
      }),
    ).toBe(true);
  });

  it("does NOT redirect on Library, Upload, Story, Interactive, Profile, Kids Daily, Home", () => {
    const openPaths = [
      "/library",
      "/upload",
      "/story/abc",
      "/interactive",
      "/profile",
      "/kids-daily",
      "/kids-daily/episode-1",
      "/",
    ];
    for (const p of openPaths) {
      expect(
        shouldRedirectToOnboarding({
          isAuthenticated: true,
          onboardedAt: null,
          pathname: p,
        }),
      ).toBe(false);
    }
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

  it("does NOT redirect on /login or /register", () => {
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
        pathname: "/content-hub",
      }),
    ).toBe(true);
  });
});
