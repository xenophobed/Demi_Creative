/**
 * Pure reducer for the camera capture state machine. Extracted from
 * useCamera so the transition table can be exhaustively unit-tested
 * without mounting a DOM or stubbing `navigator.mediaDevices`.
 *
 * State diagram (see #581):
 *   idle
 *     ├── start()          → consent-required | requesting
 *     └── (unsupported on mount)
 *   consent-required
 *     ├── onGranted()      → requesting
 *     └── onDismiss()      → idle
 *   requesting
 *     ├── streamReady      → live
 *     └── streamError      → error
 *   live
 *     ├── capture()        → captured
 *     ├── toggleFacing()   → requesting
 *     └── stop()           → idle
 *   captured
 *     ├── retake()         → requesting
 *     └── confirm()        → idle (consumer keeps the blob)
 *   error
 *     ├── retry()          → requesting
 *     └── cancel()         → idle
 *   unsupported (terminal)
 */

import type { CameraErrorKind } from './cameraErrors'

export type CameraState =
  | 'idle'
  | 'consent-required'
  | 'requesting'
  | 'live'
  | 'captured'
  | 'error'
  | 'unsupported'

export type CameraEvent =
  | { type: 'start'; consentGranted: boolean }
  | { type: 'consentGranted' }
  | { type: 'consentDismissed' }
  | { type: 'streamReady' }
  | { type: 'streamError'; errorKind: CameraErrorKind }
  | { type: 'capture' }
  | { type: 'retake' }
  | { type: 'confirm' }
  | { type: 'toggleFacing' }
  | { type: 'retry' }
  | { type: 'stop' }
  | { type: 'markUnsupported' }

export function cameraReducer(state: CameraState, event: CameraEvent): CameraState {
  // Terminal: nothing escapes unsupported.
  if (state === 'unsupported') return 'unsupported'

  switch (event.type) {
    case 'markUnsupported':
      return 'unsupported'

    case 'start':
      if (state !== 'idle' && state !== 'error') return state
      return event.consentGranted ? 'requesting' : 'consent-required'

    case 'consentGranted':
      return state === 'consent-required' ? 'requesting' : state

    case 'consentDismissed':
      return state === 'consent-required' ? 'idle' : state

    case 'streamReady':
      return state === 'requesting' ? 'live' : state

    case 'streamError':
      return state === 'requesting' ? 'error' : state

    case 'capture':
      return state === 'live' ? 'captured' : state

    case 'retake':
      return state === 'captured' ? 'requesting' : state

    case 'confirm':
      return state === 'captured' ? 'idle' : state

    case 'toggleFacing':
      // Toggling restarts the stream regardless of current live/captured.
      return state === 'live' || state === 'captured' ? 'requesting' : state

    case 'retry':
      return state === 'error' ? 'requesting' : state

    case 'stop':
      return 'idle'

    default:
      return state
  }
}

export const TERMINAL_STATES: ReadonlySet<CameraState> = new Set(['unsupported'])

export function isActiveStreamState(state: CameraState): boolean {
  return state === 'requesting' || state === 'live'
}
