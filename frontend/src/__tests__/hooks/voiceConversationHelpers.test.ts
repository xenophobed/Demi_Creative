import { describe, expect, it } from "vitest";
import {
  buildAudioChunkFrame,
  buildWsUrl,
  computeRms,
  detectBargeIn,
  detectSilenceVad,
  detectVoiceCapabilities,
  dispatchForServerEvent,
  isSafariBelow16,
  parseServerEvent,
  pickAudioMimeType,
  type ServerEvent,
} from "@/hooks/voiceConversationHelpers";

// ---------------------------- detectVoiceCapabilities ---------------------

describe("detectVoiceCapabilities (#617)", () => {
  const fullEnv = {
    getUserMedia: () => undefined,
    MediaRecorder: function MediaRecorder() {},
    WebSocket: function WebSocket() {},
    AudioContext: function AudioContext() {},
    userAgent:
      "Mozilla/5.0 (Macintosh) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
  };

  it("supported when every global is present", () => {
    const report = detectVoiceCapabilities(fullEnv);
    expect(report.supported).toBe(true);
    expect(report.missing).toEqual([]);
  });

  it("flags each missing global by name", () => {
    const report = detectVoiceCapabilities({
      getUserMedia: undefined,
      MediaRecorder: undefined,
      WebSocket: undefined,
      AudioContext: undefined,
    });
    expect(report.supported).toBe(false);
    expect(report.missing).toEqual([
      "getUserMedia",
      "MediaRecorder",
      "WebSocket",
      "AudioContext",
    ]);
  });

  it("flags ios_safari_too_old when UA matches Safari < 16", () => {
    const report = detectVoiceCapabilities({
      ...fullEnv,
      userAgent:
        "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
    });
    expect(report.supported).toBe(false);
    expect(report.missing).toContain("ios_safari_too_old");
  });
});

describe("isSafariBelow16", () => {
  it("matches Safari 15 mobile UA", () => {
    expect(
      isSafariBelow16(
        "Mozilla/5.0 (iPhone) AppleWebKit/605.1.15 Version/15.0 Mobile/15E148 Safari/604.1",
      ),
    ).toBe(true);
  });

  it("doesn't match Safari 16+", () => {
    expect(
      isSafariBelow16(
        "Mozilla/5.0 (iPhone) AppleWebKit/605.1.15 Version/16.4 Mobile/15E148 Safari/604.1",
      ),
    ).toBe(false);
  });

  it("doesn't match Chrome on macOS even though it includes 'Safari'", () => {
    expect(
      isSafariBelow16(
        "Mozilla/5.0 (Macintosh) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
      ),
    ).toBe(false);
  });
});

// ---------------------------- pickAudioMimeType ---------------------------

describe("pickAudioMimeType (#617)", () => {
  it("prefers audio/webm;codecs=opus when supported", () => {
    expect(
      pickAudioMimeType((m) => m === "audio/webm;codecs=opus"),
    ).toBe("audio/webm;codecs=opus");
  });

  it("falls back to audio/mp4 on Safari (no webm)", () => {
    expect(pickAudioMimeType((m) => m === "audio/mp4")).toBe("audio/mp4");
  });

  it("returns empty string when nothing is supported", () => {
    expect(pickAudioMimeType(() => false)).toBe("");
  });

  it("returns empty string when no predicate is supplied", () => {
    expect(pickAudioMimeType()).toBe("");
  });
});

// ---------------------------- computeRms ----------------------------------

describe("computeRms (#617)", () => {
  it("returns 0 for an empty buffer", () => {
    expect(computeRms(new Uint8Array(0))).toBe(0);
  });

  it("returns ~0 for a pure-silence buffer (all 128s)", () => {
    const buf = new Uint8Array(256).fill(128);
    expect(computeRms(buf)).toBe(0);
  });

  it("returns near 1.0 for a max-amplitude square wave", () => {
    const buf = new Uint8Array(256);
    for (let i = 0; i < buf.length; i++) buf[i] = i % 2 === 0 ? 0 : 255;
    expect(computeRms(buf)).toBeGreaterThan(0.9);
  });
});

// ---------------------------- detectBargeIn -------------------------------

