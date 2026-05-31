/**
 * useVoiceInput — records short audio via MediaRecorder, posts to
 * /api/v1/audio/transcriptions, and returns the safety-moderated
 * transcript (#584).
 *
 * State machine and helpers live in pure modules so they can be unit
 * tested without DOM. This hook is the thin glue between the reducer,
 * MediaRecorder, and the transcription service.
 *
 * Hard rules from PRD §3.15:
 *   - Recording auto-stops at maxDurationMs (default 30s).
 *   - Audio bytes only live in memory; the backend route enforces
 *     no-disk-persistence on its side.
 *   - Safety-failed transcripts surface as state='rejected' WITHOUT
 *     invoking onText, so the input field never gets unsafe content.
 */

import { useCallback, useEffect, useReducer, useRef, useState } from 'react'
import {
  transcriptionService,
  type TranscriptionResponse,
} from '@/api/services/transcriptionService'
import {
  voiceReducer,
  type VoiceInputState,
} from './voiceInputStateMachine'

export type AgeBand = '3-5' | '6-8' | '9-12'

export interface UseVoiceInputOptions {
  ageGroup: AgeBand
  maxDurationMs?: number
  languageHint?: string
  onText?: (text: string) => void
  onRejected?: () => void
  onError?: (kind: 'denied' | 'unknown') => void
}

export interface UseVoiceInputResult {
  state: VoiceInputState
  partialText: string
  start: (consentGranted: boolean) => void
  stop: () => void
  reset: () => void
  consentGranted: () => void
  consentDismissed: () => void
}

const AGE_TO_TARGET: Record<AgeBand, number> = {
  '3-5': 4,
  '6-8': 7,
  '9-12': 10,
}

function pickMimeType(): string {
  if (typeof MediaRecorder === 'undefined') return ''
  // Prefer webm/opus (Chrome/Firefox/Android) over mp4 (Safari).
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/mpeg']
  for (const candidate of candidates) {
    if (MediaRecorder.isTypeSupported?.(candidate)) return candidate
  }
  return ''
}

function filenameFor(mime: string): string {
  if (mime.includes('mp4')) return 'recording.mp4'
  if (mime.includes('mpeg')) return 'recording.mp3'
  return 'recording.webm'
}

export function useVoiceInput(options: UseVoiceInputOptions): UseVoiceInputResult {
  const { ageGroup, maxDurationMs = 30_000, languageHint, onText, onRejected, onError } = options

  const [state, dispatch] = useReducer(voiceReducer, 'idle' as VoiceInputState)
  const [partialText, setPartialText] = useState('')

  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const stopTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Capability check on mount.
  useEffect(() => {
    if (
      typeof navigator === 'undefined' ||
      !navigator.mediaDevices?.getUserMedia ||
      typeof MediaRecorder === 'undefined'
    ) {
      dispatch({ type: 'markUnsupported' })
    }
  }, [])

  const clearTimer = useCallback(() => {
    if (stopTimerRef.current != null) {
      clearTimeout(stopTimerRef.current)
      stopTimerRef.current = null
    }
  }, [])

  const stopStream = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
  }, [])

  // Cleanup on unmount.
  useEffect(() => () => {
    clearTimer()
    if (recorderRef.current && recorderRef.current.state !== 'inactive') {
      try { recorderRef.current.stop() } catch { /* swallow */ }
    }
    stopStream()
  }, [clearTimer, stopStream])

  // Pump the request stage: get mic, start MediaRecorder, schedule the auto-stop.
  useEffect(() => {
    if (state !== 'requesting') return
    let cancelled = false

    navigator.mediaDevices
      .getUserMedia({ audio: true, video: false })
      .then((stream) => {
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop())
          return
        }
        streamRef.current = stream
        const mimeType = pickMimeType()
        let recorder: MediaRecorder
        try {
          recorder = mimeType
            ? new MediaRecorder(stream, { mimeType })
            : new MediaRecorder(stream)
        } catch (err) {
          dispatch({ type: 'streamError' })
          onError?.('unknown')
          return
        }
        recorderRef.current = recorder
        chunksRef.current = []
        recorder.ondataavailable = (ev) => {
          if (ev.data && ev.data.size > 0) chunksRef.current.push(ev.data)
        }
        recorder.onstop = async () => {
          const collected = chunksRef.current
          const effectiveMime = recorder.mimeType || mimeType || 'audio/webm'
          const blob = new Blob(collected, { type: effectiveMime })
          stopStream()
          if (blob.size === 0) {
            dispatch({ type: 'transcriptionRejected' })
            onRejected?.()
            return
          }
          try {
            const result: TranscriptionResponse = await transcriptionService.transcribe({
              audio: blob,
              filename: filenameFor(effectiveMime),
              targetAge: AGE_TO_TARGET[ageGroup],
              languageHint,
            })
            if (!result.safety_passed || !result.text) {
              setPartialText('')
              dispatch({ type: 'transcriptionRejected' })
              onRejected?.()
              return
            }
            setPartialText(result.text)
            dispatch({ type: 'transcriptionPassed' })
            onText?.(result.text)
          } catch (err) {
            dispatch({ type: 'transcriptionError' })
            onError?.('unknown')
          }
        }
        recorder.start()
        dispatch({ type: 'streamReady' })
        clearTimer()
        stopTimerRef.current = setTimeout(() => {
          if (recorderRef.current && recorderRef.current.state === 'recording') {
            recorderRef.current.stop()
            dispatch({ type: 'stopRecording' })
          }
        }, maxDurationMs)
      })
      .catch((err) => {
        if (cancelled) return
        const name = (err as { name?: string })?.name
        const kind = name === 'NotAllowedError' || name === 'SecurityError' ? 'denied' : 'unknown'
        dispatch({ type: 'streamError' })
        onError?.(kind)
      })

    return () => { cancelled = true }
  }, [state, ageGroup, maxDurationMs, languageHint, clearTimer, stopStream, onText, onRejected, onError])

  const start = useCallback((consentGranted: boolean) => {
    setPartialText('')
    dispatch({ type: 'start', consentGranted })
  }, [])

  const stop = useCallback(() => {
    clearTimer()
    if (recorderRef.current && recorderRef.current.state === 'recording') {
      recorderRef.current.stop()
      dispatch({ type: 'stopRecording' })
    }
  }, [clearTimer])

  const reset = useCallback(() => {
    setPartialText('')
    dispatch({ type: 'reset' })
  }, [])

  const consentGranted = useCallback(() => dispatch({ type: 'consentGranted' }), [])
  const consentDismissed = useCallback(() => dispatch({ type: 'consentDismissed' }), [])

  return {
    state,
    partialText,
    start,
    stop,
    reset,
    consentGranted,
    consentDismissed,
  }
}
