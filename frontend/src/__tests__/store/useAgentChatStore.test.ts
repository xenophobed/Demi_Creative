/* @vitest-environment node */

import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/services/agentService", () => ({
  agentService: {
    listAgentSessions: vi.fn(),
    getAgentSessionMessages: vi.fn(),
    createAgentSession: vi.fn(),
    renameAgentSession: vi.fn(),
    archiveAgentSession: vi.fn(),
    deleteAgentSession: vi.fn(),
  },
}));

type AgentChatStore = typeof import("../../store/useAgentChatStore").default;

let useAgentChatStore: AgentChatStore;
let agentService: typeof import("@/api/services/agentService").agentService;

beforeAll(async () => {
  useAgentChatStore = (
    await import("../../store/useAgentChatStore")
  ).default;
  agentService = (await import("@/api/services/agentService")).agentService;
});

beforeEach(() => {
  useAgentChatStore.getState().reset();
});

describe("useAgentChatStore.selectSession modality mapping (#668)", () => {
  it("tags server-loaded voice messages with source=voice", async () => {
    vi.mocked(agentService.getAgentSessionMessages).mockResolvedValueOnce({
      session_id: "s1",
      messages: [
        {
          message_id: "m1",
          role: "user",
          text: "spoken prompt",
          input_modality: "voice",
          output_modality: "text",
          result_metadata: {},
          created_at: "2026-06-13T00:00:00",
        },
        {
          message_id: "m2",
          role: "assistant",
          text: "spoken reply",
          input_modality: "text",
          output_modality: "voice",
          result_metadata: {},
          created_at: "2026-06-13T00:00:01",
        },
        {
          message_id: "m3",
          role: "user",
          text: "typed prompt",
          input_modality: "text",
          output_modality: "text",
          result_metadata: {},
          created_at: "2026-06-13T00:00:02",
        },
      ],
    });

    await useAgentChatStore.getState().selectSession("s1");

    const messages = useAgentChatStore.getState().messages;
    expect(messages.map((m) => m.source)).toEqual([
      "voice",
      "voice",
      undefined,
    ]);
  });
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
