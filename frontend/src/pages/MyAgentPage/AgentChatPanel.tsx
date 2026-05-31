/**
 * AgentChatPanel — the chat surface for the user's buddy (#510).
 *
 * Owns: message list state, draft + image attachment, AbortController
 * lifecycle, and the streaming SSE pipeline. Pure merge logic lives in
 * `./chatMessageState` so the streaming-delta semantics stay
 * unit-testable without RTL.
 *
 * Layout: the panel fills its parent's height. MyAgentPage gives it
 * `h-[calc(100vh-7rem)]` so the composer sticks to the viewport floor
 * and the message list scrolls inside the panel.
 *
 * Parent epic: #436
 */
import {
  ChangeEvent,
  FormEvent,
  KeyboardEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  ExternalLink,
  ImagePlus,
  Loader2,
  Send,
  Settings,
  Sparkles,
  Square,
  X,
} from "lucide-react";
import { agentService } from "@/api/services/agentService";
import { memoryService } from "@/api/services/memoryService";
import { useLaunchFlowNavigation } from "@/hooks/useLaunchFlowNavigation";
import useAgentChatStore from "@/store/useAgentChatStore";
import useChildStore from "@/store/useChildStore";
import VoiceInputButton from "@/components/common/VoiceInputButton";
import ParentConsentGate from "@/components/common/ParentConsentGate";
import type { Agent } from "@/types/agent";
import type { AgeGroup, MemoryCharacter } from "@/types/api";
import type {
  SSEErrorData,
  SSELaunchFlowData,
  SSESessionData,
  SSEStatusData,
  SSEThinkingData,
  SSEToolResultData,
  SSEToolUseData,
} from "@/types/api";
import {
  chipPrefillForCharacter,
  pickRecurringCharacter,
} from "./recurringCharacter";

interface Props {
  agent: Agent;
  childId: string;
  ageGroup?: AgeGroup | null;
  interests?: string[];
  /** Open the persona editor sheet (gear button in header). */
  onConfigure?: () => void;
}

/**
 * Conversation starters surfaced in the empty state. Each chip
 * pre-fills the composer so the user can tweak before sending. The
 * order roughly maps to the three specialist flows the proxy can
 * delegate to, so a single tap shows the launch_flow handoff working
 * end-to-end.
 */
const STARTER_PROMPTS: string[] = [
  "Tell me a bedtime story about a friendly dragon",
  "What's in the news today for kids?",
  "Let's make an interactive choose-your-own adventure",
];

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

function launchMessage(agent: Agent, flow: SSELaunchFlowData): string {
  if (flow.flow_type === "image_story" && !flow.prefill?.story_id) {
    return `${agent.agent_name} is ready to turn an image into a story.`;
  }
  if (flow.flow_type === "kids_daily" && !flow.prefill?.episode_id) {
    return `${agent.agent_name} is ready to open Kids Daily.`;
  }
  return `${agent.agent_name} made ${launchLabel(flow)}.`;
}

function resultMessage(data: unknown): string {
  if (data && typeof data === "object" && "message" in data) {
    const message = (data as { message?: unknown }).message;
    if (typeof message === "string") return message;
  }
  return "";
}

