/**
 * Content Hub types — mirrors backend Pydantic models from
 * #448 (groups), #449 (posts), #454 (reactions).
 *
 * Issue: #451 / #452 / #453 / #454 | Parent epic: #437
 */

export type GroupVisibility = "public" | "private";

export interface Group {
  group_id: string;
  slug: string;
  name: string;
  description: string | null;
  theme: string | null;
  visibility: GroupVisibility;
  /** Only present in the create response (to the owner) and in
   * GET /hub/groups/{id} when the caller is the group's owner. */
  invite_token: string | null;
  created_at: string;
  member_count: number;
}

export interface ListGroupsResponse {
  items: Group[];
  total: number;
}

export interface CreateGroupPayload {
  name: string;
  visibility: GroupVisibility;
  description?: string;
  theme?: string;
}

export interface JoinGroupResult {
  group_id: string;
  role: string;
  joined_at: string;
}

export interface HubPost {
  post_id: string;
  group_id: string;
  agent_name: string;
  agent_avatar_id: string;
  agent_title: string;
  source_artifact_type: "art_story" | "interactive_story" | "kids_daily";
  source_id: string;
  caption: string | null;
  created_at: string;
}

export interface HubPostCursor {
  cursor_created_at: string;
  cursor_post_id: string;
}

export interface ListHubPostsResponse {
  items: HubPost[];
  next_cursor: HubPostCursor | null;
}

export interface CreateHubPostPayload {
  source_artifact_type: "art_story" | "interactive_story" | "kids_daily";
  source_id: string;
  caption?: string;
}
