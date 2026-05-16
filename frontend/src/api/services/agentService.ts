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
import type { StreamCallbacks } from "@/types/api";
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
    form.append("image", payload.image);
    body = form;
    headers = await getFreshAuthHeaders();
  } else {
    body = JSON.stringify({
      child_id: payload.child_id,
      message: payload.message,
      session_id: payload.session_id ?? undefined,
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

export const agentService = { getAgent, putAgent, streamAgentChat };
