/**
 * Pure reducer for the voice-input state machine (#584).
 *
 * Extracted from useVoiceInput so the transition table can be
 * exhaustively unit-tested without mounting a DOM or stubbing
 * MediaRecorder.
 *
 * States:
 *   idle             — ready to record
 *   consent-required — child profile has microphone_consent=false
 *   requesting       — getUserMedia in flight (browser permission prompt)
 *   recording        — actively recording audio
 *   processing       — recording stopped, POSTing to /api/v1/audio/transcriptions
 *   done             — transcript returned (safety_passed=true, non-empty text)
 *   rejected         — server returned safety_passed=false (kid-friendly retry)
 *   error            — anything else (denied, network, provider failure)
 *   unsupported      — MediaRecorder / getUserMedia not available (terminal)
 */

export type VoiceInputState =
  | 'idle'
  | 'consent-required'
  | 'requesting'
  | 'recording'
  | 'processing'
  | 'done'
  | 'rejected'
  | 'error'
  | 'unsupported'

export type VoiceInputEvent =
  | { type: 'start'; consentGranted: boolean }
  | { type: 'consentGranted' }
  | { type: 'consentDismissed' }
  | { type: 'streamReady' }
  | { type: 'streamError' }
  | { type: 'stopRecording' }
  | { type: 'transcriptionPassed' }
  | { type: 'transcriptionRejected' }
  | { type: 'transcriptionError' }
  | { type: 'reset' }
  | { type: 'markUnsupported' }

export function voiceReducer(
  state: VoiceInputState,
  event: VoiceInputEvent,
): VoiceInputState {
  if (state === 'unsupported') return 'unsupported'

  switch (event.type) {
    case 'markUnsupported':
      return 'unsupported'

    case 'start':
      if (state !== 'idle' && state !== 'done' && state !== 'rejected' && state !== 'error') {
        return state
      }
      return event.consentGranted ? 'requesting' : 'consent-required'

    case 'consentGranted':
      return state === 'consent-required' ? 'requesting' : state

    case 'consentDismissed':
      return state === 'consent-required' ? 'idle' : state

    case 'streamReady':
      return state === 'requesting' ? 'recording' : state

    case 'streamError':
      return state === 'requesting' ? 'error' : state

    case 'stopRecording':
      return state === 'recording' ? 'processing' : state

    case 'transcriptionPassed':
      return state === 'processing' ? 'done' : state

    case 'transcriptionRejected':
      return state === 'processing' ? 'rejected' : state

    case 'transcriptionError':
      return state === 'processing' ? 'error' : state

    case 'reset':
      return 'idle'

    default:
      return state
  }
}

export function isBusyState(state: VoiceInputState): boolean {
  return state === 'requesting' || state === 'recording' || state === 'processing'
}
