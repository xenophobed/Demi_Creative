/**
 * TalkToBuddyPanel (#618) — UI for the Talk-to-Buddy realtime voice
 * surface (PRD §3.16).
 *
 * Two variants (PRD §3.16.5 v2, #635):
 *   - `overlay` (default): full-screen sheet on mobile, floating side
 *     panel on desktop. The original presentation.
 *   - `inline`: drops the fixed positioning and rounded chrome so the
 *     same component can render inside `AgentChatPanel`'s composer slot
 *     (replacing the textarea/send form). Used by the new header-pill
 *     entry pattern from #636.
 *
 * Pure helpers (state copy map, indicator picker, entry-button truth
 * table) live in `talkToBuddyHelpers.ts` so the test load stays off
 * this presentational component.
 *
 * The panel does NOT own the WebSocket or MediaRecorder — those live
 * in `useVoiceConversation` (#617). This component only renders the
 * current state and forwards user-pressed events (Start, End, Retry).
 * The hook is instantiated in a TalkToBuddyContainer up in
 * AgentChatPanel (#620), which forwards state + handlers down here.
 *
 * NOTE: PR #629 accidentally shipped a duplicate of the test file as
 * this component. PR #620 reconstructed the real component content.
 */

import { motion } from "framer-motion";
import {
  isEndButtonEnabled,
  isPanelVisible,
  resolveCaptionsVisibility,
  TALK_PANEL_STATE_COPY,
} from "./talkToBuddyHelpers";
import { pickOrbMode } from "./buddyOrbHelpers";
import { BuddyOrb } from "./BuddyOrb";
import type { VoiceConversationState } from "@/hooks/voiceConversationStateMachine";

/**
 * Rendering variant. `overlay` (default) keeps the existing fixed
 * positioning + rounded chrome so PR #620's TalkToBuddyContainer
 * keeps working unchanged. `inline` drops both so the panel fits
 * inside AgentChatPanel's composer slot (#636 consumer).
 */
export type TalkToBuddyPanelVariant = "overlay" | "inline";

export interface TalkToBuddyPanelProps {
  state: VoiceConversationState;
  /** Latest STT partial transcript ("what I'm hearing you say so far"). */
  partialTranscript?: string;
  /** Latest assistant text delta accumulator. */
  assistantText?: string;
  /** RMS-derived mic input level 0..1 for the waveform animation. */
  inputLevel?: number;
  /** RMS-derived TTS output level 0..1 for the speaking animation (#651). */
  outputLevel?: number;
  /** Raw child age in years. When < 6, the BuddyOrb renders the face overlay. */
  childAge?: number | null;
  prefersReducedMotion?: boolean;
  /**
   * #608 captions-visibility override. When the parent surface observes
   * a `safety_block` event from the voice hook, it sets this to ``true``
   * so the kid sees the fallback caption regardless of the per-age
   * default (which would otherwise hide captions for pre-readers).
   * ``undefined`` lets the panel fall back to ``captionsDefaultForAge``.
   */
  captionsVisibleOverride?: boolean;
  onStart: () => void;
  onEnd: () => void;
  onRetry?: () => void;
  /** Optional close button for the panel itself (separate from End).
   *  Hidden in `inline` variant where the bubble unmounts on End. */
  onClose?: () => void;
  /** Layout. Default `overlay` preserves PR #620's behavior. */
  variant?: TalkToBuddyPanelVariant;
}

/**
 * Tailwind class string for the outer wrapper, keyed by variant.
 * Exported so #636's contract test can assert which classes the
 * inline branch drops (no `fixed inset-0`, no `z-40`, no `shadow-2xl`).
 */
export const PANEL_WRAPPER_CLASS: Record<TalkToBuddyPanelVariant, string> = {
  overlay:
    "fixed inset-0 z-40 flex flex-col bg-gradient-to-b from-violet-50 to-white lg:inset-auto lg:bottom-4 lg:right-4 lg:h-[640px] lg:w-[420px] lg:rounded-2xl lg:border lg:border-gray-200 lg:shadow-2xl",
  inline:
    "flex flex-col gap-3 rounded-2xl border border-violet-200 bg-violet-50/40 p-3",
};

