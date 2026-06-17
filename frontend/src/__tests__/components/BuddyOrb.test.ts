/**
 * Component-level contract tests for BuddyOrb (#651).
 *
 * We follow the no-render contract from #635: only exported
 * class-string maps and computed-style helpers are tested here, never
 * the React tree. Keeping component tests DOM-less avoids pulling in
 * @testing-library/react as a dependency and keeps CI fast.
 */
import { describe, expect, it } from "vitest";
import {
  ORB_FACE_AGE_CEILING,
  shouldRenderFace,
  computeOrbInlineStyle,
} from "@/pages/MyAgentPage/BuddyOrb";

describe("BuddyOrb age-gating contract (#651)", () => {
  it("renders the face overlay for pre-readers under the age ceiling", () => {
    expect(shouldRenderFace(3)).toBe(true);
    expect(shouldRenderFace(5)).toBe(true);
    expect(shouldRenderFace(ORB_FACE_AGE_CEILING - 1)).toBe(true);
  });

  it("hides the face for readers at or above the age ceiling", () => {
    expect(shouldRenderFace(ORB_FACE_AGE_CEILING)).toBe(false);
    expect(shouldRenderFace(7)).toBe(false);
    expect(shouldRenderFace(12)).toBe(false);
  });

  it("hides the face when age is missing (defensive default)", () => {
    expect(shouldRenderFace(null)).toBe(false);
    expect(shouldRenderFace(undefined)).toBe(false);
  });

  it("documents 6 as the cutoff (pre-reader vs reader boundary)", () => {
    // Lock the magic number so a future refactor surfaces in code review.
    expect(ORB_FACE_AGE_CEILING).toBe(6);
  });
});

describe("BuddyOrb inline style contract (#651)", () => {
  it("sets width and height to the exact diameter (locks the box for layout)", () => {
    const style = computeOrbInlineStyle(180);
    expect(style.width).toBe(180);
    expect(style.height).toBe(180);
  });

  it("scales proportionally for the pre-reader hero size", () => {
    const style = computeOrbInlineStyle(220);
    expect(style.width).toBe(style.height);
  });
});
