import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useQuery } from '@tanstack/react-query'
import Card from '@/components/common/Card'
import Button from '@/components/common/Button'
import { storyService } from '@/api/services/storyService'
import useChildStore from '@/store/useChildStore'

const ROLE_META = {
  curious_kid: { label: 'Curious Kid', emoji: '🧒' },
  fun_expert: { label: 'Fun Expert', emoji: '🧑‍🏫' },
  guest: { label: 'Guest Anchor', emoji: '🦉' },
} as const

function morningShowAudioSrc(url?: string | null): string | null {
  if (!url) return null
  return url.startsWith('/') ? url : `/${url}`
}

function formatDuration(seconds?: number | null): string {
  if (!seconds || seconds <= 0) return '1 min'
  const mins = Math.max(1, Math.round(seconds / 60))
  return `${mins} min`
}

function MorningShowPage() {
  const navigate = useNavigate()
  const { episodeId } = useParams<{ episodeId: string }>()
  const { currentChild, defaultChildId } = useChildStore()

  const [currentLineIndex, setCurrentLineIndex] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [playbackRate, setPlaybackRate] = useState(1)
  const [lineElapsed, setLineElapsed] = useState(0)
  const [hasStarted, setHasStarted] = useState(false)

  const audioRef = useRef<HTMLAudioElement | null>(null)
  const startTrackedRef = useRef(false)
  const completionTrackedRef = useRef(false)

  const { data: episode, isLoading, error } = useQuery({
    queryKey: ['morning-show-episode', episodeId],
    queryFn: () => storyService.getMorningShowEpisode(episodeId || ''),
    enabled: !!episodeId,
  })

  const lines = episode?.dialogue_script.lines ?? []
  const currentLine = lines[currentLineIndex]

  const illustrations = useMemo(
    () => (episode?.illustrations ?? []).slice().sort((a, b) => a.display_order - b.display_order),
    [episode?.illustrations]
  )

  const currentStoryTime = (currentLine?.timestamp_start ?? 0) + lineElapsed
  const totalDuration = episode?.dialogue_script.total_duration || 1
  const progressRatio = Math.min(1, Math.max(0, currentStoryTime / totalDuration))
  const trackingChildId = currentChild?.child_id || defaultChildId || episode?.child_id || ''

  const activeIllustrationIndex = illustrations.length > 0
    ? Math.min(
        illustrations.length - 1,
        Math.floor((currentStoryTime / totalDuration) * illustrations.length)
      )
    : 0

  const activeIllustration = illustrations[activeIllustrationIndex]

  const isFinished = hasStarted && !isPlaying && currentLineIndex >= Math.max(0, lines.length - 1)

  const trackEvent = async (
    eventType: 'start' | 'progress' | 'complete' | 'abandon',
    progress: number
  ) => {
    if (!episode || !trackingChildId) return
    try {
      await storyService.trackMorningShowEvent({
        child_id: trackingChildId,
        episode_id: episode.episode_id,
        topic: episode.category,
        event_type: eventType,
        progress,
        played_seconds: progress * totalDuration,
      })
    } catch {
      // Playback should continue even if tracking fails.
    }
  }

  useEffect(() => {
    if (!episode || !audioRef.current || lines.length === 0) return

    const currentAudioUrl = morningShowAudioSrc(episode.audio_urls[String(currentLineIndex)])

    if (!currentAudioUrl) {
      if (isPlaying && currentLineIndex < lines.length - 1) {
        setCurrentLineIndex((prev) => prev + 1)
      } else {
        setIsPlaying(false)
      }
      return
    }

    const audio = audioRef.current
    audio.src = currentAudioUrl
    audio.playbackRate = playbackRate
    setLineElapsed(0)

    if (isPlaying) {
      audio
        .play()
        .catch(() => {
          setIsPlaying(false)
        })
    } else {
      audio.pause()
    }
  }, [episode, currentLineIndex, isPlaying, playbackRate, lines.length])

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    const handleEnded = () => {
      if (currentLineIndex < lines.length - 1) {
        setCurrentLineIndex((prev) => prev + 1)
      } else {
        setIsPlaying(false)
      }
    }

    const handleTimeUpdate = () => {
      setLineElapsed(audio.currentTime)
    }

    audio.addEventListener('ended', handleEnded)
    audio.addEventListener('timeupdate', handleTimeUpdate)

    return () => {
      audio.removeEventListener('ended', handleEnded)
      audio.removeEventListener('timeupdate', handleTimeUpdate)
    }
  }, [currentLineIndex, lines.length])

  useEffect(() => {
    if (!episode || !hasStarted || completionTrackedRef.current) return
    if (isFinished && progressRatio >= 0.8) {
      completionTrackedRef.current = true
      void trackEvent('complete', progressRatio)
    }
  }, [episode, hasStarted, isFinished, progressRatio])

  useEffect(() => {
    return () => {
      if (!episode || !hasStarted || completionTrackedRef.current) return
      if (progressRatio < 0.5) {
        void trackEvent('abandon', progressRatio)
      }
    }
  }, [episode, hasStarted, progressRatio])

  if (isLoading) {
    return <div className="text-center py-16 text-gray-500">Loading Morning Show episode...</div>
  }

  if (error || !episode) {
    return (
      <div className="max-w-2xl mx-auto text-center py-16 space-y-4">
        <h1 className="text-2xl font-bold text-gray-800">Episode not found</h1>
        <p className="text-gray-500">This Morning Show episode may have been removed.</p>
        <Button onClick={() => navigate('/library')}>Back to Library</Button>
      </div>
    )
  }

  const ageGroup = episode.age_group
  const avatarSize = ageGroup === '3-5' ? 'text-3xl' : 'text-2xl'

  return (
    <div className="space-y-4">
      <audio ref={audioRef} preload="auto" />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">{episode.kid_title}</h1>
          <p className="text-sm text-gray-500">
            {episode.category.toUpperCase()} · {formatDuration(episode.duration_seconds)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/morning-show/subscriptions">
            <Button variant="outline" size="sm">Manage Topics</Button>
          </Link>
          <Button variant="ghost" size="sm" onClick={() => navigate('/library')}>Back to Library</Button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        <div className="space-y-4">
          <Card className="overflow-hidden">
            <div className="relative aspect-video bg-slate-100 rounded-xl overflow-hidden">
              <AnimatePresence mode="wait">
                {activeIllustration ? (
                  <motion.img
                    key={activeIllustration.url}
                    src={activeIllustration.url}
                    alt={activeIllustration.description}
                    className="absolute inset-0 w-full h-full object-cover"
                    initial={{ opacity: 0, scale: 1.02 }}
                    animate={{
                      opacity: 1,
                      scale: activeIllustration.animation_type === 'zoom' ? 1.08 : 1.04,
                      x: activeIllustration.animation_type === 'pan' ? -12 : 0,
                      y: activeIllustration.animation_type === 'ken_burns' ? -8 : 0,
                    }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 1.2, ease: 'easeInOut' }}
                  />
                ) : (
                  <div className="absolute inset-0 flex items-center justify-center text-gray-400">No illustrations</div>
                )}
              </AnimatePresence>
            </div>
          </Card>

          <Card>
            <div className="flex flex-wrap items-center gap-3">
              {(['curious_kid', 'fun_expert', 'guest'] as const).map((role) => {
                const active = currentLine?.role === role
                return (
                  <motion.div
                    key={role}
                    className={`px-3 py-2 rounded-xl border text-sm ${active ? 'border-primary bg-primary/10 text-primary' : 'border-gray-200 text-gray-500'}`}
                    animate={active ? { scale: [1, 1.04, 1] } : { scale: 1 }}
                    transition={{ duration: 0.8, repeat: active ? Infinity : 0 }}
                  >
                    <span className={`${avatarSize} mr-2`}>{ROLE_META[role].emoji}</span>
                    {ROLE_META[role].label}
                  </motion.div>
                )
              })}
            </div>
          </Card>

          <Card>
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  onClick={() => {
                    if (lines.length === 0) return
                    setHasStarted(true)
                    if (!startTrackedRef.current) {
                      startTrackedRef.current = true
                      void trackEvent('start', progressRatio)
                    }
                    setIsPlaying((prev) => !prev)
                  }}
                >
                  {isPlaying ? 'Pause' : 'Play'}
                </Button>
                <select
                  className="text-sm px-2 py-1.5 rounded-lg border border-gray-200"
                  value={playbackRate}
                  onChange={(e) => setPlaybackRate(Number(e.target.value))}
                >
                  <option value={0.8}>0.8x</option>
                  <option value={1}>1.0x</option>
                  <option value={1.2}>1.2x</option>
                </select>
                <div className="text-sm text-gray-500">
                  Line {lines.length > 0 ? currentLineIndex + 1 : 0}/{lines.length}
                </div>
              </div>

              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <motion.div
                  className="h-full bg-primary"
                  animate={{ width: `${Math.min(100, Math.max(0, (currentStoryTime / totalDuration) * 100))}%` }}
                  transition={{ duration: 0.2 }}
                />
              </div>

              <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
                {lines.map((line, index) => {
                  const active = index === currentLineIndex
                  return (
                    <div
                      key={`${line.role}-${index}`}
                      className={`rounded-xl border px-3 py-2 text-sm transition-colors ${
                        active ? 'border-primary bg-primary/5' : 'border-gray-200 bg-white'
                      }`}
                    >
                      <p className="font-semibold text-xs text-gray-500 mb-1">
                        {ROLE_META[line.role].emoji} {ROLE_META[line.role].label}
                      </p>
                      <p className="text-gray-700">{line.text}</p>
                    </div>
                  )
                })}
              </div>
            </div>
          </Card>
        </div>

        <aside className="space-y-4">
          <Card>
            <h2 className="text-lg font-bold text-gray-800 mb-2">Episode Info</h2>
            <p className="text-sm text-gray-600 leading-relaxed">{episode.kid_content}</p>
          </Card>

          {isFinished && (
            <>
              <Card>
                <h3 className="text-base font-bold text-gray-800 mb-2">Why Should I Care?</h3>
                <p className="text-sm text-gray-600">{episode.why_care}</p>
              </Card>

              <Card>
                <h3 className="text-base font-bold text-gray-800 mb-2">Key Concepts</h3>
                <div className="space-y-2">
                  {episode.key_concepts.map((concept) => (
                    <div key={concept.term} className="text-sm bg-gray-50 rounded-lg p-2">
                      <span className="font-semibold text-gray-800">{concept.emoji} {concept.term}:</span>{' '}
                      <span className="text-gray-600">{concept.explanation}</span>
                    </div>
                  ))}
                </div>
              </Card>

              <Card>
                <h3 className="text-base font-bold text-gray-800 mb-2">Think About It</h3>
                <div className="space-y-2">
                  {episode.interactive_questions.map((q, idx) => (
                    <div key={idx} className="text-sm bg-primary/5 border border-primary/15 rounded-lg p-2">
                      <p className="text-gray-700">{q.emoji} {q.question}</p>
                    </div>
                  ))}
                </div>
              </Card>
            </>
          )}
        </aside>
      </div>
    </div>
  )
}

export default MorningShowPage
