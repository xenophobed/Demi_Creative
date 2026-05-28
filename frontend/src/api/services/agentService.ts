/**
 * Agent Service — API methods for the buddy persona endpoints (#442).
 *
 * Backend endpoints (#439):
 *   GET  /me/agent?child_id=...   -> Agent or 404
 *   PUT  /me/agent                -> Agent (upserted)
 *
 * apiClient already prefixes /api/v1 — call with bare paths.
 */

import { AxiosError } from "axios";
import apiClient from "../client";
import { consumeSSEStream } from "../utils/sseStream";
import { getFreshAuthHeaders } from "../authUtils";
import type {
  AgentChatMessagesResponse,
  AgentChatSessionListResponse,
  AgentChatSessionSummary,
  StreamCallbacks,
} from "@/types/api";
import type { Agent, AgentChatPayload, UpsertAgentPayload } from "@/types/agent";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v1";

/**
 * Fetch the agent persona for the given child. Resolves to `null` when
 * the server returns 404 (no agent yet for this child profile) so the
 * UI can render the empty/onboarding state without a try/catch.
 */
export async function getAgent(childId: string): Promise<Agent | null> {
  try {
    const r = await apiClient.get<Agent>("/me/agent", {
      params: { child_id: childId },
    });
    return r.data;
  } catch (err) {
    if (
      err instanceof AxiosError &&
      err.response?.status === 404
    ) {
      return null;
    }
    throw err;
  }
}

/**
 * Upsert the agent persona. The server validates avatar whitelist,
 * runs safety checks on agent_name and on free-text titles, and
 * fails closed with 503 when the safety MCP is unavailable. Errors
 * propagate to the caller so the form can map detail.code -> field.
 */
export async function putAgent(payload: UpsertAgentPayload): Promise<Agent> {
  const r = await apiClient.put<Agent>("/me/agent", payload);
  return r.data;
}

export async function streamAgentChat(
  payload: AgentChatPayload,
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  let body: BodyInit;
  let headers: HeadersInit;
  if (payload.image) {
    const form = new FormData();
    form.append("child_id", payload.child_id);
    form.append("message", payload.message);
    if (payload.session_id) form.append("session_id", payload.session_id);
    if (payload.age_group) form.append("age_group", payload.age_group);
    if (payload.interests?.length) form.append("interests", payload.interests.join(","));
    form.append("image", payload.image);
    body = form;
    headers = await getFreshAuthHeaders();
  } else {
    body = JSON.stringify({
      child_id: payload.child_id,
      message: payload.message,
      session_id: payload.session_id ?? undefined,
      age_group: payload.age_group ?? undefined,
      interests: payload.interests?.length ? payload.interests : undefined,
    });
    headers = {
      ...(await getFreshAuthHeaders()),
      "Content-Type": "application/json",
    };
  }

  const response = await fetch(`${API_BASE_URL}/me/agent/chat/stream`, {
    method: "POST",
    headers,
    body,
    signal,
  });
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  await consumeSSEStream(response, callbacks);
}

// ---------------------------------------------------------------------------
// Multi-topic chat sessions (#569). apiClient prefixes /api/v1.
// ---------------------------------------------------------------------------

export async function listAgentSessions(
  childId?: string,
  opts?: { includeArchived?: boolean; limit?: number; offset?: number },
): Promise<AgentChatSessionListResponse> {
  const params: Record<string, string | number | boolean> = {};
  if (childId) params.child_id = childId;
  if (opts?.includeArchived) params.include_archived = true;
  if (opts?.limit != null) params.limit = opts.limit;
  if (opts?.offset != null) params.offset = opts.offset;
  const r = await apiClient.get<AgentChatSessionListResponse>(
    "/me/agent/sessions",
    { params },
  );
  return r.data;
}

export async function getAgentSessionMessages(
  sessionId: string,
  opts?: { limit?: number; beforeCreatedAt?: string },
): Promise<AgentChatMessagesResponse> {
  const params: Record<string, string | number> = {};
  if (opts?.limit != null) params.limit = opts.limit;
  if (opts?.beforeCreatedAt) params.before_created_at = opts.beforeCreatedAt;
  const r = await apiClient.get<AgentChatMessagesResponse>(
    `/me/agent/sessions/${sessionId}/messages`,
    { params },
  );
  return r.data;
}

export async function createAgentSession(
  childId: string,
  title?: string,
): Promise<AgentChatSessionSummary> {
  const r = await apiClient.post<AgentChatSessionSummary>(
    "/me/agent/sessions",
    { child_id: childId, title: title ?? undefined },
  );
  return r.data;
}

export async function renameAgentSession(
  sessionId: string,
  title: string,
): Promise<AgentChatSessionSummary> {
  const r = await apiClient.patch<AgentChatSessionSummary>(
    `/me/agent/sessions/${sessionId}`,
    { title },
  );
  return r.data;
}

export async function archiveAgentSession(
  sessionId: string,
  archived: boolean,
): Promise<AgentChatSessionSummary> {
  const r = await apiClient.patch<AgentChatSessionSummary>(
    `/me/agent/sessions/${sessionId}`,
    { archived },
  );
  return r.data;
}

export async function deleteAgentSession(sessionId: string): Promise<void> {
  await apiClient.delete(`/me/agent/sessions/${sessionId}`);
}

export const agentService = {
  getAgent,
  putAgent,
  streamAgentChat,
  listAgentSessions,
  getAgentSessionMessages,
  createAgentSession,
  renameAgentSession,
  archiveAgentSession,
  deleteAgentSession,
};
