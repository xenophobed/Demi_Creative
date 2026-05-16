/**
 * Content Hub service — wraps the backend hub endpoints landed in
 * #448 (groups), #449 (posts).
 *
 * apiClient is configured with baseURL=/api/v1, so we hit bare paths.
 *
 * Issue: #451 | Parent epic: #437
 */

import { AxiosError } from "axios";
import apiClient from "../client";
import type {
  CreateGroupPayload,
  CreateHubPostPayload,
  Group,
  HubPost,
  HubPostCursor,
  JoinGroupResult,
  ListGroupsResponse,
  ListHubPostsResponse,
} from "@/types/hub";

export async function listGroups(): Promise<ListGroupsResponse> {
  const r = await apiClient.get<ListGroupsResponse>("/hub/groups");
  return r.data;
}

export async function createGroup(
  payload: CreateGroupPayload,
): Promise<Group> {
  const r = await apiClient.post<Group>("/hub/groups", payload);
  return r.data;
}

export async function getGroup(groupId: string): Promise<Group | null> {
  try {
    const r = await apiClient.get<Group>(`/hub/groups/${groupId}`);
    return r.data;
  } catch (err) {
    if (err instanceof AxiosError && err.response?.status === 404) return null;
    throw err;
  }
}

export async function joinGroup(
  groupId: string,
  inviteToken?: string,
): Promise<JoinGroupResult> {
  const params = inviteToken ? { invite: inviteToken } : undefined;
  const r = await apiClient.post<JoinGroupResult>(
    `/hub/groups/${groupId}/join`,
    null,
    params ? { params } : undefined,
  );
  return r.data;
}

export async function joinByInvite(inviteToken: string): Promise<Group> {
  const r = await apiClient.post<Group>("/hub/groups/join-by-invite", {
    invite_token: inviteToken,
  });
  return r.data;
}

export async function listGroupPosts(
  groupId: string,
  opts: {
    limit?: number;
    cursor?: HubPostCursor | null;
  } = {},
): Promise<ListHubPostsResponse> {
  const params: Record<string, unknown> = {};
  if (opts.limit) params.limit = opts.limit;
  if (opts.cursor) {
    params.cursor_created_at = opts.cursor.cursor_created_at;
    params.cursor_post_id = opts.cursor.cursor_post_id;
  }
  const r = await apiClient.get<ListHubPostsResponse>(
    `/hub/groups/${groupId}/posts`,
    Object.keys(params).length ? { params } : undefined,
  );
  return r.data;
}

export async function createHubPost(
  groupId: string,
  payload: CreateHubPostPayload,
): Promise<HubPost> {
  const r = await apiClient.post<HubPost>(
    `/hub/groups/${groupId}/posts`,
    payload,
  );
  return r.data;
}

export const hubService = {
  listGroups,
  createGroup,
  getGroup,
  joinGroup,
  joinByInvite,
  listGroupPosts,
  createHubPost,
};
