/**
 * Pin the chat message merge semantics for the My Agent chat surface
 * (#510). The proxy streams reply text as multiple `thinking` deltas
 * and then sends a final `result.message` — these helpers decide how
 * those events accumulate into the visible message list.
 *
 * Bugs we want to catch:
 *   - A streaming bubble swallowing a user reply that arrives between
 *     deltas (we don't ship a multi-user chat, but the invariant keeps
 *     the renderer simple).
 *   - The `complete` event re-rendering the bubble's text from the
 *     final `result.message` losing the streamed text when the proxy
 *     emitted only deltas.
 *   - An empty delta opening a phantom assistant bubble.
 */
import { describe, expect, it } from "vitest";
import {
  appendAssistantDelta,
  settleAssistantMessage,
  type ChatMessage,
} from "@/pages/MyAgentPage/chatMessageState";

let counter = 0;
const id = () => `id_${++counter}`;

describe("appendAssistantDelta", () => {
  it("opens a new streaming assistant bubble when the list is empty", () => {
    counter = 0;
    const out = appendAssistantDelta([], "Hi ", id);
    expect(out).toEqual([
      { id: "id_1", role: "assistant", text: "Hi ", streaming: true },
    ]);
  });

  it("extends the trailing streaming assistant bubble", () => {
    counter = 0;
    const first: ChatMessage[] = [
      { id: "x", role: "assistant", text: "Hi", streaming: true },
    ];
    const out = appendAssistantDelta(first, " there!", id);
    expect(out).toEqual([
      { id: "x", role: "assistant", text: "Hi there!", streaming: true },
    ]);
  });

  it("opens a new streaming bubble after a user message", () => {
    counter = 0;
    const initial: ChatMessage[] = [
      { id: "u1", role: "user", text: "hello" },
    ];
    const out = appendAssistantDelta(initial, "Hi!", id);
    expect(out).toHaveLength(2);
    expect(out[1]).toEqual({
      id: "id_1",
      role: "assistant",
      text: "Hi!",
      streaming: true,
    });
  });

  it("opens a new streaming bubble after a settled assistant message", () => {
    counter = 0;
    const initial: ChatMessage[] = [
      { id: "a1", role: "assistant", text: "Hi!", streaming: false },
    ];
    const out = appendAssistantDelta(initial, "More.", id);
    expect(out).toHaveLength(2);
    expect(out[1].streaming).toBe(true);
  });

  it("is a no-op for empty deltas (no phantom bubble)", () => {
    const initial: ChatMessage[] = [
      { id: "u1", role: "user", text: "hi" },
    ];
    const out = appendAssistantDelta(initial, "", id);
    expect(out).toBe(initial);
  });
});

describe("settleAssistantMessage", () => {
  it("replaces the trailing streaming bubble's text with the final reply", () => {
    counter = 0;
    const initial: ChatMessage[] = [
      { id: "u1", role: "user", text: "hi" },
      { id: "a1", role: "assistant", text: "Hi ", streaming: true },
    ];
    const out = settleAssistantMessage(initial, "Hi there, friend!", id);
    expect(out[1]).toEqual({
      id: "a1",
      role: "assistant",
      text: "Hi there, friend!",
      streaming: false,
    });
  });

  it("flips streaming off without overwriting text when settle text is empty", () => {
    const initial: ChatMessage[] = [
      { id: "a1", role: "assistant", text: "Streamed full reply.", streaming: true },
    ];
    const out = settleAssistantMessage(initial, "", id);
    expect(out[0]).toEqual({
      id: "a1",
      role: "assistant",
      text: "Streamed full reply.",
      streaming: false,
    });
  });

  it("opens a new settled bubble when the tail is a user message and we have final text", () => {
    counter = 0;
    const initial: ChatMessage[] = [
      { id: "u1", role: "user", text: "hi" },
    ];
    const out = settleAssistantMessage(initial, "Hi back!", id);
    expect(out).toHaveLength(2);
    expect(out[1]).toEqual({
      id: "id_1",
      role: "assistant",
      text: "Hi back!",
      streaming: false,
    });
  });
});