export function TalkToBuddyPanel({
  state,
  partialTranscript = "",
  assistantText = "",
  inputLevel = 0,
  outputLevel = 0,
  childAge = null,
  prefersReducedMotion = false,
  captionsVisibleOverride,
  onStart,
  onEnd,
  onRetry,
  onClose,
  variant = "overlay",
}: TalkToBuddyPanelProps) {
  if (!isPanelVisible(state)) return null;

  const status = TALK_PANEL_STATE_COPY[state];
  const orbMode = pickOrbMode(state, prefersReducedMotion);
  const endEnabled = isEndButtonEnabled(state);
  const canStart = state === "idle" || state === "error";

  // #608 captions visibility: default depends on age band (pre-readers
  // get them off); ``captionsVisibleOverride`` lets the parent surface
  // force them on after a `safety_block` event. The truth table is in
  // ``resolveCaptionsVisibility`` so the unit test can lock it without
  // mounting React.
  const captionsVisible = resolveCaptionsVisibility(
    childAge,
    captionsVisibleOverride,
  );

  const isInline = variant === "inline";
  const wrapperClass = PANEL_WRAPPER_CLASS[variant];

  // Inline variant is a region within the existing chat (not a dialog),
  // so it should not announce itself as a modal. Overlay keeps the
  // dialog semantics so screen readers treat it as a takeover surface.
  const role = isInline ? "region" : "dialog";
  const ariaModal: { "aria-modal"?: "true" } = isInline
    ? {}
    : { "aria-modal": "true" };

  // The header is thinner in the inline variant (no separate border, no
  // bg gradient — those belong to the overlay). End button is the same
  // affordance in both; X close only renders in overlay where it acts
  // as a secondary dismiss for the modal.
  const headerClass = isInline
    ? "flex items-center justify-between gap-2"
    : "flex items-center justify-between border-b border-gray-200 px-4 py-3";

  const bodyClass = isInline
    ? "min-h-0 max-h-48 overflow-y-auto"
    : "flex-1 overflow-y-auto px-4 py-4";

  const footerClass = isInline
    ? ""
    : "border-t border-gray-200 px-4 py-3";

  const startButtonClass = isInline
    ? "w-full rounded-xl bg-primary px-6 py-3 text-sm font-bold text-white shadow-sm hover:bg-primary/90"
    : "w-full rounded-xl bg-primary px-6 py-4 text-base font-bold text-white shadow-md hover:bg-primary/90";

  return (
    <section
      role={role}
      {...ariaModal}
      aria-label="Talk to your buddy"
      className={wrapperClass}
    >
      <header className={headerClass}>
        <div className="flex items-center gap-2">
          <h2
            className={
              isInline
                ? "text-sm font-semibold text-gray-800"
                : "text-lg font-semibold text-gray-800"
            }
          >
            Talk to Buddy
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onEnd}
            disabled={!endEnabled}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            End
          </button>
          {!isInline && onClose && (
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
        className={bodyClass}
        aria-live="polite"
        aria-atomic="false"
      >
        <div className={isInline ? "mb-2 flex justify-center" : "mb-4 flex justify-center"}>
          <BuddyOrb
            mode={orbMode}
            inputLevel={inputLevel}
            outputLevel={outputLevel}
            childAge={childAge}
            prefersReducedMotion={prefersReducedMotion}
          />
        </div>
        <p
          className={
            isInline
              ? "mb-2 text-center text-xs font-medium text-gray-600"
              : "mb-3 text-center text-sm font-medium text-gray-600"
          }
        >
          {status}
        </p>

        {captionsVisible && partialTranscript && (
          <div
            className={
              isInline
                ? "mb-2 rounded-lg bg-emerald-50 p-2 text-xs text-emerald-900"
                : "mb-3 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-900"
            }
          >
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-emerald-700">
              You
            </p>
            <p>{partialTranscript}</p>
          </div>
        )}

        {captionsVisible && assistantText && (
          <div
            className={
              isInline
                ? "mb-2 rounded-lg bg-violet-50 p-2 text-xs text-violet-900"
                : "mb-3 rounded-lg bg-violet-50 p-3 text-sm text-violet-900"
            }
          >
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-violet-700">
              Buddy
            </p>
            <p>{assistantText}</p>
          </div>
        )}
      </div>

      <footer className={footerClass}>
        {canStart && (
          <motion.button
            type="button"
            onClick={onStart}
            whileTap={{ scale: 0.97 }}
            className={startButtonClass}
          >
            {state === "error" ? "Try Again" : "Start Talking"}
          </motion.button>
        )}
        {state === "error" && onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="mt-2 w-full text-xs font-medium text-violet-600 underline"
          >
            Reset and start over
          </button>
        )}
        {!canStart && !isInline && (
          <p className="text-center text-xs text-gray-500">
            Tap End to stop the conversation when you're done.
          </p>
        )}
      </footer>
    </section>
  );
}

export default TalkToBuddyPanel;
