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

export type ConsentKind = 'camera' | 'microphone' | 'voice_conversation'

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

export const GATE_ERROR_COPY = {
  wrong_password: "That password didn't match. Try again.",
  child_not_found:
    "We can't find this child profile. Refresh the page and try again.",
  parent_required:
    "Only a parent account can change this. Log out and log in as the parent.",
  missing_email:
    "Sign in first, then try again.",
  unknown:
    "Something went wrong. Try again or refresh the page.",
} as const

export type GateErrorKind = keyof typeof GATE_ERROR_COPY

/** Map a thrown error from authService.login OR updateConsent to a
 *  user-facing copy key. Pure function so we can unit-test the mapping
 *  without rendering the modal.
 */
export function classifyGateError(err: unknown): GateErrorKind {
  const status =
    typeof err === 'object' && err !== null && 'response' in err
      ? (err as { response?: { status?: number } }).response?.status
      : undefined
  const code =
    typeof err === 'object' && err !== null && 'response' in err
      ? (err as { response?: { data?: { detail?: { code?: string } } } }).response?.data?.detail?.code
      : undefined

  if (status === 404 || code === 'CHILD_PROFILE_NOT_FOUND') return 'child_not_found'
  if (status === 403 || code === 'PARENT_ROLE_REQUIRED') return 'parent_required'
  if (status === 400 || status === 401 || status === 422) return 'wrong_password'

  // Supabase login throws a plain Error with a message — treat as
  // password-class failure since that's the most common interpretation.
  if (err instanceof Error && /password|credential|invalid/i.test(err.message)) {
    return 'wrong_password'
  }

  return 'unknown'
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
  voice_conversation: {
    '3-5': {
      emoji: '💬',
      title: 'Talk with your buddy?',
      body: "Ask a grown-up to say yes. Your buddy can listen AND talk back — like a real friend.",
    },
    '6-8': {
      emoji: '💬',
      title: 'Talk back-and-forth with your buddy?',
      body: "We need a grown-up's OK before your buddy speaks out loud. We only keep the words (not the audio) and check every reply for kid-safe content.",
    },
    '9-12': {
      emoji: '💬',
      title: 'Enable voice conversation',
      body: 'A parent must approve two-way voice chat. Audio is never stored — only the moderated transcript persists in your chat history, same as text mode. The session has a daily time cap.',
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
  // Map each kind to the child_profiles boolean it flips.
  const consentField =
    kind === 'camera'
      ? 'camera_consent'
      : kind === 'microphone'
        ? 'microphone_consent'
        : 'voice_conversation_consent'

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

    // Split the two calls so we can attribute the failure correctly.
    // Bundling them was the bug behind #603 — a 404 on consent-update
    // showed up as "password didn't match" and sent users hunting for a
    // password they hadn't actually mistyped.
    try {
      await authService.login({
        username_or_email: user.email,
        password,
      })
    } catch (err) {
      console.warn('ParentConsentGate: login failed', err)
      const kind = classifyGateError(err)
      // Login failure is almost always a password mismatch; map other
      // codes through the classifier in case the auth backend evolves.
      setError(
        kind === 'unknown' ? GATE_ERROR_COPY.wrong_password : GATE_ERROR_COPY[kind],
      )
      setSubmitting(false)
      return
    }

    try {
      await updateConsent(childId, { [consentField]: true })
      onGranted()
    } catch (err) {
      console.warn('ParentConsentGate: consent update failed', err)
      const kind = classifyGateError(err)
      setError(GATE_ERROR_COPY[kind])
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
