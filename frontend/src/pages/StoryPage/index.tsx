import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import Button from '@/components/common/Button'
import Loading from '@/components/common/Loading'
import AgeAwareContent from '@/components/common/AgeAwareContent'
import BookContainer from '@/components/story/BookContainer'
import StoryDisplay from '@/components/story/StoryDisplay'
import TabbedMetadata from '@/components/story/TabbedMetadata'
import useStoryStore from '@/store/useStoryStore'
import useChildStore from '@/store/useChildStore'
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
  const { currentChild } = useChildStore()

  // On-demand audio state (for 10-12 age group)
  const [onDemandAudioUrl, setOnDemandAudioUrl] = useState<string | null>(null)
  const [isAudioGenerating, setIsAudioGenerating] = useState(false)

  // Only use currentStory if it matches the URL's storyId
  const matchingStory = currentStory?.story_id === storyId ? currentStory : null

  // If store doesn't have the matching story, fetch from API
  const { data: fetchedStory, isLoading, error } = useQuery({
    queryKey: ['story', storyId],
    queryFn: () => storyService.getStory(storyId!),
    enabled: !matchingStory && !!storyId,
    retry: 1,
  })

  // Use matching store story or fetched story
  const story = matchingStory || fetchedStory

  // If API returned a story, save to store
  useEffect(() => {
    if (fetchedStory && !matchingStory) {
      setCurrentStory(fetchedStory)
    }
  }, [fetchedStory, matchingStory, setCurrentStory])

  // On-demand audio handler for 10-12 age group
  const handleRequestAudio = useCallback(async () => {
    if (!story || isAudioGenerating) return
    setIsAudioGenerating(true)
    try {
      const result = await storyService.generateAudioForStory(story.story_id)
      setOnDemandAudioUrl(result.audio_url)
    } catch {
      // Silently fail - button will remain clickable
    } finally {
      setIsAudioGenerating(false)
    }
  }, [story, isAudioGenerating])

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
  // Use the story's age_group (content was generated for it), fall back to child store
  const ageGroup = story.age_group || currentChild?.age_group || null

  return (
    <motion.div
      className="story-page"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      {/* Header with back button */}
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

        {/* Empty spacer to maintain layout */}
        <div className="w-10" />
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

      {/* Book container with story - age-aware display */}
      <AgeAwareContent
        ageGroup={ageGroup}
        audioUrl={story.audio_url ? getAudioUrl(story.audio_url) : onDemandAudioUrl}
        onRequestAudio={handleRequestAudio}
        isAudioLoading={isAudioGenerating}
        autoPlayAudio={ageGroup === '3-5'}
        textContent={
          <BookContainer>
            <StoryDisplay
              story={story.story}
              title={story.story.text.split('\n')[0]?.slice(0, 50) || `Story #${story.story_id.slice(0, 6)}`}
              imageUrl={imageUrl}
            />
          </BookContainer>
        }
      />

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
          onClick={() => navigate('/library')}
          leftIcon={<span>📚</span>}
        >
          My Library
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

export default StoryPage
