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
import type { Agent, UpsertAgentPayload } from "@/types/agent";

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

export const agentService = { getAgent, putAgent };
