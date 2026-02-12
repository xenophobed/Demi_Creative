import { useState, useCallback } from 'react'
import { motion } from 'framer-motion'
import Button from '@/components/common/Button'
import Card from '@/components/common/Card'
import AgeAwareContent from '@/components/common/AgeAwareContent'
import { StreamingVisualizer } from '@/components/streaming/StreamingVisualizer'
import { storyService } from '@/api/services/storyService'
import useChildStore from '@/store/useChildStore'
import type { AgeGroup, NewsCategory, NewsToKidsResponse } from '@/types/api'
import type { AnimationPhase } from '@/types/streaming'

const AGE_GROUPS: { value: AgeGroup; label: string; emoji: string }[] = [
  { value: '3-5', label: '3-5 yrs', emoji: '🧒' },
  { value: '6-9', label: '6-9 yrs', emoji: '👦' },
  { value: '10-12', label: '10-12 yrs', emoji: '🧑' },
]

const CATEGORIES: { value: NewsCategory; label: string; emoji: string }[] = [
  { value: 'science', label: 'Science', emoji: '🔬' },
  { value: 'nature', label: 'Nature', emoji: '🌿' },
  { value: 'technology', label: 'Technology', emoji: '💻' },
  { value: 'space', label: 'Space', emoji: '🚀' },
  { value: 'animals', label: 'Animals', emoji: '🐾' },
  { value: 'sports', label: 'Sports', emoji: '⚽' },
  { value: 'culture', label: 'Culture', emoji: '🎨' },
  { value: 'general', label: 'General', emoji: '📰' },
]

