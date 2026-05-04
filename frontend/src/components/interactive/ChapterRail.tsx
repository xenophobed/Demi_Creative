import { useEffect, useMemo, useRef } from "react";
import {
  AnimatePresence,
  motion,
  useMotionValue,
  useReducedMotion,
  useSpring,
  useTransform,
  type MotionValue,
} from "framer-motion";
import type { StorySegment, StoryChoice } from "@/types/api";

interface ChapterRailProps {
  segments: StorySegment[];
  /** One choice_id per segment the user has advanced past. */
  choiceHistory: string[];
  /** When set, segments at indices >= lockedAfterIndex render as locked. Pass `null` to disable. */
  lockedAfterIndex?: number | null;
  /** Called with a segment index when the user requests to jump there. */
  onJump: (index: number) => void;
  /** Index currently in viewport. */
  activeIndex: number;
  /**
   * Optional continuous scroll progress in [0, segments.length-1] for
   * proximity-based dot sizing. When omitted we fall back to the integer
   * `activeIndex`, so the rail still works for callers that have not
   * adopted the new hook output.
   */
  scrollProgress?: MotionValue<number>;
}

type NodeState = "done" | "active" | "upcoming" | "locked";

function nodeState(
  index: number,
  activeIndex: number,
  lockedAfterIndex: number | null,
): NodeState {
  if (lockedAfterIndex != null && index >= lockedAfterIndex) return "locked";
  if (index === activeIndex) return "active";
  if (index < activeIndex) return "done";
  return "upcoming";
}

interface ChoiceMeta {
  emoji: string;
  text: string;
}

function choiceMetaAt(
  segment: StorySegment | undefined,
  choiceId: string | undefined,
): ChoiceMeta | null {
  if (!segment || !choiceId) return null;
  const choices: StoryChoice[] = Array.isArray(segment.choices)
    ? segment.choices
    : [];
  const found = choices.find((c) => c.choice_id === choiceId);
  if (!found) return { emoji: "✅", text: choiceId };
  return { emoji: found.emoji || "✅", text: found.text || choiceId };
}

const TRAVELER_LAYOUT_ID = "chapter-traveler";
const TRAVELER_EMOJI = "🐾";

// Proximity-falloff defaults shared by desktop + mobile dots.
const DOT_SIZE_MIN = 6;
const DOT_SIZE_MAX = 16;
const DOT_OPACITY_MIN = 0.4;
const DOT_OPACITY_MAX = 1.0;
const DOT_FALLOFF = 4;

// Vertical row pitch on desktop (px per chapter). Used to translate the
// inner <ol> so that the active chapter sits at the rail's vertical
// midpoint — the rail "scrolls past" while staying sticky.
const DESKTOP_ROW_PITCH = 28;

// Spring config for size/opacity transitions. Tuned for buttery feel
// per issue #431 (stiffness ~220, damping ~30).
const DOT_SPRING = { stiffness: 220, damping: 30, mass: 0.6 } as const;

/**
 * Pure helper: lerp from `max` (at distance 0) to `min` (at distance >=
 * `falloff`). Exported for unit tests in issue #435.
 */
export function computeDotSize(
  distance: number,
  opts?: { min?: number; max?: number; falloff?: number },
): number {
  const min = opts?.min ?? DOT_SIZE_MIN;
  const max = opts?.max ?? DOT_SIZE_MAX;
  const falloff = opts?.falloff ?? DOT_FALLOFF;
  const d = Math.abs(distance);
  if (d <= 0) return max;
  if (d >= falloff) return min;
  const t = d / falloff; // 0..1
  return max + (min - max) * t;
}

/**
 * Pure helper: lerp from `max` (at distance 0) to `min` (at distance >=
 * `falloff`). Same shape as `computeDotSize`. Exported for unit tests.
 */
export function computeDotOpacity(
  distance: number,
  opts?: { min?: number; max?: number; falloff?: number },
): number {
  const min = opts?.min ?? DOT_OPACITY_MIN;
  const max = opts?.max ?? DOT_OPACITY_MAX;
  const falloff = opts?.falloff ?? DOT_FALLOFF;
  const d = Math.abs(distance);
  if (d <= 0) return max;
  if (d >= falloff) return min;
  const t = d / falloff;
  return max + (min - max) * t;
}

