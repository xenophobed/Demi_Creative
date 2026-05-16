/**
 * Pure state-transition helpers for the My Agent chat surface (#510).
 *
 * Lives next to AgentChatPanel so the panel can stay a thin React shell
 * and these decisions ("how do streaming text deltas merge with the
 * settled message?") are unit-testable without mounting React.
 *
 * Parent epic: #436.
 */

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  streaming?: boolean;
}

/**
 * Merge an SSE `thinking` delta into the message list. When the last
 * entry is a streaming assistant message we append the delta to it;
 * otherwise we open a new streaming assistant bubble. Empty deltas are
 * no-ops so consecutive whitespace bursts from the SDK don't double-
 * render.
 */
export function appendAssistantDelta(
  messages: ChatMessage[],
  delta: string,
  nextId: () => string,
): ChatMessage[] {
  if (!delta) return messages;
  const last = messages[messages.length - 1];
  if (last?.role === "assistant" && last.streaming) {
    return messages.map((m, i) =>
      i === messages.length - 1 ? { ...m, text: `${m.text}${delta}` } : m,
    );
  }
  return [
    ...messages,
    { id: nextId(), role: "assistant", text: delta, streaming: true },
  ];
}

/**
 * Finalise the streaming assistant bubble at the tail of the list.
 *  - With a non-empty `text`, replace the last assistant bubble's
 *    text (the canonical reply from the `result` event always wins
 *    over the streamed deltas).
 *  - With an empty `text`, just flip `streaming` off (used by the
 *    `complete` event when the proxy chose to stream the full reply
 *    via `thinking` deltas rather than send a final `result.message`).
 */
export function settleAssistantMessage(
  messages: ChatMessage[],
  text: string,
  nextId: () => string,
): ChatMessage[] {
  if (!text) {
    return messages.map((m) =>
      m.role === "assistant" ? { ...m, streaming: false } : m,
    );
  }
  const last = messages[messages.length - 1];
  if (last?.role === "assistant") {
    return messages.map((m, i) =>
      i === messages.length - 1 ? { ...m, text, streaming: false } : m,
    );
  }
  return [
    ...messages,
    { id: nextId(), role: "assistant", text, streaming: false },
  ];
}
