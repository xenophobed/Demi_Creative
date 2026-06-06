/**
 * Pure helpers for BuddyOrb (#651).
 *
 * Extracted so reducer-state-to-mode mapping, age-adapted sizing,
 * color palette, and the audio-reactive scale formula can all be unit-
 * tested without rendering React. Same separation pattern as
 * talkToBuddyHelpers (#618) and CameraCapture helpers (#581).
 *
 * Design rationale:
 *   - Mode is the full 8-state reducer enum (plus "static") so each
 *     reducer state has a distinct visual pattern. The previous
 *     `pickIndicator` (#618) only had 3 variants, which is why kids
 *     couldn't tell "thinking" from "listening". This is the #651 win.
 *   - Error palette is AMBER, not red — research flag from the 2026-06
 *     synthesis: red faces/colors scare children and read as "punishment".
 *   - `breathFactor` is a pure sin-based formula so the audio-frame
 *     callback in BuddyOrb can call it 60Hz without recomputing state.
 */
import type { VoiceConversationState } from "@/hooks/voiceConversationStateMachine";

/**
 * Distinct visual modes for the orb. Mirrors the reducer enum but
 * adds `"static"` as the reduced-motion fallback so the BuddyOrb's
 * animation loop has a single sentinel to check.
 */
export type OrbMode =
  | "idle"
  | "connecting"
  | "listening"
  | "thinking"
  | "speaking"
  | "interrupted"
  | "ending"
  | "error"
  | "static";

/**
 * Map the reducer state to the orb's visual mode.
 *
 * Reduced-motion users always get `"idle"` (a calm static gradient).
 * The terminal `"unsupported"` state also collapses to `"static"` — the
 * panel never mounts in that state but we still want a defined return.
 */
export function pickOrbMode(
  state: VoiceConversationState,
  prefersReducedMotion: boolean,
): OrbMode {
  if (prefersReducedMotion) return "idle";
  if (state === "unsupported") return "static";
  // Every other reducer state maps 1:1 to the orb mode of the same name.
  return state;
}

/**
 * Age-adapted orb diameter in pixels.
 *
 * 3-5 → 220 (orb is the hero; transcript is secondary)
 * 6-8 → 180 (balanced)
 * 9-12 → 140 (transcript is the hero; orb is a comfort indicator)
 *
 * Defaults to 180 when age is unknown — safe middle ground that won't
 * dominate the layout for an unknown reader yet stays readable.
 */
export function orbDiameterForAge(age?: number | null): number {
  if (age == null) return 180;
  if (age < 6) return 220;
  if (age < 9) return 180;
  return 140;
}

/**
 * Tailwind class strings for the orb's core gradient and outer halo.
 *
 * Error uses AMBER (warm warning) instead of red (research flag: red
 * scares kids and reads as punishment). Idle/connecting share a calm
 * indigo so the transition into listening (green) feels like waking up.
 */
export function orbColorForMode(mode: OrbMode): {
  core: string;
  halo: string;
} {
  switch (mode) {
    case "listening":
      // Mic-active: warm green. Same hue as the existing pulse-listening
      // pill so returning users recognize the signal.
      return {
        core: "bg-gradient-to-br from-emerald-300 via-emerald-400 to-emerald-500",
        halo: "bg-emerald-400",
      };
    case "thinking":
      // Buddy-thinking: cool sky-blue. Visually distinct from speaking
      // (violet) and listening (green) — the "I'm processing" beat.
      return {
        core: "bg-gradient-to-br from-sky-300 via-sky-400 to-indigo-500",
        halo: "bg-sky-400",
      };
    case "speaking":
      // Buddy-talking: violet (matches existing pulse-speaking).
      return {
        core: "bg-gradient-to-br from-violet-300 via-violet-400 to-violet-600",
        halo: "bg-violet-400",
      };
    case "interrupted":
      // Brief flash back toward listening — same green but with a
      // shorter motion so the panel doesn't feel like it skipped a state.
      return {
        core: "bg-gradient-to-br from-emerald-200 via-emerald-400 to-violet-400",
        halo: "bg-emerald-300",
      };
    case "ending":
      // Fading farewell: dusk pink/orange. Distinct from idle so the
      // user sees the exhale.
      return {
        core: "bg-gradient-to-br from-rose-200 via-rose-300 to-amber-200",
        halo: "bg-rose-300",
      };
    case "error":
      // AMBER — friendly warning, NOT red.
      return {
        core: "bg-gradient-to-br from-amber-200 via-amber-300 to-amber-500",
        halo: "bg-amber-400",
      };
    case "connecting":
      // Same indigo as idle but slightly brighter to signal "warming up".
      return {
        core: "bg-gradient-to-br from-indigo-300 via-indigo-400 to-violet-400",
        halo: "bg-indigo-400",
      };
    case "static":
    case "idle":
    default:
      // Calm resting indigo — the orb at rest.
      return {
        core: "bg-gradient-to-br from-indigo-200 via-indigo-300 to-violet-300",
        halo: "bg-indigo-300",
      };
  }
}

/**
 * Audio-reactive scale factor for the orb.
 *
 * Returns a multiplier in [0.9, 1.5] so the orb breathes around 1.0x.
 * Pure: same (t, mode, level) → same factor. Safe to call inside
 * `useAnimationFrame` at 60Hz with no allocations.
 *
 * - `static` mode pins at 1.0 (reduced-motion contract).
 * - `idle`/`connecting` get a slow 0.2 Hz heartbeat even when level=0
 *   so the orb never looks frozen (acceptance criterion).
 * - `listening`/`speaking` blend the heartbeat with a level-driven
 *   boost capped at +0.4 so loud peaks don't shake the layout.
 * - `interrupted` is a quick pop centered ~120ms (covered by the spring
 *   animation in BuddyOrb; the scale formula stays gentle).
 */
export function breathFactor(t: number, mode: OrbMode, level: number): number {
  if (mode === "static") return 1.0;

  // Base heartbeat: 0.2 Hz when calm, slightly faster when active.
  const calmFreq = 0.2; // hz
  const activeFreq = 0.5; // hz
  const isActive =
    mode === "listening" ||
    mode === "speaking" ||
    mode === "thinking" ||
    mode === "interrupted";
  const freq = isActive ? activeFreq : calmFreq;

  // 2π * f * t/1000 — t is ms from useAnimationFrame.
  const phase = (2 * Math.PI * freq * t) / 1000;
  const baseAmp = 0.05; // ±5% breathing baseline
  const base = 1.0 + baseAmp * Math.sin(phase);

  // Level-reactive boost only for the audio-active modes.
  let boost = 0;
  const safeLevel = Math.max(0, Math.min(1, level));
  if (mode === "listening" || mode === "speaking") {
    // Cap at +0.4 so the orb scales in [~0.95, 1.45].
    boost = 0.4 * safeLevel;
  } else if (mode === "interrupted") {
    // Slight extra emphasis when interrupted but no audio yet.
    boost = 0.1;
  }

  // Clamp the final factor into the documented [0.9, 1.5] range so
  // callers — and tests — can rely on the bound regardless of inputs.
  const raw = base + boost;
  return Math.max(0.9, Math.min(1.5, raw));
}
