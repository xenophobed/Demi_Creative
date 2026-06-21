/**
 * Pure helpers for useVoiceConversation (#617).
 *
 * Extracted so the load-bearing logic — mime selection, RMS math, VAD
 * decisions, WS event parsing, URL composition — can be unit-tested
 * without spinning up MediaRecorder or AudioContext. Same split pattern
 * as cameraStateMachine + cameraErrors (#581) and voiceInputStateMachine
 * (#584).
 */

import type { VoiceConversationEvent } from "./voiceConversationStateMachine";

// ---------------------------------------------------------------------------
// Capability detection
// ---------------------------------------------------------------------------

export interface VoiceCapabilityEnv {
  /** `navigator.mediaDevices.getUserMedia` resolved at hook-mount time. */
  getUserMedia?: unknown;
  /** Global `MediaRecorder` constructor. */
  MediaRecorder?: unknown;
  /** `WebSocket` constructor. */
  WebSocket?: unknown;
  /** `AudioContext` or `webkitAudioContext`. */
  AudioContext?: unknown;
  /** Browser user-agent string, for narrow Safari < 16 exclusion. */
  userAgent?: string;
}

export interface VoiceCapabilityReport {
  supported: boolean;
  missing: string[];
}

/** Returns whether the device meets the bar for realtime voice and
 *  enumerates which globals were missing. iOS Safari < 16 is excluded
 *  because MediaRecorder for `audio/mp4` is unreliable there.
 */
export function detectVoiceCapabilities(
  env: VoiceCapabilityEnv,
): VoiceCapabilityReport {
  const missing: string[] = [];
  if (typeof env.getUserMedia !== "function") missing.push("getUserMedia");
  if (typeof env.MediaRecorder !== "function") missing.push("MediaRecorder");
  if (typeof env.WebSocket !== "function") missing.push("WebSocket");
  if (typeof env.AudioContext !== "function") missing.push("AudioContext");

  if (env.userAgent && isSafariBelow16(env.userAgent)) {
    missing.push("ios_safari_too_old");
  }

  return { supported: missing.length === 0, missing };
}

/** iOS Safari < 16 shipped MediaRecorder with persistent crash bugs.
 *  We exclude it here so the panel falls back to typed chat instead of
 *  failing mid-utterance on the live stream.
 */
export function isSafariBelow16(userAgent: string): boolean {
  if (!/Safari/.test(userAgent) || /Chrome|CriOS|Edg|Firefox/.test(userAgent)) {
    return false;
  }
  const match = userAgent.match(/Version\/(\d+)/);
  if (!match) return false;
  return Number(match[1]) < 16;
}

// ---------------------------------------------------------------------------
// MIME selection
// ---------------------------------------------------------------------------

/** Preference order: opus is best quality+size, mp4 is the Safari
 *  fallback, mpeg is a last-resort container. Returns `""` when nothing
 *  in the list is supported — caller treats as `unsupported`.
 */
export function pickAudioMimeType(
  isTypeSupported?: (mime: string) => boolean,
): string {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4",
    "audio/mpeg",
  ];
  if (!isTypeSupported) return "";
  for (const candidate of candidates) {
    if (isTypeSupported(candidate)) return candidate;
  }
  return "";
}

// ---------------------------------------------------------------------------
// RMS + barge-in math
// ---------------------------------------------------------------------------

/** RMS of an AnalyserNode time-domain Uint8Array (values 0..255 centered
 *  at 128). Returns a normalized 0..1 magnitude. Pure — no DOM.
 */
export function computeRms(buffer: Uint8Array): number {
  if (buffer.length === 0) return 0;
  let sumSquares = 0;
  for (let i = 0; i < buffer.length; i++) {
    const sample = (buffer[i] - 128) / 128;
    sumSquares += sample * sample;
  }
  return Math.sqrt(sumSquares / buffer.length);
}

export interface BargeInArgs {
  state: string;
  rms: number;
  threshold: number;
  nowMs: number;
  firstAboveAt: number | null;
  sustainedMs: number;
}

export interface BargeInResult {
  trigger: boolean;
  nextFirstAboveAt: number | null;
}

/** Barge-in fires when the kid's mic input is sustained above
 *  `threshold` for `sustainedMs` while the buddy is speaking. Single-
 *  frame spikes (e.g. a cough) don't trip it.
 */
