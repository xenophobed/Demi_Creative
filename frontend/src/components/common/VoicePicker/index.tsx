import { useState, useEffect, useCallback, useRef } from 'react'
import { Howl } from 'howler'
import { motion, AnimatePresence } from 'framer-motion'
import type { AgeGroup } from '@/types/api'
import apiClient from '@/api/client'
import { storyService } from '@/api/services/storyService'
import {
  Bot,
  BookOpen,
  LoaderCircle,
  Mic,
  Play,
  Radio,
  Theater,
  UserRound,
  Volume2,
} from 'lucide-react'

export interface VoiceEntry {
  voice_id: string
  provider: string
  display_name: string
  description: string
  recommended_for: string
}

interface VoicePickerProps {
  ageGroup: AgeGroup | null
  selectedVoice: string
  onVoiceChange: (voiceId: string, provider: string) => void
  className?: string
}

const PROVIDER_LABELS: Record<string, string> = {
  openai: 'Standard',
  replicate: 'Expressive',
  elevenlabs: 'Premium',
}

const PROVIDER_COLORS: Record<string, string> = {
  openai: 'bg-blue-50 border-blue-200',
  replicate: 'bg-purple-50 border-purple-200',
  elevenlabs: 'bg-amber-50 border-amber-200',
}

const VOICE_ICONS: Record<string, typeof Mic> = {
  // OpenAI
  nova: UserRound,
  shimmer: Radio,
  fable: BookOpen,
  echo: UserRound,
  alloy: Bot,
  onyx: Theater,
  // ElevenLabs (by display name keywords)
  default: Mic,
}

function getVoiceIcon(voice: VoiceEntry): typeof Mic {
  // Check by voice_id first (OpenAI voices)
  if (voice.voice_id in VOICE_ICONS) return VOICE_ICONS[voice.voice_id]
  // Infer from description
  const desc = voice.description.toLowerCase()
  if (desc.includes('female') || desc.includes('girl') || desc.includes('woman')) return UserRound
  if (desc.includes('male') || desc.includes('man') || desc.includes('boy') || desc.includes('knight')) return UserRound
  return VOICE_ICONS.default
}

// Max voices shown per age group for young children
const MAX_VOICES_YOUNG = 4

const STORAGE_KEY = 'last-voice-preference'

function loadLastVoice(): { voiceId: string; provider: string } | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return stored ? JSON.parse(stored) : null
  } catch {
    return null
  }
}

function saveLastVoice(voiceId: string, provider: string) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ voiceId, provider }))
  } catch {
    // Ignore storage errors
  }
}

const COLLAPSED_LIMIT = 6