export default function AgentChatPanel({
  agent,
  childId,
  ageGroup,
  interests = [],
  onConfigure,
}: Props) {
  const [draft, setDraft] = useState("");
  const [image, setImage] = useState<File | null>(null);
  // Messages + the active session id live in the shared store (#569) so
  // the sidebar (#570) and this panel stay in lock-step when the user
  // switches topics.
  const messages = useAgentChatStore((s) => s.messages);
  const sessionId = useAgentChatStore((s) => s.currentSessionId);
  const appendUserMessage = useAgentChatStore((s) => s.appendUserMessage);
  const appendStreamingDelta = useAgentChatStore((s) => s.appendStreamingDelta);
  const settleAssistant = useAgentChatStore((s) => s.settleAssistantMessage);
  const adoptServerSession = useAgentChatStore((s) => s.adoptServerSession);
  const [isStreaming, setIsStreaming] = useState(false);
  const [statusText, setStatusText] = useState<string | null>(null);
  const [toolText, setToolText] = useState<string | null>(null);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [recurringCharacter, setRecurringCharacter] =
    useState<MemoryCharacter | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  // The session id the in-flight stream belongs to. Lets us tell a
  // user-initiated session switch (abort) apart from the proxy adopting
  // a server-issued session mid-stream (do not abort).
  const streamSessionRef = useRef<string | null>(null);
  const imageInputRef = useRef<HTMLInputElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const {
    onLaunchFlow,
    pendingLaunchFlow,
    navigateToPendingFlow,
    resetPendingFlow,
  } = useLaunchFlowNavigation();

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  // Abort an in-flight stream when the user switches to a *different*
  // session than the stream belongs to, so partial deltas don't bleed
  // into the newly selected session's history (#570). A mid-stream
  // adopt of the server session keeps streamSessionRef in sync, so that
  // case does not trip this guard.
  useEffect(() => {
    if (
      abortRef.current &&
      streamSessionRef.current !== null &&
      sessionId !== streamSessionRef.current
    ) {
      abortRef.current.abort();
      abortRef.current = null;
      setIsStreaming(false);
      setStatusText(null);
      setToolText(null);
    }
  }, [sessionId]);

  // Fetch recurring characters for the active child to surface a
  // "Remember…" chip above the composer (#560). Cancelled on
  // child-id change so a slow response for a previous child can't
  // overwrite the next child's chip — the same active-child precedent
  // we follow across creation surfaces (#548).
  useEffect(() => {
    if (!childId) {
      setRecurringCharacter(null);
      return;
    }
    let cancelled = false;
    memoryService
      .getCharacters(childId)
      .then((response) => {
        if (cancelled) return;
        setRecurringCharacter(pickRecurringCharacter(response.characters));
      })
      .catch(() => {
        if (cancelled) return;
        // Non-critical surface — hide the chip on failure.
        setRecurringCharacter(null);
      });
    return () => {
      cancelled = true;
    };
  }, [childId]);

  const tail = messages[messages.length - 1]?.text ?? "";
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, tail]);

  const buddyGlyph = useMemo(() => avatarGlyph(agent), [agent]);
  const canSend = Boolean(draft.trim()) && !isStreaming && Boolean(childId);
  const imageInputId = `agent-chat-image-${agent.agent_id}`;
  const currentChild = useChildStore((s) => s.currentChild);
  const [showMicConsentGate, setShowMicConsentGate] = useState(false);

  const clearImage = () => {
    setImage(null);
    if (imageInputRef.current) imageInputRef.current.value = "";
  };

  const onImageChange = (event: ChangeEvent<HTMLInputElement>) => {
    setImage(event.target.files?.[0] ?? null);
  };

  const onDraftKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  };

  const useStarter = (prompt: string) => {
    setDraft(prompt);
    setTimeout(() => textareaRef.current?.focus(), 0);
  };

  const useRecurringCharacter = () => {
    if (!recurringCharacter) return;
    useStarter(chipPrefillForCharacter(recurringCharacter.name));
  };

  const cancelStream = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    streamSessionRef.current = null;
    setIsStreaming(false);
    setToolText(null);
    setStatusText(`${agent.agent_name} stopped.`);
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = draft.trim();
    if (!message || isStreaming) return;

    const controller = new AbortController();
    const attachedImage = image;
    abortRef.current?.abort();
    abortRef.current = controller;
    setDraft("");
    clearImage();
    setErrorText(null);
    setToolText(null);
    setStatusText(`${agent.agent_name} is thinking...`);
    resetPendingFlow();
    appendUserMessage(message);
    streamSessionRef.current = sessionId;
    setIsStreaming(true);

    try {
      await agentService.streamAgentChat(
        {
          child_id: childId,
          message,
          session_id: sessionId,
          age_group: ageGroup,
          interests,
          image: attachedImage,
        },
        {
          onSession: (data: SSESessionData) => {
            streamSessionRef.current = data.session_id;
            adoptServerSession(data.session_id);
          },
          onStatus: (data: SSEStatusData) => setStatusText(data.message),
          onThinking: (data: SSEThinkingData) => appendStreamingDelta(data.content),
          onToolUse: (data: SSEToolUseData) => setToolText(data.message),
          onToolResult: (data: SSEToolResultData) =>
            setToolText(data.message ?? "Specialist finished."),
          onLaunchFlow,
          onResult: (data) => settleAssistant(resultMessage(data)),
          onError: (data: SSEErrorData) => {
            setErrorText(data.message);
            settleAssistant(data.message);
          },
          onComplete: (data: SSEStatusData) => {
            setStatusText(data.message);
            settleAssistant("");
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
        settleAssistant(messageText);
      }
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
      streamSessionRef.current = null;
      setIsStreaming(false);
    }
  };

  return (
    <section className="flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
      <header className="flex items-center justify-between gap-3 border-b border-gray-100 bg-gradient-to-r from-violet-50 to-pink-50 px-5 py-3.5">
        <div className="flex items-center gap-3">
          <div
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-white text-2xl shadow-sm ring-1 ring-violet-100"
            aria-hidden="true"
          >
            {buddyGlyph}
          </div>
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold text-gray-900">
              {agent.agent_name}
            </h2>
            <p className="truncate text-xs font-medium text-violet-700">
              {agent.agent_title}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {isStreaming && (
            <Loader2
              size={18}
              className="shrink-0 animate-spin text-violet-600"
              aria-label="Streaming"
            />
          )}
          {onConfigure && (
            <button
              type="button"
              onClick={onConfigure}
              className="inline-flex h-9 w-9 items-center justify-center rounded-full text-gray-500 hover:bg-white hover:text-violet-700 focus:outline-none focus:ring-2 focus:ring-violet-500"
              aria-label="Configure buddy"
              title="Configure buddy"
            >
              <Settings size={18} />
            </button>
          )}
        </div>
      </header>

      <div
        className="min-h-0 flex-1 overflow-y-auto bg-gradient-to-b from-gray-50 to-white px-5 py-5"
        aria-live="polite"
      >
        {messages.length === 0 ? (
          <div className="mx-auto flex h-full max-w-md flex-col items-center justify-center gap-5 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-white text-3xl shadow-md ring-2 ring-violet-100">
              {buddyGlyph}
            </div>
            <div>
              <p className="text-base font-semibold text-gray-900">
                Hi! I'm {agent.agent_name}.
              </p>
              <p className="mt-1 flex items-center justify-center gap-1 text-sm text-gray-600">
                <Sparkles size={14} className="text-violet-500" />
                Pick a starter or type your own.
              </p>
            </div>
            <div className="flex flex-col gap-2">
              {STARTER_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => useStarter(prompt)}
                  className="rounded-full border border-violet-200 bg-white px-4 py-2 text-left text-sm text-violet-900 shadow-sm transition-colors hover:border-violet-400 hover:bg-violet-50 focus:outline-none focus:ring-2 focus:ring-violet-500"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {messages.map((message) => (
              <div
                key={message.id}
                className={[
                  "flex w-full",
                  message.role === "user" ? "justify-end" : "justify-start",
                ].join(" ")}
              >
                {message.role === "assistant" && (
                  <div
                    aria-hidden="true"
                    className="mr-2 mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white text-base shadow-sm ring-1 ring-violet-100"
                  >
                    {buddyGlyph}
                  </div>
                )}
                <div
                  className={[
                    "max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm leading-6 shadow-sm",
                    message.role === "user"
                      ? "rounded-br-md bg-violet-600 text-white"
                      : "rounded-bl-md border border-gray-100 bg-white text-gray-800",
                  ].join(" ")}
                >
                  {message.text}
                  {message.streaming && (
                    <span
                      aria-hidden="true"
                      className="ml-0.5 inline-block h-3 w-1 animate-pulse rounded-sm bg-violet-400 align-middle"
                    />
                  )}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {(statusText || toolText || errorText) && (
        <div className="border-t border-gray-100 bg-white px-5 py-1.5 text-xs">
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
        <div className="mx-5 mb-3 flex flex-col gap-3 rounded-xl border border-violet-200 bg-violet-50 p-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm font-medium text-violet-900">
            {launchMessage(agent, pendingLaunchFlow)}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              className="inline-flex items-center gap-1 rounded-full bg-violet-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-violet-700 focus:outline-none focus:ring-2 focus:ring-violet-500"
              onClick={navigateToPendingFlow}
            >
              <ExternalLink size={15} /> Open
            </button>
            <button
              type="button"
              className="inline-flex items-center gap-1 rounded-full border border-violet-200 bg-white px-3 py-1.5 text-sm font-medium text-violet-800 hover:bg-violet-100 focus:outline-none focus:ring-2 focus:ring-violet-500"
              onClick={resetPendingFlow}
            >
              <X size={15} /> Stay
            </button>
          </div>
        </div>
      )}

      <form
        className="border-t border-gray-100 bg-white px-4 py-3"
        onSubmit={onSubmit}
      >
        <label htmlFor="agent-chat-message" className="sr-only">
          Message {agent.agent_name}
        </label>
        {recurringCharacter && !isStreaming && (
          <div className="mb-2">
            <button
              type="button"
              onClick={useRecurringCharacter}
              className="inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-900 transition-colors hover:border-amber-400 hover:bg-amber-100 focus:outline-none focus:ring-2 focus:ring-amber-500"
              title={`Chat about ${recurringCharacter.name}`}
            >
              <Sparkles size={12} className="text-amber-500" />
              Remember {recurringCharacter.name}?
            </button>
          </div>
        )}
        {image && (
          <div className="mb-2 flex items-center justify-between gap-2 rounded-lg border border-violet-100 bg-violet-50 px-3 py-1.5 text-xs text-violet-800">
            <span className="truncate">{image.name}</span>
            <button
              type="button"
              className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md hover:bg-violet-100 focus:outline-none focus:ring-2 focus:ring-violet-500"
              onClick={clearImage}
              aria-label="Remove attached image"
            >
              <X size={14} />
            </button>
          </div>
        )}
        <div className="flex items-end gap-2">
          <textarea
            id="agent-chat-message"
            ref={textareaRef}
            rows={1}
            className="max-h-32 min-h-11 min-w-0 flex-1 resize-y rounded-2xl border border-gray-300 px-4 py-2.5 text-sm leading-6 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500 disabled:bg-gray-100"
            value={draft}
            disabled={isStreaming}
            placeholder={`Message ${agent.agent_name}…  (Shift+Enter for newline)`}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onDraftKeyDown}
          />
          <input
            ref={imageInputRef}
            id={imageInputId}
            type="file"
            accept="image/*"
            className="sr-only"
            disabled={isStreaming}
            onChange={onImageChange}
          />
          <label
            htmlFor={imageInputId}
            className={[
              "inline-flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-full border border-gray-300 text-gray-600 hover:bg-gray-50 focus-within:ring-2 focus-within:ring-violet-500",
              isStreaming ? "pointer-events-none bg-gray-100 text-gray-300" : "",
            ].join(" ")}
            title="Attach image"
          >
            <ImagePlus size={18} />
            <span className="sr-only">Attach image</span>
          </label>
          {ageGroup &&
            (currentChild?.microphone_consent === true ? (
              <VoiceInputButton
                ageGroup={ageGroup}
                consentGranted
                onText={(text) =>
                  setDraft((prev) => (prev ? `${prev} ${text}` : text))
                }
                className="shrink-0"
              />
            ) : (
              <button
                type="button"
                onClick={() => setShowMicConsentGate(true)}
                disabled={isStreaming}
                className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-gray-300 text-gray-600 hover:bg-gray-50 disabled:pointer-events-none disabled:bg-gray-100 disabled:text-gray-300"
                title="Ask a grown-up to allow the microphone"
              >
                <span aria-hidden="true">🎤</span>
                <span className="sr-only">Ask a grown-up to allow the microphone</span>
              </button>
            ))}
          {isStreaming ? (
            <button
              type="button"
              className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-gray-300 text-gray-600 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-violet-500"
              onClick={cancelStream}
              aria-label="Cancel response"
              title="Stop"
            >
              <Square size={16} />
            </button>
          ) : (
            <button
              type="submit"
              className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-violet-600 text-white shadow-sm transition-colors hover:bg-violet-700 focus:outline-none focus:ring-2 focus:ring-violet-500 disabled:bg-gray-300"
              disabled={!canSend}
              aria-label="Send message"
            >
              <Send size={18} />
            </button>
          )}
        </div>
      </form>
      {showMicConsentGate && ageGroup && (
        <ParentConsentGate
          kind="microphone"
          ageGroup={ageGroup}
          childId={childId}
          onGranted={() => setShowMicConsentGate(false)}
          onDismiss={() => setShowMicConsentGate(false)}
        />
      )}
    </section>
  );
}
