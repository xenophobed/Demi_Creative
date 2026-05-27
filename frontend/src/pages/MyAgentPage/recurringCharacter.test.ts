import { describe, it, expect } from "vitest";

import {
  chipPrefillForCharacter,
  pickRecurringCharacter,
} from "./recurringCharacter";
import type { MemoryCharacter } from "@/types/api";

function mkChar(overrides: Partial<MemoryCharacter>): MemoryCharacter {
  return {
    name: "Sparkle",
    description: null,
    visual_features: null,
    traits: null,
    appearance_count: 2,
    first_seen_at: "2026-01-01T00:00:00",
    last_seen_at: "2026-01-02T00:00:00",
    ...overrides,
  };
}

describe("pickRecurringCharacter", () => {
  it("returns null when the input is null or empty", () => {
    expect(pickRecurringCharacter(null)).toBeNull();
    expect(pickRecurringCharacter(undefined)).toBeNull();
    expect(pickRecurringCharacter([])).toBeNull();
  });

  it("returns null when no character has appeared at least twice", () => {
    expect(
      pickRecurringCharacter([
        mkChar({ name: "Lightning", appearance_count: 1 }),
        mkChar({ name: "Comet", appearance_count: 1 }),
      ]),
    ).toBeNull();
  });

  it("picks the character with the highest appearance_count", () => {
    const winner = pickRecurringCharacter([
      mkChar({ name: "Sparkle", appearance_count: 2 }),
      mkChar({ name: "Lightning", appearance_count: 5 }),
      mkChar({ name: "Comet", appearance_count: 3 }),
    ]);
    expect(winner?.name).toBe("Lightning");
  });

  it("breaks count ties by most-recent last_seen_at", () => {
    const winner = pickRecurringCharacter([
      mkChar({
        name: "Sparkle",
        appearance_count: 4,
        last_seen_at: "2026-01-01T00:00:00",
      }),
      mkChar({
        name: "Lightning",
        appearance_count: 4,
        last_seen_at: "2026-03-01T00:00:00",
      }),
    ]);
    expect(winner?.name).toBe("Lightning");
  });

  it("skips characters with empty names even when count is high", () => {
    const winner = pickRecurringCharacter([
      mkChar({ name: "", appearance_count: 10 }),
      mkChar({ name: "Sparkle", appearance_count: 2 }),
    ]);
    expect(winner?.name).toBe("Sparkle");
  });

  it("respects the 2-appearance floor exactly (>= 2)", () => {
    expect(
      pickRecurringCharacter([mkChar({ appearance_count: 2 })])?.name,
    ).toBe("Sparkle");
    expect(
      pickRecurringCharacter([mkChar({ appearance_count: 1 })]),
    ).toBeNull();
  });
});

describe("chipPrefillForCharacter", () => {
  it("composes a clear, child-friendly opener", () => {
    expect(chipPrefillForCharacter("Sparkle the Brave Lion")).toBe(
      "Tell me more about Sparkle the Brave Lion",
    );
  });
});
