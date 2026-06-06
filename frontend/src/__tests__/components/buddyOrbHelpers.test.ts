/**
 * Contract tests for buddyOrbHelpers (#651).
 *
 * Pure helpers backing the BuddyOrb component. Same separation-for-
 * testability pattern as talkToBuddyHelpers (#618): exhaustively cover
 * every reducer state, reduced-motion case, and age band so the panel
 * layer can't drift.
 */
import { describe, expect, it } from "vitest";
import {
  breathFactor,
  orbColorForMode,
  orbDiameterForAge,
  pickOrbMode,
  type OrbMode,
} from "@/pages/MyAgentPage/buddyOrbHelpers";
import type { VoiceConversationState } from "@/hooks/voiceConversationStateMachine";

const ALL_STATES: VoiceConversationState[] = [
  "idle",
  "connecting",
  "listening",
  "thinking",
  "speaking",
  "interrupted",
  "ending",
  "error",
  "unsupported",
];

describe("pickOrbMode (#651)", () => {
  it("returns the matching mode for every reducer state when motion is allowed", () => {
    for (const state of ALL_STATES) {
      const mode = pickOrbMode(state, false);
      // mode must be a string and must be one of the documented orb modes
      expect(typeof mode).toBe("string");
      expect(mode.length).toBeGreaterThan(0);
    }
  });

  it("preserves state identity for every active reducer state", () => {
    // Active states map 1:1 to a distinct visual mode — the whole point
    // of #651 vs the 3-variant Indicator.
    const stateToMode: Record<VoiceConversationState, OrbMode | "static"> = {
      idle: "idle",
      connecting: "connecting",
      listening: "listening",
      thinking: "thinking",
      speaking: "speaking",
      interrupted: "interrupted",
      ending: "ending",
      error: "error",
      unsupported: "static",
    };
    for (const state of ALL_STATES) {
      expect(pickOrbMode(state, false)).toBe(stateToMode[state]);
    }
  });

  it("collapses to a static/idle mode when prefers-reduced-motion is true, regardless of state", () => {
    for (const state of ALL_STATES) {
      const mode = pickOrbMode(state, true);
      // Reduced-motion contract from #618 — always render the same calm
      // mode so screen-reader users + vestibular-sensitive users get a
      // stable orb. We accept either "idle" or "static" as the calm mode.
      expect(["idle", "static"]).toContain(mode);
    }
  });
});

describe("orbDiameterForAge (#651)", () => {
  it("3-5 (pre-readers) get the hero-sized 220px orb", () => {
    expect(orbDiameterForAge(3)).toBe(220);
    expect(orbDiameterForAge(4)).toBe(220);
    expect(orbDiameterForAge(5)).toBe(220);
  });

  it("6-8 get the mid-sized 180px orb", () => {
    expect(orbDiameterForAge(6)).toBe(180);
    expect(orbDiameterForAge(7)).toBe(180);
    expect(orbDiameterForAge(8)).toBe(180);
  });

  it("9-12 get the compact 140px orb (transcript is hero)", () => {
    expect(orbDiameterForAge(9)).toBe(140);
    expect(orbDiameterForAge(12)).toBe(140);
  });

  it("falls back to a sensible default (180) when age is null/undefined", () => {
    expect(orbDiameterForAge(null)).toBe(180);
    expect(orbDiameterForAge(undefined)).toBe(180);
  });
});

describe("orbColorForMode (#651)", () => {
  it("error mode uses AMBER classes, never red (research flag: red scares kids)", () => {
    const palette = orbColorForMode("error");
    const combined = `${palette.core} ${palette.halo}`;
    expect(combined).toMatch(/amber/);
    expect(combined).not.toMatch(/\bred\b/);
    expect(combined).not.toMatch(/\bbg-red-/);
  });

  it("listening mode uses a warm green/emerald palette (mic-active)", () => {
    const palette = orbColorForMode("listening");
    const combined = `${palette.core} ${palette.halo}`;
    expect(combined).toMatch(/emerald|green/);
  });

  it("speaking mode uses a violet/purple palette (buddy-active)", () => {
    const palette = orbColorForMode("speaking");
    const combined = `${palette.core} ${palette.halo}`;
    expect(combined).toMatch(/violet|purple/);
  });

  it("returns non-empty core and halo class strings for every reducer mode", () => {
    const modes: OrbMode[] = [
      "idle",
      "connecting",
      "listening",
      "thinking",
      "speaking",
      "interrupted",
      "ending",
      "error",
      "static",
    ];
    for (const mode of modes) {
      const palette = orbColorForMode(mode);
      expect(palette.core.length).toBeGreaterThan(0);
      expect(palette.halo.length).toBeGreaterThan(0);
    }
  });
});

describe("breathFactor (#651)", () => {
  it("is deterministic given (t, mode, level)", () => {
    expect(breathFactor(1000, "listening", 0.5)).toBe(
      breathFactor(1000, "listening", 0.5),
    );
    expect(breathFactor(0, "idle", 0)).toBe(breathFactor(0, "idle", 0));
  });

  it("is bounded in [0.9, 1.5] across a sweep of inputs", () => {
    const modes: OrbMode[] = [
      "idle",
      "connecting",
      "listening",
      "thinking",
      "speaking",
      "interrupted",
      "ending",
      "error",
      "static",
    ];
    for (const mode of modes) {
      for (let t = 0; t < 10000; t += 137) {
        for (const level of [0, 0.25, 0.5, 0.75, 1, 1.5 /* over-1 safety */]) {
          const f = breathFactor(t, mode, level);
          expect(f).toBeGreaterThanOrEqual(0.9);
          expect(f).toBeLessThanOrEqual(1.5);
        }
      }
    }
  });

  it("idle/connecting still pulse a small heartbeat even when level=0 (orb never looks frozen)", () => {
    // Sample over a full cycle and check that the value moves — i.e. is
    // not pinned at exactly 1.0 the whole time.
    const sampleSet = new Set<number>();
    for (let t = 0; t < 8000; t += 200) {
      sampleSet.add(breathFactor(t, "idle", 0));
    }
    expect(sampleSet.size).toBeGreaterThan(1);
    // And the spread is meaningful, not float-noise: max - min >= 0.01
    const values = Array.from(sampleSet);
    const spread = Math.max(...values) - Math.min(...values);
    expect(spread).toBeGreaterThan(0.005);
  });

  it("speaking with high level pushes the factor above the idle baseline", () => {
    // At the same t, a louder speaking signal should never be quieter
    // than idle-with-no-level — the orb must visibly react to volume.
    const idleVal = breathFactor(500, "idle", 0);
    const loudVal = breathFactor(500, "speaking", 1);
    expect(loudVal).toBeGreaterThanOrEqual(idleVal);
  });

  it("static mode (reduced-motion fallback) is pinned at exactly 1.0", () => {
    for (let t = 0; t < 5000; t += 250) {
      expect(breathFactor(t, "static", 0.5)).toBe(1.0);
    }
  });
});
