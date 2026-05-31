/**
 * useCamera — stream lifecycle + state machine for camera capture (#581).
 *
 * Owns the MediaStream and exposes refs for the consumer to attach to
 * <video> and <canvas> elements. Logic lives in the pure
 * `cameraReducer` so it can be unit-tested without a DOM; this hook is
 * the thin glue that wires `getUserMedia` to dispatched events.
 *
 * Cleanup rule: every getUserMedia stream MUST be stopped on unmount
 * AND before any re-request (toggle/retake). The stopTracks helper is
 * also what releases the GPU surface on iOS Safari (via
 * `srcObject = null`).
 *
 * The consumer (CameraCapture / a future tabbed picker) is responsible
 * for rendering the ParentConsentGate when `needsConsent` is true.
 * This hook does NOT call getUserMedia until `start(consentGranted=true)`.
 */

import { useCallback, useEffect, useReducer, useRef, useState } from 'react'
import { classifyCameraError, type CameraErrorKind } from './cameraErrors'
import {
  cameraReducer,
  type CameraEvent,
  type CameraState,
} from './cameraStateMachine'

export type CameraFacing = 'user' | 'environment'

export interface UseCameraOptions {
  initialFacing?: CameraFacing
}

export interface UseCameraResult {
  state: CameraState
  errorKind: CameraErrorKind | null
  facing: CameraFacing
  videoRef: React.RefObject<HTMLVideoElement>
  canvasRef: React.RefObject<HTMLCanvasElement>
  start: (consentGranted: boolean) => void
  stop: () => void
  capture: () => Promise<Blob>
  retake: () => void
  confirm: () => void
  toggleFacing: () => void
  retry: () => void
  consentGranted: () => void
  consentDismissed: () => void
}

export function useCamera(options: UseCameraOptions = {}): UseCameraResult {
  const [state, dispatch] = useReducer(cameraReducer, 'idle' as CameraState)
  const [errorKind, setErrorKind] = useState<CameraErrorKind | null>(null)
  const [facing, setFacing] = useState<CameraFacing>(options.initialFacing ?? 'environment')

  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const streamRef = useRef<MediaStream | null>(null)

  const stopTracks = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null
    }
  }, [])

  // Detect unsupported environments once on mount.
  useEffect(() => {
    if (
      typeof navigator === 'undefined' ||
      !navigator.mediaDevices ||
      typeof navigator.mediaDevices.getUserMedia !== 'function'
    ) {
      dispatch({ type: 'markUnsupported' })
    }
  }, [])

  // Cleanup every track on unmount — non-negotiable on iOS Safari.
  useEffect(() => () => stopTracks(), [stopTracks])

  // Request a fresh stream whenever the reducer says we should be
  // requesting. Also re-fires when `facing` changes so toggleFacing
  // restarts the stream cleanly.
  useEffect(() => {
    if (state !== 'requesting') return

    let cancelled = false
    stopTracks()

    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: facing }, audio: false })
      .then((stream) => {
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop())
          return
        }
        streamRef.current = stream
        const video = videoRef.current
        if (video) {
          video.srcObject = stream
          // Defer the 'streamReady' transition to loadedmetadata so the
          // consumer never sees a zero-dimension <video> on Safari.
          const onReady = () => {
            if (!cancelled) dispatch({ type: 'streamReady' })
          }
          video.addEventListener('loadedmetadata', onReady, { once: true })
        } else {
          dispatch({ type: 'streamReady' })
        }
      })
      .catch((err) => {
        if (cancelled) return
        const kind = classifyCameraError(err)
        setErrorKind(kind)
        dispatch({ type: 'streamError', errorKind: kind })
      })

    return () => {
      cancelled = true
    }
  }, [state, facing, stopTracks])

  const send = useCallback((event: CameraEvent) => dispatch(event), [])

  const start = useCallback((consentGranted: boolean) => {
    setErrorKind(null)
    send({ type: 'start', consentGranted })
  }, [send])

  const stop = useCallback(() => {
    stopTracks()
    send({ type: 'stop' })
  }, [send, stopTracks])

  const capture = useCallback((): Promise<Blob> => {
    return new Promise((resolve, reject) => {
      const video = videoRef.current
      const canvas = canvasRef.current
      if (!video || !canvas) {
        reject(new Error('camera refs not attached'))
        return
      }
      const width = video.videoWidth
      const height = video.videoHeight
      if (!width || !height) {
        reject(new Error('camera stream not ready'))
        return
      }
      canvas.width = width
      canvas.height = height
      const ctx = canvas.getContext('2d')
      if (!ctx) {
        reject(new Error('canvas 2d context unavailable'))
        return
      }
      // Mirror the captured frame for the front camera so the saved
      // photo matches what the user saw on screen.
      if (facing === 'user') {
        ctx.translate(width, 0)
        ctx.scale(-1, 1)
      }
      ctx.drawImage(video, 0, 0, width, height)
      canvas.toBlob(
        (blob) => {
          if (!blob) {
            reject(new Error('canvas.toBlob returned null'))
            return
          }
          send({ type: 'capture' })
          // Stop the live stream once we have the snapshot — the
          // captured blob is the source of truth from here.
          stopTracks()
          resolve(blob)
        },
        'image/jpeg',
        0.92,
      )
    })
  }, [facing, send, stopTracks])

  const retake = useCallback(() => send({ type: 'retake' }), [send])
  const confirm = useCallback(() => send({ type: 'confirm' }), [send])
  const retry = useCallback(() => send({ type: 'retry' }), [send])
  const consentGranted = useCallback(() => send({ type: 'consentGranted' }), [send])
  const consentDismissed = useCallback(() => send({ type: 'consentDismissed' }), [send])

  const toggleFacing = useCallback(() => {
    setFacing((prev) => (prev === 'user' ? 'environment' : 'user'))
    send({ type: 'toggleFacing' })
  }, [send])

  return {
    state,
    errorKind,
    facing,
    videoRef,
    canvasRef,
    start,
    stop,
    capture,
    retake,
    confirm,
    toggleFacing,
    retry,
    consentGranted,
    consentDismissed,
  }
}
