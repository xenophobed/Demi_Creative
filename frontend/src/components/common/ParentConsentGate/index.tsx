/**
 * ParentConsentGate (#588) — in-app modal that gates first-use of camera
 * or microphone surfaces in epic #579 (PRD §3.15).
 *
 * Rendered by CameraCapture (#581) and VoiceInputButton (#584) before
 * any `navigator.mediaDevices.getUserMedia` call when the child profile
 * has not yet granted the corresponding consent flag.
 *
 * Flow:
 *   1. Show kid-friendly explainer + age-adapted copy.
 *   2. Parent re-enters their password (verified via authService.login
 *      against the currently-stored email — refreshes the session).
 *   3. On success, call useChildStore.updateConsent(childId, {<kind>_consent: true})
 *      then invoke onGranted. The browser permission prompt fires next,
 *      owned by the consumer hook.
 *
 * The component NEVER calls getUserMedia itself. It is a pure consent
 * gate so the same component can wrap either camera or microphone
 * surfaces without coupling to media stream code.
 */

import { useState } from 'react'
import authService from '@/api/services/authService'
import useAuthStore from '@/store/useAuthStore'
import useChildStore from '@/store/useChildStore'
import type { AgeGroup } from '@/types/api'

export type ConsentKind = 'camera' | 'microphone'

export interface ParentConsentGateProps {
  kind: ConsentKind
  ageGroup: AgeGroup
  childId: string
  onGranted: () => void
  onDismiss: () => void
}

interface GateCopy {
  emoji: string
  title: string
  body: string
}

export const GATE_COPY: Record<ConsentKind, Record<AgeGroup, GateCopy>> = {
  camera: {
    '3-5': {
      emoji: '📸',
      title: 'Can we use the camera?',
      body: "Ask a grown-up to type their password so we can take a picture of your drawing.",
    },
    '6-8': {
      emoji: '📸',
      title: 'Use the camera?',
      body: "We need a grown-up's OK before we use the camera. Your photo only gets used to make your story.",
    },
    '9-12': {
      emoji: '📸',
      title: 'Allow camera access',
      body: 'A parent must approve camera access before the browser asks. Photos are only used to create your story and follow the same retention rules as uploaded files.',
    },
  },
  microphone: {
    '3-5': {
      emoji: '🎤',
      title: 'Can we listen to you?',
      body: "Ask a grown-up to type their password so we can hear your story idea.",
    },
    '6-8': {
      emoji: '🎤',
      title: 'Use the microphone?',
      body: "We need a grown-up's OK before we listen. We only turn your words into text — we don't save the recording.",
    },
    '9-12': {
      emoji: '🎤',
      title: 'Allow microphone access',
      body: 'A parent must approve microphone access. Audio is transcribed and never stored — only the moderated text reaches your input.',
    },
  },
}

export function ParentConsentGate({
  kind,
  ageGroup,
  childId,
  onGranted,
  onDismiss,
}: ParentConsentGateProps) {
  const user = useAuthStore((s) => s.user)
  const updateConsent = useChildStore((s) => s.updateConsent)

  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const copy = GATE_COPY[kind][ageGroup]
  const consentField = kind === 'camera' ? 'camera_consent' : 'microphone_consent'

  async function handleAllow(event: React.FormEvent) {
    event.preventDefault()
    if (!user?.email) {
      setError("Sign in first, then try again.")
      return
    }
    if (!password) {
      setError("Please enter the parent password.")
      return
    }

    setSubmitting(true)
    setError(null)
    try {
      await authService.login({
        username_or_email: user.email,
        password,
      })
      await updateConsent(childId, { [consentField]: true })
      onGranted()
    } catch (err) {
      setError("That password didn't match. Please try again.")
    } finally {
      setSubmitting(false)
    }
  }

  function handleDismiss() {
    if (submitting) return
    onDismiss()
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={copy.title}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onKeyDown={(e) => {
        if (e.key === 'Escape') handleDismiss()
      }}
    >
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex flex-col items-center gap-2 text-center">
          <span className="text-5xl" aria-hidden="true">{copy.emoji}</span>
          <h2 className="text-xl font-bold text-gray-800">{copy.title}</h2>
          <p className="text-sm text-gray-600">{copy.body}</p>
        </div>

        <form onSubmit={handleAllow} className="space-y-3">
          <label className="block text-sm font-medium text-gray-700">
            Parent password
            <input
              type="password"
              autoComplete="current-password"
              autoFocus
              value={password}
              disabled={submitting}
              onChange={(e) => {
                setPassword(e.target.value)
                if (error) setError(null)
              }}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-base focus:border-primary focus:outline-none disabled:opacity-60"
            />
          </label>

          {error && (
            <p
              role="alert"
              className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700"
            >
              {error}
            </p>
          )}

          <div className="flex gap-2 pt-2">
            <button
              type="button"
              onClick={handleDismiss}
              disabled={submitting}
              className="flex-1 rounded-xl border border-gray-300 px-4 py-3 text-base font-semibold text-gray-700 disabled:opacity-60"
            >
              Not now
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="flex-1 rounded-xl bg-primary px-4 py-3 text-base font-bold text-white shadow disabled:opacity-60"
            >
              {submitting ? 'Checking…' : 'Allow'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default ParentConsentGate
