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
  buildWsUrl,
  computeRms,
  detectBargeIn,
  detectSilenceVad,
  detectVoiceCapabilities,
  dispatchForServerEvent,
  parseServerEvent,
  pickAudioMimeType,
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
  const [sessionId, setSessionId] = useState<string | null>(null);

  const stateRef = useRef<VoiceConversationState>("idle");
  stateRef.current = state;

  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const rafRef = useRef<number | null>(null);
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
      ctx.close().catch(() => { /* ignore */ });
    }
    audioCtxRef.current = null;
    analyserRef.current = null;
    sourceRef.current = null;
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
    stopRecorder();
    stopStream();
    stopPlayback();
    closeAudioContext();
    closeWebSocket(1000, "teardown");
    seqRef.current = 0;
    lastSpeechAtRef.current = null;
    firstAboveAtRef.current = null;
    sentVadEndRef.current = false;
  }, [stopAnalyserLoop, stopRecorder, stopStream, stopPlayback, closeAudioContext, closeWebSocket]);

  useEffect(() => () => teardown(), [teardown]);

  function scheduleTtsEndProbe() {
    if (ttsEndTimerRef.current != null) clearTimeout(ttsEndTimerRef.current);
    ttsEndTimerRef.current = setTimeout(() => {
      const now = nowMs();
      const last = lastTtsChunkAtRef.current ?? now;
      if (now - last >= TTS_END_QUIET_WINDOW_MS) send({ type: "ttsEnd" });
    }, TTS_END_QUIET_WINDOW_MS + 50);
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
    audio.onended = () => send({ type: "ttsEnd" });
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

  const start = useCallback(
    async (consentGranted: boolean) => {
      if (!consentGranted) return;
      setPartialTranscript("");
      setAssistantText("");
      setInputLevel(0);
      send({ type: "start", consentGranted: true });

      let response: VoiceSessionStartResponse;
      try {
        response = await realtimeVoiceService.startSession({
          child_id: childId,
          persona,
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
    [childId, persona, bargeInRmsThreshold, bargeInSustainedMs, silenceVadMs, onCaption, onError, send],
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
    sessionId,
  };
}
