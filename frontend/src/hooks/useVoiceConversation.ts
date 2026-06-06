/**
 * useVoiceConversation (#617).
 *
 * Glue between the pure reducer (#616) and the browser-side MediaRecorder
 * + WebSocket + AudioContext. All load-bearing logic — mime selection,
 * RMS math, barge-in detection, server-event parsing — lives in
 * `voiceConversationHelpers.ts` so this file stays thin and unit-test
 * scope stays on pure modules.
 *
 * Lifecycle:
 *   start(consentGranted) → mints session via REST → opens WS →
 *   begins MediaRecorder loop (250ms timeslice) → on each chunk,
 *   sends `audio_chunk` frame → on silence-VAD, sends `vad_end` →
 *   broker emits transcripts + audio → we play assembled audio Blob
 *   in an `<audio>` element. Cleanup on unmount stops everything in
 *   the non-negotiable order documented in the plan.
 *
 * Per the plan, no auto-reconnect — single-use token contract. Consumer
 * gets `retry()` which resets to idle so they can call `start()` again
 * (which mints a fresh token).
 */

import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import {
  realtimeVoiceService,
  type VoiceSessionStartResponse,
} from "@/api/services/realtimeVoiceService";
import {
  buildAudioChunkFrame,
  buildSdpExchangeRequest,
  buildWsUrl,
  computeRms,
  detectBargeIn,
  detectSilenceVad,
  detectVoiceCapabilities,
  dispatchForServerEvent,
  parseRealtimeEvent,
  parseServerEvent,
  pickAudioMimeType,
  RTC_HANDSHAKE_BUDGET_MS,
} from "./voiceConversationHelpers";
import {
  voiceConversationReducer,
  type VoiceConversationEvent,
  type VoiceConversationState,
} from "./voiceConversationStateMachine";

export type VoiceErrorKind =
  | "auth"
  | "quota"
  | "safety"
  | "network"
  | "unknown";

export interface VoiceCaption {
  kind: "partial" | "final" | "assistant" | "safety_block";
  text: string;
  /** Only set on `final` — false means safety rejected, true means it passed. */
  safetyPassed?: boolean;
  /** Only set on `assistant` — true on the last delta of a turn. */
  isFinal?: boolean;
}

export interface UseVoiceConversationOptions {
  childId: string;
  persona?: string;
  bargeInRmsThreshold?: number;
  bargeInSustainedMs?: number;
  silenceVadMs?: number;
  /** #647: Ask the backend for the WebRTC direct-mode transport. The
   *  hook still falls back to the WS server-relay path if the RTC
   *  handshake fails within `RTC_HANDSHAKE_BUDGET_MS`. Default false
   *  preserves pre-#647 behavior so the WS path stays the safe default. */
  preferWebRTC?: boolean;
  onCaption?: (caption: VoiceCaption) => void;
  onError?: (kind: VoiceErrorKind, detail?: string) => void;
}

export interface UseVoiceConversationResult {
  state: VoiceConversationState;
  start: (consentGranted: boolean) => Promise<void>;
  end: () => void;
  retry: () => void;
  consentGranted: () => void;
  consentDismissed: () => void;
  partialTranscript: string;
  assistantText: string;
  inputLevel: number;
  /**
   * RMS-derived TTS output level 0..1 (#651). Mirrors `inputLevel` but
   * is sourced from the AnalyserNode wired between the assistant audio
   * element and the AudioContext destination. Used by BuddyOrb to drive
   * the speaking animation. Stays at 0 in environments without the Web
   * Audio API (test/SSR) or when no TTS is currently playing.
   */
  outputLevel: number;
  /**
   * #608 captions auto-show signal. Flips ``true`` the first time a
   * ``safety_block`` event arrives in this session; stays ``true`` for
   * the rest of the session so the kid keeps seeing the fallback
   * sentence on the panel. Reset to ``false`` on the next ``start``.
   *
   * This is a side-channel hint, not a reducer state transition — the
   * voice state machine doesn't pivot on safety_block (we keep the
   * session alive and continue listening). The panel reads this flag
   * to flip ``captionsVisibleOverride`` on TalkToBuddyPanel.
   */
  safetyBlockedSeen: boolean;
  sessionId: string | null;
}

