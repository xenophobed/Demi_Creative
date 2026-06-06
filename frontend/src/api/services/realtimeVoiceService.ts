/**
 * Talk-to-Buddy realtime voice service (#616).
 *
 * Thin wrapper around `POST /api/v1/me/agent/voice/session`. Mirrors the
 * `transcriptionService.ts` pattern: no retries, no auth glue beyond
 * `apiClient`, raw response surfaced unchanged.
 *
 * The WebSocket itself is opened by `useVoiceConversation` (#617) — this
 * service only mints the ephemeral handshake material.
 */

import apiClient from "../client";

export interface VoiceProviderConfig {
  provider: "mock" | "hybrid" | "openai_realtime";
  sample_rate_hz: number;
  audio_format: "pcm16" | "opus";
}

export interface VoiceSessionStartRequest {
  child_id: string;
  /** Optional persona override; falls back to child_profile.voice_persona. */
  persona?: string;
  /** #647: Opt into the WebRTC direct-mode transport when the active
   *  provider supports it (OpenAI Realtime today). Backend silently
   *  degrades to ``transport: "ws"`` for non-OpenAI providers. */
  prefer_webrtc?: boolean;
}

export interface VoiceSessionStartResponse {
  session_id: string;
  ephemeral_token: string;
  /** ISO-8601 timestamp. */
  expires_at: string;
  ws_url: string;
  provider_config: VoiceProviderConfig;
  /** #647: ``ws`` = server-relay broker (default). ``webrtc`` =
   *  browser-direct handshake against OpenAI Realtime. */
  transport?: "ws" | "webrtc";
  /** #647: Ephemeral OpenAI Realtime client secret. Required for the
   *  WebRTC SDP exchange; ignored on the WS path. */
  openai_realtime_client_secret?: string | null;
}

export const realtimeVoiceService = {
  async startSession(
    payload: VoiceSessionStartRequest,
  ): Promise<VoiceSessionStartResponse> {
    // `prefer_webrtc` rides as a query param to match the backend route
    // shape (a query gives the broker a clean opt-in without growing the
    // request body schema for clients that never want WebRTC).
    const url = payload.prefer_webrtc
      ? "/me/agent/voice/session?prefer_webrtc=true"
      : "/me/agent/voice/session";
    const { prefer_webrtc, ...body } = payload;
    void prefer_webrtc;
    const response = await apiClient.post<VoiceSessionStartResponse>(url, body);
    return response.data;
  },
};

export default realtimeVoiceService;