export function detectBargeIn(args: BargeInArgs): BargeInResult {
  if (args.state !== "speaking") {
    return { trigger: false, nextFirstAboveAt: null };
  }
  if (args.rms < args.threshold) {
    return { trigger: false, nextFirstAboveAt: null };
  }
  const firstAt = args.firstAboveAt ?? args.nowMs;
  const elapsed = args.nowMs - firstAt;
  if (elapsed >= args.sustainedMs) {
    return { trigger: true, nextFirstAboveAt: null };
  }
  return { trigger: false, nextFirstAboveAt: firstAt };
}

export interface SilenceVadArgs {
  rms: number;
  threshold: number;
  nowMs: number;
  lastSpeechAt: number | null;
  silenceMs: number;
}

export interface SilenceVadResult {
  trigger: boolean;
  nextLastSpeechAt: number | null;
}

/** End-of-utterance detection. Fires `vad_end` after `silenceMs` of
 *  sub-threshold input, but only if the kid actually spoke first
 *  (`lastSpeechAt` must be non-null).
 */
export function detectSilenceVad(args: SilenceVadArgs): SilenceVadResult {
  if (args.rms >= args.threshold) {
    return { trigger: false, nextLastSpeechAt: args.nowMs };
  }
  if (args.lastSpeechAt === null) {
    return { trigger: false, nextLastSpeechAt: null };
  }
  const silentFor = args.nowMs - args.lastSpeechAt;
  if (silentFor >= args.silenceMs) {
    return { trigger: true, nextLastSpeechAt: null };
  }
  return { trigger: false, nextLastSpeechAt: args.lastSpeechAt };
}

// ---------------------------------------------------------------------------
// WS frame builders + parser
// ---------------------------------------------------------------------------

/** Default PCM capture rate (Hz) for the WS-broker path. Matches the GA
 *  OpenAI Realtime session default; overridden by the session response's
 *  `provider_config.sample_rate_hz` when present. #755 */
export const PCM_TARGET_SAMPLE_RATE = 24000;

/** ScriptProcessor buffer size (samples/channel). ~85ms at 24kHz — small
 *  enough for low latency, large enough to keep WS frame overhead modest. */
export const PCM_FRAME_SAMPLES = 2048;

/** Convert a Float32 mono buffer (range [-1,1]) to little-endian 16-bit PCM.
 *  OpenAI Realtime input requires raw pcm16, not the webm/opus container
 *  MediaRecorder emits — this is the core of the #755 fix. Returns the
 *  underlying ArrayBuffer ready for `buildAudioChunkFrame`.
 */
export function floatToPcm16(input: Float32Array): ArrayBuffer {
  const out = new Int16Array(input.length);
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i]));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out.buffer;
}

/** Build the discriminated `audio_chunk` envelope the broker expects.
 *  Uses btoa over a chunked Latin-1 conversion to avoid hitting argument-
 *  list limits on large ArrayBuffers.
 */
export function buildAudioChunkFrame(
  seq: number,
  bytes: ArrayBuffer,
): { type: "audio_chunk"; seq: number; audio_b64: string } {
  const view = new Uint8Array(bytes);
  let binary = "";
  const chunkSize = 0x8000;
  for (let i = 0; i < view.length; i += chunkSize) {
    const slice = view.subarray(i, Math.min(view.length, i + chunkSize));
    binary += String.fromCharCode(...slice);
  }
  // btoa is available in browsers; in Node tests we polyfill via Buffer.
  const audio_b64 =
    typeof btoa === "function"
      ? btoa(binary)
      : Buffer.from(view).toString("base64");
  return { type: "audio_chunk", seq, audio_b64 };
}

export type ServerEvent =
  | { type: "partial_transcript"; text: string; seq?: number }
  | { type: "final_transcript"; text: string; safety_passed?: boolean }
  | { type: "assistant_text"; delta: string; is_final?: boolean }
  | { type: "audio_chunk"; seq: number; audio_b64: string }
  | {
      type: "safety_block";
      direction: "utterance" | "reply";
      fallback_text: string;
    }
  | { type: "quota_exhausted"; seconds_remaining?: number }
  | { type: "error"; code: string; message?: string }
  | { type: "bad_json" };

/** Parse a JSON server frame into a typed event. Malformed JSON returns
 *  a sentinel `{type:'bad_json'}` so the consumer can log + ignore
 *  without a try/catch.
 */
