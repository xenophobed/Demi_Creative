/**
 * groupTheme — deterministic visual accents for a Content Hub group.
 *
 * Picks a palette index by hashing the group's slug, so the same group
 * always renders with the same color story across sessions and devices.
 *
 * Issue: GroupPage magazine redesign | Parent epic: #437
 */

import type { HubPost } from "@/types/hub";

export interface GroupAccent {
  /** Tailwind gradient classes for the page banner background. */
  bannerGradient: string;
  /** Tailwind gradient classes for the post-cover placeholder. */
  coverGradient: string;
  /** Tailwind text color for theme-tinted accents (chips, dividers). */
  accentText: string;
  /** Tailwind background for chip pills. */
  chipBg: string;
}

const PALETTE: GroupAccent[] = [
  {
    bannerGradient: "from-pink-200 via-rose-100 to-orange-100",
    coverGradient: "from-pink-300 via-rose-200 to-orange-200",
    accentText: "text-rose-700",
    chipBg: "bg-rose-100 text-rose-700",
  },
  {
    bannerGradient: "from-violet-200 via-purple-100 to-fuchsia-100",
    coverGradient: "from-violet-300 via-purple-200 to-fuchsia-200",
    accentText: "text-violet-700",
    chipBg: "bg-violet-100 text-violet-700",
  },
  {
    bannerGradient: "from-sky-200 via-cyan-100 to-emerald-100",
    coverGradient: "from-sky-300 via-cyan-200 to-emerald-200",
    accentText: "text-sky-700",
    chipBg: "bg-sky-100 text-sky-700",
  },
  {
    bannerGradient: "from-amber-200 via-yellow-100 to-lime-100",
    coverGradient: "from-amber-300 via-yellow-200 to-lime-200",
    accentText: "text-amber-700",
    chipBg: "bg-amber-100 text-amber-700",
  },
  {
    bannerGradient: "from-emerald-200 via-teal-100 to-sky-100",
    coverGradient: "from-emerald-300 via-teal-200 to-sky-200",
    accentText: "text-emerald-700",
    chipBg: "bg-emerald-100 text-emerald-700",
  },
  {
    bannerGradient: "from-indigo-200 via-blue-100 to-cyan-100",
    coverGradient: "from-indigo-300 via-blue-200 to-cyan-200",
    accentText: "text-indigo-700",
    chipBg: "bg-indigo-100 text-indigo-700",
  },
];

/**
 * Stable string hash (djb2). Browser/server agnostic, no deps.
 */
function hashStr(s: string): number {
  let h = 5381;
  for (let i = 0; i < s.length; i++) {
    h = (h * 33) ^ s.charCodeAt(i);
  }
  return h >>> 0;
}

export function accentForSlug(slug: string | undefined | null): GroupAccent {
  if (!slug) return PALETTE[0];
  return PALETTE[hashStr(slug) % PALETTE.length];
}

/**
 * Deterministic emoji for a theme tag. Falls back to a sparkle if the
 * theme is empty or unknown.
 */
const THEME_EMOJI: Record<string, string> = {
  fantasy: "🧙",
  dragons: "🐉",
  space: "🚀",
  ocean: "🌊",
  animals: "🦁",
  forest: "🌳",
  science: "🔬",
  music: "🎵",
  art: "🎨",
  invention: "💡",
  food: "🍰",
  sports: "⚽",
  heroes: "🦸",
  robots: "🤖",
  magic: "✨",
};

export function emojiForTheme(theme: string | null | undefined): string {
  if (!theme) return "✨";
  const key = theme.trim().toLowerCase();
  return THEME_EMOJI[key] ?? "✨";
}

/**
 * Per-source-type cover treatment. Art stories get a warm bookish
 * gradient, interactive stories a playful violet — both override the
 * group's accent so individual posts read differently at a glance.
 */
export function coverFor(
  type: HubPost["source_artifact_type"],
): { gradient: string; icon: string; label: string } {
  if (type === "art_story") {
    return {
      gradient: "from-pink-300 via-orange-200 to-amber-200",
      icon: "📖",
      label: "Art story",
    };
  }
  return {
    gradient: "from-violet-400 via-fuchsia-300 to-sky-300",
    icon: "🌟",
    label: "Interactive story",
  };
}
