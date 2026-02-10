import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Button from '@/components/common/Button'
import ImageUploader from '@/components/upload/ImageUploader'
import ImagePreview from '@/components/upload/ImagePreview'
import { StreamingVisualizer } from '@/components/streaming/StreamingVisualizer'
import { PerspectiveContainer } from '@/components/depth/PerspectiveContainer'
import TiltCard from '@/components/depth/TiltCard'
import { FloatingElement } from '@/components/depth/ParallaxContainer'
import { useStreamVisualizationContext } from '@/providers/StreamVisualizationProvider'
import useStoryStore from '@/store/useStoryStore'
import useChildStore, { DEFAULT_INTERESTS } from '@/store/useChildStore'
import useStoryGeneration from '@/hooks/useStoryGeneration'
import type { AgeGroup, VoiceType } from '@/types/api'
import type { AnimationPhase } from '@/types/streaming'

const AGE_GROUPS: { value: AgeGroup; label: string; emoji: string; description: string }[] = [
  { value: '3-5', label: '3-5 yrs', emoji: '🧒', description: 'Simple & Fun' },
  { value: '6-9', label: '6-9 yrs', emoji: '👦', description: 'Engaging' },
  { value: '10-12', label: '10-12 yrs', emoji: '🧑', description: 'Rich Stories' },
]

const VOICE_OPTIONS: { value: VoiceType; label: string; emoji: string }[] = [
  { value: 'nova', label: 'Gentle', emoji: '👩' },
  { value: 'shimmer', label: 'Lively', emoji: '💃' },
  { value: 'fable', label: 'Storyteller', emoji: '📖' },
  { value: 'echo', label: 'Warm', emoji: '👨' },
  { value: 'alloy', label: 'Robot', emoji: '🤖' },
]

