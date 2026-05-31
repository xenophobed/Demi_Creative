/**
 * VoiceInputButton (#584) — drop-in mic button that records audio,
 * posts to /api/v1/audio/transcriptions, and calls onText with the
 * safety-moderated transcript.
 *
 * Designed to sit next to any <input> or <textarea>. The consumer
 * (e.g. InteractiveStoryPage in #585, AgentChatPanel in #586) decides
 * what to do with the returned text — append vs replace, truncate vs not.
 *
 * Consent gating: the consumer surface is responsible for rendering
 * <ParentConsentGate kind="microphone" /> (from #588) when
 * currentChild.microphone_consent is false. This component takes a
 * consentGranted prop and starts immediately when true.
 */

import { useCallback } from 'react'
import { motion } from 'framer-motion'
import { useVoiceInput, type AgeBand } from '@/hooks/useVoiceInput'

export interface VoiceInputButtonProps {
  ageGroup: AgeBand
  onText: (text: string) => void
  contextHint?: string
  maxDurationMs?: number
  /**
   * When true, the caller has already established mic consent. When
   * false, the button stays in idle and the consumer should mount the
   * consent gate, then update this prop.
   */
  consentGranted?: boolean
  className?: string
}

const STATUS_COPY: Record<string, string> = {
  idle: 'Tap to speak',
  'consent-required': 'Parent permission needed',
  requesting: 'Asking for microphone…',
  recording: "I'm listening — tap to stop",
  processing: 'Working on what you said…',
  done: 'Got it!',
  rejected: "Didn't catch that. Try again?",
  error: "Microphone trouble. Try again or type instead.",
  unsupported: "This browser can't record voice yet.",
}

export function VoiceInputButton({
  ageGroup,
  onText,
  maxDurationMs,
  consentGranted = true,
  className = '',
}: VoiceInputButtonProps) {
  const voice = useVoiceInput({ ageGroup, maxDurationMs, onText })

  const handleToggle = useCallback(() => {
    if (voice.state === 'recording') {
      voice.stop()
    } else if (voice.state === 'idle' || voice.state === 'done' || voice.state === 'rejected' || voice.state === 'error') {
      voice.start(consentGranted)
    }
  }, [voice, consentGranted])

  const disabled =
    voice.state === 'unsupported' ||
    voice.state === 'requesting' ||
    voice.state === 'processing' ||
    voice.state === 'consent-required'

  const recording = voice.state === 'recording'

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <motion.button
        type="button"
        onClick={handleToggle}
        disabled={disabled}
        whileTap={disabled ? undefined : { scale: 0.92 }}
        animate={
          recording
            ? { scale: [1, 1.08, 1] }
            : { scale: 1 }
        }
        transition={
          recording
            ? { duration: 1, repeat: Infinity }
            : { duration: 0.2 }
        }
        className={`
          inline-flex h-12 w-12 items-center justify-center rounded-full
          text-2xl shadow-md transition-colors
          ${recording ? 'bg-red-500 text-white' : 'bg-primary text-white'}
          disabled:cursor-not-allowed disabled:opacity-60
        `}
        aria-label={recording ? 'Stop recording' : 'Start voice input'}
        aria-pressed={recording}
      >
        <span aria-hidden="true">{recording ? '⏹️' : '🎤'}</span>
      </motion.button>

      <span
        aria-live="polite"
        className="text-sm text-gray-600"
      >
        {STATUS_COPY[voice.state] ?? STATUS_COPY.idle}
      </span>
    </div>
  )
}

export default VoiceInputButton
