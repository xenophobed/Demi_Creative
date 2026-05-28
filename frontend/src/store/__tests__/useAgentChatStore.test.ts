import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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

import { agentService } from "@/api/services/agentService";
import useAgentChatStore from "../useAgentChatStore";
import type { AgentChatSessionSummary } from "@/types/api";

const mocked = agentService as unknown as Record<string, ReturnType<typeof vi.fn>>;

function session(
  id: string,
  overrides: Partial<AgentChatSessionSummary> = {},
): AgentChatSessionSummary {
  return {
    session_id: id,
    child_id: "c1",
    title: id,
    last_message_preview: "",
    archived_at: null,
    created_at: "2026-01-01T00:00:00",
    updated_at: "2026-01-01T00:00:00",
    ...overrides,
  };
}

beforeEach(() => {
  useAgentChatStore.getState().reset();
});

afterEach(() => {
  Object.values(mocked).forEach((fn) => fn.mockReset());
});

describe("loadSessions", () => {
  it("populates and sorts sessions by updated_at desc", async () => {
    mocked.listAgentSessions.mockResolvedValueOnce({
      sessions: [
        session("a", { updated_at: "2026-01-01T00:00:00" }),
        session("b", { updated_at: "2026-03-01T00:00:00" }),
      ],
    });
    await useAgentChatStore.getState().loadSessions("c1");
    const ids = useAgentChatStore.getState().sessions.map((s) => s.session_id);
    expect(ids).toEqual(["b", "a"]);
  });

  it("records an error message on failure", async () => {
    mocked.listAgentSessions.mockRejectedValueOnce(new Error("boom"));
    await expect(
      useAgentChatStore.getState().loadSessions("c1"),
    ).rejects.toThrow("boom");
    expect(useAgentChatStore.getState().error).toBe("boom");
  });
});

describe("selectSession", () => {
  it("loads messages and sets currentSessionId", async () => {
    mocked.getAgentSessionMessages.mockResolvedValueOnce({
      session_id: "s1",
      messages: [
        { message_id: "m1", role: "user", text: "hi", result_metadata: {}, created_at: "t1" },
        { message_id: "m2", role: "assistant", text: "hello", result_metadata: {}, created_at: "t2" },
      ],
    });
    await useAgentChatStore.getState().selectSession("s1");
    const st = useAgentChatStore.getState();
    expect(st.currentSessionId).toBe("s1");
    expect(st.messages.map((m) => m.text)).toEqual(["hi", "hello"]);
  });
});

describe("newSession", () => {
  it("prepends the created session, selects it, and clears messages", async () => {
    useAgentChatStore.setState({
      sessions: [session("old")],
      messages: [{ id: "x", role: "user", text: "stale" }],
    });
    mocked.createAgentSession.mockResolvedValueOnce(session("new"));
    const created = await useAgentChatStore.getState().newSession("c1");
    const st = useAgentChatStore.getState();
    expect(created.session_id).toBe("new");
    expect(st.sessions[0].session_id).toBe("new");
    expect(st.currentSessionId).toBe("new");
    expect(st.messages).toEqual([]);
  });
});

describe("renameSession", () => {
  it("optimistically updates then commits server value", async () => {
    useAgentChatStore.setState({ sessions: [session("s1", { title: "old" })] });
    mocked.renameAgentSession.mockResolvedValueOnce(session("s1", { title: "New Title" }));
    await useAgentChatStore.getState().renameSession("s1", "New Title");
    expect(useAgentChatStore.getState().sessions[0].title).toBe("New Title");
  });

  it("rolls back on failure", async () => {
    useAgentChatStore.setState({ sessions: [session("s1", { title: "old" })] });
    mocked.renameAgentSession.mockRejectedValueOnce(new Error("nope"));
    await expect(
      useAgentChatStore.getState().renameSession("s1", "bad"),
    ).rejects.toThrow("nope");
    expect(useAgentChatStore.getState().sessions[0].title).toBe("old");
  });
});

