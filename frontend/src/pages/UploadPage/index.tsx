import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Button from '@/components/common/Button'
import ImageUploader from '@/components/upload/ImageUploader'
import ImagePreview from '@/components/upload/ImagePreview'
import { StreamingVisualizer } from '@/components/streaming/StreamingVisualizer'
import { PerspectiveContainer } from '@/components/depth/PerspectiveContainer'
import TiltCard from '@/components/depth/TiltCard'
import { useStreamVisualizationContext } from '@/providers/StreamVisualizationProvider'
import useStoryStore from '@/store/useStoryStore'
import useAuthStore from '@/store/useAuthStore'
import useChildStore, { DEFAULT_INTERESTS } from '@/store/useChildStore'
import useStoryGeneration from '@/hooks/useStoryGeneration'
import QuotaExceededOverlay, { isQuotaError } from '@/components/common/QuotaExceededOverlay'
import type { AgeGroup } from '@/types/api'
import type { AnimationPhase } from '@/types/streaming'
import LoginPrompt from '@/components/common/LoginPrompt'
import VoicePicker from '@/components/common/VoicePicker'
import SuggestedThemes from '@/components/common/SuggestedThemes'
import {
  Baby,
  Cake,
  Droplets,
  Heart,
  Image,
  ImagePlus,
  Lightbulb,
  Mic,
  Paintbrush,
  Palette,
  Pencil,
  Sparkles,
  Square,
  UserRound,
  UsersRound,
  XCircle,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

const AGE_GROUPS: {
  value: AgeGroup
  label: string
  icon: LucideIcon
  description: string
}[] = [
  { value: '3-5', label: '3-5 yrs', icon: Baby, description: 'Simple & Fun' },
  { value: '6-8', label: '6-8 yrs', icon: UserRound, description: 'Engaging' },
  { value: '9-12', label: '9-12 yrs', icon: UsersRound, description: 'Rich Stories' },
]

const ART_THEMES = [
  { value: 'none', label: 'Keep Original', icon: Image, description: 'Use your drawing as-is', swatch: 'linear-gradient(135deg, #e5e7eb, #d1d5db)' },
  { value: 'cartoon', label: 'Cartoon', icon: Palette, description: 'Fun cartoon style', swatch: 'linear-gradient(135deg, #FFD700, #FF6B6B)' },
  { value: 'oil_painting', label: 'Oil Painting', icon: Paintbrush, description: 'Classic oil painting', swatch: 'linear-gradient(135deg, #8B4513, #DAA520)' },
  { value: 'watercolor', label: 'Watercolor', icon: Droplets, description: 'Soft watercolor', swatch: 'linear-gradient(135deg, #87CEEB, #98FB98)' },
  { value: 'pixel_art', label: 'Pixel Art', icon: Square, description: 'Retro pixel style', swatch: 'linear-gradient(135deg, #00FF00, #0000FF)' },
  { value: 'anime', label: 'Anime', icon: Sparkles, description: 'Anime illustration', swatch: 'linear-gradient(135deg, #FF69B4, #9370DB)' },
  { value: 'crayon', label: 'Crayon', icon: Pencil, description: 'Crayon drawing', swatch: 'linear-gradient(135deg, #FF4500, #FFD700)' },
  { value: 'storybook', label: 'Storybook', icon: ImagePlus, description: 'Storybook illustration', swatch: 'linear-gradient(135deg, #DEB887, #8FBC8F)' },
] as const

const YOUNG_CHILD_THEMES = new Set(['none', 'cartoon', 'crayon', 'watercolor', 'storybook'])

function UploadPage() {
  const {
    selectedImage,
    imagePreviewUrl,
    selectedVoice,
    selectedArtTheme,
    enableAudio,
    uploadError,
    setUploadError,
    setSelectedImage,
    setSelectedVoice,
    setSelectedArtTheme,
    setEnableAudio,
  } = useStoryStore()

  const { isAuthenticated } = useAuthStore()

  const { currentChild, setAgeGroup, setInterests, addInterest, removeInterest } =
    useChildStore()

  const { prefersReducedMotion } = useStreamVisualizationContext()

  const [selectedAgeGroup, setSelectedAgeGroup] = useState<AgeGroup | null>(
    currentChild?.age_group || null
  )
  const [selectedInterestsList, setSelectedInterestsList] = useState<string[]>(
    (currentChild?.interests || []).filter((i) => DEFAULT_INTERESTS.includes(i))
  )

  useEffect(() => {
    if (!currentChild) return
    setSelectedAgeGroup(currentChild.age_group || null)
    setSelectedInterestsList(
      (currentChild.interests || []).filter((i) => DEFAULT_INTERESTS.includes(i)),
    )
  }, [currentChild?.child_id, currentChild?.age_group, currentChild?.interests])

  const { generateStream, cancel, isLoading, isGenerating, streaming, uploadStatus: currentUploadStatus } = useStoryGeneration()

  if (!isAuthenticated) {
    return (
      <div className="max-w-lg mx-auto mt-12">
        <LoginPrompt feature="create stories" />
      </div>
    )
  }

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
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
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
    <div className="space-y-6">
      {/* Page title with floating decoration */}
      <motion.div
        className="text-center relative"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ type: 'spring', stiffness: 100 }}
      >
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Pencil size={26} />
        </div>
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
            <StepHeader number={1} title="Upload Your Artwork" icon={ImagePlus} />
            <AnimatePresence mode="wait">
              {imagePreviewUrl ? (
                <motion.div
                  key="preview"
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
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
                  <ImageUploader
                    onFileSelect={setSelectedImage}
                    childId={currentChild?.child_id}
                    ageGroup={currentChild?.age_group}
                  />
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
            <StepHeader number={2} title="Select Your Age" icon={Cake} />
            <div className="grid grid-cols-3 gap-4">
              {AGE_GROUPS.map((group, index) => {
                const Icon = group.icon
                return (
                  <motion.button
                    key={group.value}
                    className={`age-select-card p-4 rounded-card border-2 transition-all ${
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
                            y: -4,
                          }
                    }
                    whileTap={{ scale: 0.95 }}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 + index * 0.1 }}
                  >
                    <div className="text-center">
                      <motion.div
                        className={`mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-lg ${
                          selectedAgeGroup === group.value
                            ? 'bg-primary text-white'
                            : 'bg-gray-100 text-gray-600'
                        }`}
                        animate={
                          selectedAgeGroup === group.value
                            ? { scale: [1, 1.1, 1], rotate: [0, 5, -5, 0] }
                            : {}
                        }
                        transition={{ duration: 0.5 }}
                      >
                        <Icon size={24} />
                      </motion.div>
                      <span className="font-bold text-gray-800">{group.label}</span>
                      <span className="block text-sm text-gray-500 mt-1">
                        {group.description}
                      </span>
                    </div>
                  </motion.button>
                )
              })}
            </div>
          </div>
        </TiltCard>
      </motion.div>

      {/* Step 3: Art Style */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25 }}
      >
        <TiltCard maxTilt={4} glare={false} dynamicShadow className="w-full">
          <div className="bg-white rounded-card p-6">
            <StepHeader number={3} title="Choose Art Style" icon={Palette} optional />
            <p className="text-gray-500 text-sm mb-4">
              Transform your drawing into a different art style
            </p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {ART_THEMES
                .filter(t => {
                  if (!selectedAgeGroup || selectedAgeGroup !== '3-5') return true
                  return YOUNG_CHILD_THEMES.has(t.value)
                })
                .map((theme, index) => {
                  const Icon = theme.icon
                  return (
                    <motion.button
                      key={theme.value}
                      className={`rounded-card border-2 transition-all text-center overflow-hidden ${
                        selectedArtTheme === theme.value
                          ? 'border-primary bg-primary/10 shadow-lg ring-2 ring-purple-500 scale-105'
                          : 'border-gray-200 hover:border-gray-300 hover:shadow-md'
                      }`}
                      onClick={() => setSelectedArtTheme(theme.value)}
                      whileHover={prefersReducedMotion ? {} : { scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                      initial={{ opacity: 0, scale: 0.9 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ delay: 0.25 + index * 0.03 }}
                    >
                      <div
                        className="w-full h-8 rounded-t-lg"
                        style={{ background: theme.swatch }}
                      />
                      <div className="p-3 pt-2">
                        <Icon className="mx-auto mb-1 text-gray-700" size={22} />
                        <span className="font-medium text-gray-800 text-sm block">{theme.label}</span>
                        <span className="text-xs text-gray-500">{theme.description}</span>
                      </div>
                    </motion.button>
                  )
                })}
            </div>
          </div>
        </TiltCard>
      </motion.div>

      {/* Step 4: Interests with floating tags */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <TiltCard maxTilt={4} glare={false} dynamicShadow className="w-full">
          <div className="bg-white rounded-card p-6">
            <StepHeader
              number={4}
              title="What Do You Like?"
              icon={Heart}
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

      {/* Suggested Themes — personalised recommendations (#292) */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35 }}
      >
        <TiltCard maxTilt={4} glare={false} dynamicShadow className="w-full">
          <div className="bg-white rounded-card p-6">
            <StepHeader number={5} title="Suggested Themes" icon={Lightbulb} optional />
            <SuggestedThemes
              onSelect={(theme) => {
                if (!selectedInterestsList.includes(theme) && selectedInterestsList.length < 5) {
                  const newList = [...selectedInterestsList, theme]
                  setSelectedInterestsList(newList)
                  addInterest(theme)
                }
              }}
            />
          </div>
        </TiltCard>
      </motion.div>

      {/* Step 6: Voice selection with 3D effect */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <TiltCard maxTilt={4} glare={false} dynamicShadow className="w-full">
          <div className="bg-white rounded-card p-6">
            <StepHeader
              number={6}
              title="Choose a Narrator"
              icon={Mic}
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

              {/* Voice selection (#151) */}
              <AnimatePresence>
                {enableAudio && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                  >
                    <VoicePicker
                      ageGroup={selectedAgeGroup}
                      selectedVoice={selectedVoice}
                      onVoiceChange={(voiceId, provider) => setSelectedVoice(voiceId, provider)}
                    />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </TiltCard>
      </motion.div>

      {/* Quota exceeded overlay */}
      <QuotaExceededOverlay
        show={isQuotaError(uploadError)}
        message={uploadError ?? ''}
        onDismiss={() => setUploadError(null)}
      />

      {/* Error message (non-quota errors) */}
      <AnimatePresence>
        {uploadError && !isQuotaError(uploadError) && (
          <motion.div
            className="bg-red-100 border border-red-200 rounded-card p-4 text-red-700"
            initial={{ opacity: 0, y: -10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.95 }}
          >
            <div className="flex items-center gap-2">
              <XCircle size={18} />
              <span>{uploadError}</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Generate button with glow effect */}
      <motion.div
        className="z-10"
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
                  className="inline-flex"
                  animate={{ rotate: [0, 10, -10, 0], scale: [1, 1.1, 1] }}
                  transition={{ duration: 2, repeat: Infinity }}
                >
                  <Sparkles size={20} />
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
  icon: Icon,
  optional = false,
}: {
  number: number
  title: string
  icon: LucideIcon
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
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gray-100 text-gray-600">
        <Icon size={18} />
      </span>
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
