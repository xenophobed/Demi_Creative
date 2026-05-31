/**
 * Classify navigator.mediaDevices.getUserMedia rejection types into a
 * discriminated union so the UI can show a kind-specific message and
 * the hook can pick the right recovery path.
 *
 * MDN reference: https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia#exceptions
 */

export type CameraErrorKind =
  | 'permission_denied'    // NotAllowedError, SecurityError
  | 'no_device'            // NotFoundError
  | 'device_busy'          // NotReadableError, TrackStartError
  | 'overconstrained'      // OverconstrainedError, ConstraintNotSatisfiedError
  | 'unsupported'          // getUserMedia API not present
  | 'aborted'              // AbortError
  | 'unknown'

export function classifyCameraError(err: unknown): CameraErrorKind {
  if (err == null) return 'unknown'
  const name =
    typeof err === 'object' && err !== null && 'name' in err
      ? String((err as { name?: unknown }).name ?? '')
      : ''

  switch (name) {
    case 'NotAllowedError':
    case 'SecurityError':
      return 'permission_denied'
    case 'NotFoundError':
      return 'no_device'
    case 'NotReadableError':
    case 'TrackStartError':
      return 'device_busy'
    case 'OverconstrainedError':
    case 'ConstraintNotSatisfiedError':
      return 'overconstrained'
    case 'AbortError':
      return 'aborted'
    default:
      return 'unknown'
  }
}

export const CAMERA_ERROR_COPY: Record<CameraErrorKind, string> = {
  permission_denied:
    "We need camera permission to take a photo. You can allow it in your browser settings.",
  no_device: "We can't find a camera on this device.",
  device_busy:
    "The camera is in use by another app. Close it and try again.",
  overconstrained:
    "We couldn't open the requested camera. Trying the other one…",
  unsupported:
    "This browser doesn't support taking photos here. Use the file upload instead.",
  aborted: "Camera startup was interrupted. Try again.",
  unknown: "Something went wrong with the camera. Try again or use file upload.",
}