function UploadPage() {
  const {
    selectedImage,
    imagePreviewUrl,
    selectedVoice,
    enableAudio,
    uploadError,
    setSelectedImage,
    setSelectedVoice,
    setEnableAudio,
  } = useStoryStore()

  const { currentChild, setAgeGroup, setInterests, addInterest, removeInterest } =
    useChildStore()

  const { prefersReducedMotion } = useStreamVisualizationContext()

  const [selectedAgeGroup, setSelectedAgeGroup] = useState<AgeGroup | null>(
    currentChild?.age_group || null
  )
  const [selectedInterestsList, setSelectedInterestsList] = useState<string[]>(
    (currentChild?.interests || []).filter((i) => DEFAULT_INTERESTS.includes(i))
  )

  const { generateStream, cancel, isLoading, isGenerating, streaming, uploadStatus: currentUploadStatus } = useStoryGeneration()

  const handleAgeGroupSelect = (ageGroup: AgeGroup) => {
    setSelectedAgeGroup(ageGroup)
    setAgeGroup(ageGroup)
  }

  const handleInterestToggle = (interest: string) => {
    if (selectedInterestsList.includes(interest)) {
      const newList = selectedInterestsList.filter((i) => i !== interest)
      setSelectedInterestsList(newList)
      removeInterest(interest)
    } else if (selectedInterestsList.length < 5) {
      const newList = [...selectedInterestsList, interest]
      setSelectedInterestsList(newList)
      addInterest(interest)
    }
  }

  const handleGenerate = () => {
    if (!selectedAgeGroup) return
    setInterests(selectedInterestsList)
    generateStream(selectedAgeGroup, selectedInterestsList)
  }

  const isReady = selectedImage && selectedAgeGroup

  // Map streaming state to animation phase
  const getAnimationPhase = (): AnimationPhase => {
    if (!streaming.isStreaming && currentUploadStatus !== 'uploading' && currentUploadStatus !== 'processing') {
      return 'idle'
    }
    if (currentUploadStatus === 'uploading') return 'connecting'
    if (streaming.thinkingContent) return 'thinking'
    if (streaming.streamMessage.includes('tool') || streaming.streamMessage.includes('analyz')) {
      return 'tool_executing'
    }
    return 'thinking'
  }

  const animationPhase = getAnimationPhase()

  // Show loading state with enhanced streaming visualization
  if (currentUploadStatus === 'uploading' || currentUploadStatus === 'processing' || isLoading || isGenerating) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] perspective-1000">
        <PerspectiveContainer enableTilt={false} className="w-full max-w-md">
          <StreamingVisualizer
            phase={animationPhase}
            message={streaming.streamMessage || getLoadingMessage(currentUploadStatus)}
            thinkingContent={streaming.thinkingContent}
            layout="card"
            showParticles={false}
            showSparkles
          />
        </PerspectiveContainer>
        <motion.div
          className="mt-6 text-center max-w-md"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
        >
          <p className="text-gray-500">
            {streaming.isStreaming ? 'AI is crafting your unique story...' : 'Preparing...'}
          </p>
          {!streaming.thinkingContent && (
            <p className="text-gray-400 text-sm mt-2">This may take a moment, please wait</p>
          )}
        </motion.div>
        <motion.button
          className="mt-4 px-6 py-2 rounded-full bg-gray-200 hover:bg-red-100 text-gray-600 hover:text-red-600 text-sm font-medium transition-colors"
          onClick={cancel}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
        >
          Cancel Generation
        </motion.button>
      </div>
    )
  }

  return (
    <div className="space-y-6 perspective-1500">
      {/* Page title with floating decoration */}
      <motion.div
        className="text-center relative"
        initial={{ opacity: 0, y: -20, rotateX: 15 }}
        animate={{ opacity: 1, y: 0, rotateX: 0 }}
        transition={{ type: 'spring', stiffness: 100 }}
      >
        <FloatingElement depth="near" float className="inline-block">
          <span className="text-3xl">✏️</span>
        </FloatingElement>
        <h1 className="text-2xl font-bold text-gray-800 mt-2">Create New Story</h1>
        <p className="text-gray-500 mt-2">Upload your artwork, begin the magical journey</p>
      </motion.div>

      {/* Step 1: Upload image with 3D tilt */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <TiltCard maxTilt={6} glare dynamicShadow className="w-full">
          <div className="bg-white rounded-card p-6">
            <StepHeader number={1} title="Upload Your Artwork" emoji="🖼️" />
            <AnimatePresence mode="wait">
              {imagePreviewUrl ? (
                <motion.div
                  key="preview"
                  initial={{ opacity: 0, scale: 0.9, rotateY: -10 }}
                  animate={{ opacity: 1, scale: 1, rotateY: 0 }}
                  exit={{ opacity: 0, scale: 0.9, rotateY: 10 }}
                  transition={{ type: 'spring', stiffness: 200 }}
                >
                  <ImagePreview
                    src={imagePreviewUrl}
                    fileName={selectedImage?.name}
                    onRemove={() => setSelectedImage(null)}
                  />
                </motion.div>
              ) : (
                <motion.div
                  key="uploader"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                >
                  <ImageUploader onFileSelect={setSelectedImage} />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </TiltCard>
      </motion.div>

      {/* Step 2: Age selection with 3D cards */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <TiltCard maxTilt={4} glare={false} dynamicShadow className="w-full">
          <div className="bg-white rounded-card p-6">
            <StepHeader number={2} title="Select Your Age" emoji="🎂" />
            <div className="grid grid-cols-3 gap-4">
              {AGE_GROUPS.map((group, index) => (
                <motion.button
                  key={group.value}
                  className={`age-select-card p-4 rounded-card border-2 transition-all preserve-3d ${
                    selectedAgeGroup === group.value
                      ? 'border-primary bg-primary/10 shadow-lg'
                      : 'border-gray-200 hover:border-gray-300 hover:shadow-md'
                  }`}
                  onClick={() => handleAgeGroupSelect(group.value)}
                  whileHover={
                    prefersReducedMotion
                      ? {}
                      : {
                          scale: 1.05,
                          rotateY: 5,
                          z: 20,
                        }
                  }
                  whileTap={{ scale: 0.95 }}
                  initial={{ opacity: 0, y: 20, rotateX: 15 }}
                  animate={{ opacity: 1, y: 0, rotateX: 0 }}
                  transition={{ delay: 0.2 + index * 0.1 }}
                >
                  <div className="text-center">
                    <motion.span
                      className="text-4xl block mb-2"
                      animate={
                        selectedAgeGroup === group.value
                          ? { scale: [1, 1.1, 1], rotate: [0, 5, -5, 0] }
                          : {}
                      }
                      transition={{ duration: 0.5 }}
                    >
                      {group.emoji}
                    </motion.span>
                    <span className="font-bold text-gray-800">{group.label}</span>
                    <span className="block text-sm text-gray-500 mt-1">
                      {group.description}
                    </span>
                  </div>
                </motion.button>
              ))}
            </div>
          </div>
        </TiltCard>
      </motion.div>

      {/* Step 3: Interests with floating tags */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <TiltCard maxTilt={4} glare={false} dynamicShadow className="w-full">
          <div className="bg-white rounded-card p-6">
            <StepHeader
              number={3}
              title="What Do You Like?"
              emoji="❤️"
              optional
            />
            <p className="text-gray-500 text-sm mb-4">
              Select up to 5 interests to personalize your story (selected {selectedInterestsList.length}/5)
            </p>
            <div className="flex flex-wrap gap-2">
              {DEFAULT_INTERESTS.map((interest, index) => {
                const isSelected = selectedInterestsList.includes(interest)
                const isDisabled = !isSelected && selectedInterestsList.length >= 5
                return (
                  <motion.button
                    key={interest}
                    className={`interest-tag preserve-3d ${
                      isSelected ? 'tag-bubble-selected' : 'tag-bubble-unselected'
                    } ${isDisabled ? 'opacity-50 cursor-not-allowed' : ''}`}
                    onClick={() => !isDisabled && handleInterestToggle(interest)}
                    disabled={isDisabled}
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.3 + index * 0.02 }}
                    whileHover={
                      isDisabled || prefersReducedMotion
                        ? {}
                        : {
                            scale: 1.1,
                            y: -3,
                            boxShadow: '0 5px 15px rgba(0,0,0,0.1)',
                          }
                    }
                    whileTap={isDisabled ? {} : { scale: 0.95 }}
                  >
                    {interest}
                  </motion.button>
                )
              })}
            </div>
          </div>
        </TiltCard>
      </motion.div>

      {/* Step 4: Voice selection with 3D effect */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <TiltCard maxTilt={4} glare={false} dynamicShadow className="w-full">
          <div className="bg-white rounded-card p-6">
            <StepHeader
              number={4}
              title="Choose a Narrator"
              emoji="🎙️"
              optional
            />
            <div className="space-y-4">
              {/* Toggle */}
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={enableAudio}
                  onChange={(e) => setEnableAudio(e.target.checked)}
                  className="w-5 h-5 rounded text-primary focus:ring-primary"
                />
                <span className="text-gray-700">Generate audio narration</span>
              </label>

              {/* Voice selection */}
              <AnimatePresence>
                {enableAudio && (
                  <motion.div
                    className="grid grid-cols-2 md:grid-cols-5 gap-3"
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                  >
                    {VOICE_OPTIONS.map((voice, index) => (
                      <motion.button
                        key={voice.value}
                        className={`voice-card p-3 rounded-lg border-2 transition-all preserve-3d ${
                          selectedVoice === voice.value
                            ? 'border-secondary bg-secondary/10 shadow-lg'
                            : 'border-gray-200 hover:border-gray-300'
                        }`}
                        onClick={() => setSelectedVoice(voice.value)}
                        initial={{ opacity: 0, scale: 0.8 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ delay: index * 0.05 }}
                        whileHover={
                          prefersReducedMotion
                            ? {}
                            : {
                                scale: 1.05,
                                rotateY: 5,
                              }
                        }
                        whileTap={{ scale: 0.95 }}
                      >
                        <div className="text-center">
                          <motion.span
                            className="text-2xl block mb-1"
                            animate={
                              selectedVoice === voice.value
                                ? { scale: [1, 1.2, 1] }
                                : {}
                            }
                          >
                            {voice.emoji}
                          </motion.span>
                          <span className="text-sm text-gray-700">{voice.label}</span>
                        </div>
                      </motion.button>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </TiltCard>
      </motion.div>

      {/* Error message */}
      <AnimatePresence>
        {uploadError && (
          <motion.div
            className="bg-red-100 border border-red-200 rounded-card p-4 text-red-700"
            initial={{ opacity: 0, y: -10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.95 }}
          >
            <div className="flex items-center gap-2">
              <span>❌</span>
              <span>{uploadError}</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Generate button with glow effect */}
      <motion.div
        className="sticky bottom-4 z-10"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
      >
        <motion.div
          whileHover={
            isReady && !prefersReducedMotion
              ? {
                  scale: 1.02,
                  boxShadow: '0 0 30px rgba(255, 107, 107, 0.4)',
                }
              : {}
          }
          whileTap={isReady ? { scale: 0.98 } : {}}
          className="rounded-btn"
        >
          <Button
            size="lg"
            className="w-full shadow-lg"
            onClick={handleGenerate}
            disabled={!isReady || isGenerating}
            isLoading={isLoading}
          >
            {isReady ? (
              <>
                <motion.span
                  className="text-xl"
                  animate={{ rotate: [0, 10, -10, 0], scale: [1, 1.1, 1] }}
                  transition={{ duration: 2, repeat: Infinity }}
                >
                  ✨
                </motion.span>
                Generate My Story
              </>
            ) : (
              'Complete the steps above'
            )}
          </Button>
        </motion.div>
      </motion.div>
    </div>
  )
}

function StepHeader({
  number,
  title,
  emoji,
  optional = false,
}: {
  number: number
  title: string
  emoji: string
  optional?: boolean
}) {
  return (
    <div className="flex items-center gap-3 mb-4">
      <motion.span
        className="w-8 h-8 rounded-full bg-primary text-white flex items-center justify-center font-bold text-sm shadow-md"
        whileHover={{ scale: 1.1, rotate: 5 }}
      >
        {number}
      </motion.span>
      <FloatingElement depth="near" float={false}>
        <span className="text-xl">{emoji}</span>
      </FloatingElement>
      <h2 className="text-lg font-bold text-gray-800">{title}</h2>
      {optional && (
        <span className="text-sm text-gray-400 ml-auto">Optional</span>
      )}
    </div>
  )
}

function getLoadingMessage(status: string): string {
  switch (status) {
    case 'uploading':
      return 'Uploading your artwork...'
    case 'processing':
      return 'Creating your story...'
    default:
      return 'Please wait...'
  }
}

export default UploadPage
