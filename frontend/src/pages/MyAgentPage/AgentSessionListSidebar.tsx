/**
 * AgentSessionListSidebar — the multi-topic session list (#570).
 *
 * Reads session state from useAgentChatStore. On wide screens the
 * MyAgentPage renders this as a left column; on small screens it lives
 * behind a slide-over drawer toggled from the chat header.
 *
 * Per-row Rename / Archive / Delete actions are hidden for ages 3-5
 * (destructive controls are parent-territory for the youngest tier,
 * per PRD §3.11.8). Delete always confirms before calling the store.
 *
 * Parent epic: #565
 */

import { useState } from "react";
import { MoreVertical, Pencil, Archive, Trash2, Plus } from "lucide-react";
import useAgentChatStore from "@/store/useAgentChatStore";
import type { AgeGroup } from "@/types/api";
import { relativeTime, sessionDisplayTitle } from "./sessionListHelpers";

interface Props {
  childId: string;
  ageGroup?: AgeGroup | null;
  /** Called after a row is selected — lets the page close the mobile drawer. */
  onSelected?: () => void;
}

export default function AgentSessionListSidebar({
  childId,
  ageGroup,
  onSelected,
}: Props) {
  const sessions = useAgentChatStore((s) => s.sessions);
  const currentSessionId = useAgentChatStore((s) => s.currentSessionId);
  const isLoading = useAgentChatStore((s) => s.isLoadingSessions);
  const selectSession = useAgentChatStore((s) => s.selectSession);
  const newSession = useAgentChatStore((s) => s.newSession);
  const renameSession = useAgentChatStore((s) => s.renameSession);
  const archiveSession = useAgentChatStore((s) => s.archiveSession);
  const deleteSession = useAgentChatStore((s) => s.deleteSession);

  const [menuOpenFor, setMenuOpenFor] = useState<string | null>(null);
  const [confirmDeleteFor, setConfirmDeleteFor] = useState<string | null>(null);

  // Destructive + edit controls are parent-territory for the youngest
  // tier — hide the kebab entirely for ages 3-5.
  const showRowActions = ageGroup !== "3-5";

  const handleSelect = (sessionId: string) => {
    setMenuOpenFor(null);
    if (sessionId !== currentSessionId) {
      void selectSession(sessionId);
    }
    onSelected?.();
  };

  const handleNew = () => {
    setMenuOpenFor(null);
    void newSession(childId);
    onSelected?.();
  };

  const handleRename = (sessionId: string, currentTitle: string) => {
    setMenuOpenFor(null);
    const next = window.prompt("Rename this chat", currentTitle);
    if (next && next.trim()) {
      void renameSession(sessionId, next.trim());
    }
  };

  const handleArchive = (sessionId: string) => {
    setMenuOpenFor(null);
    void archiveSession(sessionId, true);
  };

  const handleDelete = (sessionId: string) => {
    setConfirmDeleteFor(null);
    setMenuOpenFor(null);
    void deleteSession(sessionId);
  };

  return (
    <aside className="flex h-full min-h-0 w-full flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-gray-100 px-3 py-3">
        <h2 className="text-sm font-semibold text-gray-900">Chats</h2>
        <button
          type="button"
          onClick={handleNew}
          className="inline-flex items-center gap-1 rounded-full bg-violet-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-violet-700 focus:outline-none focus:ring-2 focus:ring-violet-500"
          aria-label="New chat"
          title="New chat"
        >
          <Plus size={14} /> New
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {sessions.length === 0 ? (
          <p className="px-2 py-6 text-center text-xs text-gray-500">
            {isLoading ? "Loading chats…" : "No chats yet — say hi to start one"}
          </p>
        ) : (
          <ul className="flex flex-col gap-1">
            {sessions.map((session) => {
              const active = session.session_id === currentSessionId;
              return (
                <li key={session.session_id} className="relative">
                  <button
                    type="button"
                    onClick={() => handleSelect(session.session_id)}
                    className={[
                      "w-full rounded-lg px-3 py-2 text-left transition-colors",
                      active
                        ? "bg-violet-50 ring-1 ring-violet-200"
                        : "hover:bg-gray-50",
                    ].join(" ")}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-medium text-gray-900">
                        {sessionDisplayTitle(session)}
                      </span>
                      <span className="shrink-0 text-[10px] text-gray-400">
                        {relativeTime(session.updated_at)}
                      </span>
                    </div>
                    {session.last_message_preview && (
                      <p className="mt-0.5 truncate text-xs text-gray-500">
                        {session.last_message_preview}
                      </p>
                    )}
                  </button>

                  {showRowActions && (
                    <div className="absolute right-1 top-1.5">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setMenuOpenFor(
                            menuOpenFor === session.session_id
                              ? null
                              : session.session_id,
                          );
                        }}
                        className="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 focus:outline-none focus:ring-2 focus:ring-violet-500"
                        aria-label="Chat options"
                      >
                        <MoreVertical size={15} />
                      </button>

                      {menuOpenFor === session.session_id && (
                        <div className="absolute right-0 z-10 mt-1 w-36 overflow-hidden rounded-lg border border-gray-200 bg-white shadow-lg">
                          <button
                            type="button"
                            onClick={() =>
                              handleRename(
                                session.session_id,
                                sessionDisplayTitle(session),
                              )
                            }
                            className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-gray-700 hover:bg-gray-50"
                          >
                            <Pencil size={13} /> Rename
                          </button>
                          <button
                            type="button"
                            onClick={() => handleArchive(session.session_id)}
                            className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-gray-700 hover:bg-gray-50"
                          >
                            <Archive size={13} /> Archive
                          </button>
                          <button
                            type="button"
                            onClick={() => setConfirmDeleteFor(session.session_id)}
                            className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-red-600 hover:bg-red-50"
                          >
                            <Trash2 size={13} /> Delete
                          </button>
                        </div>
                      )}
                    </div>
                  )}

                  {confirmDeleteFor === session.session_id && (
                    <div className="absolute right-0 z-20 mt-1 w-52 rounded-lg border border-gray-200 bg-white p-3 shadow-lg">
                      <p className="text-xs text-gray-700">
                        Delete this chat? This can't be undone.
                      </p>
                      <div className="mt-2 flex justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => setConfirmDeleteFor(null)}
                          className="rounded-md px-2 py-1 text-xs text-gray-600 hover:bg-gray-100"
                        >
                          Cancel
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDelete(session.session_id)}
                          className="rounded-md bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-700"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </aside>
  );
}
