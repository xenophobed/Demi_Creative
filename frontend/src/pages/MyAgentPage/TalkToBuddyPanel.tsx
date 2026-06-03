/**
 * TalkToBuddyPanel (#618) — full-screen UI for the Talk-to-Buddy
 * realtime voice surface (PRD §3.16).
 *
 * Mobile sheet on (pointer: coarse) and (max-width: 1024px); desktop
 * side panel otherwise. Pure helpers (state copy map, indicator picker,
 * entry-button truth table) live in `talkToBuddyHelpers.ts` so the
 * test load stays off this presentational component.
 *
 * The panel does NOT own the WebSocket or MediaRecorder — those live
 * in `useVoiceConversation` (#617). This component only renders the
 * current state and forwards user-pressed events (Start, End, Retry).
 * The hook is instantiated in a TalkToBuddyContainer up in
 * AgentChatPanel (#620), which forwards state + handlers down here.
 *
 * NOTE: PR #629 accidentally shipped a duplicate of the test file as
 * this component. PR #620 reconstructs the real component content.
 */

import { motion } from "framer-motion";
import {
  isEndButtonEnabled,
  isPanelVisible,
  pickIndicator,
  TALK_PANEL_STATE_COPY,
} from "./talkToBuddyHelpers";
import type { VoiceConversationState } from "@/hooks/voiceConversationStateMachine";

export interface TalkToBuddyPanelProps {
  state: VoiceConversationState;
  /** Latest STT partial transcript ("what I'm hearing you say so far"). */
  partialTranscript?: string;
  /** Latest assistant text delta accumulator. */
  assistantText?: string;
  /** RMS-derived mic input level 0..1 for the waveform animation. */
  inputLevel?: number;
  prefersReducedMotion?: boolean;
  onStart: () => void;
  onEnd: () => void;
  onRetry?: () => void;
  /** Optional close button for the panel itself (separate from End). */
  onClose?: () => void;
}

function Indicator({
  variant,
  level,
}: {
  variant: "static" | "pulse-listening" | "pulse-speaking";
  level: number;
}) {
  if (variant === "static") {
    return (
      <div
        className="h-2 w-2 rounded-full bg-primary"
        aria-hidden="true"
      />
    );
  }
  const colorClass =
    variant === "pulse-listening" ? "bg-emerald-500" : "bg-violet-500";
  const scale = 1 + Math.min(0.4, (level ?? 0) * 0.4);
  return (
    <motion.div
      className={`h-3 w-3 rounded-full ${colorClass}`}
      animate={{ scale: [1, scale, 1] }}
      transition={{ duration: 0.8, repeat: Infinity, ease: "easeInOut" }}
      aria-hidden="true"
    />
  );
}

export function TalkToBuddyPanel({
  state,
  partialTranscript = "",
  assistantText = "",
  inputLevel = 0,
  prefersReducedMotion = false,
  onStart,
  onEnd,
  onRetry,
  onClose,
}: TalkToBuddyPanelProps) {
  if (!isPanelVisible(state)) return null;

  const status = TALK_PANEL_STATE_COPY[state];
  const indicator = pickIndicator(state, prefersReducedMotion);
  const endEnabled = isEndButtonEnabled(state);
  const canStart = state === "idle" || state === "error";

  return (
    <section
      role="dialog"
      aria-modal="true"
      aria-label="Talk to your buddy"
      className="fixed inset-0 z-40 flex flex-col bg-gradient-to-b from-violet-50 to-white lg:inset-auto lg:bottom-4 lg:right-4 lg:h-[640px] lg:w-[420px] lg:rounded-2xl lg:border lg:border-gray-200 lg:shadow-2xl"
    >
      <header className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
        <div className="flex items-center gap-2">
          <Indicator variant={indicator} level={inputLevel} />
          <h2 className="text-lg font-semibold text-gray-800">
            Talk to Buddy
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onEnd}
            disabled={!endEnabled}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            End
          </button>
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              aria-label="Close Talk to Buddy"
              className="rounded-lg p-1.5 text-gray-600 hover:bg-gray-100"
            >
              ×
            </button>
          )}
        </div>
      </header>

      <div
        className="flex-1 overflow-y-auto px-4 py-4"
        aria-live="polite"
        aria-atomic="false"
      >
        <p className="mb-3 text-center text-sm font-medium text-gray-600">
          {status}
        </p>

        {partialTranscript && (
          <div className="mb-3 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-900">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-emerald-700">
              You
            </p>
            <p>{partialTranscript}</p>
          </div>
        )}

        {assistantText && (
          <div className="mb-3 rounded-lg bg-violet-50 p-3 text-sm text-violet-900">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-violet-700">
              Buddy
            </p>
            <p>{assistantText}</p>
          </div>
        )}
      </div>

      <footer className="border-t border-gray-200 px-4 py-3">
        {canStart && (
          <motion.button
            type="button"
            onClick={onStart}
            whileTap={{ scale: 0.97 }}
            className="w-full rounded-xl bg-primary px-6 py-4 text-base font-bold text-white shadow-md hover:bg-primary/90"
          >
            {state === "error" ? "Try Again" : "Start Talking"}
          </motion.button>
        )}
        {state === "error" && onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="mt-2 w-full text-sm font-medium text-violet-600 underline"
          >
            Reset and start over
          </button>
        )}
        {!canStart && (
          <p className="text-center text-xs text-gray-500">
            Tap End to stop the conversation when you're done.
          </p>
        )}
      </footer>
    </section>
  );
}

export default TalkToBuddyPanel;
