/**
 * Logic-only tests for the curated titles list and the age-gating helper.
 * No DOM rendering — `@testing-library/react` is intentionally not a
 * dependency in this project, so we keep these to pure logic.
 */
import { describe, expect, it } from "vitest";
import { CURATED_TITLES, customTitleAllowed } from "./agentTitles";

describe("CURATED_TITLES", () => {
  it("is exactly 20 entries — locked by PRD §3.11.3", () => {
    expect(CURATED_TITLES.length).toBe(20);
  });

  it("has no duplicates", () => {
    const seen = new Set<string>();
    for (const t of CURATED_TITLES) {
      expect(seen.has(t)).toBe(false);
      seen.add(t);
    }
  });

  it("starts with 'Story Wizard' (matches backend order)", () => {
    expect(CURATED_TITLES[0]).toBe("Story Wizard");
  });
});

describe("customTitleAllowed", () => {
  it("returns true only for 9-12", () => {
    expect(customTitleAllowed("9-12")).toBe(true);
  });
  it("returns false for younger tiers", () => {
    expect(customTitleAllowed("3-5")).toBe(false);
    expect(customTitleAllowed("6-8")).toBe(false);
  });
  it("returns false when age is unknown", () => {
    expect(customTitleAllowed(undefined)).toBe(false);
    expect(customTitleAllowed(null)).toBe(false);
  });
});