export function parseServerEvent(raw: string): ServerEvent {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return { type: "bad_json" };
  }
  if (typeof parsed !== "object" || parsed === null) {
    return { type: "bad_json" };
  }
  const obj = parsed as Record<string, unknown>;
  const type = obj.type;
  switch (type) {
    case "partial_transcript":
      return {
        type,
        text: String(obj.text ?? ""),
        seq: typeof obj.seq === "number" ? obj.seq : undefined,
      };
    case "final_transcript":
      return {
        type,
        text: String(obj.text ?? ""),
        safety_passed:
          typeof obj.safety_passed === "boolean"
            ? obj.safety_passed
            : undefined,
      };
    case "assistant_text":
      return {
        type,
        delta: String(obj.delta ?? ""),
        is_final:
          typeof obj.is_final === "boolean" ? obj.is_final : undefined,
      };
    case "audio_chunk":
      return {
        type,
        seq: typeof obj.seq === "number" ? obj.seq : 0,
        audio_b64: String(obj.audio_b64 ?? ""),
      };
    case "safety_block":
      return {
        type,
        direction: obj.direction === "reply" ? "reply" : "utterance",
        fallback_text: String(obj.fallback_text ?? ""),
      };
    case "quota_exhausted":
      return {
        type,
        seconds_remaining:
          typeof obj.seconds_remaining === "number"
            ? obj.seconds_remaining
            : undefined,
      };
    case "error":
      return {
        type,
        code: String(obj.code ?? "unknown"),
        message: typeof obj.message === "string" ? obj.message : undefined,
      };
    default:
      return { type: "bad_json" };
  }
}

/** Map a parsed server event to reducer events. Returns 0+ events
 *  because `audio_chunk` only triggers `ttsStart` on the FIRST chunk
 *  of an assistant turn (subsequent chunks are pure data, not state
 *  transitions).
 */
export function dispatchForServerEvent(
  event: ServerEvent,
  ctx: { hasReceivedTtsStart: boolean },
): VoiceConversationEvent[] {
  switch (event.type) {
    case "partial_transcript":
      return [{ type: "sttPartial" }];
    case "final_transcript":
      return [{ type: "sttFinal" }];
    case "assistant_text":
      return [{ type: "assistantTextDelta" }];
    case "audio_chunk":
      // First chunk of an assistant turn → ttsStart; the rest are data.
      return ctx.hasReceivedTtsStart ? [] : [{ type: "ttsStart" }];
    case "safety_block":
      // A blocked utterance returns us to listening via the reducer's
      // sttFinal path so the panel can show the fallback copy and the
      // child can speak again. A blocked reply goes through the same
      // path because the reducer treats both as "transcription done".
      return [{ type: "sttFinal" }];
    case "quota_exhausted":
      return [{ type: "streamError" }];
    case "error":
      return [{ type: "streamError" }];
    case "bad_json":
      return [];
    default:
      return [];
  }
}

// ---------------------------------------------------------------------------
// WebRTC direct-mode transport (#647)
// ---------------------------------------------------------------------------

/** Default OpenAI Realtime SDP exchange endpoint. The browser POSTs its
 *  SDP offer here with the ephemeral client secret as Bearer auth and
 *  gets a `application/sdp` answer back. Kept module-level so tests can
 *  reason about the URL shape without needing OpenAI's environment.
 */
const OPENAI_REALTIME_SDP_URL = "https://api.openai.com/v1/realtime";

export interface SdpExchangeRequest {
  url: string;
  headers: Record<string, string>;
  body: string;
}

/** Build the POST request shape for the OpenAI Realtime SDP handshake
 *  (#647). Pure — caller wraps it in `fetch`. The body is the raw SDP
 *  string with `Content-Type: application/sdp`; OpenAI returns the SDP
 *  answer with the same MIME.
 *
 *  We URL-encode the model name because OpenAI's docs allow slashes in
 *  model identifiers and a raw `/` would split the path.
 */
export function buildSdpExchangeRequest(
  clientSecret: string,
  model: string,
  offer: RTCSessionDescriptionInit,
): SdpExchangeRequest {
  const url = `${OPENAI_REALTIME_SDP_URL}?model=${encodeURIComponent(model)}`;
  return {
    url,
    headers: {
      Authorization: `Bearer ${clientSecret}`,
      "Content-Type": "application/sdp",
    },
    body: offer.sdp ?? "",
  };
}

/** Discriminated event shape emitted by the OpenAI Realtime data channel
 *  (#647). Mirrors the WS server-relay event taxonomy so downstream
 *  caption + audio handling can be reused — the only difference is the
 *  wire format coming off `RTCDataChannel.onmessage` vs `WebSocket
 *  .onmessage`.
 */
