/**
 * Multi-topic buddy chat session store (#569, epic #565 §3.11.8).
 *
 * Owns the session list, the currently-selected session, and that
 * session's message list. The streaming pipeline in AgentChatPanel
 * pushes deltas here via appendStreamingDelta / settleAssistantMessage
 * so the visible history always belongs to exactly one session.
 *
 * Mutations are optimistic where the UX benefits (rename, archive,
 * delete) and roll back to the prior snapshot on API failure — the
 * sidebar should never show a state the server rejected.
 */

import { create } from "zustand";
import { agentService } from "@/api/services/agentService";
import type { AgentChatSessionSummary } from "@/types/api";
import {
  appendAssistantDelta,
  settleAssistantMessage,
  type ChatMessage,
} from "@/pages/MyAgentPage/chatMessageState";

interface AgentChatState {
  sessions: AgentChatSessionSummary[];
  currentSessionId: string | null;
  messages: ChatMessage[];
  isLoadingSessions: boolean;
  isLoadingMessages: boolean;
  error: string | null;

  loadSessions: (childId: string) => Promise<void>;
  selectSession: (sessionId: string) => Promise<void>;
  newSession: (childId: string) => Promise<AgentChatSessionSummary>;
  renameSession: (sessionId: string, title: string) => Promise<void>;
  archiveSession: (sessionId: string, archived: boolean) => Promise<void>;
  deleteSession: (sessionId: string) => Promise<void>;
  // Streaming pipeline hooks (called by AgentChatPanel).
  appendStreamingDelta: (delta: string) => void;
  settleAssistantMessage: (text: string) => void;
  appendUserMessage: (text: string) => void;
  // Realtime voice transcripts merge into the same chat history with
  // a `source: "voice"` tag so the UI can render a mic icon (#619).
  appendVoiceCaption: (turn: { role: "user" | "assistant"; text: string }) => void;
  // Reconcile the server-issued session id from the first SSE `session`
  // event when the turn started without a selected session.
  adoptServerSession: (sessionId: string) => void;
  reset: () => void;
}

let _counter = 0;
function nextId(prefix: string): string {
  _counter += 1;
  return `${prefix}_${Date.now()}_${_counter}`;
}
const nextAssistantId = () => nextId("assistant");

function sortByUpdatedDesc(
  sessions: AgentChatSessionSummary[],
): AgentChatSessionSummary[] {
  return [...sessions].sort((a, b) =>
    (b.updated_at ?? "").localeCompare(a.updated_at ?? ""),
  );
}

const useAgentChatStore = create<AgentChatState>((set, get) => ({
  sessions: [],
  currentSessionId: null,
  messages: [],
  isLoadingSessions: false,
  isLoadingMessages: false,
  error: null,

  loadSessions: async (childId) => {
    set({ isLoadingSessions: true, error: null });
    try {
      const res = await agentService.listAgentSessions(childId);
      set({ sessions: sortByUpdatedDesc(res.sessions) });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : "Failed to load sessions" });
      throw err;
    } finally {
      set({ isLoadingSessions: false });
    }
  },

  selectSession: async (sessionId) => {
    set({ currentSessionId: sessionId, isLoadingMessages: true, error: null });
    try {
      const res = await agentService.getAgentSessionMessages(sessionId);
      // Guard against a race: a newer selectSession may have won while
      // this request was in flight. Only apply if still current.
      if (get().currentSessionId !== sessionId) return;
      set({
        messages: res.messages.map((m) => ({
          id: m.message_id,
          role: m.role,
          text: m.text,
        })),
      });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : "Failed to load messages" });
      throw err;
    } finally {
      if (get().currentSessionId === sessionId) {
        set({ isLoadingMessages: false });
      }
    }
  },

  newSession: async (childId) => {
    const created = await agentService.createAgentSession(childId);
    set((state) => ({
      sessions: [created, ...state.sessions],
      currentSessionId: created.session_id,
      messages: [],
    }));
    return created;
  },

  renameSession: async (sessionId, title) => {
    const prev = get().sessions;
    // Optimistic: reflect the new title immediately.
    set({
      sessions: prev.map((s) =>
        s.session_id === sessionId ? { ...s, title } : s,
      ),
    });
    try {
      const updated = await agentService.renameAgentSession(sessionId, title);
      set((state) => ({
        sessions: state.sessions.map((s) =>
          s.session_id === sessionId ? updated : s,
        ),
      }));
    } catch (err) {
      set({ sessions: prev, error: err instanceof Error ? err.message : "Rename failed" });
      throw err;
    }
  },

  archiveSession: async (sessionId, archived) => {
    const prev = get().sessions;
    // Optimistic: archived sessions drop out of the default list.
    set({
      sessions: archived
        ? prev.filter((s) => s.session_id !== sessionId)
        : prev,
    });
    try {
      await agentService.archiveAgentSession(sessionId, archived);
    } catch (err) {
      set({ sessions: prev, error: err instanceof Error ? err.message : "Archive failed" });
      throw err;
    }
  },

  deleteSession: async (sessionId) => {
    const prev = get().sessions;
    const wasCurrent = get().currentSessionId === sessionId;
    const remaining = prev.filter((s) => s.session_id !== sessionId);
    // Optimistic removal; if we deleted the active session, fall back to
    // the next one in the list (or an empty "new chat" state).
    const nextCurrent = wasCurrent
      ? remaining[0]?.session_id ?? null
      : get().currentSessionId;
    set({
      sessions: remaining,
      currentSessionId: nextCurrent,
      messages: wasCurrent ? [] : get().messages,
    });
    try {
      await agentService.deleteAgentSession(sessionId);
      // If we fell back to another session, load its history.
      if (wasCurrent && nextCurrent) {
        await get().selectSession(nextCurrent);
      }
    } catch (err) {
      set({
        sessions: prev,
        currentSessionId: get().currentSessionId,
        error: err instanceof Error ? err.message : "Delete failed",
      });
      throw err;
    }
  },

  appendUserMessage: (text) => {
    set((state) => ({
      messages: [...state.messages, { id: nextId("user"), role: "user", text }],
    }));
  },

  appendVoiceCaption: (turn) => {
    // Merge a voice-channel transcript into the same message list the
    // text panel renders so parents see one unified chat history (#619).
    set((state) => ({
      messages: [
        ...state.messages,
        {
          id: nextId(`voice_${turn.role}`),
          role: turn.role,
          text: turn.text,
          source: "voice",
        },
      ],
    }));
  },

  appendStreamingDelta: (delta) => {
    set((state) => ({
      messages: appendAssistantDelta(state.messages, delta, nextAssistantId),
    }));
  },

  settleAssistantMessage: (text) => {
    set((state) => ({
      messages: settleAssistantMessage(state.messages, text, nextAssistantId),
    }));
  },

  adoptServerSession: (sessionId) => {
    if (!get().currentSessionId) {
      set({ currentSessionId: sessionId });
    }
  },

  reset: () =>
    set({
      sessions: [],
      currentSessionId: null,
      messages: [],
      isLoadingSessions: false,
      isLoadingMessages: false,
      error: null,
    }),
}));

export default useAgentChatStore;
