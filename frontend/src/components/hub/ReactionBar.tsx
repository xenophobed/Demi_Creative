/**
 * ReactionBar — three preset reactions (heart, star, wow) for hub posts.
 *
 * Optimistic toggle: tap increments/decrements immediately, reverts on
 * server error. The full count + viewer-active set returned by the
 * server is the source of truth, so a successful response just snaps
 * to the canonical state.
 *
 * Issue: #454 | Parent epic: #437
 */

import { useEffect, useMemo, useState } from "react";
import {
  reactionsService,
  type ReactionCounts,
  type ReactionState,
  type ReactionType,
} from "@/api/services/reactionsService";

const REACTION_ORDER: ReactionType[] = ["heart", "star", "wow"];

const REACTION_EMOJI: Record<ReactionType, string> = {
  heart: "❤️",
  star: "🌟",
  wow: "🤩",
};

const REACTION_LABEL: Record<ReactionType, string> = {
  heart: "Heart",
  star: "Star",
  wow: "Wow",
};

interface Props {
  postId: string;
  /** Initial state from the feed payload, if available. */
  initialCounts?: ReactionCounts;
  initialViewerReactions?: ReactionType[];
  className?: string;
  disabled?: boolean;
}

const ZERO_COUNTS: ReactionCounts = { heart: 0, star: 0, wow: 0 };

export default function ReactionBar({
  postId,
  initialCounts,
  initialViewerReactions = [],
  className = "",
  disabled,
}: Props) {
  const [state, setState] = useState<ReactionState>({
    post_id: postId,
    counts: initialCounts ?? ZERO_COUNTS,
    viewer_reactions: initialViewerReactions,
  });
  const [pending, setPending] = useState<ReactionType | null>(null);

  // If the parent only knows the post_id (not the counts), fetch lazily.
  useEffect(() => {
    let cancelled = false;
    if (initialCounts !== undefined) return;
    reactionsService
      .getReactions(postId)
      .then((s) => {
        if (!cancelled) setState(s);
      })
      .catch(() => {
        // Stay with the zero state on read failure — the bar is still
        // usable; the next toggle will refresh.
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [postId]);

  const viewerSet = useMemo(
    () => new Set(state.viewer_reactions),
    [state.viewer_reactions],
  );

  const onToggle = async (kind: ReactionType) => {
    if (pending) return;
    setPending(kind);

    // Optimistic update.
    const prev = state;
    const isActive = viewerSet.has(kind);
    const optimistic: ReactionState = {
      post_id: postId,
      counts: {
        ...prev.counts,
        [kind]: Math.max(0, prev.counts[kind] + (isActive ? -1 : 1)),
      },
      viewer_reactions: isActive
        ? prev.viewer_reactions.filter((r) => r !== kind)
        : [...prev.viewer_reactions, kind],
    };
    setState(optimistic);

    try {
      const result = await reactionsService.toggleReaction(postId, kind);
      setState({
        post_id: result.post_id,
        counts: result.counts,
        viewer_reactions: result.viewer_reactions,
      });
    } catch {
      // Revert on error.
      setState(prev);
    } finally {
      setPending(null);
    }
  };

  return (
    <div className={`flex items-center gap-2 ${className}`} role="group" aria-label="Reactions">
      {REACTION_ORDER.map((kind) => {
        const active = viewerSet.has(kind);
        return (
          <button
            key={kind}
            type="button"
            disabled={disabled || pending !== null}
            aria-pressed={active}
            aria-label={REACTION_LABEL[kind]}
            onClick={() => onToggle(kind)}
            className={[
              "inline-flex items-center gap-1 rounded-full border px-2 py-1 text-sm transition-colors",
              "focus:outline-none focus:ring-2 focus:ring-primary/60",
              active
                ? "border-primary bg-primary/10 text-primary-dark"
                : "border-gray-200 bg-white text-gray-600 hover:border-gray-300",
              "disabled:opacity-60",
            ].join(" ")}
          >
            <span aria-hidden="true">{REACTION_EMOJI[kind]}</span>
            <span className="text-xs font-medium tabular-nums">
              {state.counts[kind]}
            </span>
          </button>
        );
      })}
    </div>
  );
}