describe("archiveSession", () => {
  it("optimistically removes an archived session from the list", async () => {
    useAgentChatStore.setState({ sessions: [session("s1"), session("s2")] });
    mocked.archiveAgentSession.mockResolvedValueOnce(session("s1", { archived_at: "now" }));
    await useAgentChatStore.getState().archiveSession("s1", true);
    const ids = useAgentChatStore.getState().sessions.map((s) => s.session_id);
    expect(ids).toEqual(["s2"]);
  });

  it("rolls back on failure", async () => {
    useAgentChatStore.setState({ sessions: [session("s1"), session("s2")] });
    mocked.archiveAgentSession.mockRejectedValueOnce(new Error("x"));
    await expect(
      useAgentChatStore.getState().archiveSession("s1", true),
    ).rejects.toThrow("x");
    expect(useAgentChatStore.getState().sessions.map((s) => s.session_id)).toEqual([
      "s1",
      "s2",
    ]);
  });
});

describe("deleteSession", () => {
  it("removes the session and falls back to the next when deleting current", async () => {
    useAgentChatStore.setState({
      sessions: [session("s1"), session("s2")],
      currentSessionId: "s1",
      messages: [{ id: "m", role: "user", text: "hi" }],
    });
    mocked.deleteAgentSession.mockResolvedValueOnce(undefined);
    mocked.getAgentSessionMessages.mockResolvedValueOnce({
      session_id: "s2",
      messages: [],
    });
    await useAgentChatStore.getState().deleteSession("s1");
    const st = useAgentChatStore.getState();
    expect(st.sessions.map((s) => s.session_id)).toEqual(["s2"]);
    expect(st.currentSessionId).toBe("s2");
  });

  it("falls back to null when the last session is deleted", async () => {
    useAgentChatStore.setState({
      sessions: [session("only")],
      currentSessionId: "only",
    });
    mocked.deleteAgentSession.mockResolvedValueOnce(undefined);
    await useAgentChatStore.getState().deleteSession("only");
    const st = useAgentChatStore.getState();
    expect(st.sessions).toEqual([]);
    expect(st.currentSessionId).toBeNull();
    expect(st.messages).toEqual([]);
  });

  it("rolls back on failure", async () => {
    useAgentChatStore.setState({
      sessions: [session("s1"), session("s2")],
      currentSessionId: "s1",
    });
    mocked.deleteAgentSession.mockRejectedValueOnce(new Error("fail"));
    await expect(
      useAgentChatStore.getState().deleteSession("s1"),
    ).rejects.toThrow("fail");
    expect(useAgentChatStore.getState().sessions.map((s) => s.session_id)).toEqual([
      "s1",
      "s2",
    ]);
  });
});

describe("streaming pipeline", () => {
  it("appends user message, streams deltas, then settles", () => {
    const store = useAgentChatStore.getState();
    store.appendUserMessage("hello buddy");
    store.appendStreamingDelta("Hi ");
    store.appendStreamingDelta("there!");
    let msgs = useAgentChatStore.getState().messages;
    expect(msgs.map((m) => m.text)).toEqual(["hello buddy", "Hi there!"]);
    expect(msgs[1].streaming).toBe(true);

    store.settleAssistantMessage("");
    msgs = useAgentChatStore.getState().messages;
    expect(msgs[1].streaming).toBe(false);
  });
});

describe("adoptServerSession", () => {
  it("sets currentSessionId only when none is selected", () => {
    useAgentChatStore.getState().adoptServerSession("server_1");
    expect(useAgentChatStore.getState().currentSessionId).toBe("server_1");
    // Does not clobber an existing selection.
    useAgentChatStore.getState().adoptServerSession("server_2");
    expect(useAgentChatStore.getState().currentSessionId).toBe("server_1");
  });
});

describe("reset", () => {
  it("clears all state", () => {
    useAgentChatStore.setState({
      sessions: [session("s1")],
      currentSessionId: "s1",
      messages: [{ id: "m", role: "user", text: "hi" }],
    });
    useAgentChatStore.getState().reset();
    const st = useAgentChatStore.getState();
    expect(st.sessions).toEqual([]);
    expect(st.currentSessionId).toBeNull();
    expect(st.messages).toEqual([]);
  });
});
