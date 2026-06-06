/**
 * TalkToBuddyPanel variant contract tests (#635).
 *
 * The panel itself doesn't have a render test (no @testing-library/react
 * in deps — same constraint that's held since #581). What we CAN lock
 * down without a DOM is the exported PANEL_WRAPPER_CLASS map: it
 * encodes the load-bearing CSS difference between `overlay` and
 * `inline`. If a future contributor accidentally drops `fixed inset-0`
 * from overlay (regression toward inline behavior) or adds it to
 * inline (regression toward overlay), this test fails.
 */

import { describe, expect, it } from "vitest";
import {
  PANEL_WRAPPER_CLASS,
  type TalkToBuddyPanelVariant,
} from "@/pages/MyAgentPage/TalkToBuddyPanel";

describe("TalkToBuddyPanel: PANEL_WRAPPER_CLASS (#635)", () => {
  it("exports a class string for both variants", () => {
    const variants: TalkToBuddyPanelVariant[] = ["overlay", "inline"];
    for (const variant of variants) {
      expect(typeof PANEL_WRAPPER_CLASS[variant]).toBe("string");
      expect(PANEL_WRAPPER_CLASS[variant].length).toBeGreaterThan(10);
    }
  });

  it("overlay variant pins to viewport (fixed inset-0)", () => {
    // The full-screen sheet on mobile + floating panel on desktop both
    // require fixed positioning. If anyone drops this, overlay collapses
    // into inline-by-accident.
    expect(PANEL_WRAPPER_CLASS.overlay).toContain("fixed");
    expect(PANEL_WRAPPER_CLASS.overlay).toContain("inset-0");
    expect(PANEL_WRAPPER_CLASS.overlay).toContain("z-40");
  });

  it("inline variant does NOT use fixed positioning", () => {
    // The whole point of the inline variant is that it sits inside
    // AgentChatPanel's flex column. fixed/inset/z-* in this map would
    // break the in-place swap.
    expect(PANEL_WRAPPER_CLASS.inline).not.toContain("fixed");
    expect(PANEL_WRAPPER_CLASS.inline).not.toContain("inset-0");
    expect(PANEL_WRAPPER_CLASS.inline).not.toContain("z-40");
    expect(PANEL_WRAPPER_CLASS.inline).not.toContain("shadow-2xl");
  });

  it("inline variant declares itself as a flex column for composer-slot fit", () => {
    // The composer slot is a vertical region; the inline variant must
    // stack header → body → footer like the overlay does, just without
    // the chrome.
    expect(PANEL_WRAPPER_CLASS.inline).toContain("flex");
    expect(PANEL_WRAPPER_CLASS.inline).toContain("flex-col");
  });

  it("both variants share NO conflicting positioning classes", () => {
    // Sanity: there's no class that means both "stays in flow" and
    // "leaves the flow" at the same time.
    const overlayHasFixed = PANEL_WRAPPER_CLASS.overlay.includes("fixed");
    const inlineHasFixed = PANEL_WRAPPER_CLASS.inline.includes("fixed");
    expect(overlayHasFixed && inlineHasFixed).toBe(false);
  });
});
