import { motion } from 'framer-motion'
import type { StoryContent } from '@/types/api'
import FloatingImage from '../FloatingImage'

interface StoryDisplayProps {
  story: StoryContent
  title?: string
  imageUrl?: string | null
  className?: string
}

/**
 * StoryDisplay - Book-style story display with floating image
 *
 * Features:
 * - Drop cap on first paragraph
 * - Text wraps around floated image on desktop
 * - Sparkle decorations around title
 * - Immersive reading experience
 */
function StoryDisplay({ story, title, imageUrl, className = '' }: StoryDisplayProps) {
  // Split story text into paragraphs
  const paragraphs = story.text.split('\n\n').filter(p => p.trim())

  return (
    <motion.article
      className={`story-display ${className}`}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
    >
      {/* Story title with sparkles */}
      {title && (
        <motion.header
          className="story-title-section"
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <span className="sparkle sparkle-left">✨</span>
          <h1 className="story-title">{title}</h1>
          <span className="sparkle sparkle-right">✨</span>
        </motion.header>
      )}

      {/* Story content with floating image */}
      <div className="story-content-wrapper">
        {/* Floating artwork */}
        {imageUrl && (
          <FloatingImage
            src={imageUrl}
            alt="Your artwork that inspired this story"
            caption="Your artwork"
          />
        )}

        {/* Story paragraphs with drop cap */}
        <div className="story-text">
          {paragraphs.map((paragraph, index) => (
            <motion.p
              key={index}
              className={`story-paragraph ${index === 0 ? 'first-paragraph' : ''}`}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 + index * 0.1, duration: 0.3 }}
            >
              {paragraph}
            </motion.p>
          ))}
        </div>
      </div>

      {/* Story metadata footer */}
      <motion.footer
        className="story-meta"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4 }}
      >
        <div className="story-meta-item">
          <span className="meta-icon">📝</span>
          <span>{story.word_count} words</span>
        </div>
        {story.age_adapted && (
          <div className="story-meta-item success">
            <span className="meta-icon">✓</span>
            <span>Age adapted</span>
          </div>
        )}
      </motion.footer>
    </motion.article>
  )
}

// Story card preview component (for history list)
export function StoryCard({
  title,
  preview,
  createdAt,
  imageUrl,
  onClick,
  className = '',
}: {
  title: string
  preview: string
  createdAt: string
  imageUrl?: string | null
  onClick?: () => void
  className?: string
}) {
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleDateString('zh-CN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return (
    <motion.div
      className={`card-kid cursor-pointer ${className}`}
      onClick={onClick}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
    >
      <div className="flex gap-4">
        {/* Thumbnail */}
        <div className="flex-shrink-0 w-16 h-16 rounded-lg overflow-hidden bg-gradient-to-br from-primary/20 to-secondary/20 flex items-center justify-center">
          {imageUrl ? (
            <img src={imageUrl.startsWith('/') ? imageUrl : '/' + imageUrl} alt="" className="w-full h-full object-cover" />
          ) : (
            <span className="text-3xl">📚</span>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <h3 className="font-bold text-gray-800 mb-1 truncate">{title}</h3>
          <p className="text-gray-500 text-sm line-clamp-2">{preview}</p>
          <p className="text-gray-400 text-xs mt-2">{formatDate(createdAt)}</p>
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
    </motion.div>
  )
}

export default StoryDisplay
