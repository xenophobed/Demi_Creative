/* @vitest-environment node */

import { describe, expect, it } from "vitest";
import { getAchievementAgeCopy } from ".";

describe("getAchievementAgeCopy", () => {
  it("uses visual-first copy for youngest children", () => {
    const copy = getAchievementAgeCopy("3-5");

    expect(copy.title).toBe("My Badges");
    expect(copy.empty).toContain("picture badges");
    expect(copy.progress).toBe("creative moments");
  });

  it("uses simple badge progress for 6-8 children", () => {
    const copy = getAchievementAgeCopy("6-8");

    expect(copy.title).toBe("Achievement Badges");
    expect(copy.empty).toContain("stories");
    expect(copy.progress).toBe("badges earned");
  });

  it("uses milestone copy for older children without ranking pressure", () => {
    const copy = getAchievementAgeCopy("9-12");
    const combined = Object.values(copy).join(" ").toLowerCase();

    expect(copy.title).toBe("Creative Milestones");
    expect(copy.progress).toBe("milestones unlocked");
    expect(combined).not.toContain("leaderboard");
    expect(combined).not.toContain("ranking");
    expect(combined).not.toContain("streak");
  });
});
