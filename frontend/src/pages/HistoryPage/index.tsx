import { Link, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import Button from '@/components/common/Button'
import Card from '@/components/common/Card'
import useStoryStore from '@/store/useStoryStore'
import SafetyBadge from '@/components/story/SafetyBadge'

function HistoryPage() {
  const navigate = useNavigate()
  const { storyHistory, clearHistory, setCurrentStory } = useStoryStore()

  const handleStoryClick = (storyId: string) => {
    const story = storyHistory.find((s) => s.story_id === storyId)
    if (story) {
      setCurrentStory(story)
    }
    navigate(`/story/${storyId}`)
  }

  const handleClearHistory = () => {
    if (window.confirm('Are you sure you want to clear all story history? This cannot be undone.')) {
      clearHistory()
    }
  }

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return (
    <div className="space-y-6">
      {/* Page title */}
      <motion.div
        className="flex items-center justify-between"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1 className="text-2xl font-bold text-gray-800 flex items-center gap-2">
          <span className="text-3xl">📚</span>
          My Stories
        </h1>
        {storyHistory.length > 0 && (
          <Button
            variant="ghost"
            size="sm"
            onClick={handleClearHistory}
            className="text-gray-500"
          >
            Clear History
          </Button>
        )}
      </motion.div>

      {/* Story list */}
      <AnimatePresence mode="popLayout">
        {storyHistory.length > 0 ? (
          <motion.div className="space-y-4">
            {storyHistory.map((story, index) => (
              <motion.div
                key={story.story_id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, x: -100 }}
                transition={{ delay: index * 0.05 }}
              >
                <Card
                  className="cursor-pointer"
                  onClick={() => handleStoryClick(story.story_id)}
                >
                  <div className="flex gap-4">
                    {/* Thumbnail */}
                    <div className="flex-shrink-0 w-20 h-20 rounded-lg bg-gradient-to-br from-primary/20 via-secondary/10 to-accent/20 flex items-center justify-center overflow-hidden">
                      {story.image_url ? (
                        <img
                          src={story.image_url.startsWith('/') ? story.image_url : '/' + story.image_url}
                          alt="Artwork"
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <motion.span
                          className="text-4xl"
                          whileHover={{ rotate: [0, -10, 10, 0] }}
                          transition={{ duration: 0.5 }}
                        >
                          📖
                        </motion.span>
                      )}
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <h3 className="font-bold text-gray-800 truncate">
                          Story #{story.story_id.slice(0, 8)}
                        </h3>
                        <SafetyBadge score={story.safety_score} />
                      </div>

                      <p className="text-gray-500 text-sm mt-1 line-clamp-2">
                        {story.story.text.slice(0, 120)}...
                      </p>

                      <div className="flex items-center gap-4 mt-2 text-xs text-gray-400">
                        <span className="flex items-center gap-1">
                          <span>📝</span>
                          {story.story.word_count} words
                        </span>
                        <span className="flex items-center gap-1">
                          <span>🕐</span>
                          {formatDate(story.created_at)}
                        </span>
                        {story.audio_url && (
                          <span className="flex items-center gap-1 text-secondary">
                            <span>🔊</span>
                            Audio
                          </span>
                        )}
                      </div>

                      {/* Educational value tags */}
                      {story.educational_value.themes.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          {story.educational_value.themes.slice(0, 3).map((theme) => (
                            <span
                              key={theme}
                              className="text-xs px-2 py-0.5 bg-primary/10 text-primary rounded-full"
                            >
                              {theme}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Arrow */}
                    <div className="flex-shrink-0 flex items-center text-gray-400">
                      <motion.span
                        animate={{ x: [0, 4, 0] }}
                        transition={{ duration: 1.5, repeat: Infinity }}
                      >
                        →
                      </motion.span>
                    </div>
                  </div>
                </Card>
              </motion.div>
            ))}
          </motion.div>
        ) : (
          // Empty state
          <motion.div
            className="text-center py-16"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
          >
            <motion.div
              className="text-8xl mb-6"
              animate={{ y: [0, -10, 0] }}
              transition={{ duration: 2, repeat: Infinity }}
            >
              📭
            </motion.div>
            <h2 className="text-xl font-bold text-gray-800 mb-2">
              No stories yet
            </h2>
            <p className="text-gray-500 mb-6">
              Upload your first artwork and start creating amazing stories!
            </p>
            <Link to="/upload">
              <Button size="lg" leftIcon={<span>✨</span>}>
                Start Creating
              </Button>
            </Link>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Bottom statistics */}
      {storyHistory.length > 0 && (
        <motion.div
          className="text-center py-4 text-gray-500"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
        >
          <p>
            Total: <span className="font-bold text-primary">{storyHistory.length}</span> stories
          </p>
        </motion.div>
      )}
    </div>
  )
}

export default HistoryPage
