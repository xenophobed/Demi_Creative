/**
 * Pure helpers for TalkToBuddyPanel (#618).
 *
 * Extracted so the state-copy map and entry-button truth table can be
 * unit-tested without rendering React. Same separation-for-testability
 * pattern we used for ImageUploader (#580) and CameraCapture (#581).
 */

import type { VoiceConversationState } from "@/hooks/voiceConversationStateMachine";

/**
 * User-facing status copy keyed by the voiceConversationStateMachine
 * state. Kid-friendly tone — these strings end up in an ARIA live
 * region so screen readers get the same context as sighted users.
 */
export const TALK_PANEL_STATE_COPY: Record<VoiceConversationState, string> = {
  idle: "Tap the big button to start talking with your buddy.",
  connecting: "Connecting to your buddy...",
  listening: "Listening — I'm here whenever you're ready to speak.",
  thinking: "Hmm... let me think about that.",
  speaking: "Buddy is talking — say something to interrupt!",
  interrupted: "Got it, hold on...",
  ending: "Wrapping up your chat...",
  error:
    "Something went wrong with the voice chat. Try again, or switch to typing.",
  unsupported:
    "Voice chat isn't available on this device. You can keep using typed chat.",
};

/**
 * Capability + consent + child-profile preconditions for the Talk
 * button to appear on AgentChatPanel. All four must be true.
 *
 * Pure helper so the integration story (#620) can lock the truth table
 * without mounting AgentChatPanel.
 */
export interface TalkButtonPreconditions {
  /** Browser supports the realtime voice surface (getUserMedia +
   *  MediaRecorder + WebSocket + AudioContext). Comes from the hook's
   *  capability check. */
  supportsVoice: boolean;
  /** child_profiles.microphone_consent is true. */
  micConsentGranted: boolean;
  /** child_profiles.voice_conversation_consent is true. */
  voiceConversationConsentGranted: boolean;
  /** A child profile is currently selected. The Talk button is per-child,
   *  not per-account, because consent + quota live on the child row. */
  hasCurrentChild: boolean;
}

export function shouldShowEntryButton(
  preconditions: TalkButtonPreconditions,
): boolean {
  return (
    preconditions.supportsVoice &&
    preconditions.micConsentGranted &&
    preconditions.voiceConversationConsentGranted &&
    preconditions.hasCurrentChild
  );
}

/**
 * Whether the panel should be visible for a given state. Used by the
 * panel's outer wrapper to mount the surface only when there's actually
 * something to show. `idle` returns true because the parent surface
 * may want to mount the panel BEFORE the user taps Start.
 */
export function isPanelVisible(state: VoiceConversationState): boolean {
  return state !== "unsupported";
}

/**
 * Whether the End button should be enabled. The end action is always
 * safe to dispatch (the reducer no-ops on idle/error), but the button
 * looks disabled when there's no active session.
 */
export function isEndButtonEnabled(state: VoiceConversationState): boolean {
  return (
    state === "connecting" ||
    state === "listening" ||
    state === "thinking" ||
    state === "speaking" ||
    state === "interrupted" ||
    state === "ending"
  );
}

/**
 * Pick the visual "indicator" pattern for the current state. The panel
 * renders a pulsing waveform for `listening`/`speaking`/`interrupted`
 * and a static pill for other states (reduced-motion users always get
 * the static pill regardless of state).
 */
export type IndicatorVariant = "static" | "pulse-listening" | "pulse-speaking";

export function pickIndicator(
  state: VoiceConversationState,
  prefersReducedMotion: boolean,
): IndicatorVariant {
  if (prefersReducedMotion) return "static";
  if (state === "listening" || state === "interrupted") return "pulse-listening";
  if (state === "speaking" || state === "thinking") return "pulse-speaking";
  return "static";
}

/**
 * Pick the next ParentConsentGate kind to render in the consent chain,
 * or null when both consents are granted (#620).
 *
 * PRD §3.16.3 specifies stacked consent: microphone first, then
 * voice_conversation. This pure helper locks the ordering so the
 * AgentChatPanel integration can't drift.
 *
 * Defensive: a null/undefined child returns "mic" so the panel
 * surfaces the first gate rather than crashing on an undefined read.
 */
export type PendingGate = "mic" | "voice" | null;

export interface ChildConsentState {
  micConsent?: boolean;
  voiceConsent?: boolean;
}

export function nextPendingGate(
  child: ChildConsentState | null | undefined,
): PendingGate {
  if (!child) return "mic";
  if (!child.micConsent) return "mic";
  if (!child.voiceConsent) return "voice";
  return null;
}
