/**
 * SuggestedThemes - displays personalised theme recommendation chips (#292).
 *
 * Fetches recommendations from GET /api/v1/memory/recommendations/{child_id}
 * and renders them as clickable chips. When clicked, the caller receives the
 * selected string via `onSelect`.
 */

import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { memoryService } from "@/api/services/memoryService";
import useChildStore from "@/store/useChildStore";
import useAuthStore from "@/store/useAuthStore";

type SuggestedThemeMode = "tag" | "prompt";

interface SuggestedThemesProps {
  /** Called when the user clicks a chip */
  onSelect: (theme: string) => void;
  /** Maximum chips to show (default 5) */
  limit?: number;
  /** tag: short labels, prompt: more inspiring story starters */
  mode?: SuggestedThemeMode;
}

const FALLBACK_TAGS = [
  "Time Travel",
  "Hidden Treasure",
  "Sky Islands",
  "Secret Garden",
  "Robot Friends",
  "Ocean Kingdom",
  "Tiny Dragons",
  "Moon Camp",
  "Jungle Quest",
  "Magic School",
];

const FALLBACK_PROMPT_SEEDS = [
  "a floating city",
  "a talking backpack",
  "an upside-down forest",
  "a midnight train",
  "a lost star map",
  "a tiny inventor",
  "a cloud kingdom",
  "a secret museum",
];

const TAG_EMOJIS = ["🌟", "🧭", "🚀", "🦄", "🧩", "🌈", "🗺️", "🎈"];

const EN_PROMPT_TEMPLATES: Array<(seed: string) => string> = [
  (seed) => `A rescue mission inside ${seed}`,
  (seed) => `What if ${seed} kept one impossible secret?`,
  (seed) => `A race against sunset to save ${seed}`,
  (seed) => `A tiny hero trapped in ${seed}`,
  (seed) => `A mystery only solvable through ${seed}`,
  (seed) => `One choice can rewrite ${seed}`,
];

const ZH_PROMPT_TEMPLATES: Array<(seed: string) => string> = [
  (seed) => `A timed rescue inside ${seed}`,
  (seed) => `What if ${seed} hid an impossible secret?`,
  (seed) => `A race before sunset to protect ${seed}`,
  (seed) => `A tiny hero trapped in ${seed}`,
  (seed) => `A puzzle only you can solve about ${seed}`,
  (seed) => `One choice that rewrites the fate of ${seed}`,
];

function normalizeTheme(raw: string): string {
  return raw.replace(/\s+/g, " ").trim();
}

function uniqueThemes(input: string[]): string[] {
  const seen = new Set<string>();
  const output: string[] = [];
  for (const item of input) {
    const normalized = normalizeTheme(item);
    if (!normalized) continue;
    const key = normalized.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    output.push(normalized);
  }
  return output;
}

function hashString(value: string): number {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash << 5) - hash + value.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

function maybeTitleCase(theme: string): string {
  if (!/^[A-Za-z0-9][A-Za-z0-9\s'-]*$/.test(theme)) return theme;
  return theme.toLowerCase().replace(/\b\w/g, (char) => char.toUpperCase());
}

function emojiForTheme(theme: string): string {
  return TAG_EMOJIS[hashString(theme) % TAG_EMOJIS.length];
}

function isCJK(input: string): boolean {
  return /[\u3400-\u9FBF]/.test(input);
}

function buildTagSuggestions(personalized: string[], limit: number): string[] {
  const merged = uniqueThemes([...personalized, ...FALLBACK_TAGS]);
  return merged.slice(0, limit).map(maybeTitleCase);
}

function buildPromptSuggestions(
  personalized: string[],
  limit: number,
): string[] {
  const seeds = uniqueThemes([...personalized, ...FALLBACK_PROMPT_SEEDS]);
  const prompts: string[] = [];

  for (let i = 0; i < seeds.length; i += 1) {
    const seed = seeds[i];
    const templates = isCJK(seed) ? ZH_PROMPT_TEMPLATES : EN_PROMPT_TEMPLATES;
    const template = templates[(hashString(seed) + i) % templates.length];
    prompts.push(template(seed));
  }

  for (let i = 0; i < seeds.length - 1; i += 1) {
    const first = seeds[i];
    const second = seeds[i + 1];
    if (isCJK(first + second)) {
      prompts.push(`The day when ${first} met ${second}`);
    } else {
      prompts.push(`When ${first} meets ${second}`);
    }
  }

  return uniqueThemes(prompts).slice(0, limit);
}

export default function SuggestedThemes({
  onSelect,
  limit = 5,
  mode = "tag",
}: SuggestedThemesProps) {
  const { isAuthenticated } = useAuthStore();
  const { defaultChildId } = useChildStore();
  const [personalizedThemes, setPersonalizedThemes] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasFetched, setHasFetched] = useState(false);

  useEffect(() => {
    let cancelled = false;

    if (!isAuthenticated || !defaultChildId) {
      setPersonalizedThemes([]);
      setHasFetched(true);
      return () => {
        cancelled = true;
      };
    }

    setLoading(true);
    setHasFetched(false);

    memoryService
      .getRecommendations(defaultChildId, limit)
      .then((res) => {
        if (!cancelled)
          setPersonalizedThemes(uniqueThemes(res.recommendations));
      })
      .catch(() => {
        if (!cancelled) setPersonalizedThemes([]);
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
          setHasFetched(true);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, defaultChildId, limit]);

  const suggestions = useMemo(() => {
    if (mode === "prompt") {
      return buildPromptSuggestions(personalizedThemes, limit);
    }
    return buildTagSuggestions(personalizedThemes, limit);
  }, [mode, personalizedThemes, limit]);

  const title = loading
    ? "Finding fresh ideas..."
    : personalizedThemes.length > 0
      ? "Inspired by your stories"
      : hasFetched
        ? "Idea starters"
        : "Suggested for you";

  if (suggestions.length === 0) return null;

  return (
    <div className="space-y-2">
      <p className="text-sm text-gray-500 font-medium">{title}</p>
      <div className="flex flex-wrap gap-2">
        <AnimatePresence initial={false}>
          {suggestions.map((theme, i) => (
            <motion.button
              key={`${theme}-${i}`}
              className={
                mode === "prompt"
                  ? "px-3 py-2 rounded-full text-sm font-medium bg-primary/10 text-primary border border-primary/25 hover:bg-primary/15 transition-colors text-left"
                  : "px-3 py-1.5 rounded-full text-sm font-medium bg-secondary/10 text-secondary border border-secondary/25 hover:bg-secondary/20 transition-colors"
              }
              onClick={() => onSelect(theme)}
              initial={{ opacity: 0, y: 6, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, y: -4, scale: 0.96 }}
              transition={{ delay: i * 0.05 }}
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.95 }}
            >
              <span className="mr-1">
                {mode === "prompt" ? "✨" : emojiForTheme(theme)}
              </span>
              {theme}
            </motion.button>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
