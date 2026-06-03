/**
 * Pure reducer for the Talk-to-Buddy realtime voice state machine (#616).
 *
 * Extracted from useVoiceConversation so the transition table can be
 * exhaustively unit-tested without mounting a DOM, opening a WebSocket,
 * or calling getUserMedia. Mirrors the voiceInputStateMachine.ts pattern
 * shipped in #584.
 *
 * State diagram (PRD §3.16):
 *   idle ─start──► connecting ─tokenReceived──► connecting (WS opens) ─wsOpen──► listening
 *   listening ─sttPartial──► listening
 *   listening ─sttFinal──► thinking ─assistantTextDelta──► thinking
 *   thinking ─ttsStart──► speaking ─ttsEnd──► listening
 *   speaking ─bargeIn──► interrupted ─wsOpen|sttPartial──► listening
 *   any ─endRequested──► ending ─wsClose──► idle
 *   any ─streamError──► error ─reset──► idle
 *   idle ─markUnsupported──► unsupported (terminal)
 */

export type VoiceConversationState =
  | 'idle'
  | 'connecting'
  | 'listening'
  | 'thinking'
  | 'speaking'
  | 'interrupted'
  | 'ending'
  | 'error'
  | 'unsupported'

export type VoiceConversationEvent =
  | { type: 'start'; consentGranted: boolean }
  | { type: 'consentGranted' }
  | { type: 'consentDismissed' }
  | { type: 'tokenReceived' }
  | { type: 'wsOpen' }
  | { type: 'wsClose' }
  | { type: 'sttPartial' }
  | { type: 'sttFinal' }
  | { type: 'assistantTextDelta' }
  | { type: 'ttsStart' }
  | { type: 'ttsEnd' }
  | { type: 'bargeIn' }
  | { type: 'endRequested' }
  | { type: 'streamError' }
  | { type: 'markUnsupported' }
  | { type: 'reset' }

/**
 * Pure reducer. `(state, event) => next state`.
 *
 * Two terminal-ish rules:
 *   1. `unsupported` absorbs every event (true terminal).
 *   2. `endRequested` is universal — it always transitions to `ending`
 *      (except from `unsupported`) because the user-pressed-End signal
 *      must never be ignored.
 */
export function voiceConversationReducer(
  state: VoiceConversationState,
  event: VoiceConversationEvent,
): VoiceConversationState {
  // Terminal absorption: once unsupported, nothing changes.
  if (state === 'unsupported') return 'unsupported'

  // User-pressed-End is honored from every active state.
  if (event.type === 'endRequested') {
    return state === 'idle' ? 'idle' : 'ending'
  }

  // markUnsupported also fires unconditionally — only the capability
  // check can put us here, and once we get the signal we never come back.
  if (event.type === 'markUnsupported') return 'unsupported'

  // reset returns to idle from any non-terminal state.
  if (event.type === 'reset') return 'idle'

  // Per-state dispatch table.
  switch (state) {
    case 'idle':
      if (event.type === 'start') {
        return event.consentGranted ? 'connecting' : 'idle'
      }
      return state

    case 'connecting':
      switch (event.type) {
        case 'wsOpen':
          return 'listening'
        case 'streamError':
        case 'wsClose':
          return 'error'
        case 'tokenReceived':
          return 'connecting' // self-loop: token in hand, still connecting WS
        default:
          return state
      }

    case 'listening':
      switch (event.type) {
        case 'sttPartial':
          return 'listening'
        case 'sttFinal':
          return 'thinking'
        case 'streamError':
        case 'wsClose':
          return 'error'
        default:
          return state
      }

    case 'thinking':
      switch (event.type) {
        case 'assistantTextDelta':
          return 'thinking'
        case 'ttsStart':
          return 'speaking'
        case 'streamError':
        case 'wsClose':
          return 'error'
        default:
          return state
      }

    case 'speaking':
      switch (event.type) {
        case 'bargeIn':
          return 'interrupted'
        case 'ttsEnd':
          return 'listening'
        case 'streamError':
        case 'wsClose':
          return 'error'
        default:
          return state
      }

    case 'interrupted':
      // Interrupt cancels the current TTS. Once we hear a partial from
      // the new utterance OR the WS confirms the cancel landed, return
      // to listening. Otherwise stay parked.
      switch (event.type) {
        case 'sttPartial':
        case 'wsOpen':
          return 'listening'
        case 'streamError':
        case 'wsClose':
          return 'error'
        default:
          return state
      }

    case 'ending':
      // Ending state waits for the server to acknowledge with wsClose.
      // streamError during shutdown is non-fatal — we're already closing.
      switch (event.type) {
        case 'wsClose':
          return 'idle'
        default:
          return state
      }

    case 'error':
      // Stay in error until the consumer dispatches reset.
      return state

    default:
      return state
  }
}

/**
 * True when the hook owns either the mic stream or the WS connection.
 * Used by consumers to decide whether cleanup is required on unmount.
 */
export function isActiveSessionState(state: VoiceConversationState): boolean {
  return (
    state === 'connecting' ||
    state === 'listening' ||
    state === 'thinking' ||
    state === 'speaking' ||
    state === 'interrupted' ||
    state === 'ending'
  )
}

export const TERMINAL_STATES: ReadonlySet<VoiceConversationState> = new Set([
  'unsupported',
])
