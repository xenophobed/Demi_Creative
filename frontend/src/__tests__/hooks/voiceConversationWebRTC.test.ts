/**
 * WebRTC direct-mode transport helpers (#647).
 *
 * These tests lock the pure-helper surface used by `useVoiceConversation`
 * when the session response opts into `transport: "webrtc"`. They cover:
 *
 *  - `buildSdpExchangeRequest` — pure request builder for the SDP offer
 *    POST to OpenAI's realtime endpoint. No network.
 *  - `parseRealtimeEvent` — pure parser for the data-channel JSON
 *    envelopes the model emits. Same shape as the WS server-relay
 *    events so the hook can reuse downstream handling.
 *
 * The hook-level transport switching + RTC handshake-failure fallback
 * are exercised indirectly: we assert that the helpers exposed for the
 * switch (request builder + parser) are deterministic and side-effect-
 * free so a 3s timeout in the hook can branch reliably.
 */

import { describe, expect, it } from "vitest";
import {
  buildSdpExchangeRequest,
  parseRealtimeEvent,
  shouldFallbackToWs,
  type RealtimeDataChannelEvent,
} from "@/hooks/voiceConversationHelpers";

// ---------------------------------------------------------------------------
// buildSdpExchangeRequest
// ---------------------------------------------------------------------------

describe("buildSdpExchangeRequest (#647)", () => {
  const offer: RTCSessionDescriptionInit = {
    type: "offer",
    sdp: "v=0\r\no=- 1 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n",
  };

  it("builds the OpenAI realtime SDP exchange POST", () => {
    const req = buildSdpExchangeRequest(
      "ek_test_secret_abc",
      "gpt-realtime-mini",
      offer,
    );
    expect(req.url).toMatch(/^https:\/\/api\.openai\.com\/v1\/realtime/);
    expect(req.url).toContain("model=gpt-realtime-mini");
    expect(req.headers["Authorization"]).toBe("Bearer ek_test_secret_abc");
    expect(req.headers["Content-Type"]).toBe("application/sdp");
    // Body is the raw SDP — NOT a JSON envelope. OpenAI's realtime
    // endpoint expects ``application/sdp`` per the public docs.
    expect(req.body).toBe(offer.sdp);
  });

  it("URL-encodes the model name for safety", () => {
    const req = buildSdpExchangeRequest(
      "ek_x",
      "gpt realtime/2",
      offer,
    );
    // Either '+' or '%20' is acceptable; we just need the slash escaped
    // so the URL parses on the server side.
    expect(req.url).not.toContain("realtime/2");
    expect(req.url).toContain("gpt");
  });

  it("returns a pure object — no side effects, same input same output", () => {
    const a = buildSdpExchangeRequest("ek_x", "gpt-realtime-mini", offer);
    const b = buildSdpExchangeRequest("ek_x", "gpt-realtime-mini", offer);
    expect(a).toEqual(b);
  });

  it("handles an empty SDP gracefully (caller will not actually use it)", () => {
    const req = buildSdpExchangeRequest("ek_x", "gpt-realtime-mini", {
      type: "offer",
      sdp: "",
    });
    expect(req.body).toBe("");
  });
});

// ---------------------------------------------------------------------------
// parseRealtimeEvent
// ---------------------------------------------------------------------------

describe("parseRealtimeEvent (#647)", () => {
  it("parses response.text.delta as text_delta", () => {
    const ev = parseRealtimeEvent(
      JSON.stringify({ type: "response.text.delta", delta: "hello" }),
    );
    expect(ev.kind).toBe("text_delta");
    expect((ev as Extract<RealtimeDataChannelEvent, { kind: "text_delta" }>).text).toBe(
      "hello",
    );
  });

  it("parses response.audio.delta as audio_chunk with base64 payload", () => {
    const ev = parseRealtimeEvent(
      JSON.stringify({
        type: "response.audio.delta",
        delta: "AAEC",
      }),
    );
    expect(ev.kind).toBe("audio_chunk");
    expect(
      (ev as Extract<RealtimeDataChannelEvent, { kind: "audio_chunk" }>).audioB64,
    ).toBe("AAEC");
  });

  it("parses response.function_call_arguments.done as tool_call", () => {
    const ev = parseRealtimeEvent(
      JSON.stringify({
        type: "response.function_call_arguments.done",
        name: "lookup_story",
        call_id: "call_123",
        arguments: '{"topic":"dinosaurs"}',
      }),
    );
    expect(ev.kind).toBe("tool_call");
    const tc = ev as Extract<RealtimeDataChannelEvent, { kind: "tool_call" }>;
    expect(tc.name).toBe("lookup_story");
    expect(tc.callId).toBe("call_123");
    expect(tc.argumentsJson).toBe('{"topic":"dinosaurs"}');
  });

  it("parses response.done as response_done", () => {
    const ev = parseRealtimeEvent(JSON.stringify({ type: "response.done" }));
    expect(ev.kind).toBe("response_done");
  });

  it("returns kind: 'unknown' for an unrecognized event type", () => {
    const ev = parseRealtimeEvent(
      JSON.stringify({ type: "something.weird.we.do.not.handle" }),
    );
    expect(ev.kind).toBe("unknown");
  });

  it("returns kind: 'unknown' for malformed JSON (never throws)", () => {
    const ev = parseRealtimeEvent("not json at all");
    expect(ev.kind).toBe("unknown");
  });
});

// ---------------------------------------------------------------------------
// shouldFallbackToWs (handshake-timeout decision)
// ---------------------------------------------------------------------------

describe("shouldFallbackToWs (#647)", () => {
  it("fires fallback when elapsed >= 3000ms in 'connecting'", () => {
    expect(
      shouldFallbackToWs({
        startedAtMs: 1000,
        nowMs: 4000,
        rtcConnectionState: "connecting",
      }),
    ).toBe(true);
  });

  it("does not fire fallback when RTC reached 'connected' even after 3s", () => {
    expect(
      shouldFallbackToWs({
        startedAtMs: 1000,
        nowMs: 5000,
        rtcConnectionState: "connected",
      }),
    ).toBe(false);
  });

  it("fires fallback on explicit 'failed' state regardless of elapsed", () => {
    expect(
      shouldFallbackToWs({
        startedAtMs: 1000,
        nowMs: 1100,
        rtcConnectionState: "failed",
      }),
    ).toBe(true);
  });

  it("does not fire fallback before the 3s budget elapses", () => {
    expect(
      shouldFallbackToWs({
        startedAtMs: 1000,
        nowMs: 1500,
        rtcConnectionState: "connecting",
      }),
    ).toBe(false);
  });
});
