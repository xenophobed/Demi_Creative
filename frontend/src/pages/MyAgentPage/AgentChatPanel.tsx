import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { ExternalLink, Loader2, Send, Sparkles, X } from "lucide-react";
import { agentService } from "@/api/services/agentService";
import { useLaunchFlowNavigation } from "@/hooks/useLaunchFlowNavigation";
import type { Agent } from "@/types/agent";
import type {
  SSEErrorData,
  SSELaunchFlowData,
  SSEStatusData,
  SSEThinkingData,
  SSEToolResultData,
  SSEToolUseData,
} from "@/types/api";
import {
  appendAssistantDelta,
  settleAssistantMessage,
  type ChatMessage,
} from "./chatMessageState";

interface Props {
  agent: Agent;
  childId: string;
}

function nextMessageId(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

const nextAssistantId = () => nextMessageId("assistant");

function avatarGlyph(agent: Agent): string {
  return agent.agent_avatar_id.startsWith("emoji:")
    ? agent.agent_avatar_id.slice("emoji:".length)
    : "✦";
}

function launchLabel(flow: SSELaunchFlowData): string {
  switch (flow.flow_type) {
    case "image_story":
      return "an image story";
    case "interactive_story":
      return "an interactive story";
    case "kids_daily":
      return "a Kids Daily episode";
    default:
      return "a new creation";
  }
}

function resultMessage(data: unknown): string {
  if (data && typeof data === "object" && "message" in data) {
    const message = (data as { message?: unknown }).message;
    if (typeof message === "string") return message;
  }
  return "";
}

export default function AgentChatPanel({ agent, childId }: Props) {
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [statusText, setStatusText] = useState<string | null>(null);
  const [toolText, setToolText] = useState<string | null>(null);
  const [errorText, setErrorText] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const {
    onLaunchFlow,
    pendingLaunchFlow,
    navigateToPendingFlow,
    resetPendingFlow,
  } = useLaunchFlowNavigation();

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  const heading = useMemo(
    () => `Chat with ${agent.agent_name}`,
    [agent.agent_name],
  );
  const canSend = Boolean(draft.trim()) && !isStreaming && Boolean(childId);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = draft.trim();
    if (!message || isStreaming) return;

    const controller = new AbortController();
    abortRef.current?.abort();
    abortRef.current = controller;
    setDraft("");
    setErrorText(null);
    setToolText(null);
    setStatusText(`${agent.agent_name} is thinking...`);
    resetPendingFlow();
    setMessages((prev) => [
      ...prev,
      { id: nextMessageId("user"), role: "user", text: message },
    ]);
    setIsStreaming(true);

    try {
      await agentService.streamAgentChat(
        { child_id: childId, message, session_id: sessionId },
        {
          onSession: (data) => setSessionId(data.session_id),
          onStatus: (data: SSEStatusData) => setStatusText(data.message),
          onThinking: (data: SSEThinkingData) =>
            setMessages((prev) =>
              appendAssistantDelta(prev, data.content, nextAssistantId),
            ),
          onToolUse: (data: SSEToolUseData) => setToolText(data.message),
          onToolResult: (data: SSEToolResultData) =>
            setToolText(data.message ?? "Specialist finished."),
          onLaunchFlow,
          onResult: (data) =>
            setMessages((prev) =>
              settleAssistantMessage(prev, resultMessage(data), nextAssistantId),
            ),
          onError: (data: SSEErrorData) => {
            setErrorText(data.message);
            setMessages((prev) =>
              settleAssistantMessage(prev, data.message, nextAssistantId),
            );
          },
          onComplete: (data: SSEStatusData) => {
            setStatusText(data.message);
            setMessages((prev) => settleAssistantMessage(prev, "", nextAssistantId));
          },
        },
        controller.signal,
      );
    } catch (err) {
      if (!controller.signal.aborted) {
        const messageText =
          err instanceof Error
            ? err.message
            : "My Agent chat is temporarily unavailable.";
        setErrorText(messageText);
        setMessages((prev) =>
          settleAssistantMessage(prev, messageText, nextAssistantId),
        );
      }
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
      setIsStreaming(false);
    }
  };

  return (
    <section className="flex flex-col gap-4 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <header className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-violet-50 text-2xl">
            {avatarGlyph(agent)}
          </div>
          <div>
            <h2 className="text-base font-semibold text-gray-900">{heading}</h2>
            <p className="text-xs font-medium text-violet-700">
              {agent.agent_title}
            </p>
          </div>
        </div>
        {isStreaming && (
          <Loader2
            size={18}
            className="shrink-0 animate-spin text-violet-600"
            aria-hidden="true"
          />
        )}
      </header>

      <div
        className="flex max-h-80 min-h-32 flex-col gap-3 overflow-y-auto rounded-md border border-gray-100 bg-gray-50 p-3"
        aria-live="polite"
      >
        {messages.length === 0 ? (
          <div className="flex h-24 items-center justify-center text-sm text-gray-500">
            <Sparkles size={16} className="mr-2 text-violet-500" />
            Say hello to begin.
          </div>
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              className={[
                "max-w-[85%] rounded-lg px-3 py-2 text-sm leading-6",
                message.role === "user"
                  ? "self-end bg-violet-600 text-white"
                  : "self-start border border-gray-200 bg-white text-gray-800",
              ].join(" ")}
            >
              {message.text}
            </div>
          ))
        )}
      </div>

      {(statusText || toolText || errorText) && (
        <div className="min-h-5 text-xs">
          {errorText ? (
            <p className="text-red-600" role="alert">
              {errorText}
            </p>
          ) : (
            <p className="text-gray-500">{toolText ?? statusText}</p>
          )}
        </div>
      )}

      {pendingLaunchFlow && (
        <div className="flex flex-col gap-3 rounded-lg border border-violet-200 bg-violet-50 p-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm font-medium text-violet-900">
            {agent.agent_name} made {launchLabel(pendingLaunchFlow)}.
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              className="inline-flex items-center gap-1 rounded-md bg-violet-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-violet-700 focus:outline-none focus:ring-2 focus:ring-violet-500"
              onClick={navigateToPendingFlow}
            >
              <ExternalLink size={15} /> Open
            </button>
            <button
              type="button"
              className="inline-flex items-center gap-1 rounded-md border border-violet-200 bg-white px-3 py-1.5 text-sm font-medium text-violet-800 hover:bg-violet-100 focus:outline-none focus:ring-2 focus:ring-violet-500"
              onClick={resetPendingFlow}
            >
              <X size={15} /> Stay
            </button>
          </div>
        </div>
      )}

      <form className="flex gap-2" onSubmit={onSubmit}>
        <label htmlFor="agent-chat-message" className="sr-only">
          Message
        </label>
        <input
          id="agent-chat-message"
          type="text"
          className="min-w-0 flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500 disabled:bg-gray-100"
          value={draft}
          disabled={isStreaming}
          placeholder={`Message ${agent.agent_name}`}
          onChange={(e) => setDraft(e.target.value)}
        />
        <button
          type="submit"
          className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-violet-600 text-white hover:bg-violet-700 focus:outline-none focus:ring-2 focus:ring-violet-500 disabled:bg-gray-300"
          disabled={!canSend}
          aria-label="Send message"
        >
          <Send size={17} />
        </button>
      </form>
    </section>
  );
}
