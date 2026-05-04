/**
 * PostCard — single hub-post tile for the group feed (#452).
 *
 * Renders the agent persona byline (reused AgentBylineChip from #445),
 * caption (if any), and the ReactionBar from #454. The card is clickable
 * — tapping the title navigates to the source artifact (story / interactive
 * session) so the reader can experience what the buddy made.
 *
 * Privacy: this component reads ONLY from `HubPost` snapshot fields. No
 * users-table data is referenced here, matching the COPPA invariant
 * locked by the contract test in #450.
 */

import { useNavigate } from "react-router-dom";
import AgentBylineChip from "@/components/common/AgentBylineChip";
import ReactionBar from "@/components/hub/ReactionBar";
import type { HubPost } from "@/types/hub";

interface Props {
  post: HubPost;
}

function destinationFor(post: HubPost): string {
  if (post.source_artifact_type === "art_story") {
    return `/story/${post.source_id}`;
  }
  // interactive_story stories live behind the InteractiveStoryPage with
  // a session id — the source_id IS the session id.
  return `/interactive?session=${encodeURIComponent(post.source_id)}`;
}

export default function PostCard({ post }: Props) {
  const navigate = useNavigate();
  const destination = destinationFor(post);

  // Adapt HubPost.byline-shaped fields to the AgentBylineChip's `Agent`
  // contract. We only use the fields the chip actually reads.
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
    <article className="flex flex-col gap-3 rounded-2xl border border-gray-200 bg-white p-4 shadow-sm transition-shadow hover:shadow-md">
      <header className="flex flex-col gap-2">
        <AgentBylineChip agent={bylineAgent} />
        <h3 className="text-base font-semibold text-gray-900">
          {post.source_artifact_type === "interactive_story"
            ? "Interactive story"
            : "Art story"}
        </h3>
      </header>

      {post.caption && (
        <p className="text-sm text-gray-700 line-clamp-3">{post.caption}</p>
      )}

      <div className="flex items-center justify-between gap-2">
        <ReactionBar postId={post.post_id} />
        <button
          type="button"
          className="rounded-md bg-violet-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-violet-700"
          onClick={() => navigate(destination)}
        >
          Read story →
        </button>
      </div>

      <p className="text-xs text-gray-400">
        Posted {new Date(post.created_at).toLocaleDateString()}
      </p>
    </article>
  );
}
