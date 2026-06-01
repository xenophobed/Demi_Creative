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
  provider: "mock" | "hybrid";
  sample_rate_hz: number;
  audio_format: "pcm16" | "opus";
}

export interface VoiceSessionStartRequest {
  child_id: string;
  /** Optional persona override; falls back to child_profile.voice_persona. */
  persona?: string;
}

export interface VoiceSessionStartResponse {
  session_id: string;
  ephemeral_token: string;
  /** ISO-8601 timestamp. */
  expires_at: string;
  ws_url: string;
  provider_config: VoiceProviderConfig;
}

export const realtimeVoiceService = {
  async startSession(
    payload: VoiceSessionStartRequest,
  ): Promise<VoiceSessionStartResponse> {
    const response = await apiClient.post<VoiceSessionStartResponse>(
      "/me/agent/voice/session",
      payload,
    );
    return response.data;
  },
};

export default realtimeVoiceService;