describe("detectBargeIn (#617)", () => {
  const baseline = {
    state: "speaking" as const,
    rms: 0.1,
    threshold: 0.04,
    nowMs: 1000,
    firstAboveAt: null,
    sustainedMs: 150,
  };

  it("never triggers when state !== speaking", () => {
    expect(
      detectBargeIn({ ...baseline, state: "listening" }),
    ).toEqual({ trigger: false, nextFirstAboveAt: null });
  });

  it("resets firstAboveAt when input drops below threshold", () => {
    expect(
      detectBargeIn({
        ...baseline,
        rms: 0.01,
        firstAboveAt: 900,
      }),
    ).toEqual({ trigger: false, nextFirstAboveAt: null });
  });

  it("does not trigger on a single-frame spike", () => {
    const result = detectBargeIn({ ...baseline, nowMs: 1000 });
    expect(result.trigger).toBe(false);
    expect(result.nextFirstAboveAt).toBe(1000);
  });

  it("triggers after sustained input above threshold", () => {
    const result = detectBargeIn({
      ...baseline,
      nowMs: 1300,
      firstAboveAt: 1100,
    });
    expect(result.trigger).toBe(true);
  });
});

// ---------------------------- detectSilenceVad ----------------------------

describe("detectSilenceVad (#617)", () => {
  const baseline = {
    rms: 0.005,
    threshold: 0.04,
    nowMs: 5000,
    lastSpeechAt: 3000,
    silenceMs: 1500,
  };

  it("resets lastSpeechAt when speech is detected", () => {
    expect(
      detectSilenceVad({ ...baseline, rms: 0.1 }),
    ).toEqual({ trigger: false, nextLastSpeechAt: 5000 });
  });

  it("never triggers if the user never spoke", () => {
    expect(
      detectSilenceVad({ ...baseline, lastSpeechAt: null }),
    ).toEqual({ trigger: false, nextLastSpeechAt: null });
  });

  it("does not trigger before the silence window elapses", () => {
    expect(
      detectSilenceVad({ ...baseline, nowMs: 4000 }),
    ).toEqual({ trigger: false, nextLastSpeechAt: 3000 });
  });

  it("triggers exactly at the silence window", () => {
    expect(
      detectSilenceVad({ ...baseline, nowMs: 4500 }).trigger,
    ).toBe(true);
  });

  it("triggers after the silence window", () => {
    expect(detectSilenceVad(baseline).trigger).toBe(true);
  });
});

// ---------------------------- buildAudioChunkFrame ------------------------

describe("buildAudioChunkFrame (#617)", () => {
  it("base64-encodes the input bytes", () => {
    const frame = buildAudioChunkFrame(0, new Uint8Array([1, 2, 3]).buffer);
    expect(frame.type).toBe("audio_chunk");
    expect(frame.seq).toBe(0);
    // 1,2,3 → AQID in base64
    expect(frame.audio_b64).toBe("AQID");
  });

  it("threads the sequence number through", () => {
    const frame = buildAudioChunkFrame(42, new Uint8Array([]).buffer);
    expect(frame.seq).toBe(42);
  });

  it("handles a 64KB buffer without throwing argument-list errors", () => {
    const big = new Uint8Array(65_536);
    for (let i = 0; i < big.length; i++) big[i] = i & 0xff;
    const frame = buildAudioChunkFrame(1, big.buffer);
    expect(frame.audio_b64.length).toBeGreaterThan(80_000);
  });
});

// ---------------------------- parseServerEvent ----------------------------

describe("parseServerEvent (#617)", () => {
  it("returns bad_json for malformed input", () => {
    expect(parseServerEvent("not json").type).toBe("bad_json");
    expect(parseServerEvent("[]").type).toBe("bad_json");
    expect(parseServerEvent("null").type).toBe("bad_json");
  });

  it("parses partial_transcript", () => {
    const ev = parseServerEvent(
      JSON.stringify({ type: "partial_transcript", text: "hi", seq: 1 }),
    );
    expect(ev.type).toBe("partial_transcript");
    expect((ev as { text: string }).text).toBe("hi");
  });

  it("parses final_transcript with safety_passed", () => {
    const ev = parseServerEvent(
      JSON.stringify({
        type: "final_transcript",
        text: "tell me a story",
        safety_passed: true,
      }),
    );
    expect(ev.type).toBe("final_transcript");
  });

  it("parses safety_block direction strictly", () => {
    const ev = parseServerEvent(
      JSON.stringify({
        type: "safety_block",
        direction: "reply",
        fallback_text: "let's try something else",
      }),
    );
    expect(ev.type).toBe("safety_block");
    expect((ev as { direction: string }).direction).toBe("reply");
  });

  it("collapses unknown direction values to 'utterance'", () => {
    const ev = parseServerEvent(
      JSON.stringify({
        type: "safety_block",
        direction: "garbage",
        fallback_text: "...",
      }),
    );
    expect((ev as { direction: string }).direction).toBe("utterance");
  });

  it("treats unknown event types as bad_json", () => {
    expect(
      parseServerEvent(JSON.stringify({ type: "made_up", foo: 1 })).type,
    ).toBe("bad_json");
  });
});

