import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import Button from '@/components/common/Button'
import Card from '@/components/common/Card'
import AgeAwareContent from '@/components/common/AgeAwareContent'
import EducationalTags from '@/components/story/EducationalTags'
import StorySegmentDisplay from '@/components/interactive/StorySegmentDisplay'
import ChoiceButtons from '@/components/interactive/ChoiceButtons'
import ProgressIndicator from '@/components/interactive/ProgressIndicator'
import { StreamingVisualizer } from '@/components/streaming/StreamingVisualizer'
import { PerspectiveContainer } from '@/components/depth/PerspectiveContainer'
import { storyService } from '@/api/services/storyService'
import useInteractiveStory from '@/hooks/useInteractiveStory'
import useInteractiveStoryStore from '@/store/useInteractiveStoryStore'
import useStreamVisualization from '@/hooks/useStreamVisualization'
import useChildStore, { DEFAULT_INTERESTS } from '@/store/useChildStore'
import type { AgeGroup } from '@/types/api'
import type { AnimationPhase } from '@/types/streaming'

type PageState = 'setup' | 'playing' | 'completed'

const AGE_GROUPS: { value: AgeGroup; label: string; emoji: string }[] = [
  { value: '3-5', label: '3-5 yrs', emoji: '🧒' },
  { value: '6-9', label: '6-9 yrs', emoji: '👦' },
  { value: '10-12', label: '10-12 yrs', emoji: '🧑' },
]