interface DesktopDotProps {
  index: number;
  state: NodeState;
  ariaLabel: string;
  disabled: boolean;
  onJump: (i: number) => void;
  // When scrollProgress is provided, drive size/opacity off the live MV.
  // When omitted we use the static distance to integer activeIndex.
  scrollProgress: MotionValue<number> | null;
  staticDistance: number;
  reducedMotion: boolean;
}

/**
 * One dot in the desktop rail. Internally subscribes to the live
 * `scrollProgress` MotionValue (when supplied) so size + opacity
 * follow the user's scroll continuously.
 */
function DesktopDot({
  index,
  state,
  ariaLabel,
  disabled,
  onJump,
  scrollProgress,
  staticDistance,
  reducedMotion,
}: DesktopDotProps) {
  // Always supply a MotionValue to useTransform so hook order is stable
  // and the v11 overload resolves cleanly. When the parent does not pass
  // a real scrollProgress we feed a constant MV holding the static index
  // distance — useTransform still produces a usable MV.
  const fallbackMV = useMotionValue(staticDistance + index);
  const inputMV: MotionValue<number> = scrollProgress ?? fallbackMV;
  const sizeFromMV = useTransform(inputMV, (v: number) =>
    computeDotSize(v - index),
  );
  const opacityFromMV = useTransform(inputMV, (v: number) =>
    computeDotOpacity(v - index),
  );

  const sizeStatic = computeDotSize(staticDistance);
  const opacityStatic = computeDotOpacity(staticDistance);

  // useSpring must be called unconditionally to satisfy the rules of
  // hooks. We spring the MV-derived values; consumers below pick which
  // value to actually use based on whether scrollProgress was supplied.
  const sizeSpring = useSpring(sizeFromMV, DOT_SPRING);
  const opacitySpring = useSpring(opacityFromMV, DOT_SPRING);

  // Decide what to bind to the DOM. Reduced-motion always shows MAX.
  let widthStyle: number | MotionValue<number>;
  let heightStyle: number | MotionValue<number>;
  let opacityStyle: number | MotionValue<number>;
  if (reducedMotion) {
    widthStyle = DOT_SIZE_MAX;
    heightStyle = DOT_SIZE_MAX;
    opacityStyle = DOT_OPACITY_MAX;
  } else if (scrollProgress) {
    widthStyle = sizeSpring;
    heightStyle = sizeSpring;
    opacityStyle = opacitySpring;
  } else {
    widthStyle = sizeStatic;
    heightStyle = sizeStatic;
    opacityStyle = opacityStatic;
  }

  const colorClass =
    state === "done"
      ? "bg-primary"
      : state === "locked"
        ? "bg-gray-300"
        : "bg-primary/70"; // upcoming uses a softer primary so the rail reads as one family

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => !disabled && onJump(index)}
      aria-label={ariaLabel}
      className={`group/node mx-auto flex items-center justify-center rounded-full ${
        disabled ? "cursor-not-allowed" : "cursor-pointer hover:scale-110"
      } focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2`}
      style={{ width: 24, height: 24 }} /* hit-box stays generous */
    >
      <motion.span
        aria-hidden
        className={`block rounded-full ${colorClass}`}
        style={{
          width: widthStyle as number,
          height: heightStyle as number,
          opacity: opacityStyle as number,
        }}
      />
    </button>
  );
}

interface MobileDotProps {
  index: number;
  state: NodeState;
  ariaLabel: string;
  disabled: boolean;
  onJump: (i: number) => void;
  scrollProgress: MotionValue<number> | null;
  staticDistance: number;
  reducedMotion: boolean;
  registerRef: (i: number, el: HTMLButtonElement | null) => void;
}

