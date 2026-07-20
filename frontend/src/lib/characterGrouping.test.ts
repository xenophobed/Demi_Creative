import { describe, expect, it } from "vitest";
import { splitByAppearanceFrequency } from "@/lib/characterGrouping";
import type { MemoryCharacter } from "@/types/api";

const character = (name: string, appearance_count: number): MemoryCharacter => ({
  name,
  description: `${name} description`,
  visual_features: null,
  traits: null,
  appearance_count,
  main_story_count: 0,
  character_role: "other",
  first_seen_at: "2026-01-01T00:00:00Z",
  last_seen_at: "2026-01-01T00:00:00Z",
});

describe("splitByAppearanceFrequency", () => {
  it("keeps the most frequent character as main for a small cast", () => {
    const result = splitByAppearanceFrequency([
      character("Pip", 1),
      character("Star", 3),
    ]);

    expect(result.main.map(({ name }) => name)).toEqual(["Star"]);
    expect(result.other.map(({ name }) => name)).toEqual(["Pip"]);
  });

  it("keeps tied top characters together", () => {
    const result = splitByAppearanceFrequency([
      character("Pip", 2),
      character("Star", 2),
      character("Nova", 1),
    ]);

    expect(result.main.map(({ name }) => name)).toEqual(["Pip", "Star"]);
    expect(result.other.map(({ name }) => name)).toEqual(["Nova"]);
  });
});
