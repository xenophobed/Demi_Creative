import { describe, expect, it } from "vitest";

import { shouldUseFallbackMemory } from "@/hooks/useMemoryApi";

/**
 * The memory fallback must never override an explicitly-selected child that
 * has its own data. It may only borrow the resolved primary child's memory
 * when the selected child has none. (#747)
 */
describe("shouldUseFallbackMemory", () => {
  it("does NOT override a selected child that has its own data", () => {
    // Diana selected (score 15) vs higher-activity Demi (score 25).
    expect(shouldUseFallbackMemory(true, 15, 25)).toBe(false);
  });

  it("falls back when the selected child has no memory but the primary does", () => {
    expect(shouldUseFallbackMemory(true, 0, 25)).toBe(true);
  });

  it("does not fall back when there is no fallback child", () => {
    expect(shouldUseFallbackMemory(false, 0, 25)).toBe(false);
  });

  it("does not fall back when both children are empty", () => {
    expect(shouldUseFallbackMemory(true, 0, 0)).toBe(false);
  });

  it("does not fall back when the selected child has data even if primary is empty", () => {
    expect(shouldUseFallbackMemory(true, 10, 0)).toBe(false);
  });
});