function MobileDot({
  index,
  state,
  ariaLabel,
  disabled,
  onJump,
  scrollProgress,
  staticDistance,
  reducedMotion,
  registerRef,
}: MobileDotProps) {
  const fallbackMV = useMotionValue(staticDistance + index);
  const inputMV: MotionValue<number> = scrollProgress ?? fallbackMV;
  const sizeFromMV = useTransform(inputMV, (v: number) =>
    computeDotSize(v - index),
  );
  const opacityFromMV = useTransform(inputMV, (v: number) =>
    computeDotOpacity(v - index),
  );
  const sizeSpring = useSpring(sizeFromMV, DOT_SPRING);
  const opacitySpring = useSpring(opacityFromMV, DOT_SPRING);

  const sizeStatic = computeDotSize(staticDistance);
  const opacityStatic = computeDotOpacity(staticDistance);

  let widthStyle: number | MotionValue<number>;
  let heightStyle: number | MotionValue<number>;
  let opacityStyle: number | MotionValue<number>;
  if (reducedMotion) {
    widthStyle = DOT_SIZE_MAX;
    heightStyle = DOT_SIZE_MAX;
    opacityStyle = DOT_OPACITY_MAX;
  } else if (scrollProgress) {
    widthStyle = sizeSpring;
    heightStyle = sizeSpring;
    opacityStyle = opacitySpring;
  } else {
    widthStyle = sizeStatic;
    heightStyle = sizeStatic;
    opacityStyle = opacityStatic;
  }

  const colorClass =
    state === "done"
      ? "bg-primary"
      : state === "locked"
        ? "bg-gray-300"
        : "bg-primary/70";

  return (
    <button
      ref={(el) => registerRef(index, el)}
      type="button"
      disabled={disabled}
      onClick={() => !disabled && onJump(index)}
      aria-label={ariaLabel}
      className={`shrink-0 inline-flex items-center justify-center rounded-full ${
        disabled ? "cursor-not-allowed" : "cursor-pointer"
      } focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2`}
      style={{ width: 24, height: 24 }}
    >
      <motion.span
        aria-hidden
        className={`block rounded-full ${colorClass}`}
        style={{
          width: widthStyle as number,
          height: heightStyle as number,
          opacity: opacityStyle as number,
        }}
      />
    </button>
  );
}

