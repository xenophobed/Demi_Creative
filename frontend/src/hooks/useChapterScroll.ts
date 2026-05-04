import { useCallback, useEffect, useRef, useState } from "react";
import { motionValue, type MotionValue } from "framer-motion";

/**
 * Tracks which story segment is currently in the viewport via IntersectionObserver
 * and exposes a `scrollTo(index)` to jump back to any chapter.
 *
 * Also publishes a continuous `scrollProgress` (float in `[0, segmentCount-1]`)
 * computed from each chapter node's distance to the viewport mid-line. The
 * integer `activeIndex` is still the IO-based winner; `scrollProgress` exists
 * so consumers can drive smooth, scroll-following animations (e.g. proximity
 * sizing in `ChapterRail`) without the IO threshold quantization.
 *
 * The component renders one DOM node per segment with `data-chapter-index="N"`;
 * the hook observes those nodes and reports the active chapter index whenever
 * the user scrolls.
 */
export function useChapterScroll(segmentCount: number) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [scrollProgress, setScrollProgress] = useState(0);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const visibilityRef = useRef<Map<number, number>>(new Map());
  const scrollProgressMVRef = useRef<MotionValue<number>>(motionValue(0));
  const rafRef = useRef<number | null>(null);

  const refreshActive = useCallback(() => {
    let bestIndex = 0;
    let bestRatio = -1;
    visibilityRef.current.forEach((ratio, index) => {
      if (ratio > bestRatio) {
        bestRatio = ratio;
        bestIndex = index;
      }
    });
    setActiveIndex((prev) => (prev === bestIndex ? prev : bestIndex));
  }, []);

  const recomputeProgress = useCallback(() => {
    const root = containerRef.current;
    if (!root) return;
    const nodes = Array.from(
      root.querySelectorAll<HTMLElement>("[data-chapter-index]"),
    );
    if (nodes.length === 0) return;
    const progress = computeScrollProgress(nodes, window.innerHeight / 2);
    scrollProgressMVRef.current.set(progress);
    setScrollProgress((prev) =>
      Math.abs(prev - progress) < 0.001 ? prev : progress,
    );
  }, []);

  const scheduleRecompute = useCallback(() => {
    if (rafRef.current != null) return;
    rafRef.current = window.requestAnimationFrame(() => {
      rafRef.current = null;
      recomputeProgress();
    });
  }, [recomputeProgress]);

  useEffect(() => {
    const root = containerRef.current;
    if (!root) return;

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const idx = Number(
            (entry.target as HTMLElement).dataset.chapterIndex,
          );
          if (Number.isNaN(idx)) continue;
          if (entry.isIntersecting) {
            visibilityRef.current.set(idx, entry.intersectionRatio);
          } else {
            visibilityRef.current.delete(idx);
          }
        }
        refreshActive();
        scheduleRecompute();
      },
      {
        // Bias toward the chapter occupying the upper-middle of the viewport.
        rootMargin: "-20% 0px -55% 0px",
        threshold: [0, 0.25, 0.5, 0.75, 1],
      },
    );

    const nodes = root.querySelectorAll<HTMLElement>("[data-chapter-index]");
    nodes.forEach((node) => observer.observe(node));

    window.addEventListener("scroll", scheduleRecompute, { passive: true });
    window.addEventListener("resize", scheduleRecompute);
    scheduleRecompute();

    return () => {
      observer.disconnect();
      window.removeEventListener("scroll", scheduleRecompute);
      window.removeEventListener("resize", scheduleRecompute);
      if (rafRef.current != null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, [segmentCount, refreshActive, scheduleRecompute]);

  const scrollTo = useCallback((index: number) => {
    const root = containerRef.current;
    if (!root) return;
    const target = root.querySelector<HTMLElement>(
      `[data-chapter-index="${index}"]`,
    );
    if (!target) return;
    target.scrollIntoView({ behavior: "smooth", block: "center" });
  }, []);

  return {
    containerRef,
    activeIndex,
    scrollProgress,
    scrollProgressMV: scrollProgressMVRef.current,
    scrollTo,
    setActiveIndex,
  };
}

/**
 * Pure helper: given a list of chapter DOM nodes (or any objects exposing
 * `getBoundingClientRect`), find which two are closest to a target Y line
 * (the viewport mid-line) and linearly interpolate their indices.
 *
 * Returns a float in `[0, nodes.length - 1]`. Exported so the proximity
 * math can be unit-tested without rendering a component.
 */
export function computeScrollProgress(
  nodes: Array<{ getBoundingClientRect: () => DOMRect }>,
  targetY: number,
): number {
  if (nodes.length === 0) return 0;
  if (nodes.length === 1) return 0;

  let aboveIdx = -1;
  let aboveCenter = -Infinity;
  let belowIdx = -1;
  let belowCenter = Infinity;
  let nearestIdx = 0;
  let nearestDist = Infinity;

  for (let i = 0; i < nodes.length; i++) {
    const rect = nodes[i].getBoundingClientRect();
    const center = rect.top + rect.height / 2;
    const dist = Math.abs(center - targetY);
    if (dist < nearestDist) {
      nearestDist = dist;
      nearestIdx = i;
    }
    if (center <= targetY && center > aboveCenter) {
      aboveCenter = center;
      aboveIdx = i;
    }
    if (center >= targetY && center < belowCenter) {
      belowCenter = center;
      belowIdx = i;
    }
  }

  if (aboveIdx === -1) return belowIdx;
  if (belowIdx === -1) return aboveIdx;
  if (aboveIdx === belowIdx) return aboveIdx;

  const span = belowCenter - aboveCenter;
  if (span <= 0) return nearestIdx;
  const t = (targetY - aboveCenter) / span;
  return aboveIdx + (belowIdx - aboveIdx) * Math.min(1, Math.max(0, t));
}
