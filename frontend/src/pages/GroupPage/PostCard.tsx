/**
 * PostCard — magazine-spread tile for a hub-post (Option A redesign).
 *
 * Layout (top → bottom):
 *   - 16:9 cover band (gradient + emoji icon based on source_artifact_type)
 *     with the agent persona byline floating top-right
 *   - Type chip + relative timestamp row
 *   - Caption (line-clamped to 3) — or a styled placeholder if absent
 *   - Reactions + "Read story →" pill on the same row at the bottom
 *
 * Privacy: still reads ONLY from `HubPost` snapshot fields. The COPPA
 * contract test in #450 stays green.
 *
 * Issue: GroupPage magazine redesign | Parent epic: #437
 */

import { useNavigate } from "react-router-dom";
import AgentBylineChip from "@/components/common/AgentBylineChip";
import ReactionBar from "@/components/hub/ReactionBar";
import type { HubPost } from "@/types/hub";
import { coverFor } from "./groupTheme";

interface Props {
  post: HubPost;
}

function destinationFor(post: HubPost): string {
  if (post.source_artifact_type === "art_story") {
    return `/story/${post.source_id}`;
  }
  if (post.source_artifact_type === "kids_daily") {
    return `/kids-daily/${encodeURIComponent(post.source_id)}`;
  }
  return `/interactive?session=${encodeURIComponent(post.source_id)}`;
}

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  const now = Date.now();
  const seconds = Math.max(0, Math.floor((now - then) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

export default function PostCard({ post }: Props) {
  const navigate = useNavigate();
  const destination = destinationFor(post);
  const cover = coverFor(post.source_artifact_type);

  const bylineAgent = {
    agent_id: "snapshot",
    user_id: "snapshot",
    child_id: "snapshot",
    agent_name: post.agent_name,
    agent_avatar_id: post.agent_avatar_id,
    agent_title: post.agent_title,
    created_at: post.created_at,
    updated_at: post.created_at,
  };

  return (
    <article className="k12-card group flex flex-col overflow-hidden">
      {/* Cover band */}
      <button
        type="button"
        aria-label={`Open ${cover.label}`}
        onClick={() => navigate(destination)}
        className={`relative aspect-video w-full overflow-hidden bg-gradient-to-br ${cover.gradient} text-white`}
      >
        <span
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 flex items-center justify-center text-7xl drop-shadow-md transition-transform duration-300 group-hover:scale-110"
        >
          {cover.icon}
        </span>
        {/* Byline chip floats over the cover */}
        <div className="absolute right-3 top-3 max-w-[80%] rounded-full bg-white/90 px-2 py-1 shadow-sm backdrop-blur-sm">
          <AgentBylineChip agent={bylineAgent} />
        </div>
      </button>

      {/* Body */}
      <div className="flex flex-1 flex-col gap-3 p-5">
        <div className="flex items-center justify-between gap-2 text-xs">
          <span
            className={
              post.source_artifact_type === "art_story"
                ? "rounded-full bg-rose-100 px-2 py-0.5 font-semibold text-rose-700"
                : post.source_artifact_type === "kids_daily"
                  ? "rounded-full bg-emerald-100 px-2 py-0.5 font-semibold text-emerald-700"
                  : "rounded-full bg-secondary/15 px-2 py-0.5 font-semibold text-teal-700"
            }
          >
            {cover.label}
          </span>
          <span className="text-gray-400">{relativeTime(post.created_at)}</span>
        </div>

        {post.caption ? (
          <p className="text-sm leading-relaxed text-gray-800 line-clamp-3">
            {post.caption}
          </p>
        ) : (
          <p className="text-sm italic text-gray-400">
            Tap to read what {post.agent_name} made.
          </p>
        )}

        <div className="mt-auto flex items-center justify-between gap-3 pt-2">
          <ReactionBar postId={post.post_id} />
          <button
            type="button"
            onClick={() => navigate(destination)}
            className="k12-button-primary shrink-0 px-3 py-1.5"
          >
            Read →
          </button>
        </div>
      </div>
    </article>
  );
}
