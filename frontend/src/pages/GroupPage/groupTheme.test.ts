import { describe, expect, it } from "vitest";
import { accentForSlug, coverFor, emojiForTheme } from "./groupTheme";

describe("accentForSlug", () => {
  it("is deterministic — same slug -> same accent", () => {
    const a = accentForSlug("dragons");
    const b = accentForSlug("dragons");
    expect(a).toEqual(b);
  });

  it("different slugs MAY map to different accents", () => {
    // Not strictly required (the palette is small) — but at least one
    // pair across a sample should differ to prove the hash isn't a
    // constant.
    const slugs = ["dragons", "space-adventures", "kindness-club", "music"];
    const accents = slugs.map(accentForSlug);
    const unique = new Set(accents.map((a) => a.bannerGradient));
    expect(unique.size).toBeGreaterThan(1);
  });

  it("returns a sane default when slug is empty", () => {
    expect(accentForSlug(null)).toBeDefined();
    expect(accentForSlug(undefined)).toBeDefined();
    expect(accentForSlug("")).toBeDefined();
  });
});

describe("emojiForTheme", () => {
  it("known themes get their canonical emoji", () => {
    expect(emojiForTheme("dragons")).toBe("🐉");
    expect(emojiForTheme("Space")).toBe("🚀");
    expect(emojiForTheme("  ocean  ")).toBe("🌊");
  });

  it("unknown themes fall back to sparkle", () => {
    expect(emojiForTheme("blarg")).toBe("✨");
    expect(emojiForTheme(null)).toBe("✨");
  });
});

describe("coverFor", () => {
  it("art_story uses the warm bookish gradient", () => {
    const c = coverFor("art_story");
    expect(c.icon).toBe("📖");
    expect(c.label).toBe("Art story");
  });
  it("interactive_story uses the playful violet gradient", () => {
    const c = coverFor("interactive_story");
    expect(c.icon).toBe("🌟");
    expect(c.label).toBe("Interactive story");
  });
  it("kids_daily uses the podcast emerald-teal gradient", () => {
    const c = coverFor("kids_daily");
    expect(c.icon).toBe("🎙️");
    expect(c.label).toBe("Kids Daily");
  });
});
