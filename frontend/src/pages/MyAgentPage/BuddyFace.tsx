/**
 * BuddyFace (#651) — small SVG face overlay for pre-readers (age < 6).
 *
 * Five visual states matching the orb mode. Renders inside the orb so
 * a kid who can't read the status copy still understands what the buddy
 * is doing. Pure SVG + Tailwind — zero new dependencies.
 *
 * Error face is friendly-concerned (slight frown + soft eyes), NOT a
 * red X. Research flag from the 2026-06 synthesis: red and scary error
 * iconography distresses children and erodes trust in the buddy.
 *
 * The speaking mouth is driven by `outputLevel` so kids see the buddy
 * "open its mouth" with louder syllables — the headline alive feel.
 */
import { motion } from "framer-motion";
import type { OrbMode } from "./buddyOrbHelpers";

interface BuddyFaceProps {
  mode: OrbMode;
  /** 0..1 audio level from the assistant's TTS analyser. */
  outputLevel: number;
}

/**
 * Width of the open-mouth shape in SVG units, derived from outputLevel.
 * Pure helper exported for testability. Capped so loud peaks don't draw
 * a mouth wider than the face.
 */
export function mouthOpennessFor(outputLevel: number): number {
  const safe = Math.max(0, Math.min(1, outputLevel));
  // Min mouth height 2, max 14 — the face viewBox is 60x60.
  return 2 + 12 * safe;
}

export function BuddyFace({ mode, outputLevel }: BuddyFaceProps) {
  const eyesClosed = mode === "thinking";
  const wideEyes = mode === "listening";
  const eyeR = wideEyes ? 4.5 : eyesClosed ? 0.6 : 3;
  // Mouth depends on mode.
  let mouthEl: JSX.Element;
  if (mode === "speaking") {
    const h = mouthOpennessFor(outputLevel);
    mouthEl = (
      <motion.ellipse
        cx={30}
        cy={42}
        rx={6}
        ry={h / 2}
        fill="#4c1d95"
        opacity={0.85}
      />
    );
  } else if (mode === "listening") {
    // Slightly open mouth — "I'm listening".
    mouthEl = (
      <ellipse cx={30} cy={42} rx={5} ry={2} fill="#4c1d95" opacity={0.75} />
    );
  } else if (mode === "error") {
    // Friendly concerned — gentle frown, NOT a red X.
    mouthEl = (
      <path
        d="M22 44 Q30 38 38 44"
        stroke="#92400e"
        strokeWidth={2.2}
        strokeLinecap="round"
        fill="none"
      />
    );
  } else if (mode === "thinking") {
    // Tiny pursed line — eyes-closed thinking pose.
    mouthEl = (
      <line
        x1={26}
        y1={42}
        x2={34}
        y2={42}
        stroke="#4c1d95"
        strokeWidth={2}
        strokeLinecap="round"
      />
    );
  } else {
    // idle / connecting / interrupted / ending — gentle smile.
    mouthEl = (
      <path
        d="M22 41 Q30 47 38 41"
        stroke="#4c1d95"
        strokeWidth={2.2}
        strokeLinecap="round"
        fill="none"
      />
    );
  }

  // Slow blink for idle — runs as a CSS-driven keyframe via framer to
  // avoid React re-renders per frame.
  const blink =
    mode === "idle"
      ? { ry: [eyeR, 0.5, eyeR] }
      : { ry: eyeR };

  return (
    <svg
      viewBox="0 0 60 60"
      className="pointer-events-none absolute inset-0 h-full w-full"
      role="img"
      aria-label={`Buddy is ${mode}`}
    >
      {/* Eyes */}
      <motion.ellipse
        cx={22}
        cy={28}
        rx={eyeR}
        ry={eyeR}
        fill="#312e81"
        animate={blink}
        transition={{
          duration: 0.3,
          repeat: mode === "idle" ? Infinity : 0,
          repeatDelay: 3.5,
        }}
      />
      <motion.ellipse
        cx={38}
        cy={28}
        rx={eyeR}
        ry={eyeR}
        fill="#312e81"
        animate={blink}
        transition={{
          duration: 0.3,
          repeat: mode === "idle" ? Infinity : 0,
          repeatDelay: 3.5,
        }}
      />
      {/* Mouth */}
      {mouthEl}
    </svg>
  );
}

export default BuddyFace;