// ---------------------------- dispatchForServerEvent ----------------------

describe("dispatchForServerEvent (#617)", () => {
  it("maps partial_transcript → sttPartial", () => {
    const events = dispatchForServerEvent(
      { type: "partial_transcript", text: "hi" } as ServerEvent,
      { hasReceivedTtsStart: false },
    );
    expect(events).toEqual([{ type: "sttPartial" }]);
  });

  it("maps final_transcript → sttFinal", () => {
    const events = dispatchForServerEvent(
      { type: "final_transcript", text: "hi" } as ServerEvent,
      { hasReceivedTtsStart: false },
    );
    expect(events).toEqual([{ type: "sttFinal" }]);
  });

  it("first audio_chunk → ttsStart; subsequent chunks → []", () => {
    const first = dispatchForServerEvent(
      { type: "audio_chunk", seq: 0, audio_b64: "" } as ServerEvent,
      { hasReceivedTtsStart: false },
    );
    expect(first).toEqual([{ type: "ttsStart" }]);
    const subsequent = dispatchForServerEvent(
      { type: "audio_chunk", seq: 1, audio_b64: "" } as ServerEvent,
      { hasReceivedTtsStart: true },
    );
    expect(subsequent).toEqual([]);
  });

  it("safety_block → sttFinal (re-enters listening via reducer)", () => {
    const events = dispatchForServerEvent(
      {
        type: "safety_block",
        direction: "utterance",
        fallback_text: "x",
      } as ServerEvent,
      { hasReceivedTtsStart: false },
    );
    expect(events).toEqual([{ type: "sttFinal" }]);
  });

  it("quota_exhausted and error both → streamError", () => {
    expect(
      dispatchForServerEvent(
        { type: "quota_exhausted" } as ServerEvent,
        { hasReceivedTtsStart: false },
      ),
    ).toEqual([{ type: "streamError" }]);
    expect(
      dispatchForServerEvent(
        { type: "error", code: "x" } as ServerEvent,
        { hasReceivedTtsStart: false },
      ),
    ).toEqual([{ type: "streamError" }]);
  });

  it("bad_json → no dispatch", () => {
    expect(
      dispatchForServerEvent({ type: "bad_json" } as ServerEvent, {
        hasReceivedTtsStart: false,
      }),
    ).toEqual([]);
  });
});

// ---------------------------- buildWsUrl ----------------------------------

describe("buildWsUrl (#617)", () => {
  it("composes wss:// from an https origin + relative path", () => {
    expect(
      buildWsUrl(
        "https://example.com",
        "/api/v1/me/agent/voice/stream",
        "tok123",
      ),
    ).toBe("wss://example.com/api/v1/me/agent/voice/stream?token=tok123");
  });

  it("composes ws:// from an http origin + relative path", () => {
    expect(
      buildWsUrl(
        "http://localhost:8000",
        "/api/v1/me/agent/voice/stream",
        "tok",
      ),
    ).toBe("ws://localhost:8000/api/v1/me/agent/voice/stream?token=tok");
  });

  it("passes through absolute ws:// URLs", () => {
    expect(
      buildWsUrl(
        "https://example.com",
        "wss://other.example.com/voice",
        "x",
      ),
    ).toBe("wss://other.example.com/voice?token=x");
  });

  it("appends with & when path already has a query string", () => {
    expect(
      buildWsUrl("https://e.com", "/voice?room=42", "tok"),
    ).toBe("wss://e.com/voice?room=42&token=tok");
  });

  it("URL-encodes the token", () => {
    expect(
      buildWsUrl("https://e.com", "/voice", "tok+with/special chars"),
    ).toBe("wss://e.com/voice?token=tok%2Bwith%2Fspecial%20chars");
  });
});
