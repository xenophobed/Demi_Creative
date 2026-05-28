/**
 * Pure helpers for the session list sidebar (#570).
 *
 * Kept separate from the component so the display logic is unit-testable
 * without a DOM (the project does not ship @testing-library/react).
 */

import type { AgentChatSessionSummary } from "@/types/api";

/** Human label for a session row, falling back when untitled. */
export function sessionDisplayTitle(session: AgentChatSessionSummary): string {
  const title = (session.title ?? "").trim();
  return title || "New chat";
}

/**
 * Compact relative time ("just now", "5m", "3h", "2d", or a date).
 * `nowMs` is injectable so tests are deterministic.
 */
export function relativeTime(iso: string, nowMs: number = Date.now()): string {
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return "";
  const diffSec = Math.max(0, Math.floor((nowMs - then) / 1000));
  if (diffSec < 45) return "just now";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 7) return `${diffDay}d`;
  // Older than a week — show a short date.
  const d = new Date(then);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}
