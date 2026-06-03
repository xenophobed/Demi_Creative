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
