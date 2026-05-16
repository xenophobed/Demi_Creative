import { describe, expect, it } from "vitest";
import {
  AUTO_NAME_SUGGESTIONS,
  shouldAutoOpenOnboarding,
  stepsForAge,
} from "./onboardingState";

describe("shouldAutoOpenOnboarding", () => {
  it("does NOT open for anonymous users", () => {
    expect(
      shouldAutoOpenOnboarding({
        isAuthenticated: false,
        onboardedAt: null,
        hasExistingAgent: false,
      }),
    ).toBe(false);
  });
  it("does NOT open if onboardedAt is set", () => {
    expect(
      shouldAutoOpenOnboarding({
        isAuthenticated: true,
        onboardedAt: "2026-01-01T00:00:00",
        hasExistingAgent: true,
      }),
    ).toBe(false);
  });
  it("opens when authenticated + not onboarded yet (no agent)", () => {
    expect(
      shouldAutoOpenOnboarding({
        isAuthenticated: true,
        onboardedAt: null,
        hasExistingAgent: false,
      }),
    ).toBe(true);
  });
  it("does NOT open when an agent already exists, even if consent hasn't been recorded", () => {
    // #510 follow-up: stacking the modal on top of the live chat panel
    // looks broken. Treat a saved buddy as implicit consent and let the
    // user chat; the persona editor below the chat still lets them
    // tweak the buddy without re-onboarding.
    expect(
      shouldAutoOpenOnboarding({
        isAuthenticated: true,
        onboardedAt: undefined,
        hasExistingAgent: true,
      }),
    ).toBe(false);
  });
});

describe("stepsForAge", () => {
  it("3-5 gets a stripped flow without name/title steps", () => {
    expect(stepsForAge("3-5")).toEqual(["greeting", "avatar", "consent"]);
  });
  it("6-8 gets the full flow", () => {
    expect(stepsForAge("6-8")).toEqual([
      "greeting",
      "name",
      "avatar",
      "title",
      "consent",
    ]);
  });
  it("9-12 gets the full flow", () => {
    expect(stepsForAge("9-12")).toEqual([
      "greeting",
      "name",
      "avatar",
      "title",
      "consent",
    ]);
  });
  it("undefined age falls back to the full flow", () => {
    expect(stepsForAge(undefined)).toEqual([
      "greeting",
      "name",
      "avatar",
      "title",
      "consent",
    ]);
  });
});

describe("AUTO_NAME_SUGGESTIONS", () => {
  it("has at least 4 entries with no duplicates", () => {
    expect(AUTO_NAME_SUGGESTIONS.length).toBeGreaterThanOrEqual(4);
    const seen = new Set(AUTO_NAME_SUGGESTIONS);
    expect(seen.size).toBe(AUTO_NAME_SUGGESTIONS.length);
  });
});