const DEFAULT_BARGE_IN_RMS = 0.04;
const DEFAULT_BARGE_IN_SUSTAINED_MS = 150;
const DEFAULT_SILENCE_VAD_MS = 1500;
const AUDIO_CHUNK_TIMESLICE_MS = 250;
const TTS_END_QUIET_WINDOW_MS = 400;

function nowMs(): number {
  return typeof performance !== "undefined" ? performance.now() : Date.now();
}

function pickAudioContextCtor(): typeof AudioContext | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    AudioContext?: typeof AudioContext;
    webkitAudioContext?: typeof AudioContext;
  };
  return w.AudioContext ?? w.webkitAudioContext ?? null;
}

export function useVoiceConversation(
  options: UseVoiceConversationOptions,
): UseVoiceConversationResult {
  const {
    childId,
    persona,
    bargeInRmsThreshold = DEFAULT_BARGE_IN_RMS,
    bargeInSustainedMs = DEFAULT_BARGE_IN_SUSTAINED_MS,
    silenceVadMs = DEFAULT_SILENCE_VAD_MS,
    preferWebRTC = false,
    onCaption,
    onError,
  } = options;

  const [state, dispatch] = useReducer(
    voiceConversationReducer,
    "idle" as VoiceConversationState,
  );
  const [partialTranscript, setPartialTranscript] = useState("");
  const [assistantText, setAssistantText] = useState("");
  const [inputLevel, setInputLevel] = useState(0);
  const [outputLevel, setOutputLevel] = useState(0);
  // #608 captions auto-show signal. Sticky for the rest of the session
  // once a safety_block is observed; reset on the next start().
  const [safetyBlockedSeen, setSafetyBlockedSeen] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);

  const stateRef = useRef<VoiceConversationState>("idle");
  stateRef.current = state;

  const wsRef = useRef<WebSocket | null>(null);
  // #647: WebRTC peer connection + data channel for the direct-mode path.
  // Both stay null on the WS path so cleanup is a no-op.
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const dcRef = useRef<RTCDataChannel | null>(null);
  // Remote audio analyser node — same shape as outputAnalyserRef on the
  // WS path so BuddyOrb still gets `outputLevel` while the buddy talks.
  const remoteStreamSourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const rafRef = useRef<number | null>(null);
  // Output-side analyser (#651): the assistant's TTS audio element fed
  // through createMediaElementSource → AnalyserNode → destination. RMS
  // from this analyser becomes `outputLevel` so the BuddyOrb can react
  // to the buddy talking, not just the kid talking.
  const outputAnalyserRef = useRef<AnalyserNode | null>(null);
  const outputSourceRef = useRef<MediaElementAudioSourceNode | null>(null);
  const outputRafRef = useRef<number | null>(null);
  const audioElementRef = useRef<HTMLAudioElement | null>(null);
  const blobUrlRef = useRef<string | null>(null);
  const ttsChunksRef = useRef<Uint8Array[]>([]);
  const hasReceivedTtsStartRef = useRef(false);
  const lastTtsChunkAtRef = useRef<number | null>(null);
  const ttsEndTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const seqRef = useRef(0);
  const lastSpeechAtRef = useRef<number | null>(null);
  const firstAboveAtRef = useRef<number | null>(null);
  const sentVadEndRef = useRef(false);

  const send = useCallback(
    (event: VoiceConversationEvent) => dispatch(event),
    [],
  );

  useEffect(() => {
    const env = {
      getUserMedia: navigator?.mediaDevices?.getUserMedia?.bind(
        navigator.mediaDevices,
      ),
      MediaRecorder: typeof MediaRecorder !== "undefined" ? MediaRecorder : undefined,
      WebSocket: typeof WebSocket !== "undefined" ? WebSocket : undefined,
      AudioContext: pickAudioContextCtor() ?? undefined,
      userAgent: navigator?.userAgent,
    };
    const report = detectVoiceCapabilities(env);
    if (!report.supported) {
      dispatch({ type: "markUnsupported" });
    }
  }, []);

  const stopAnalyserLoop = useCallback(() => {
    if (rafRef.current != null) {
      try { cancelAnimationFrame(rafRef.current); } catch { /* ignore */ }
      rafRef.current = null;
    }
  }, []);

  const stopOutputAnalyserLoop = useCallback(() => {
    if (outputRafRef.current != null) {
      try { cancelAnimationFrame(outputRafRef.current); } catch { /* ignore */ }
      outputRafRef.current = null;
    }
    setOutputLevel(0);
  }, []);

  const stopRecorder = useCallback(() => {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      try { recorder.stop(); } catch { /* ignore */ }
    }
    recorderRef.current = null;
  }, []);

  const stopStream = useCallback(() => {
    const stream = streamRef.current;
    if (stream) {
      for (const track of stream.getTracks()) {
        try { track.stop(); } catch { /* ignore */ }
      }
    }
    streamRef.current = null;
  }, []);

  const stopPlayback = useCallback(() => {
    const audio = audioElementRef.current;
    if (audio) {
      try {
        audio.pause();
        audio.removeAttribute("src");
        audio.load();
      } catch { /* ignore */ }
    }
    if (blobUrlRef.current) {
      try { URL.revokeObjectURL(blobUrlRef.current); } catch { /* ignore */ }
      blobUrlRef.current = null;
    }
    ttsChunksRef.current = [];
    hasReceivedTtsStartRef.current = false;
    if (ttsEndTimerRef.current != null) {
      clearTimeout(ttsEndTimerRef.current);
      ttsEndTimerRef.current = null;
    }
  }, []);

  const closeAudioContext = useCallback(() => {
    const ctx = audioCtxRef.current;
    if (ctx) {
      try { analyserRef.current?.disconnect(); } catch { /* ignore */ }
      try { sourceRef.current?.disconnect(); } catch { /* ignore */ }
      try { outputAnalyserRef.current?.disconnect(); } catch { /* ignore */ }
      try { outputSourceRef.current?.disconnect(); } catch { /* ignore */ }
      try { remoteStreamSourceRef.current?.disconnect(); } catch { /* ignore */ }
      ctx.close().catch(() => { /* ignore */ });
    }
    audioCtxRef.current = null;
    analyserRef.current = null;
    sourceRef.current = null;
    outputAnalyserRef.current = null;
    outputSourceRef.current = null;
    remoteStreamSourceRef.current = null;
  }, []);

  const closeRtc = useCallback(() => {
    // #647: tear down WebRTC peer + data channel. Order matters: data
    // channel first (so the model sees a clean shutdown), then the
    // peer connection. Per-track stops live with `stopStream`.
    const dc = dcRef.current;
    if (dc) {
      try { dc.close(); } catch { /* ignore */ }
    }
    dcRef.current = null;
    const pc = pcRef.current;
    if (pc) {
      try { pc.close(); } catch { /* ignore */ }
    }
    pcRef.current = null;
  }, []);

  const closeWebSocket = useCallback((code: number = 1000, reason = "") => {
    const ws = wsRef.current;
    if (ws && ws.readyState !== WebSocket.CLOSED) {
      try { ws.close(code, reason); } catch { /* ignore */ }
    }
    wsRef.current = null;
  }, []);

  const teardown = useCallback(() => {
    stopAnalyserLoop();
    stopOutputAnalyserLoop();
    stopRecorder();
    stopStream();
    stopPlayback();
    closeRtc();
    closeAudioContext();
    closeWebSocket(1000, "teardown");
    seqRef.current = 0;
    lastSpeechAtRef.current = null;
    firstAboveAtRef.current = null;
    sentVadEndRef.current = false;
  }, [stopAnalyserLoop, stopOutputAnalyserLoop, stopRecorder, stopStream, stopPlayback, closeRtc, closeAudioContext, closeWebSocket]);

  useEffect(() => () => teardown(), [teardown]);

  function scheduleTtsEndProbe() {
    if (ttsEndTimerRef.current != null) clearTimeout(ttsEndTimerRef.current);
    ttsEndTimerRef.current = setTimeout(() => {
      const now = nowMs();
      const last = lastTtsChunkAtRef.current ?? now;
      if (now - last >= TTS_END_QUIET_WINDOW_MS) send({ type: "ttsEnd" });
    }, TTS_END_QUIET_WINDOW_MS + 50);
  }

  function startOutputAnalyserLoop() {
    const analyser = outputAnalyserRef.current;
    if (!analyser) return;
    const buf = new Uint8Array(analyser.fftSize);
    const tick = () => {
      const a = outputAnalyserRef.current;
      if (!a) return;
      a.getByteTimeDomainData(buf);
      const rms = computeRms(buf);
      setOutputLevel(rms);
      outputRafRef.current = requestAnimationFrame(tick);
    };
    outputRafRef.current = requestAnimationFrame(tick);
  }

  function ensureOutputAnalyserWired(audio: HTMLAudioElement) {
    // Lazy-wire on the first TTS playback so we don't pay the cost on
    // sessions that never reach speaking. Skip cleanly if Web Audio
    // isn't available (test env, older browsers).
    const ctx = audioCtxRef.current;
    if (!ctx) return;
    if (outputAnalyserRef.current && outputSourceRef.current) return;
    try {
      const source = ctx.createMediaElementSource(audio);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      source.connect(analyser);
      // Keep audible: also connect through to the destination.
      analyser.connect(ctx.destination);
      outputSourceRef.current = source;
      outputAnalyserRef.current = analyser;
    } catch {
      // createMediaElementSource throws if called twice on the same
      // element — that's fine, we already wired it earlier.
    }
  }

  function playAssembledAudio() {
    if (ttsChunksRef.current.length === 0) return;
    const blob = new Blob(ttsChunksRef.current as BlobPart[], { type: "audio/mpeg" });
    ttsChunksRef.current = [];
    if (blobUrlRef.current) {
      try { URL.revokeObjectURL(blobUrlRef.current); } catch { /* ignore */ }
    }
    const url = URL.createObjectURL(blob);
    blobUrlRef.current = url;
    if (!audioElementRef.current) audioElementRef.current = new Audio();
    const audio = audioElementRef.current;
    audio.src = url;
    audio.onended = () => {
      stopOutputAnalyserLoop();
      send({ type: "ttsEnd" });
    };
    ensureOutputAnalyserWired(audio);
    startOutputAnalyserLoop();
    void audio.play().catch(() => {
      onError?.("network", "Audio playback was blocked by the browser");
    });
  }

  function handleServerFrame(raw: string) {
    const event = parseServerEvent(raw);
    if (event.type === "bad_json") return;
    const dispatched = dispatchForServerEvent(event, {
      hasReceivedTtsStart: hasReceivedTtsStartRef.current,
    });
    for (const e of dispatched) {
      if (e.type === "ttsStart") hasReceivedTtsStartRef.current = true;
      send(e);
    }
    switch (event.type) {
      case "partial_transcript":
        setPartialTranscript(event.text);
        onCaption?.({ kind: "partial", text: event.text });
        break;
      case "final_transcript":
        setPartialTranscript("");
        onCaption?.({ kind: "final", text: event.text, safetyPassed: event.safety_passed });
        break;
      case "assistant_text":
        setAssistantText((prev) => prev + event.delta);
        onCaption?.({ kind: "assistant", text: event.delta, isFinal: event.is_final });
        if (event.is_final) setTimeout(playAssembledAudio, 50);
        break;
      case "audio_chunk": {
        try {
          const binary =
            typeof atob === "function"
              ? atob(event.audio_b64)
              : Buffer.from(event.audio_b64, "base64").toString("binary");
          const bytes = new Uint8Array(binary.length);
          for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
          ttsChunksRef.current.push(bytes);
          lastTtsChunkAtRef.current = nowMs();
          scheduleTtsEndProbe();
        } catch {
          onError?.("network", "Failed to decode audio chunk");
        }
        break;
      }
      case "safety_block":
        setAssistantText("");
        setPartialTranscript("");
        // Flip the captions auto-show signal — sticky for the rest of
        // the session so the kid keeps seeing the fallback line on
        // the panel (#608). Reset on the next start().
        setSafetyBlockedSeen(true);
        onCaption?.({ kind: "safety_block", text: event.fallback_text });
        break;
      case "quota_exhausted":
        onError?.("quota", `Voice quota exhausted. Remaining: ${event.seconds_remaining ?? 0}s`);
        break;
      case "error": {
        const kind: VoiceErrorKind = event.code === "auth_failed" ? "auth" : "unknown";
        onError?.(kind, event.message);
        break;
      }
      default:
        break;
    }
  }

  function startAnalyserLoop() {
    const analyser = analyserRef.current;
    if (!analyser) return;
    const buf = new Uint8Array(analyser.fftSize);
    const tick = () => {
      const analyserNode = analyserRef.current;
      if (!analyserNode) return;
      analyserNode.getByteTimeDomainData(buf);
      const rms = computeRms(buf);
      setInputLevel(rms);
      const now = nowMs();
      const currentState = stateRef.current;
      const bargeIn = detectBargeIn({
        state: currentState,
        rms,
        threshold: bargeInRmsThreshold,
        nowMs: now,
        firstAboveAt: firstAboveAtRef.current,
        sustainedMs: bargeInSustainedMs,
      });
      firstAboveAtRef.current = bargeIn.nextFirstAboveAt;
      if (bargeIn.trigger) {
        send({ type: "bargeIn" });
        stopPlayback();
      }
      if (currentState === "listening" && !sentVadEndRef.current) {
        const silence = detectSilenceVad({
          rms,
          threshold: bargeInRmsThreshold,
          nowMs: now,
          lastSpeechAt: lastSpeechAtRef.current,
          silenceMs: silenceVadMs,
        });
        lastSpeechAtRef.current = silence.nextLastSpeechAt;
        if (silence.trigger) {
          sentVadEndRef.current = true;
          const ws = wsRef.current;
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "vad_end", seq: seqRef.current }));
          }
        }
      }
      if (currentState !== "listening") {
        sentVadEndRef.current = false;
        lastSpeechAtRef.current = null;
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
  }

  // #647: WebRTC remote audio → AudioContext analyser. Wires the same
  // analyser-node graph the WS path uses for `outputLevel`, so BuddyOrb
  // keeps reacting to the buddy's voice on the direct-mode transport.
  function wireRemoteTrackToAnalyser(stream: MediaStream) {
    const ctx = audioCtxRef.current;
    if (!ctx) return;
    try {
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      source.connect(analyser);
      // Note: we do NOT connect to ctx.destination — the remote audio
      // element handles playback. Wiring to destination would double the
      // output.
      remoteStreamSourceRef.current = source;
      outputAnalyserRef.current = analyser;
      startOutputAnalyserLoop();
    } catch {
      // Already wired or browser refused — keep going with no analyser.
    }
  }

  // #647: data-channel events → caption + state-machine ticks. The
  // shapes differ from the WS broker but the downstream effects are the
  // same; we reuse `setAssistantText` etc. so the reducer never changes.
  function handleRtcDataChannelMessage(raw: string) {
    const ev = parseRealtimeEvent(raw);
    switch (ev.kind) {
      case "text_delta":
        setAssistantText((prev) => prev + ev.text);
        onCaption?.({ kind: "assistant", text: ev.text, isFinal: false });
        // First text delta acts as the "tts is about to start" signal
        // for the reducer; subsequent deltas are data only.
        if (!hasReceivedTtsStartRef.current) {
          hasReceivedTtsStartRef.current = true;
          send({ type: "ttsStart" });
        }
        send({ type: "assistantTextDelta" });
        break;
      case "audio_chunk":
        // Audio bytes flow over the RTC media track — the data channel
        // delta is informational. We don't buffer it; the remote track
        // is already audible via the <audio> element.
        break;
      case "tool_call":
        // Tool-call dispatch (#658 territory). For the frontend we just
        // surface the call so the panel can flash a "thinking" cue if
        // it wants to; the actual dispatch is the server's job via a
        // side WS. For v2 of #647 we keep this lightweight.
        break;
      case "response_done":
        // Final delta arrived — flag the reducer.
        send({ type: "assistantTextDelta" });
        scheduleTtsEndProbe();
        break;
      case "unknown":
      default:
        break;
    }
  }

  async function tryStartWebRtcPath(
    response: VoiceSessionStartResponse,
  ): Promise<boolean> {
    if (typeof window === "undefined" || typeof RTCPeerConnection === "undefined") {
      return false;
    }
    const clientSecret = response.openai_realtime_client_secret;
    if (!clientSecret) return false;

    const startedAtMs = nowMs();
    let pc: RTCPeerConnection;
    try {
      pc = new RTCPeerConnection({
        iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
      });
    } catch {
      return false;
    }
    pcRef.current = pc;

    // Mic input first — needed for `pc.addTrack` before the offer.
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
        video: false,
      });
    } catch (err) {
      onError?.("auth", err instanceof Error ? err.message : "Mic denied");
      closeRtc();
      return false;
    }
    streamRef.current = stream;

    // Local mic analyser (for `inputLevel` + barge-in / silence-VAD).
    const Ctor = pickAudioContextCtor();
    if (Ctor) {
      const ctx = new Ctor();
      try { await ctx.resume(); } catch { /* ignore */ }
      audioCtxRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      source.connect(analyser);
      sourceRef.current = source;
      analyserRef.current = analyser;
      startAnalyserLoop();
    }

    for (const track of stream.getAudioTracks()) {
      try { pc.addTrack(track, stream); } catch { /* ignore */ }
    }
    try {
      pc.addTransceiver("audio", { direction: "sendrecv" });
    } catch { /* some older browsers; addTrack covers most */ }

    // Remote audio → <audio> element + analyser for BuddyOrb.
    pc.ontrack = (ev) => {
      const remoteStream = ev.streams[0];
      if (!remoteStream) return;
      if (!audioElementRef.current) audioElementRef.current = new Audio();
      const audio = audioElementRef.current;
      audio.srcObject = remoteStream;
      void audio.play().catch(() => {
        onError?.("network", "Audio playback was blocked by the browser");
      });
      wireRemoteTrackToAnalyser(remoteStream);
    };

    // Data channel — tool calls + text deltas. Open BEFORE the offer
    // is created so the SDP includes the m=application section.
    const dc = pc.createDataChannel("oai-events");
    dcRef.current = dc;
    dc.onmessage = (ev) => handleRtcDataChannelMessage(String(ev.data));

    // SDP exchange against OpenAI. Pure helper builds the request shape.
    let offer: RTCSessionDescriptionInit;
    try {
      offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
    } catch {
      closeRtc();
      return false;
    }

    const model = "gpt-realtime-mini";
    const reqShape = buildSdpExchangeRequest(clientSecret, model, offer);

    // The handshake budget is enforced by `Promise.race` — if the SDP
    // exchange or ICE connection hasn't completed in 3s, abort and
    // let the caller retry on WS. This matches `shouldFallbackToWs`'s
    // policy (kept as a pure helper so tests cover the decision).
    const deadlineMs = RTC_HANDSHAKE_BUDGET_MS;

    let answerSdp: string;
    try {
      const ctrl = new AbortController();
      const budget = setTimeout(() => ctrl.abort(), deadlineMs);
      const res = await fetch(reqShape.url, {
        method: "POST",
        headers: reqShape.headers,
        body: reqShape.body,
        signal: ctrl.signal,
      });
      clearTimeout(budget);
      if (!res.ok) {
        closeRtc();
        return false;
      }
      answerSdp = await res.text();
    } catch {
      closeRtc();
      return false;
    }

    try {
      await pc.setRemoteDescription({
        type: "answer",
        sdp: answerSdp,
      });
    } catch {
      closeRtc();
      return false;
    }

    // Wait for the peer connection to reach "connected" within the rest
    // of the budget. If it doesn't, fall back to WS.
    const settled = await new Promise<boolean>((resolve) => {
      const timer = setTimeout(() => {
        const elapsed = nowMs() - startedAtMs;
        if (elapsed >= deadlineMs && pc.connectionState !== "connected") {
          resolve(false);
        } else {
          resolve(true);
        }
      }, Math.max(0, deadlineMs - (nowMs() - startedAtMs)));
      pc.onconnectionstatechange = () => {
        if (pc.connectionState === "connected") {
          clearTimeout(timer);
          resolve(true);
        } else if (pc.connectionState === "failed") {
          clearTimeout(timer);
          resolve(false);
        }
      };
    });

    if (!settled) {
      closeRtc();
      // Surface a brief transition so the panel can show "Switching..."
      // before the WS path takes over. Reusing `sttPartial` would muddy
      // the reducer; instead the panel can listen for this caption.
      onCaption?.({ kind: "partial", text: "Switching..." });
      // Reset state so the WS path can re-grab the mic + analysers.
      stopAnalyserLoop();
      stopStream();
      closeAudioContext();
      return false;
    }

    // Connected — emulate the WS open signal so the reducer reaches
    // `listening` without learning about WebRTC. The mic recorder is not
    // used on this path (RTC sends audio via the peer connection track)
    // — listening + speaking transitions are driven by data-channel
    // text deltas + the local analyser loop.
    send({ type: "wsOpen" });
    return true;
  }

  const start = useCallback(
    async (consentGranted: boolean) => {
      if (!consentGranted) return;
      setPartialTranscript("");
      setAssistantText("");
      setInputLevel(0);
      setOutputLevel(0);
      // #608: reset the captions auto-show signal so a previous
      // session's safety_block doesn't carry over into the new session.
      setSafetyBlockedSeen(false);
      send({ type: "start", consentGranted: true });

      // #647: if the caller opted into WebRTC, request it on the wire.
      // The backend silently degrades to WS for non-OpenAI providers
      // so the hook never needs to special-case the response shape.
      let response: VoiceSessionStartResponse;
      try {
        response = await realtimeVoiceService.startSession({
          child_id: childId,
          persona,
          prefer_webrtc: preferWebRTC || undefined,
        });
      } catch (err) {
        const status = (err as { response?: { status?: number } })?.response?.status;
        const kind: VoiceErrorKind =
          status === 409 ? "auth"
          : status === 429 ? "quota"
          : status === 404 ? "auth"
          : "network";
        onError?.(kind, err instanceof Error ? err.message : String(err));
        send({ type: "streamError" });
        return;
      }
      send({ type: "tokenReceived" });
      setSessionId(response.session_id);

      // #647: branch on the negotiated transport. The WebRTC path is
      // strictly an optimization — any failure path retries once with
      // ``transport: "ws"`` so the UX never loses a session to a
      // handshake glitch.
      if (response.transport === "webrtc" && response.openai_realtime_client_secret) {
        const ok = await tryStartWebRtcPath(response);
        if (ok) return;
        // Fallback into the WS path below using the same response —
        // the broker accepts the same ephemeral_token for either route.
      }

      const wsUrl = buildWsUrl(window.location.origin, response.ws_url, response.ephemeral_token);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      ws.onopen = () => send({ type: "wsOpen" });
      ws.onclose = (ev) => {
        if (ev.code !== 1000) {
          send({ type: "streamError" });
          onError?.("network", `WebSocket closed: ${ev.code}`);
        } else {
          send({ type: "wsClose" });
        }
      };
      ws.onerror = () => {
        send({ type: "streamError" });
        onError?.("network", "WebSocket error");
      };
      ws.onmessage = (ev) => handleServerFrame(ev.data);

      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
          video: false,
        });
      } catch (err) {
        onError?.("auth", err instanceof Error ? err.message : "Mic denied");
        send({ type: "streamError" });
        return;
      }
      streamRef.current = stream;

      const Ctor = pickAudioContextCtor();
      if (Ctor) {
        const ctx = new Ctor();
        try { await ctx.resume(); } catch { /* ignore */ }
        audioCtxRef.current = ctx;
        const source = ctx.createMediaStreamSource(stream);
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 512;
        source.connect(analyser);
        sourceRef.current = source;
        analyserRef.current = analyser;
        startAnalyserLoop();
      }

      const mimeType = pickAudioMimeType((m) => MediaRecorder.isTypeSupported?.(m));
      let recorder: MediaRecorder;
      try {
        recorder = mimeType
          ? new MediaRecorder(stream, { mimeType })
          : new MediaRecorder(stream);
      } catch {
        onError?.("network", "MediaRecorder failed to start");
        send({ type: "streamError" });
        return;
      }
      recorder.ondataavailable = async (ev) => {
        if (!ev.data || ev.data.size === 0) return;
        const arrayBuf = await ev.data.arrayBuffer();
        const seq = seqRef.current++;
        const frame = buildAudioChunkFrame(seq, arrayBuf);
        const wsNow = wsRef.current;
        if (wsNow && wsNow.readyState === WebSocket.OPEN) {
          wsNow.send(JSON.stringify(frame));
        }
      };
      recorderRef.current = recorder;
      recorder.start(AUDIO_CHUNK_TIMESLICE_MS);
    },
    [childId, persona, preferWebRTC, bargeInRmsThreshold, bargeInSustainedMs, silenceVadMs, onCaption, onError, send],
  );

  const end = useCallback(() => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      try { ws.send(JSON.stringify({ type: "client_done" })); } catch { /* ignore */ }
    }
    send({ type: "endRequested" });
  }, [send]);

  const retry = useCallback(() => {
    teardown();
    setPartialTranscript("");
    setAssistantText("");
    setInputLevel(0);
    setOutputLevel(0);
    setSessionId(null);
    send({ type: "reset" });
  }, [send, teardown]);

  const consentGranted = useCallback(() => send({ type: "consentGranted" }), [send]);
  const consentDismissed = useCallback(() => send({ type: "consentDismissed" }), [send]);

  return {
    state,
    start,
    end,
    retry,
    consentGranted,
    consentDismissed,
    partialTranscript,
    assistantText,
    inputLevel,
    outputLevel,
    safetyBlockedSeen,
    sessionId,
  };
}
