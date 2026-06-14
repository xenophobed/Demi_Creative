/**
 * Pure helpers for TalkToBuddyPanel (#618).
 *
 * Extracted so the state-copy map and entry-button truth table can be
 * unit-tested without rendering React. Same separation-for-testability
 * pattern we used for ImageUploader (#580) and CameraCapture (#581).
 */

import type { VoiceConversationState } from "@/hooks/voiceConversationStateMachine";
import type { AgeGroup } from "@/types/api";

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

export const TALK_PANEL_SCREEN_READER_COPY: Record<VoiceConversationState, string> = {
  idle: "Voice chat is idle.",
  connecting: "Voice chat is connecting.",
  listening: "Voice chat is listening.",
  thinking: "Buddy is thinking.",
  speaking: "Buddy is speaking.",
  interrupted: "Buddy heard the interruption.",
  ending: "Voice chat is ending.",
  error: "Voice chat needs attention.",
  unsupported: "Voice chat is not supported on this device.",
};

export function talkPanelScreenReaderState(
  state: VoiceConversationState,
  partialTranscript: string,
  assistantText: string,
): string {
  const base = TALK_PANEL_SCREEN_READER_COPY[state];
  const heard = partialTranscript.trim();
  const reply = assistantText.trim();
  if (reply) return `${base} Buddy says: ${reply}`;
  if (heard) return `${base} Heard: ${heard}`;
  return base;
}

export function reducedMotionStatusPill(
  state: VoiceConversationState,
): string | null {
  if (state === "listening" || state === "interrupted") return "Listening";
  if (state === "thinking") return "Thinking";
  if (state === "speaking") return "Speaking";
  return null;
}

export function voiceQuotaNoticeCopy(
  secondsRemaining: number | null | undefined,
): string {
  const remaining = Math.max(0, Math.floor(secondsRemaining ?? 0));
  if (remaining <= 0) {
    return "Voice time is used up for today. You can keep chatting by typing.";
  }
  if (remaining <= 60) {
    return "Voice time is almost done for today. You can keep chatting by typing when it ends.";
  }
  return `Voice time remaining today: ${Math.ceil(remaining / 60)} minutes.`;
}

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

/**
 * Whether the new "Start Talking" header pill in AgentChatPanel should
 * render (#636). Three conditions, all of them gating:
 *
 * 1. Capability + consent + child preconditions are met (delegates to
 *    `shouldShowEntryButton`).
 * 2. The chat is not currently streaming a text response — pressing
 *    Start Talking mid-stream would race the existing AbortController
 *    flow and create a confusing "buddy is typing AND listening?" state.
 * 3. The inline voice bubble is not already open — when `isTalkOpen` is
 *    true, the bubble has replaced the composer and there's no second
 *    entry point to surface in the header.
 *
 * Pure helper so the composer-swap story (#636) can lock the truth
 * table without mounting AgentChatPanel — same pattern as the entry
 * button (#618) and the variant CSS (#635).
 */
export function shouldShowHeaderTalkPill(
  preconditions: TalkButtonPreconditions,
  isStreaming: boolean,
  isTalkOpen: boolean,
): boolean {
  if (!shouldShowEntryButton(preconditions)) return false;
  if (isStreaming) return false;
  if (isTalkOpen) return false;
  return true;
}

/**
 * Captions default-on policy per age band (#608 carry-over).
 *
 * Pre-readers (3-5) cannot read captions, and parents in user testing
 * said the running text felt distracting next to the BuddyOrb. We
 * default captions OFF for that band and ON for everyone else.
 *
 * Override happens on the panel side when a `safety_block` event fires:
 * captions auto-show regardless of age so the kid sees the fallback
 * sentence the buddy speaks (PRD §3.16 — explicit rejection is a
 * teachable moment, not a silent skip).
 *
 * Pure helper so the panel test can lock the truth table without
 * mounting React. ``null`` / ``undefined`` defaults to "on" — defensive
 * fallback for the case where the child profile hasn't loaded yet.
 */
export function captionsDefaultForAge(
  age: number | null | undefined,
): boolean {
  if (age == null) return true;
  if (age < 6) return false;
  return true;
}

/**
 * Resolve the effective caption visibility from the per-age default
 * plus the parent surface's override (#608).
 *
 * Override semantics: ``true`` forces captions on (set this after a
 * ``safety_block`` event); ``undefined`` falls back to the per-age
 * default; ``false`` is intentionally NOT supported — leaving a panel
 * silent for an older reader would feel broken and there's no product
 * scenario that wants it. Mirrors the explicit-set guard inside the
 * panel render so the helper test pins the same truth table.
 */
export function resolveCaptionsVisibility(
  age: number | null | undefined,
  override: boolean | undefined,
): boolean {
  if (override === true) return true;
  return captionsDefaultForAge(age);
}

/**
 * Age-adapted entry-surface copy for the header "Start Talking" pill
 * (#638). Locks the labels to the PRD §3.16.6 age-adaptation table so
 * the visible CTA can't drift away from the spec:
 *
 * | 3-5                | 6-8                  | 9-12              |
 * | giant emoji + Talk!| "Talk to {buddy}"    | mic icon + Voice  |
 *
 * Design choices (per PRD):
 *   - 3-5 (pre-readers): a single playful word + a big mic emoji. The
 *     buddy name is deliberately omitted — a 4-year-old recognises the
 *     emoji, not the persona's name.
 *   - 6-8: the buddy NAME leads ("Talk to Sparky") because the personal
 *     relationship is the motivator at this age; no emoji to keep it
 *     reading like a sentence.
 *   - 9-12: terse, tool-like "Voice" with a mic icon — older kids treat
 *     it as a mode switch, not a character interaction.
 *
 * Reuses the canonical ``AgeGroup`` from ``@/types/api`` rather than a
 * local copy so a future fourth band (there isn't one today) can't drift
 * between modules. ``emoji`` is the empty string for 6-8 — the consuming
 * JSX renders the emoji span only when non-empty.
 */
export interface HeaderCTACopy {
  label: string;
  emoji: string;
}

export function headerCTACopy(
  ageGroup: AgeGroup,
  buddyName: string,
): HeaderCTACopy {
  switch (ageGroup) {
    case "3-5":
      return { label: "Talk!", emoji: "🎤" };
    case "9-12":
      return { label: "Voice", emoji: "🎤" };
    case "6-8":
    default:
      return { label: `Talk to ${buddyName}`, emoji: "" };
  }
}
