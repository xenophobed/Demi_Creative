/**
 * Voice session telemetry — client emit layer (#609 Phase D).
 *
 * Mirrors the backend `voice_telemetry` module: a small set of typed,
 * PII-free events for the Talk-to-Buddy realtime voice surface. The
 * backend broker is the authoritative source for session lifecycle (it
 * owns the DB row + safety verdicts); these client events add the
 * user-PERCEIVED view — e.g. time-to-first-audio as the kid's device
 * actually heard it, which can differ from the server's forward time.
 *
 * Design rules (PRD §3.16 — child safety):
 *   - PII-free by construction. Payloads carry IDs, durations, and
 *     bounded categorical fields ONLY. No transcript text, no audio.
 *   - Fire-and-forget. `emit` never throws — a dropped metric must
 *     never break a live voice turn.
 *   - Pluggable sink. The default routes to `console.debug` (visible in
 *     dev, harmless in prod). Wire a real analytics client later via
 *     `setVoiceTelemetrySink` without touching call sites.
 */

export type VoiceTelemetryEvent =
  | {
      event: "voice_session_started";
      sessionId: string;
      provider?: string;
      ageGroup?: string;
      agentId?: string;
    }
  | {
      event: "voice_session_ended";
      sessionId: string;
      durationSeconds: number;
      endedReason: string;
    }
  | {
      event: "voice_session_safety_rejection";
      sessionId: string;
      direction: "utterance" | "reply" | "unknown";
      category?: string;
    }
  | {
      event: "voice_session_launch_flow_emitted";
      sessionId: string;
      flow: string;
    }
  | {
      event: "voice_session_first_audio_ms";
      sessionId: string;
      firstAudioMs: number;
    };

export type VoiceTelemetrySink = (event: VoiceTelemetryEvent) => void;

function defaultSink(event: VoiceTelemetryEvent): void {
  // Dev-visible, prod-harmless. The integration seam for a real
  // analytics provider (PostHog/GA/etc.) is `setVoiceTelemetrySink`.
  if (typeof console !== "undefined" && typeof console.debug === "function") {
    console.debug("[voice-telemetry]", event.event, event);
  }
}

let sink: VoiceTelemetrySink = defaultSink;

/**
 * Swap the telemetry sink (e.g. install a real analytics client, or a
 * spy in tests). Pass `null` to restore the default console sink.
 */
export function setVoiceTelemetrySink(next: VoiceTelemetrySink | null): void {
  sink = next ?? defaultSink;
}

function emit(event: VoiceTelemetryEvent): void {
  try {
    sink(event);
  } catch {
    // Telemetry must never break a voice turn — swallow sink errors.
  }
}

const VALID_DIRECTIONS = new Set(["utterance", "reply"]);

export const voiceTelemetry = {
  sessionStarted(args: {
    sessionId: string;
    provider?: string;
    ageGroup?: string;
    agentId?: string;
  }): void {
    emit({ event: "voice_session_started", ...args });
  },

  sessionEnded(args: {
    sessionId: string;
    durationSeconds: number;
    endedReason: string;
  }): void {
    emit({
      event: "voice_session_ended",
      sessionId: args.sessionId,
      durationSeconds: Math.max(0, Math.round(args.durationSeconds)),
      endedReason: args.endedReason,
    });
  },

  safetyRejection(args: {
    sessionId: string;
    direction: string;
    category?: string;
  }): void {
    emit({
      event: "voice_session_safety_rejection",
      sessionId: args.sessionId,
      // Collapse any unexpected value so a wiring bug can't push a
      // free-form (possibly content-derived) string downstream.
      direction: VALID_DIRECTIONS.has(args.direction)
        ? (args.direction as "utterance" | "reply")
        : "unknown",
      category: args.category,
    });
  },

  launchFlowEmitted(args: { sessionId: string; flow: string }): void {
    emit({ event: "voice_session_launch_flow_emitted", ...args });
  },

  firstAudioMs(args: { sessionId: string; firstAudioMs: number }): void {
    emit({
      event: "voice_session_first_audio_ms",
      sessionId: args.sessionId,
      firstAudioMs: Math.max(0, Math.round(args.firstAudioMs)),
    });
  },
};
