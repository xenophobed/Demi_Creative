import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { Howl } from 'howler'
import Button from '@/components/common/Button'
import Loading from '@/components/common/Loading'
import BookContainer from '@/components/story/BookContainer'
import StoryDisplay from '@/components/story/StoryDisplay'
import TabbedMetadata from '@/components/story/TabbedMetadata'
import useStoryStore from '@/store/useStoryStore'
import storyService from '@/api/services/storyService'

// Convert audio URL to full path
function getAudioUrl(audioUrl: string): string {
  if (!audioUrl) return ''
  if (audioUrl.startsWith('./')) {
    return audioUrl.replace('./', '/')
  }
  if (audioUrl.startsWith('data/')) {
    return '/' + audioUrl
  }
  if (audioUrl.startsWith('http')) {
    return audioUrl
  }
  return audioUrl.startsWith('/') ? audioUrl : '/' + audioUrl
}

// Convert image URL to full path
function getImageUrl(imageUrl: string | null | undefined): string | null {
  if (!imageUrl) return null
  if (imageUrl.startsWith('./')) {
    return imageUrl.replace('./', '/')
  }
  if (imageUrl.startsWith('data/')) {
    return '/' + imageUrl
  }
  if (imageUrl.startsWith('http')) {
    return imageUrl
  }
  return imageUrl.startsWith('/') ? imageUrl : '/' + imageUrl
}

function StoryPage() {
  const { storyId } = useParams<{ storyId: string }>()
  const navigate = useNavigate()

  const { currentStory, setCurrentStory, reset } = useStoryStore()

  // Audio state
  const [sound, setSound] = useState<Howl | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [isAudioLoading, setIsAudioLoading] = useState(false)

  // If store doesn't have the story, try to fetch from API
  const { data: fetchedStory, isLoading, error } = useQuery({
    queryKey: ['story', storyId],
    queryFn: () => storyService.getStory(storyId!),
    enabled: !currentStory && !!storyId,
    retry: 1,
  })

  // Use story from store or API
  const story = currentStory || fetchedStory

  // If API returned a story, save to store
  useEffect(() => {
    if (fetchedStory && !currentStory) {
      setCurrentStory(fetchedStory)
    }
  }, [fetchedStory, currentStory, setCurrentStory])

  // Initialize audio
  useEffect(() => {
    if (!story?.audio_url) return

    const audioUrl = getAudioUrl(story.audio_url)
    setIsAudioLoading(true)

    const newSound = new Howl({
      src: [audioUrl],
      html5: true,
      onload: () => {
        setIsAudioLoading(false)
      },
      onend: () => {
        setIsPlaying(false)
      },
      onloaderror: () => {
        setIsAudioLoading(false)
        console.error('Failed to load audio')
      },
    })

    setSound(newSound)

    return () => {
      newSound.unload()
    }
  }, [story?.audio_url])

  const toggleAudio = useCallback(() => {
    if (!sound) return

    if (isPlaying) {
      sound.pause()
      setIsPlaying(false)
    } else {
      sound.play()
      setIsPlaying(true)
    }
  }, [sound, isPlaying])

  const handleNewStory = () => {
    reset()
    navigate('/upload')
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loading size="lg" message="Loading your story..." />
      </div>
    )
  }

  // Error state
  if (error || !story) {
    return (
      <div className="text-center py-16">
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          className="text-6xl mb-4"
        >
          😢
        </motion.div>
        <h2 className="text-xl font-bold text-gray-800 mb-2">
          Story not found
        </h2>
        <p className="text-gray-500 mb-6">
          This story may have expired or doesn't exist
        </p>
        <Link to="/upload">
          <Button>Create New Story</Button>
        </Link>
      </div>
    )
  }

  const imageUrl = getImageUrl(story.image_url)

  return (
    <motion.div
      className="story-page"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      {/* Header with back button and audio */}
      <motion.header
        className="story-page-header"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <button
          onClick={() => navigate(-1)}
          className="back-button"
          aria-label="Go back"
        >
          <span>←</span>
          <span>Back</span>
        </button>

        <h1 className="page-title">Your Story</h1>

        {story.audio_url && (
          <motion.button
            className={`audio-button ${isPlaying ? 'playing' : ''}`}
            onClick={toggleAudio}
            disabled={isAudioLoading}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            aria-label={isPlaying ? 'Pause story' : 'Listen to story'}
          >
            {isAudioLoading ? (
              <LoadingSpinner />
            ) : isPlaying ? (
              <>
                <SpeakerWaveIcon />
                <span>Pause</span>
              </>
            ) : (
              <>
                <SpeakerIcon />
                <span>Listen</span>
              </>
            )}

            {/* Audio wave animation */}
            <AnimatePresence>
              {isPlaying && (
                <motion.div
                  className="audio-waves"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                >
                  {[...Array(3)].map((_, i) => (
                    <motion.span
                      key={i}
                      className="wave-bar"
                      animate={{
                        height: ['8px', '16px', '8px'],
                      }}
                      transition={{
                        duration: 0.5,
                        repeat: Infinity,
                        delay: i * 0.1,
                      }}
                    />
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </motion.button>
        )}
      </motion.header>

      {/* Success notification */}
      <motion.div
        className="success-banner"
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <motion.span
          className="text-2xl"
          animate={{ scale: [1, 1.2, 1] }}
          transition={{ duration: 0.5 }}
        >
          🎉
        </motion.span>
        <div>
          <p className="font-bold text-gray-800">Story created successfully!</p>
          <p className="text-sm text-gray-600">
            AI crafted this unique story from your artwork
          </p>
        </div>
      </motion.div>

      {/* Book container with story */}
      <BookContainer>
        <StoryDisplay
          story={story.story}
          title={story.story.text.split('\n')[0]?.slice(0, 50) || `Story #${story.story_id.slice(0, 6)}`}
          imageUrl={imageUrl}
        />
      </BookContainer>

      {/* Tabbed metadata section */}
      <TabbedMetadata
        characters={story.characters}
        educationalValue={story.educational_value}
        analysis={story.analysis}
        safetyScore={story.safety_score}
      />

      {/* Action buttons */}
      <motion.div
        className="action-buttons"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <Button
          variant="primary"
          size="lg"
          className="flex-1"
          onClick={handleNewStory}
          leftIcon={<span>✨</span>}
        >
          Create New Story
        </Button>
        <Button
          variant="outline"
          size="lg"
          className="flex-1"
          onClick={() => navigate('/history')}
          leftIcon={<span>📚</span>}
        >
          View History
        </Button>
      </motion.div>

      {/* Share prompt */}
      <motion.p
        className="share-prompt"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
      >
        Love this story? Share it with your family!
      </motion.p>
    </motion.div>
  )
}

// Icons
function SpeakerIcon() {
  return (
    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
      <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z" />
    </svg>
  )
}

function SpeakerWaveIcon() {
  return (
    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
      <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z" />
    </svg>
  )
}

function LoadingSpinner() {
  return (
    <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  )
}

export default StoryPage
