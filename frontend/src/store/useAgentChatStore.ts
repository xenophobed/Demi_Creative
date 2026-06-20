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

  // --- Navigation-surviving streaming state (#727) ---------------------
  // These live in the store (not AgentChatPanel local state) so an
  // in-flight buddy reply keeps running and the progress/result reappear
  // when the user navigates away and back. The AbortController is held at
  // module scope below for the same reason.
  isStreaming: boolean;
  streamStatus: string | null;
  streamTool: string | null;
  streamError: string | null;
  /** The session the active stream belongs to (cross-session bleed guard). */
  streamingSessionId: string | null;

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
  // --- Streaming lifecycle (#727) -------------------------------------
  /** Abort any prior stream, arm a fresh controller, return its signal. */
  beginStream: (sessionId: string | null) => AbortSignal;
  setStreamStatus: (text: string | null) => void;
  setStreamTool: (text: string | null) => void;
  setStreamError: (text: string | null) => void;
  /** Keep the stream's owning session in sync when the server adopts one. */
  adoptStreamSession: (sessionId: string) => void;
  /** Clear progress flags; no-op if a newer stream has taken over. */
  endStream: (signal?: AbortSignal) => void;
  /** User pressed Stop — abort and leave a "stopped" note. */
  cancelStream: (note?: string) => void;
  /** Abort the active stream if the user switched to a different session. */
  abortIfSessionChanged: (currentSessionId: string | null) => void;
  reset: () => void;
}

// Module-scoped so it outlives any single mount of AgentChatPanel — a
// component unmount (navigation) must NOT abort the buddy reply (#727).
let streamAbort: AbortController | null = null;

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
  isStreaming: false,
  streamStatus: null,
  streamTool: null,
  streamError: null,
  streamingSessionId: null,

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
          source:
            m.input_modality === "voice" || m.output_modality === "voice"
              ? "voice"
              : undefined,
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

  beginStream: (sessionId) => {
    // Supersede any prior in-flight stream so two replies never interleave.
    streamAbort?.abort();
    streamAbort = new AbortController();
    set({
      isStreaming: true,
      streamStatus: null,
      streamTool: null,
      streamError: null,
      streamingSessionId: sessionId,
    });
    return streamAbort.signal;
  },

  setStreamStatus: (text) => set({ streamStatus: text }),
  setStreamTool: (text) => set({ streamTool: text }),
  setStreamError: (text) => set({ streamError: text }),

  adoptStreamSession: (sessionId) => set({ streamingSessionId: sessionId }),

  endStream: (signal) => {
    // A newer beginStream() may have replaced the controller while a stale
    // turn was finishing; if so, leave the fresh stream's state intact.
    if (signal && streamAbort && streamAbort.signal !== signal) return;
    streamAbort = null;
    set({
      isStreaming: false,
      streamStatus: null,
      streamTool: null,
      streamingSessionId: null,
    });
  },

  cancelStream: (note) => {
    streamAbort?.abort();
    streamAbort = null;
    set({
      isStreaming: false,
      streamStatus: note ?? null,
      streamTool: null,
      streamingSessionId: null,
    });
  },

  abortIfSessionChanged: (currentSessionId) => {
    const { isStreaming, streamingSessionId } = get();
    if (
      isStreaming &&
      streamingSessionId !== null &&
      currentSessionId !== streamingSessionId
    ) {
      streamAbort?.abort();
      streamAbort = null;
      set({
        isStreaming: false,
        streamStatus: null,
        streamTool: null,
        streamingSessionId: null,
      });
    }
  },

  reset: () => {
    // Active stream belongs to the prior child/session — abort it so it
    // can't write into the next child's freshly-loaded history.
    streamAbort?.abort();
    streamAbort = null;
    set({
      sessions: [],
      currentSessionId: null,
      messages: [],
      isLoadingSessions: false,
      isLoadingMessages: false,
      error: null,
      isStreaming: false,
      streamStatus: null,
      streamTool: null,
      streamError: null,
      streamingSessionId: null,
    });
  },
}));

export default useAgentChatStore;