export type RealtimeDataChannelEvent =
  | { kind: "text_delta"; text: string }
  | { kind: "audio_chunk"; audioB64: string }
  | { kind: "tool_call"; name: string; callId: string; argumentsJson: string }
  | { kind: "response_done" }
  | { kind: "function_call_arguments_done"; name: string; callId: string; argumentsJson: string }
  | { kind: "unknown" };

/** Parse one data-channel JSON envelope from OpenAI Realtime. Pure —
 *  never throws. Malformed JSON or an unrecognized `type` collapses to
 *  `{kind: "unknown"}` so the caller can log and continue without a
 *  try/catch around every message.
 *
 *  Event-type → kind mapping (locks the contract the hook reuses):
 *    response.text.delta                       → text_delta
 *    response.audio.delta                      → audio_chunk
 *    response.function_call_arguments.done     → tool_call
 *      (alias kept under function_call_arguments_done for symmetry with
 *       the upstream type name; callers should prefer ``tool_call``)
 *    response.done                             → response_done
 *    anything else                             → unknown
 */
export function parseRealtimeEvent(message: string): RealtimeDataChannelEvent {
  let parsed: unknown;
  try {
    parsed = JSON.parse(message);
  } catch {
    return { kind: "unknown" };
  }
  if (typeof parsed !== "object" || parsed === null) {
    return { kind: "unknown" };
  }
  const obj = parsed as Record<string, unknown>;
  const type = obj.type;
  switch (type) {
    case "response.text.delta":
      return {
        kind: "text_delta",
        text: String(obj.delta ?? ""),
      };
    case "response.audio.delta":
      return {
        kind: "audio_chunk",
        audioB64: String(obj.delta ?? ""),
      };
    case "response.function_call_arguments.done":
      return {
        kind: "tool_call",
        name: String(obj.name ?? ""),
        callId: String(obj.call_id ?? ""),
        argumentsJson: String(obj.arguments ?? ""),
      };
    case "response.done":
      return { kind: "response_done" };
    default:
      return { kind: "unknown" };
  }
}

export interface RtcFallbackDecisionArgs {
  startedAtMs: number;
  nowMs: number;
  rtcConnectionState: RTCPeerConnectionState;
}

/** WebRTC handshake-timeout policy (#647). Returns true when the hook
 *  should abort the RTC connection and retry the session with
 *  `transport: "ws"`. Pure — only reads its arguments, no DOM access.
 *
 *  Rules:
 *    - `failed` → fallback immediately. The browser already determined
 *      ICE can't establish a path.
 *    - `connected` → never fallback. Once we're connected the WS path is
 *      strictly worse (extra hop, extra latency).
 *    - any other state (`connecting`, `new`) → fallback once the budget
 *      `RTC_HANDSHAKE_BUDGET_MS` has elapsed. 3s matches the panel's
 *      "Switching..." copy window; longer would feel stuck.
 */
export const RTC_HANDSHAKE_BUDGET_MS = 3000;

export function shouldFallbackToWs(args: RtcFallbackDecisionArgs): boolean {
  if (args.rtcConnectionState === "failed") return true;
  if (args.rtcConnectionState === "connected") return false;
  return args.nowMs - args.startedAtMs >= RTC_HANDSHAKE_BUDGET_MS;
}

// ---------------------------------------------------------------------------
// WS URL composition
// ---------------------------------------------------------------------------

/** Join the broker WS path to the current origin, swapping http→ws and
 *  https→wss. Absolute URLs pass through. Token rides in the query string
 *  per the broker contract (see voice_realtime.py).
 */
export function buildWsUrl(
  baseOrigin: string,
  wsPath: string,
  token: string,
): string {
  // Absolute URL (already starts with ws:// or wss://) → just append token.
  if (/^wss?:\/\//i.test(wsPath)) {
    const sep = wsPath.includes("?") ? "&" : "?";
    return `${wsPath}${sep}token=${encodeURIComponent(token)}`;
  }

  // Relative URL — derive scheme from origin.
  const wsScheme = baseOrigin.startsWith("https://") ? "wss://" : "ws://";
  const host = baseOrigin.replace(/^https?:\/\//, "").replace(/\/$/, "");
  const cleanPath = wsPath.startsWith("/") ? wsPath : `/${wsPath}`;
  const sep = cleanPath.includes("?") ? "&" : "?";
  return `${wsScheme}${host}${cleanPath}${sep}token=${encodeURIComponent(token)}`;
}
