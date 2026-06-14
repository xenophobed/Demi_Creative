import { afterEach, describe, expect, it } from "vitest";
import {
  setVoiceTelemetrySink,
  voiceTelemetry,
  type VoiceTelemetryEvent,
} from "@/utils/voiceTelemetry";

describe("voiceTelemetry (#609)", () => {
  afterEach(() => {
    setVoiceTelemetrySink(null); // restore default console sink
  });

  function captureEvents() {
    const events: VoiceTelemetryEvent[] = [];
    setVoiceTelemetrySink((e) => events.push(e));
    return events;
  }

  it("emits a started event with the provided fields", () => {
    const events = captureEvents();
    voiceTelemetry.sessionStarted({ sessionId: "s1", provider: "mock" });
    expect(events).toEqual([
      { event: "voice_session_started", sessionId: "s1", provider: "mock" },
    ]);
  });

  it("rounds + floors duration on ended", () => {
    const events = captureEvents();
    voiceTelemetry.sessionEnded({
      sessionId: "s2",
      durationSeconds: 12.7,
      endedReason: "client_closed",
    });
    expect(events[0]).toEqual({
      event: "voice_session_ended",
      sessionId: "s2",
      durationSeconds: 13,
      endedReason: "client_closed",
    });
  });

  it("never emits a negative duration", () => {
    const events = captureEvents();
    voiceTelemetry.sessionEnded({
      sessionId: "s2b",
      durationSeconds: -5,
      endedReason: "ws_1006",
    });
    expect((events[0] as { durationSeconds: number }).durationSeconds).toBe(0);
  });

  it("passes through valid safety directions", () => {
    const events = captureEvents();
    voiceTelemetry.safetyRejection({
      sessionId: "s3",
      direction: "reply",
      category: "reply_blocked",
    });
    expect(events[0]).toEqual({
      event: "voice_session_safety_rejection",
      sessionId: "s3",
      direction: "reply",
      category: "reply_blocked",
    });
  });

  it("collapses an unexpected direction to 'unknown'", () => {
    const events = captureEvents();
    voiceTelemetry.safetyRejection({ sessionId: "s4", direction: "sideways" });
    expect((events[0] as { direction: string }).direction).toBe("unknown");
  });

  it("emits launch-flow + first-audio events", () => {
    const events = captureEvents();
    voiceTelemetry.launchFlowEmitted({ sessionId: "s5", flow: "image_story" });
    voiceTelemetry.firstAudioMs({ sessionId: "s5", firstAudioMs: 812.4 });
    expect(events).toEqual([
      { event: "voice_session_launch_flow_emitted", sessionId: "s5", flow: "image_story" },
      { event: "voice_session_first_audio_ms", sessionId: "s5", firstAudioMs: 812 },
    ]);
  });

  it("is fire-and-forget: a throwing sink never propagates", () => {
    setVoiceTelemetrySink(() => {
      throw new Error("analytics down");
    });
    expect(() =>
      voiceTelemetry.sessionStarted({ sessionId: "s6" }),
    ).not.toThrow();
  });

  it("never carries transcript text on any event (PII guard)", () => {
    const events = captureEvents();
    voiceTelemetry.sessionStarted({ sessionId: "s7", provider: "mock" });
    voiceTelemetry.safetyRejection({ sessionId: "s7", direction: "utterance" });
    for (const e of events) {
      const keys = Object.keys(e);
      expect(keys).not.toContain("text");
      expect(keys).not.toContain("transcript");
    }
  });
});
