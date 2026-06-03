/* @vitest-environment node */

import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/services/agentService", () => ({
  agentService: {
    listAgentSessions: vi.fn(),
    getAgentSession: vi.fn(),
    createAgentSession: vi.fn(),
    renameAgentSession: vi.fn(),
    archiveAgentSession: vi.fn(),
    deleteAgentSession: vi.fn(),
  },
}));

type AgentChatStore = typeof import("../../store/useAgentChatStore").default;

let useAgentChatStore: AgentChatStore;

beforeAll(async () => {
  useAgentChatStore = (
    await import("../../store/useAgentChatStore")
  ).default;
});

beforeEach(() => {
  useAgentChatStore.getState().reset();
});

describe("useAgentChatStore.appendVoiceCaption (#619)", () => {
  it("pushes user-role voice transcripts onto the message list", () => {
    useAgentChatStore.getState().appendVoiceCaption({
      role: "user",
      text: "tell me a story",
    });

    const messages = useAgentChatStore.getState().messages;
    expect(messages.length).toBe(1);
    expect(messages[0].role).toBe("user");
    expect(messages[0].text).toBe("tell me a story");
    expect(messages[0].source).toBe("voice");
  });

  it("pushes assistant-role voice transcripts with the voice tag", () => {
    useAgentChatStore.getState().appendVoiceCaption({
      role: "assistant",
      text: "once upon a time",
    });

    const messages = useAgentChatStore.getState().messages;
    expect(messages[0].role).toBe("assistant");
    expect(messages[0].source).toBe("voice");
  });

  it("preserves ordering when voice + text turns interleave", () => {
    const store = useAgentChatStore.getState();
    store.appendUserMessage("first typed turn");
    store.appendVoiceCaption({ role: "user", text: "second voice turn" });
    store.appendVoiceCaption({ role: "assistant", text: "buddy reply" });
    store.appendUserMessage("fourth typed turn");

    const messages = useAgentChatStore.getState().messages;
    expect(messages.map((m) => m.text)).toEqual([
      "first typed turn",
      "second voice turn",
      "buddy reply",
      "fourth typed turn",
    ]);
    // Source tags differentiate voice from text in the same list.
    expect(messages[0].source).toBeUndefined();
    expect(messages[1].source).toBe("voice");
    expect(messages[2].source).toBe("voice");
    expect(messages[3].source).toBeUndefined();
  });

  it("assigns a unique id to each voice caption", () => {
    const store = useAgentChatStore.getState();
    store.appendVoiceCaption({ role: "user", text: "a" });
    store.appendVoiceCaption({ role: "user", text: "b" });
    const ids = useAgentChatStore.getState().messages.map((m) => m.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
