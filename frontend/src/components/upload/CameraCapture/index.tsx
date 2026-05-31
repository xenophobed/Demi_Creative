/**
 * CameraCapture (#581) — live camera preview + retake + front/back
 * toggle. Pairs with `useCamera` for stream lifecycle and the pure
 * `cameraReducer` for state. Renders a fallback when the device or
 * browser doesn't support `getUserMedia`.
 *
 * This component does NOT render the consent gate itself — the parent
 * surface (CameraCapture's caller, e.g. the tabbed ImageUploader in
 * #582) checks `useChildStore.getState().currentChild?.camera_consent`
 * and renders `<ParentConsentGate kind="camera" .../>` from #588 first.
 * Keeping consent gating out of this component lets the same camera
 * UI work in surfaces with different consent flows.
 */

import { useCallback } from 'react'
import { motion } from 'framer-motion'
import { useCamera } from '@/hooks/useCamera'
import { CAMERA_ERROR_COPY } from '@/hooks/cameraErrors'
import type { CameraFacing } from '@/hooks/useCamera'

export interface CameraCaptureProps {
  onCapture: (file: File) => void
  onCancel: () => void
  initialFacing?: CameraFacing
  /**
   * When true, the caller has already established camera consent — the
   * gate UI lives outside this component, so the hook starts immediately.
   * Default true; pass false to keep the camera idle until the consumer
   * mounts the gate and confirms.
   */
  consentGranted?: boolean
}

export function CameraCapture({
  onCapture,
  onCancel,
  initialFacing = 'environment',
  consentGranted = true,
}: CameraCaptureProps) {
  const camera = useCamera({ initialFacing })

  // Kick off the stream once on mount if consent is already in hand.
  // We only start when state is idle to avoid double-fires on rerender.
  if (camera.state === 'idle' && consentGranted) {
    camera.start(true)
  }

  const handleUse = useCallback(async () => {
    try {
      const blob = await camera.capture()
      const file = new File([blob], `capture-${Date.now()}.jpg`, {
        type: 'image/jpeg',
      })
      onCapture(file)
      camera.confirm()
    } catch (err) {
      // capture() rejection is rare — surface as cancel so the parent
      // can fall back to the file picker.
      console.warn('CameraCapture: capture failed', err)
      onCancel()
    }
  }, [camera, onCancel])

  if (camera.state === 'unsupported') {
    return (
      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6 text-center">
        <p className="mb-3 text-amber-800">
          {CAMERA_ERROR_COPY.unsupported}
        </p>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-xl bg-amber-600 px-4 py-2 font-semibold text-white"
        >
          Use file upload
        </button>
      </div>
    )
  }

  if (camera.state === 'error') {
    const message =
      camera.errorKind != null
        ? CAMERA_ERROR_COPY[camera.errorKind]
        : CAMERA_ERROR_COPY.unknown
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-center">
        <p className="mb-3 text-red-700">{message}</p>
        <div className="flex justify-center gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-xl border border-red-300 px-4 py-2 font-semibold text-red-700"
          >
            Cancel
          </button>
          {camera.errorKind !== 'permission_denied' && (
            <button
              type="button"
              onClick={camera.retry}
              className="rounded-xl bg-red-600 px-4 py-2 font-semibold text-white"
            >
              Try again
            </button>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="relative aspect-square w-full overflow-hidden rounded-2xl bg-black">
        <video
          ref={camera.videoRef}
          playsInline
          muted
          autoPlay
          className={`h-full w-full object-cover ${
            camera.facing === 'user' ? 'scale-x-[-1]' : ''
          }`}
          aria-label="Camera preview"
        />
        <canvas ref={camera.canvasRef} className="hidden" />
        {camera.state === 'requesting' && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/60 text-white">
            <span className="text-sm">Opening camera…</span>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-xl border border-gray-300 px-4 py-2 font-semibold text-gray-700"
        >
          Cancel
        </button>

        {camera.state === 'live' && (
          <>
            <motion.button
              type="button"
              whileTap={{ scale: 0.95 }}
              onClick={handleUse}
              className="rounded-full bg-primary px-6 py-3 text-base font-bold text-white shadow-lg"
              aria-label="Take photo"
            >
              <span className="text-2xl" aria-hidden="true">📸</span>
            </motion.button>
            <button
              type="button"
              onClick={camera.toggleFacing}
              className="rounded-xl border border-gray-300 px-4 py-2 text-sm font-semibold text-gray-700"
              aria-label={`Switch to ${camera.facing === 'user' ? 'back' : 'front'} camera`}
            >
              {camera.facing === 'user' ? 'Back' : 'Front'}
            </button>
          </>
        )}

        {camera.state === 'captured' && (
          <>
            <button
              type="button"
              onClick={camera.retake}
              className="rounded-xl border border-gray-300 px-4 py-2 font-semibold text-gray-700"
            >
              Retake
            </button>
            <span className="text-sm text-gray-500">Sending photo…</span>
          </>
        )}

        {(camera.state === 'requesting' || camera.state === 'idle') && (
          <span className="text-sm text-gray-400">Waiting for camera…</span>
        )}

        {camera.state === 'consent-required' && (
          <span className="text-sm text-amber-700">
            Parent permission required.
          </span>
        )}
      </div>
    </div>
  )
}

export default CameraCapture