function ChapterRail({
  segments,
  choiceHistory,
  lockedAfterIndex = null,
  onJump,
  activeIndex,
  scrollProgress,
}: ChapterRailProps) {
  // All hooks must run unconditionally — never put hook calls after an early
  // return, or React's hook order will diverge across renders.
  const reducedMotion = useReducedMotion() ?? false;

  // For each chapter, the choice the user made AT that chapter to advance.
  // The active chapter has no choice yet → null.
  const choiceMetas = useMemo(
    () =>
      segments.map((seg, i) =>
        i < choiceHistory.length
          ? choiceMetaAt(seg, choiceHistory[i])
          : null,
      ),
    [segments, choiceHistory],
  );

  // Active card content: arrived-via choice came at the previous chapter.
  const activeSegment = segments[activeIndex];
  const arrivingChoice =
    activeIndex > 0
      ? choiceMetaAt(segments[activeIndex - 1], choiceHistory[activeIndex - 1])
      : null;
  const isActiveEnding = !!activeSegment?.is_ending;

  // Build aria-labels once. Locked + arrived-via suffix per issue #433.
  const ariaLabelFor = (index: number, state: NodeState): string => {
    const parts = [`Jump to chapter ${index + 1}`];
    const choice = choiceMetas[index];
    if (choice) parts.push(`arrived via ${choice.text}`);
    if (state === "locked") parts.push("locked");
    return parts.join(", ");
  };

  // Desktop: translate the inner ol so the active row is centered. We use
  // the live scrollProgress when available so the rail glides smoothly;
  // otherwise we snap to integer activeIndex.
  const olFallbackMV = useMotionValue(activeIndex);
  const olInputMV: MotionValue<number> = scrollProgress ?? olFallbackMV;
  // Half-row offset so the active row's CENTER (not its top) lands on the
  // viewport midline. Without this, item 0 renders 14px below center.
  const desktopOlOffset = useTransform(
    olInputMV,
    (v: number) => -v * DESKTOP_ROW_PITCH - DESKTOP_ROW_PITCH / 2,
  );
  const desktopOlOffsetSpring = useSpring(desktopOlOffset, DOT_SPRING);
  const staticOlOffset =
    -activeIndex * DESKTOP_ROW_PITCH - DESKTOP_ROW_PITCH / 2;

  // --- Mobile centering: scrollIntoView the active button on change ---
  const mobileButtonRefs = useRef<Map<number, HTMLButtonElement>>(new Map());
  const registerMobileRef = (i: number, el: HTMLButtonElement | null) => {
    if (el) mobileButtonRefs.current.set(i, el);
    else mobileButtonRefs.current.delete(i);
  };
  useEffect(() => {
    const el = mobileButtonRefs.current.get(activeIndex);
    if (!el) return;
    try {
      el.scrollIntoView({
        inline: "center",
        block: "nearest",
        behavior: reducedMotion ? "auto" : "smooth",
      });
    } catch {
      // ignore older browsers
    }
  }, [activeIndex, reducedMotion]);

  // Safe to early-return here: every hook above ran.
  if (segments.length === 0) return null;

  // ---- Active card body shared by desktop + mobile ----
  const activeCardLabel = (
    <>
      <span className="block text-xs font-semibold uppercase tracking-wider text-primary">
        Chapter {activeIndex + 1} of {segments.length}
      </span>
      <span className="mt-1 block text-sm leading-snug text-gray-700">
        {arrivingChoice ? (
          <>
            arrived via{" "}
            <span aria-hidden className="mr-0.5">
              {arrivingChoice.emoji}
            </span>
            <span>{arrivingChoice.text}</span>
          </>
        ) : (
          "Beginning of story"
        )}
      </span>
      {isActiveEnding && (
        <span className="mt-2 inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-700">
          <span aria-hidden>🏁</span> Ending
        </span>
      )}
    </>
  );

  const activeCardCompact = (
    <>
      <span className="text-xs font-semibold text-primary">
        Ch {activeIndex + 1}/{segments.length}
      </span>
      {arrivingChoice ? (
        <span className="ml-1.5 inline-flex items-center gap-1 text-sm text-gray-700">
          <span aria-hidden>{arrivingChoice.emoji}</span>
          <span className="truncate max-w-[10rem]">{arrivingChoice.text}</span>
        </span>
      ) : (
        <span className="ml-1.5 text-sm text-gray-500">· start</span>
      )}
      {isActiveEnding && (
        <span aria-hidden className="ml-1.5 text-sm">
          🏁
        </span>
      )}
    </>
  );

  return (
    <>
      {/* Desktop side rail — single expanded card on the active row, dots elsewhere. */}
      <aside
        aria-label="Story chapters"
        className="hidden lg:flex flex-col shrink-0 lg:w-48 lg:sticky lg:top-24 lg:self-start lg:h-[calc(100vh-7rem)]"
      >
        <div className="flex flex-col h-full">
          {/* Vertical viewport. The inner <ol> translates so the active row
              sits at the centerline — visually the rail "scrolls" past. */}
          <div className="relative flex-1 overflow-hidden">
            {/* Center guideline (subtle) so the active card has an anchor. */}
            <div
              aria-hidden
              className="pointer-events-none absolute inset-x-0 top-1/2 -translate-y-1/2 h-px bg-gradient-to-r from-transparent via-primary/20 to-transparent"
            />
            <motion.ol
              className="absolute left-0 right-0 top-1/2 flex flex-col items-stretch px-3"
              style={
                reducedMotion
                  ? { y: staticOlOffset }
                  : scrollProgress
                    ? { y: desktopOlOffsetSpring }
                    : { y: staticOlOffset }
              }
            >
              {segments.map((segment, index) => {
                const state = nodeState(index, activeIndex, lockedAfterIndex);
                const isActive = state === "active";
                const isLocked = state === "locked";
                const ariaLabel = ariaLabelFor(index, state);
                const distance = Math.abs(index - activeIndex);

                return (
                  <li
                    key={`${segment.segment_id}-${index}`}
                    className="relative flex items-center justify-center"
                    style={{ height: DESKTOP_ROW_PITCH }}
                    aria-current={isActive ? "step" : undefined}
                  >
                    {isActive ? (
                      // Expanded active card. Cross-fades on mount/unmount.
                      <AnimatePresence mode="wait" initial={false}>
                        <motion.div
                          key={`active-${index}`}
                          initial={
                            reducedMotion
                              ? false
                              : { opacity: 0, scale: 0.96 }
                          }
                          animate={{ opacity: 1, scale: 1 }}
                          exit={
                            reducedMotion
                              ? undefined
                              : { opacity: 0, scale: 0.96 }
                          }
                          transition={{ duration: 0.2 }}
                          className="relative w-full px-3 py-2"
                        >
                          <span
                            className="absolute -left-1 top-1/2 -translate-y-1/2 inline-flex h-5 w-5 items-center justify-center"
                            aria-hidden
                          >
                            <motion.span
                              layoutId={TRAVELER_LAYOUT_ID}
                              transition={{
                                type: "spring",
                                stiffness: 360,
                                damping: 28,
                              }}
                              className="text-base"
                            >
                              {TRAVELER_EMOJI}
                            </motion.span>
                          </span>
                          <div className="pl-5">{activeCardLabel}</div>
                        </motion.div>
                      </AnimatePresence>
                    ) : (
                      <DesktopDot
                        index={index}
                        state={state}
                        ariaLabel={ariaLabel}
                        disabled={isLocked}
                        onJump={onJump}
                        scrollProgress={scrollProgress ?? null}
                        staticDistance={distance}
                        reducedMotion={reducedMotion}
                      />
                    )}
                  </li>
                );
              })}
            </motion.ol>
          </div>
        </div>
      </aside>

      {/* Mobile horizontal pill row — same proximity logic on the X axis. */}
      <nav
        aria-label="Story chapters"
        className="lg:hidden sticky top-2 z-20 -mx-2"
      >
        <div className="flex items-center gap-2 overflow-x-auto px-2 py-2">
          {segments.map((segment, index) => {
            const state = nodeState(index, activeIndex, lockedAfterIndex);
            const isActive = state === "active";
            const isLocked = state === "locked";
            const ariaLabel = ariaLabelFor(index, state);
            const distance = Math.abs(index - activeIndex);

            if (isActive) {
              return (
                <div
                  key={`${segment.segment_id}-${index}`}
                  ref={(el) => {
                    // Keep the centered card scrollable-into-view too.
                    if (el) {
                      // Coerce to button-typed map for shared scrollIntoView logic.
                      mobileButtonRefs.current.set(
                        index,
                        el as unknown as HTMLButtonElement,
                      );
                    } else {
                      mobileButtonRefs.current.delete(index);
                    }
                  }}
                  aria-current="step"
                  className="shrink-0 inline-flex items-center px-2 py-1"
                >
                  <AnimatePresence mode="wait" initial={false}>
                    <motion.div
                      key={`m-active-${index}`}
                      initial={
                        reducedMotion ? false : { opacity: 0, scale: 0.96 }
                      }
                      animate={{ opacity: 1, scale: 1 }}
                      exit={
                        reducedMotion ? undefined : { opacity: 0, scale: 0.96 }
                      }
                      transition={{ duration: 0.2 }}
                      className="inline-flex items-center"
                    >
                      <motion.span
                        layoutId={TRAVELER_LAYOUT_ID}
                        transition={{
                          type: "spring",
                          stiffness: 360,
                          damping: 28,
                        }}
                        className="mr-1.5 text-base"
                      >
                        {TRAVELER_EMOJI}
                      </motion.span>
                      {activeCardCompact}
                    </motion.div>
                  </AnimatePresence>
                </div>
              );
            }

            return (
              <MobileDot
                key={`${segment.segment_id}-${index}`}
                index={index}
                state={state}
                ariaLabel={ariaLabel}
                disabled={isLocked}
                onJump={onJump}
                scrollProgress={scrollProgress ?? null}
                staticDistance={distance}
                reducedMotion={reducedMotion}
                registerRef={registerMobileRef}
              />
            );
          })}
        </div>
      </nav>
    </>
  );
}

export default ChapterRail;
export { choiceMetaAt };
export type { ChoiceMeta };