function InteractiveStoryPage() {
  const navigate = useNavigate()
  const { defaultChildId } = useChildStore()

  // Local form state
  const [selectedAge, setSelectedAge] = useState<AgeGroup | null>(null)
  const [selectedInterests, setSelectedInterests] = useState<string[]>([])
  const [theme, setTheme] = useState('')

  // Story hook - use streaming versions for better UX
  const {
    sessionId,
    storyTitle,
    ageGroup: storeAgeGroup,
    currentSegment,
    choiceHistory,
    progress,
    isLoading,
    error,
    isCompleted,
    educationalSummary,
    streaming,
    startStoryStream,
    makeChoiceStream,
    reset,
  } = useInteractiveStory()

  // On-demand audio state (for 10-12 age group)
  const [onDemandAudioUrl, setOnDemandAudioUrl] = useState<string | null>(null)
  const [isAudioGenerating, setIsAudioGenerating] = useState(false)

  // Use storeAgeGroup during play, selectedAge during setup
  const activeAgeGroup = storeAgeGroup || selectedAge

  // Stream visualization hook
  const { triggerConfetti } = useStreamVisualization()

  // Map streaming state to animation phase
  const getAnimationPhase = (): AnimationPhase => {
    if (!streaming.isStreaming) return 'idle'
    if (streaming.streamStatus === 'started') return 'connecting'
    if (streaming.thinkingContent) return 'thinking'
    if (streaming.streamMessage.includes('tool')) return 'tool_executing'
    return 'thinking'
  }

  const animationPhase = getAnimationPhase()

  // Save state
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')

  // Validate persisted session on mount — if backend says expired/invalid, reset
  const storeStatus = useInteractiveStoryStore((s) => s.status)
  const [isValidating, setIsValidating] = useState(false)
  useEffect(() => {
    if (!sessionId || storeStatus === 'completed' || storeStatus === 'idle') return
    let cancelled = false
    setIsValidating(true)
    storyService
      .getSessionStatus(sessionId)
      .then((res) => {
        if (cancelled) return
        // Session expired or completed on backend — reset frontend
        if (res.status !== 'active') {
          reset()
        }
      })
      .catch(() => {
        // Session not found on backend (404) — reset
        if (!cancelled) reset()
      })
      .finally(() => {
        if (!cancelled) setIsValidating(false)
      })
    return () => { cancelled = true }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Track segment changes for reveal animation
  const [isRevealing, setIsRevealing] = useState(false)

  useEffect(() => {
    if (currentSegment && !streaming.isStreaming) {
      setIsRevealing(true)
      const timer = setTimeout(() => setIsRevealing(false), 2000)
      return () => clearTimeout(timer)
    }
  }, [currentSegment?.segment_id, streaming.isStreaming])

  // Reset on-demand audio when segment changes
  useEffect(() => {
    setOnDemandAudioUrl(null)
    setIsAudioGenerating(false)
  }, [currentSegment?.segment_id])

  // On-demand audio handler for 10-12 age group
  const handleRequestAudio = useCallback(async () => {
    if (!sessionId || !currentSegment || isAudioGenerating) return
    setIsAudioGenerating(true)
    try {
      const result = await storyService.generateAudioOnDemand(
        sessionId,
        currentSegment.segment_id
      )
      setOnDemandAudioUrl(result.audio_url)
    } catch {
      // Silently fail - button will remain clickable
    } finally {
      setIsAudioGenerating(false)
    }
  }, [sessionId, currentSegment, isAudioGenerating])

  // Trigger confetti on completion
  useEffect(() => {
    if (isCompleted) {
      triggerConfetti()
    }
  }, [isCompleted, triggerConfetti])

  // Determine page state — show setup while validating a stale session
  const getPageState = (): PageState => {
    if (isValidating) return 'setup'
    if (isCompleted) return 'completed'
    if (currentSegment) return 'playing'
    return 'setup'
  }

  const pageState = getPageState()

  // Toggle interest selection
  const toggleInterest = (interest: string) => {
    if (selectedInterests.includes(interest)) {
      setSelectedInterests(selectedInterests.filter((i) => i !== interest))
    } else if (selectedInterests.length < 5) {
      setSelectedInterests([...selectedInterests, interest])
    }
  }

  // Start story handler - uses streaming for real-time progress
  const handleStartStory = async () => {
    if (!selectedAge || selectedInterests.length === 0) return

    try {
      await startStoryStream({
        child_id: defaultChildId,
        age_group: selectedAge,
        interests: selectedInterests,
        theme: theme || undefined,
      })
    } catch {
      // Error is handled by the hook
    }
  }

  // Choice handler - uses streaming for real-time progress
  const handleChoice = async (choiceId: string) => {
    try {
      await makeChoiceStream(choiceId)
    } catch {
      // Error is handled by the hook
    }
  }

  // Reset handler
  const handleReset = () => {
    reset()
    setSelectedAge(null)
    setSelectedInterests([])
    setTheme('')
  }

  // Save interactive story to My Stories
  const handleSaveStory = useCallback(async () => {
    if (!sessionId || saveStatus === 'saving' || saveStatus === 'saved') return
    setSaveStatus('saving')
    try {
      await storyService.saveInteractiveStory(sessionId)
      setSaveStatus('saved')
    } catch {
      setSaveStatus('error')
    }
  }, [sessionId, saveStatus])

  // Calculate total segments (estimate based on progress)
  const totalSegments = progress > 0 ? Math.round((choiceHistory.length + 1) / progress) : 5

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <motion.div
        className="text-center"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <motion.span
          className="text-5xl inline-block"
          animate={{ rotate: [0, -5, 5, 0] }}
          transition={{ duration: 3, repeat: Infinity }}
        >
          🎭
        </motion.span>
        <h1 className="text-2xl md:text-3xl font-bold text-gray-800 mt-2">
          Interactive Story
        </h1>
        <p className="text-gray-600 mt-1">Choose your adventure, create unique story endings</p>
      </motion.div>

      {/* Error display */}
      {error && (
        <motion.div
          className="bg-red-50 border border-red-200 rounded-card p-4 text-red-700"
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
        >
          <div className="flex items-center gap-2">
            <span>❌</span>
            <span>{error}</span>
          </div>
        </motion.div>
      )}

      {/* Setup View */}
      {pageState === 'setup' && (
        <motion.div
          className="space-y-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          {/* Age Group Selection */}
          <Card>
            <h2 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
              <span>👶</span>
              Select Age Group
              <span className="text-red-500">*</span>
            </h2>
            <div className="grid grid-cols-3 gap-3">
              {AGE_GROUPS.map((age) => (
                <motion.button
                  key={age.value}
                  className={`
                    p-4 rounded-xl border-2 text-center transition-colors
                    ${
                      selectedAge === age.value
                        ? 'border-primary bg-primary/10'
                        : 'border-gray-200 hover:border-primary/50'
                    }
                  `}
                  onClick={() => setSelectedAge(age.value)}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                >
                  <span className="text-2xl block mb-1">{age.emoji}</span>
                  <span className="text-sm font-medium">{age.label}</span>
                </motion.button>
              ))}
            </div>
          </Card>

          {/* Interest Tags */}
          <Card>
            <h2 className="text-lg font-bold text-gray-800 mb-2 flex items-center gap-2">
              <span>💫</span>
              Select Interests
              <span className="text-sm font-normal text-gray-500">
                (1-5)
              </span>
            </h2>
            <p className="text-sm text-gray-500 mb-4">
              Selected {selectedInterests.length}/5
            </p>
            <div className="flex flex-wrap gap-2">
              {DEFAULT_INTERESTS.map((interest) => (
                <motion.button
                  key={interest}
                  className={`
                    px-4 py-2 rounded-full text-sm font-medium transition-colors
                    ${
                      selectedInterests.includes(interest)
                        ? 'bg-secondary text-white'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }
                    ${
                      selectedInterests.length >= 5 &&
                      !selectedInterests.includes(interest)
                        ? 'opacity-50 cursor-not-allowed'
                        : ''
                    }
                  `}
                  onClick={() => toggleInterest(interest)}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  disabled={
                    selectedInterests.length >= 5 &&
                    !selectedInterests.includes(interest)
                  }
                >
                  {interest}
                </motion.button>
              ))}
            </div>
          </Card>

          {/* Theme Input */}
          <Card>
            <h2 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
              <span>🎨</span>
              Story Theme
              <span className="text-sm font-normal text-gray-500">(Optional)</span>
            </h2>
            <input
              type="text"
              value={theme}
              onChange={(e) => setTheme(e.target.value)}
              placeholder="e.g., Finding lost treasure, Space adventure..."
              className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-primary focus:outline-none transition-colors"
              maxLength={50}
            />
          </Card>

          {/* Enhanced Streaming Progress with 2.5D Visualizer */}
          {streaming.isStreaming && (
            <StreamingVisualizer
              phase={animationPhase}
              message={streaming.streamMessage || 'Creating story...'}
              thinkingContent={streaming.thinkingContent}
              layout="card"
              showParticles={false}
              showSparkles
            />
          )}

          {/* Start Button */}
          <Button
            size="lg"
            className="w-full"
            onClick={handleStartStory}
            isLoading={isLoading}
            disabled={!selectedAge || selectedInterests.length === 0 || streaming.isStreaming}
            leftIcon={<span>🚀</span>}
          >
            {streaming.isStreaming ? 'Creating...' : 'Start Story'}
          </Button>
        </motion.div>
      )}

      {/* Playing View */}
      {pageState === 'playing' && currentSegment && (
        <motion.div
          className="space-y-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          {/* Progress */}
          <ProgressIndicator
            current={choiceHistory.length}
            total={totalSegments}
            choiceHistory={choiceHistory}
          />

          {/* Story Segment with age-aware content display */}
          <AgeAwareContent
            ageGroup={activeAgeGroup}
            audioUrl={currentSegment.audio_url || onDemandAudioUrl}
            onRequestAudio={handleRequestAudio}
            isAudioLoading={isAudioGenerating}
            autoPlayAudio={activeAgeGroup === '3-5'}
            textContent={
              <PerspectiveContainer enableTilt={false}>
                <StorySegmentDisplay
                  segment={currentSegment}
                  title={storyTitle}
                  segmentIndex={choiceHistory.length}
                  isRevealing={isRevealing}
                />
              </PerspectiveContainer>
            }
          />

          {/* Choices */}
          {!currentSegment.is_ending && currentSegment.choices.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-center text-gray-600 font-medium">
                What happens next?
              </h3>
              <ChoiceButtons
                choices={currentSegment.choices}
                onChoose={handleChoice}
                isLoading={isLoading}
                disabled={isLoading}
              />
            </div>
          )}

          {/* Loading overlay with streaming visualizer */}
          {isLoading && (
            <StreamingVisualizer
              phase={animationPhase}
              message={streaming.streamMessage || 'Story is unfolding...'}
              thinkingContent={streaming.thinkingContent}
              layout="card"
              showSparkles
            />
          )}
        </motion.div>
      )}

      {/* Completed View */}
      {pageState === 'completed' && (
        <motion.div
          className="space-y-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          {/* Final segment display with celebration */}
          {currentSegment && (
            <AgeAwareContent
              ageGroup={activeAgeGroup}
              audioUrl={currentSegment.audio_url || onDemandAudioUrl}
              onRequestAudio={handleRequestAudio}
              isAudioLoading={isAudioGenerating}
              autoPlayAudio={activeAgeGroup === '3-5'}
              textContent={
                <PerspectiveContainer enableTilt={false}>
                  <StorySegmentDisplay
                    segment={currentSegment}
                    title={storyTitle}
                    segmentIndex={choiceHistory.length}
                  />
                </PerspectiveContainer>
              }
            />
          )}

          {/* Educational Summary */}
          {educationalSummary && (
            <Card>
              <h3 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
                <span>📚</span>
                What You Learned
              </h3>
              <EducationalTags value={educationalSummary} />
            </Card>
          )}

          {/* Journey summary */}
          <Card variant="colorful" colorScheme="accent">
            <div className="text-center">
              <span className="text-4xl block mb-2">🏆</span>
              <h3 className="text-lg font-bold text-gray-800 mb-1">
                You completed this story!
              </h3>
              <p className="text-gray-600 text-sm">
                Made {choiceHistory.length} choices
              </p>
            </div>
          </Card>

          {/* Action buttons */}
          <div className="flex flex-col sm:flex-row gap-3">
            <Button
              variant="secondary"
              size="lg"
              className="flex-1"
              onClick={handleSaveStory}
              disabled={saveStatus === 'saving' || saveStatus === 'saved'}
              isLoading={saveStatus === 'saving'}
              leftIcon={<span>{saveStatus === 'saved' ? '✅' : '💾'}</span>}
            >
              {saveStatus === 'saved'
                ? 'Saved!'
                : saveStatus === 'error'
                  ? 'Retry Save'
                  : 'Save to My Stories'}
            </Button>
            <Button
              variant="primary"
              size="lg"
              className="flex-1"
              onClick={handleReset}
              leftIcon={<span>🔄</span>}
            >
              Play Again
            </Button>
            <Button
              variant="outline"
              size="lg"
              className="flex-1"
              onClick={() => navigate('/')}
              leftIcon={<span>🏠</span>}
            >
              Back to Home
            </Button>
          </div>
        </motion.div>
      )}
    </div>
  )
}

export default InteractiveStoryPage
