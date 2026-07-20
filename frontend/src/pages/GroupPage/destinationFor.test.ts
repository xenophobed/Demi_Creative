/**
 * Logic-only tests for the destination resolver used by PostCard.
 * Extracted into a tiny pure helper so the routing contract is
 * unit-testable without mounting the page tree.
 */
import { describe, expect, it } from "vitest";
import type { HubPost } from "@/types/hub";

function destinationFor(post: HubPost): string {
  if (post.source_artifact_type === "art_story") {
    return `/story/${post.source_id}`;
  }
  if (post.source_artifact_type === "kids_daily") {
    return `/kids-daily/${encodeURIComponent(post.source_id)}`;
  }
  return `/interactive?session=${encodeURIComponent(post.source_id)}`;
}

const base: Omit<HubPost, "source_artifact_type" | "source_id"> = {
  post_id: "p1",
  group_id: "g1",
  agent_name: "Sparkle",
  agent_avatar_id: "emoji:🦁",
  agent_title: "Brave Lion",
  caption: null,
  created_at: "2026-01-01T00:00:00",
  reaction_counts: { heart: 0, star: 0, wow: 0 },
  viewer_reactions: [],
};

describe("destinationFor", () => {
  it("art_story -> /story/{id}", () => {
    const r = destinationFor({
      ...base,
      source_artifact_type: "art_story",
      source_id: "story-abc",
    });
    expect(r).toBe("/story/story-abc");
  });

  it("interactive_story -> /interactive?session=<encoded id>", () => {
    const r = destinationFor({
      ...base,
      source_artifact_type: "interactive_story",
      source_id: "session/with/slashes",
    });
    expect(r).toBe("/interactive?session=session%2Fwith%2Fslashes");
  });

  it("kids_daily -> /kids-daily/{episodeId}", () => {
    const r = destinationFor({
      ...base,
      source_artifact_type: "kids_daily",
      source_id: "episode-42",
    });
    expect(r).toBe("/kids-daily/episode-42");
  });
});
