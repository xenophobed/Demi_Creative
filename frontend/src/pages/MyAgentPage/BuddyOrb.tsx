/**
 * BuddyOrb (#651) — audio-reactive voice UI replacing the flat dot
 * indicator from #618.
 *
 * Every reducer state gets a visually distinct motion pattern. Driven
 * by BOTH `inputLevel` (mic RMS) and `outputLevel` (assistant TTS RMS)
 * so the orb feels alive whether the kid or the buddy is talking.
 *
 * Performance contract:
 *   - Scale is a `useMotionValue` written from `useAnimationFrame`. NO
 *     React `setState` per frame — that's the 60Hz perf trap.
 *   - All overlays (rings, orbiting dots) use Framer's declarative
 *     animation so they animate via the compositor, not React renders.
 *
 * Accessibility:
 *   - `prefers-reduced-motion` collapses to a static gradient (the
 *     #618 contract still holds via `pickOrbMode` returning "idle").
 *   - The face overlay (BuddyFace) only renders for pre-readers (< 6)
 *     so older kids who can read status copy aren't distracted.
 */
import { motion, useAnimationFrame, useMotionValue } from "framer-motion";
import type { CSSProperties } from "react";
import {
  breathFactor,
  orbColorForMode,
  orbDiameterForAge,
  type OrbMode,
} from "./buddyOrbHelpers";
import { BuddyFace } from "./BuddyFace";

/**
 * Age below which we render the BuddyFace overlay. Exported so the
 * BuddyOrb contract test can lock the magic number — research-anchored
 * "pre-reader" cutoff matches our 3-5 / 6-8 / 9-12 age band split.
 */
export const ORB_FACE_AGE_CEILING = 6;

/**
 * Pure predicate: should we draw the face? Defensive on null/undefined
 * so the parent can pass `currentChild?.age` without a guard.
 */
export function shouldRenderFace(age?: number | null): boolean {
  if (age == null) return false;
  return age < ORB_FACE_AGE_CEILING;
}

/**
 * Pure helper for the orb's outer-box inline style — width/height in
 * px. Exported so the contract test can lock the layout box without
 * mounting React.
 */
export function computeOrbInlineStyle(diameter: number): CSSProperties {
  return { width: diameter, height: diameter };
}

export interface BuddyOrbProps {
  mode: OrbMode;
  /** Mic RMS, 0..1. Drives the listening animation. */
  inputLevel: number;
  /** Assistant TTS RMS, 0..1. Drives the speaking animation. */
  outputLevel: number;
  /** Raw child age in years (3..12). Null/undefined → no face overlay. */
  childAge?: number | null;
  /** When true, all motion collapses to a static gradient. */
  prefersReducedMotion?: boolean;
}

/**
 * Small overlay: 3 expanding concentric rings that grow + fade. Tied
 * declaratively to mic level via the `key` so a louder peak restarts
 * the ring animation faster — kid sees "I heard you".
 */
function ExpandingRings({ level }: { level: number }) {
  // Higher level → faster rings. Bound the duration so quiet input
  // doesn't render a frozen ring.
  const duration = 1.6 - Math.min(0.8, level * 0.8);
  return (
    <>
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          className="pointer-events-none absolute inset-0 rounded-full border-2 border-emerald-300/60"
          initial={{ scale: 1, opacity: 0.7 }}
          animate={{ scale: 1.6, opacity: 0 }}
          transition={{
            duration,
            repeat: Infinity,
            ease: "easeOut",
            delay: i * (duration / 3),
          }}
          aria-hidden="true"
        />
      ))}
    </>
  );
}

/**
 * Small overlay: 4 orbiting dots — visually distinct from a spinner.
 * Research flag: spinners read as "loading", orbiting dots read as
 * "alive and thinking".
 */
function OrbitingDots() {
  return (
    <motion.div
      className="pointer-events-none absolute inset-0"
      animate={{ rotate: 360 }}
      transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
      aria-hidden="true"
    >
      {[0, 90, 180, 270].map((deg) => (
        <div
          key={deg}
          className="absolute left-1/2 top-0 h-2 w-2 -translate-x-1/2 rounded-full bg-sky-400 shadow-md"
          style={{ transform: `rotate(${deg}deg) translate(0,0)` }}
        />
      ))}
    </motion.div>
  );
}

export function BuddyOrb({
  mode,
  inputLevel,
  outputLevel,
  childAge,
  prefersReducedMotion = false,
}: BuddyOrbProps) {
  const diameter = orbDiameterForAge(childAge);
  const colors = orbColorForMode(mode);
  const scale = useMotionValue(1);

  // 60Hz audio-reactive loop. We write directly into the motion value;
  // NEVER call setState here (perf contract from the #651 plan).
  useAnimationFrame((t) => {
    if (prefersReducedMotion) {
      scale.set(1);
      return;
    }
    const level =
      mode === "speaking"
        ? outputLevel
        : mode === "listening"
          ? inputLevel
          : 0;
    scale.set(breathFactor(t, mode, level));
  });

  const showFace = shouldRenderFace(childAge);
  const boxStyle = computeOrbInlineStyle(diameter);

  return (
    <div
      className="relative flex items-center justify-center"
      style={boxStyle}
      aria-hidden={!showFace || undefined}
    >
      {/* Outer halo — blurred soft glow that breathes with the orb. */}
      <motion.div
        className={`absolute inset-0 rounded-full opacity-60 blur-2xl ${colors.halo}`}
        style={{ scale }}
        aria-hidden="true"
      />
      {/* Inner core gradient. */}
      <motion.div
        className={`absolute inset-2 rounded-full ${colors.core} shadow-lg`}
        style={{ scale }}
        aria-hidden="true"
      />
      {/* State-distinct overlays. */}
      {!prefersReducedMotion && mode === "listening" && (
        <ExpandingRings level={inputLevel} />
      )}
      {!prefersReducedMotion && mode === "thinking" && <OrbitingDots />}
      {/* Interrupted: quick spring pop overlay so the orb visibly
          "catches" the interruption. */}
      {!prefersReducedMotion && mode === "interrupted" && (
        <motion.div
          key="interrupt"
          className="pointer-events-none absolute inset-0 rounded-full ring-4 ring-amber-300"
          initial={{ scale: 1.15, opacity: 0.9 }}
          animate={{ scale: 0.95, opacity: 0 }}
          transition={{ duration: 0.12, ease: "easeOut" }}
          aria-hidden="true"
        />
      )}
      {/* Error: gentle tilt-wobble, AMBER not red, NOT a shake. */}
      {!prefersReducedMotion && mode === "error" && (
        <motion.div
          className="pointer-events-none absolute inset-0"
          animate={{ rotate: [-3, 3, -3] }}
          transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
          aria-hidden="true"
        />
      )}
      {/* Pre-reader face overlay. */}
      {showFace && <BuddyFace mode={mode} outputLevel={outputLevel} />}
    </div>
  );
}

export default BuddyOrb;