function NewsPage() {
  const { defaultChildId } = useChildStore()

  // Form state
  const [newsUrl, setNewsUrl] = useState('')
  const [newsText, setNewsText] = useState('')
  const [selectedAge, setSelectedAge] = useState<AgeGroup | null>(null)
  const [selectedCategory, setSelectedCategory] = useState<NewsCategory>('general')

  // Result state
  const [result, setResult] = useState<NewsToKidsResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Streaming state
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamMessage, setStreamMessage] = useState('')
  const [animationPhase, setAnimationPhase] = useState<AnimationPhase>('idle')

  const handleConvert = useCallback(async () => {
    if (!selectedAge || (!newsUrl && !newsText)) return

    setIsLoading(true)
    setIsStreaming(true)
    setError(null)
    setResult(null)
    setAnimationPhase('connecting')

    try {
      await storyService.convertNewsStream(
        {
          news_url: newsUrl || undefined,
          news_text: newsText || undefined,
          age_group: selectedAge,
          child_id: defaultChildId,
          category: selectedCategory,
          enable_audio: true,
        },
        {
          onStatus: (data) => {
            setStreamMessage(data.message)
            setAnimationPhase('thinking')
          },
          onThinking: (data) => {
            setStreamMessage(data.content)
            setAnimationPhase('thinking')
          },
          onToolUse: (data) => {
            setStreamMessage(data.message)
            setAnimationPhase('tool_executing')
          },
          onToolResult: () => {
            setAnimationPhase('thinking')
          },
          onResult: (data) => {
            setResult({
              conversion_id: data.conversion_id || '',
              kid_title: data.kid_title || 'News for Kids',
              kid_content: data.kid_content || '',
              why_care: data.why_care || '',
              key_concepts: data.key_concepts || [],
              interactive_questions: data.interactive_questions || [],
              category: data.category || selectedCategory,
              age_group: data.age_group || selectedAge,
              audio_url: data.audio_url || null,
              original_url: data.original_url || null,
              created_at: new Date().toISOString(),
            })
          },
          onComplete: () => {
            setIsStreaming(false)
            setIsLoading(false)
            setAnimationPhase('idle')
          },
          onError: (data) => {
            setError(data.message)
            setIsStreaming(false)
            setIsLoading(false)
            setAnimationPhase('idle')
          },
        }
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Conversion failed')
      setIsStreaming(false)
      setIsLoading(false)
      setAnimationPhase('idle')
    }
  }, [selectedAge, newsUrl, newsText, defaultChildId, selectedCategory])

  const handleReset = () => {
    setResult(null)
    setNewsUrl('')
    setNewsText('')
    setError(null)
  }

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
          📰
        </motion.span>
        <h1 className="text-2xl md:text-3xl font-bold text-gray-800 mt-2">
          News Explorer
        </h1>
        <p className="text-gray-600 mt-1">
          Turn real news into stories kids can understand!
        </p>
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

      {/* Input Form - show when no result */}
      {!result && (
        <motion.div
          className="space-y-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          {/* News Input */}
          <Card>
            <h2 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
              <span>📋</span>
              Paste News Article
            </h2>
            <div className="space-y-3">
              <input
                type="url"
                value={newsUrl}
                onChange={(e) => setNewsUrl(e.target.value)}
                placeholder="Paste news URL here (optional)"
                className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-primary focus:outline-none transition-colors"
              />
              <div className="text-center text-gray-400 text-sm">or</div>
              <textarea
                value={newsText}
                onChange={(e) => setNewsText(e.target.value)}
                placeholder="Paste the news article text here..."
                rows={6}
                className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-primary focus:outline-none transition-colors resize-none"
              />
            </div>
          </Card>

          {/* Age Group */}
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
                  className={`p-4 rounded-xl border-2 text-center transition-colors ${
                    selectedAge === age.value
                      ? 'border-primary bg-primary/10'
                      : 'border-gray-200 hover:border-primary/50'
                  }`}
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

          {/* Category */}
          <Card>
            <h2 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
              <span>🏷️</span>
              News Category
            </h2>
            <div className="flex flex-wrap gap-2">
              {CATEGORIES.map((cat) => (
                <motion.button
                  key={cat.value}
                  className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                    selectedCategory === cat.value
                      ? 'bg-secondary text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                  onClick={() => setSelectedCategory(cat.value)}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                >
                  {cat.emoji} {cat.label}
                </motion.button>
              ))}
            </div>
          </Card>

          {/* Streaming progress */}
          {isStreaming && (
            <StreamingVisualizer
              phase={animationPhase}
              message={streamMessage || 'Converting news...'}
              layout="card"
              showParticles={false}
              showSparkles
            />
          )}

          {/* Convert Button */}
          <Button
            size="lg"
            className="w-full"
            onClick={handleConvert}
            isLoading={isLoading}
            disabled={!selectedAge || (!newsUrl && !newsText) || isStreaming}
            leftIcon={<span>✨</span>}
          >
            {isStreaming ? 'Converting...' : 'Make it Kid-Friendly!'}
          </Button>
        </motion.div>
      )}

      {/* Result Display */}
      {result && (
        <motion.div
          className="space-y-6"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <AgeAwareContent
            ageGroup={selectedAge}
            audioUrl={result.audio_url}
            autoPlayAudio={selectedAge === '3-5'}
            textContent={
              <div className="space-y-6">
                {/* Kid Title */}
                <Card variant="colorful" colorScheme="primary">
                  <h2 className="text-xl font-bold text-gray-800 mb-2">
                    {result.kid_title}
                  </h2>
                  <div className="flex items-center gap-2 text-sm text-gray-500">
                    <span className="px-2 py-0.5 bg-white/50 rounded-full">
                      {CATEGORIES.find((c) => c.value === result.category)?.emoji}{' '}
                      {CATEGORIES.find((c) => c.value === result.category)?.label}
                    </span>
                    <span className="px-2 py-0.5 bg-white/50 rounded-full">
                      {AGE_GROUPS.find((a) => a.value === result.age_group)?.emoji}{' '}
                      {AGE_GROUPS.find((a) => a.value === result.age_group)?.label}
                    </span>
                  </div>
                </Card>

                {/* Kid Content */}
                <Card>
                  <div className="prose prose-sm max-w-none">
                    <p className="text-gray-700 leading-relaxed whitespace-pre-line">
                      {result.kid_content}
                    </p>
                  </div>
                </Card>

                {/* Why Care */}
                {result.why_care && (
                  <Card variant="colorful" colorScheme="accent">
                    <h3 className="text-lg font-bold text-gray-800 mb-2 flex items-center gap-2">
                      <span>💡</span>
                      Why Should You Care?
                    </h3>
                    <p className="text-gray-700">{result.why_care}</p>
                  </Card>
                )}

                {/* Key Concepts */}
                {result.key_concepts.length > 0 && (
                  <Card>
                    <h3 className="text-lg font-bold text-gray-800 mb-3 flex items-center gap-2">
                      <span>🔑</span>
                      Key Concepts
                    </h3>
                    <div className="space-y-3">
                      {result.key_concepts.map((concept, i) => (
                        <motion.div
                          key={i}
                          className="flex items-start gap-3 p-3 bg-gray-50 rounded-xl"
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: i * 0.1 }}
                        >
                          <span className="text-xl flex-shrink-0">{concept.emoji}</span>
                          <div>
                            <span className="font-bold text-gray-800">{concept.term}</span>
                            <p className="text-gray-600 text-sm mt-0.5">
                              {concept.explanation}
                            </p>
                          </div>
                        </motion.div>
                      ))}
                    </div>
                  </Card>
                )}

                {/* Interactive Questions */}
                {result.interactive_questions.length > 0 && (
                  <Card>
                    <h3 className="text-lg font-bold text-gray-800 mb-3 flex items-center gap-2">
                      <span>🤔</span>
                      Think About It!
                    </h3>
                    <div className="space-y-3">
                      {result.interactive_questions.map((q, i) => (
                        <motion.div
                          key={i}
                          className="p-3 bg-primary/5 rounded-xl border border-primary/20"
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: i * 0.1 }}
                        >
                          <p className="font-medium text-gray-800">
                            {q.emoji} {q.question}
                          </p>
                          {q.hint && (
                            <p className="text-gray-500 text-sm mt-1 italic">
                              Hint: {q.hint}
                            </p>
                          )}
                        </motion.div>
                      ))}
                    </div>
                  </Card>
                )}
              </div>
            }
          />

          {/* Action Buttons */}
          <div className="flex flex-col sm:flex-row gap-3">
            <Button
              variant="primary"
              size="lg"
              className="flex-1"
              onClick={handleReset}
              leftIcon={<span>📰</span>}
            >
              Convert Another
            </Button>
          </div>
        </motion.div>
      )}
    </div>
  )
}

export default NewsPage
