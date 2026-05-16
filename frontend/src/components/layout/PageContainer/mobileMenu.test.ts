import { describe, expect, it } from "vitest";
import { closeMenu, openMenu, toggleMenu } from "./mobileMenu";

/**
 * The mobile hamburger drawer (issue #427) hides itself on link clicks
 * and backdrop taps. Both paths funnel through `closeMenu`, the hamburger
 * button calls `toggleMenu`, and any future "force open" callsite uses
 * `openMenu`. Lock these contracts so a refactor can't quietly invert
 * the drawer (which would trap mobile users on a partially-opened nav).
 */
describe("mobileMenu state transitions", () => {
  it("openMenu always returns true", () => {
    expect(openMenu()).toBe(true);
  });

  it("closeMenu always returns false (used by link click + backdrop tap)", () => {
    expect(closeMenu()).toBe(false);
  });

  it("toggleMenu flips false -> true (hamburger button: closed -> open)", () => {
    expect(toggleMenu(false)).toBe(true);
  });

  it("toggleMenu flips true -> false (hamburger button: open -> closed)", () => {
    expect(toggleMenu(true)).toBe(false);
  });

  it("toggleMenu twice is identity (idempotent double-tap)", () => {
    expect(toggleMenu(toggleMenu(false))).toBe(false);
    expect(toggleMenu(toggleMenu(true))).toBe(true);
  });
});
