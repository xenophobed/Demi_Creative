/**
 * Agent persona types — mirror of backend AgentResponse / UpsertAgentRequest.
 *
 * Issue: #442 (frontend) | Parent epic: #436
 */

export interface Agent {
  agent_id: string;
  user_id: string;
  child_id: string;
  agent_name: string;
  /** Avatar id from the whitelist, e.g. "emoji:🦊". */
  agent_avatar_id: string;
  agent_title: string;
  /** ISO timestamp string. */
  created_at: string;
  /** ISO timestamp string. */
  updated_at: string;
}

export interface UpsertAgentPayload {
  agent_name: string;
  agent_avatar_id: string;
  agent_title: string;
  child_id: string;
}

/**
 * Server-side rejection codes returned in 4xx error envelopes by
 * PUT /me/agent. The route attaches a 400 with detail.code = one of
 * these so the form can surface inline errors to the right field.
 */
export type AgentErrorCode =
  | "INVALID_AVATAR"
  | "UNSAFE_AGENT_NAME"
  | "INVALID_AGENT_NAME"
  | "UNSAFE_AGENT_TITLE"
  | "INVALID_AGENT_TITLE"
  | "SAFETY_UNAVAILABLE";

export interface AgentErrorDetail {
  code: AgentErrorCode | string;
  reason?: string;
  score?: number;
}