function VoicePicker({ ageGroup, selectedVoice, onVoiceChange, className = '' }: VoicePickerProps) {
  const [voices, setVoices] = useState<VoiceEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [previewingId, setPreviewingId] = useState<string | null>(null)
  const [previewLoading, setPreviewLoading] = useState<string | null>(null)
  const [expanded, setExpanded] = useState(false)
  const previewAudioRef = useRef<Howl | null>(null)

  // Cleanup Howl on unmount
  useEffect(() => {
    return () => {
      if (previewAudioRef.current) {
        previewAudioRef.current.stop()
        previewAudioRef.current.unload()
        previewAudioRef.current = null
      }
    }
  }, [])

  // Fetch voices from API
  const fetchVoices = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (ageGroup) params.age_group = ageGroup
      const { data } = await apiClient.get<{ voices: VoiceEntry[]; total: number }>('/audio/voices', { params })
      setVoices(data.voices)
    } catch {
      // Fallback to empty — the component will show a message
      setVoices([])
    } finally {
      setLoading(false)
    }
  }, [ageGroup])

  useEffect(() => {
    fetchVoices()
  }, [fetchVoices])

  // Restore last voice on mount
  useEffect(() => {
    if (!selectedVoice) {
      const last = loadLastVoice()
      if (last) {
        onVoiceChange(last.voiceId, last.provider)
      }
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleSelect = (voice: VoiceEntry) => {
    onVoiceChange(voice.voice_id, voice.provider)
    saveLastVoice(voice.voice_id, voice.provider)
  }

  const handlePreview = async (voice: VoiceEntry, e: React.MouseEvent) => {
    e.stopPropagation()

    // Stop any current preview
    if (previewAudioRef.current) {
      previewAudioRef.current.stop()
      previewAudioRef.current.unload()
      previewAudioRef.current = null
    }

    // Toggle off if same voice
    if (previewingId === voice.voice_id) {
      setPreviewingId(null)
      return
    }

    setPreviewLoading(voice.voice_id)
    setPreviewingId(null)

    try {
      const { audio_url } = await storyService.previewVoice(voice.voice_id, voice.provider)

      const howl = new Howl({
        src: [audio_url],
        html5: true,
        onend: () => setPreviewingId(null),
        onloaderror: () => {
          setPreviewingId(null)
          setPreviewLoading(null)
        },
      })

      previewAudioRef.current = howl
      setPreviewLoading(null)
      setPreviewingId(voice.voice_id)
      howl.play()
    } catch {
      setPreviewLoading(null)
      setPreviewingId(null)
    }
  }

  // Limit voices for young children, or collapse for other age groups
  const filteredVoices = ageGroup === '3-5' ? voices.slice(0, MAX_VOICES_YOUNG) : voices
  const displayVoices = (!expanded && ageGroup !== '3-5' && filteredVoices.length > COLLAPSED_LIMIT)
    ? filteredVoices.slice(0, COLLAPSED_LIMIT)
    : filteredVoices
  const canExpand = ageGroup !== '3-5' && filteredVoices.length > COLLAPSED_LIMIT

  // Group by provider for 9-12 age group
  const showProviderInfo = ageGroup === '9-12'

  if (loading) {
    return (
      <div className={`flex items-center justify-center p-4 ${className}`}>
        <motion.span
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
          className="text-primary"
        >
          <LoaderCircle size={22} />
        </motion.span>
        <span className="ml-2 text-gray-500 text-sm">Loading voices...</span>
      </div>
    )
  }

  if (voices.length === 0) {
    return (
      <div className={`text-center text-gray-400 p-4 ${className}`}>
        No voices available
      </div>
    )
  }

  return (
    <div className={className}>
      <div className={`grid gap-2 ${
        ageGroup === '3-5'
          ? 'grid-cols-2'
          : 'grid-cols-2 md:grid-cols-4'
      }`}>
        <AnimatePresence mode="popLayout">
          {displayVoices.map((voice, index) => {
            const isSelected = selectedVoice === voice.voice_id
            const isPreviewing = previewingId === voice.voice_id
            const isLoadingPreview = previewLoading === voice.voice_id
            const VoiceIcon = getVoiceIcon(voice)

            return (
              <motion.div
                key={voice.voice_id}
                layout
                role="button"
                tabIndex={0}
                className={`relative p-3 rounded-xl border-2 transition-all text-left cursor-pointer ${
                  isSelected
                    ? 'border-secondary bg-secondary/10 shadow-md ring-2 ring-secondary/30'
                    : showProviderInfo
                      ? PROVIDER_COLORS[voice.provider] || 'border-gray-200'
                      : 'border-gray-200 hover:border-gray-300'
                }`}
                onClick={() => handleSelect(voice)}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleSelect(voice) } }}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: index * 0.03 }}
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
              >
                <div className="flex items-start gap-2">
                  <motion.span
                    className={`flex items-center justify-center rounded-lg bg-gray-100 text-gray-600 ${
                      ageGroup === '3-5' ? 'h-10 w-10' : 'h-8 w-8'
                    }`}
                    animate={isSelected ? { scale: [1, 1.2, 1] } : {}}
                  >
                    <VoiceIcon size={ageGroup === '3-5' ? 22 : 18} />
                  </motion.span>
                  <div className="flex-1 min-w-0">
                    <div className={`font-medium truncate ${ageGroup === '3-5' ? 'text-base' : 'text-sm'}`}>
                      {voice.display_name}
                    </div>
                    {ageGroup !== '3-5' && (
                      <div className="text-xs text-gray-500 truncate">{voice.description}</div>
                    )}
                    {showProviderInfo && (
                      <span className="inline-block mt-1 px-1.5 py-0.5 text-[10px] font-medium rounded bg-gray-100 text-gray-500">
                        {PROVIDER_LABELS[voice.provider] || voice.provider}
                      </span>
                    )}
                  </div>

                  {/* Preview button */}
                  <motion.button
                    className={`shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs ${
                      isPreviewing
                        ? 'bg-secondary/20 text-secondary'
                        : isLoadingPreview
                          ? 'bg-yellow-50 text-yellow-500'
                          : 'bg-gray-100 text-gray-400 hover:bg-gray-200'
                    }`}
                    onClick={(e) => handlePreview(voice, e)}
                    disabled={isLoadingPreview}
                    whileHover={{ scale: 1.1 }}
                    whileTap={{ scale: 0.9 }}
                    title="Preview voice"
                  >
                    {isLoadingPreview ? (
                      <motion.span
                        animate={{ rotate: 360 }}
                        transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                      >
                        <LoaderCircle size={14} />
                      </motion.span>
                    ) : isPreviewing ? (
                      <motion.span
                        animate={{ scale: [1, 1.3, 1] }}
                        transition={{ duration: 0.5, repeat: Infinity }}
                      >
                        <Volume2 size={14} />
                      </motion.span>
                    ) : (
                      <Play size={14} fill="currentColor" />
                    )}
                  </motion.button>
                </div>
              </motion.div>
            )
          })}
        </AnimatePresence>
      </div>
      {canExpand && (
        <motion.button
          className="mt-3 w-full py-2 text-sm font-medium text-gray-500 hover:text-primary bg-gray-50 hover:bg-primary/5 rounded-xl transition-colors"
          onClick={() => setExpanded(!expanded)}
          whileTap={{ scale: 0.98 }}
        >
          {expanded ? 'Show fewer voices' : `Show all voices (${filteredVoices.length})`}
        </motion.button>
      )}
    </div>
  )
}

export default VoicePicker
