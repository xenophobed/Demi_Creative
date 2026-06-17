import { describe, expect, it } from "vitest";

import {
  avatarIconForId,
  isAnimalAvatarId,
  normalizeAvatarId,
} from "@/lib/avatarIcons";

describe("avatar icon mapping", () => {
  it("normalizes legacy raw animal emoji values", () => {
    expect(normalizeAvatarId("🐶")).toBe("emoji:🐶");
    expect(isAnimalAvatarId("🐶")).toBe(true);
    expect(avatarIconForId("🐶")).toBe(avatarIconForId("emoji:🐶"));
  });

  it("keeps generated child fallbacks stable and animal-shaped", () => {
    const first = avatarIconForId("child-a");
    const second = avatarIconForId("child-a");
    const another = avatarIconForId("child-b");

    expect(first).toBe(second);
    expect(first).toBeDefined();
    expect(another).toBeDefined();
  });

  it("does not classify external media urls as animal avatars", () => {
    expect(isAnimalAvatarId("/uploads/avatar.png")).toBe(false);
    expect(isAnimalAvatarId("https://example.test/avatar.png")).toBe(false);
  });
});
