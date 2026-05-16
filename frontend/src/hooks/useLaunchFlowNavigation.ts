/**
 * useLaunchFlowNavigation — React glue for the My Agent `launch_flow`
 * SSE event (#496).
 *
 * The proxy emits `launch_flow` whenever a specialist tool returns a
 * typed payload (image_story / interactive_story / kids_daily). The
 * SPA consumes that event to hop the user from the buddy chat into the
 * matching standalone experience page, with prefill query params.
 *
 * Why a hook (not a service-side redirect):
 *   - Tests can pin navigation behavior without spinning up the SDK or
 *     a real router.
 *   - Page-level state (toast / animation) needs to run alongside the
 *     navigate call.
 *   - Navigation policy ("nav now" vs "wait for complete") is owned by
 *     the page, not the API layer.
 *
 * Returned shape:
 *   {
 *     onLaunchFlow,           // Plug into `StreamCallbacks.onLaunchFlow`
 *     pendingLaunchFlow,      // The most recent event captured this turn
 *     navigateToPendingFlow,  // Trigger the deferred navigate after
 *                              // `complete` / first paint
 *     resetPendingFlow,       // Drop the pending event (e.g. on abort)
 *   }
 *
 * Trade-off: we *capture* the event during the stream and *navigate*
 * after the caller signals it's safe to leave the chat surface. This
 * costs one bit of state but avoids whisking the user away before the
 * trailing `result` message is rendered (PRD §3.11 favours legible
 * feedback over speed for child users).
 */
import { useCallback, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { SSELaunchFlowData } from "@/types/api";

/**
 * Build a navigable path from a `launch_flow` payload. Exported as a
 * pure function so contract tests can pin the URL shape without
 * spinning up React Router.
 */
export function buildLaunchFlowPath(data: SSELaunchFlowData): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(data.prefill ?? {})) {
    if (value === null || value === undefined) continue;
    params.append(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${data.route}?${qs}` : data.route;
}

export interface UseLaunchFlowNavigationResult {
  /** Pass this as `StreamCallbacks.onLaunchFlow`. */
  onLaunchFlow: (data: SSELaunchFlowData) => void;
  /** The launch_flow event captured this turn, or null. */
  pendingLaunchFlow: SSELaunchFlowData | null;
  /**
   * Navigate to whatever launch_flow event was captured this turn.
   * Returns the path navigated to, or null if nothing pending. Safe
   * to call from `onComplete` — clears state on success.
   */
  navigateToPendingFlow: () => string | null;
  /** Clear the pending event without navigating (e.g. user aborted). */
  resetPendingFlow: () => void;
}

export function useLaunchFlowNavigation(): UseLaunchFlowNavigationResult {
  const navigate = useNavigate();
  const [pendingLaunchFlow, setPendingLaunchFlow] =
    useState<SSELaunchFlowData | null>(null);
  // Ref mirrors state so navigateToPendingFlow() reads the latest
  // value even when called synchronously from the same render cycle
  // that set it (e.g. onComplete fires immediately after onLaunchFlow
  // when the stream closes fast in tests).
  const pendingRef = useRef<SSELaunchFlowData | null>(null);

  const onLaunchFlow = useCallback((data: SSELaunchFlowData) => {
    pendingRef.current = data;
    setPendingLaunchFlow(data);
  }, []);

  const resetPendingFlow = useCallback(() => {
    pendingRef.current = null;
    setPendingLaunchFlow(null);
  }, []);

  const navigateToPendingFlow = useCallback((): string | null => {
    const data = pendingRef.current;
    if (!data) return null;
    const path = buildLaunchFlowPath(data);
    pendingRef.current = null;
    setPendingLaunchFlow(null);
    navigate(path);
    return path;
  }, [navigate]);

  return {
    onLaunchFlow,
    pendingLaunchFlow,
    navigateToPendingFlow,
    resetPendingFlow,
  };
}
