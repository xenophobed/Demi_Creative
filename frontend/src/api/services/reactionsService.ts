/**
 * Reactions Service — wrapper for the hub-post reactions endpoints (#454).
 *
 * Backend contract:
 *   POST /hub/posts/{post_id}/reactions { reaction_type } -> ReactionToggleResponse
 *   GET  /hub/posts/{post_id}/reactions                   -> HubReactionResponse
 */

import apiClient from "../client";

export type ReactionType = "heart" | "star" | "wow";

export interface ReactionCounts {
  heart: number;
  star: number;
  wow: number;
}

export interface ReactionState {
  post_id: string;
  counts: ReactionCounts;
  viewer_reactions: ReactionType[];
}

export interface ReactionToggleResult extends ReactionState {
  reaction_type: ReactionType;
  active: boolean;
}

export async function toggleReaction(
  postId: string,
  reactionType: ReactionType,
): Promise<ReactionToggleResult> {
  const r = await apiClient.post<ReactionToggleResult>(
    `/hub/posts/${postId}/reactions`,
    { reaction_type: reactionType },
  );
  return r.data;
}

export async function getReactions(postId: string): Promise<ReactionState> {
  const r = await apiClient.get<ReactionState>(`/hub/posts/${postId}/reactions`);
  return r.data;
}

export const reactionsService = { toggleReaction, getReactions };
