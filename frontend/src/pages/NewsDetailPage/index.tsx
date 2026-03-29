import { useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import Button from '@/components/common/Button'
import storyService from '@/api/services/storyService'

function NewsDetailPage() {
  const navigate = useNavigate()
  const { conversionId } = useParams<{ conversionId: string }>()

  const { data: conversion, isLoading, error } = useQuery({
    queryKey: ['news-conversion', conversionId],
    queryFn: () => storyService.getNewsConversion(conversionId || ''),
    enabled: !!conversionId,
  })

  if (isLoading) {
    return <div className="text-center py-16 text-gray-500">Loading news article...</div>
  }

  if (error || !conversion) {
    return (
      <div className="max-w-2xl mx-auto text-center py-16 space-y-4">
        <h1 className="text-2xl font-bold text-gray-800">Article not found</h1>
        <p className="text-gray-500">This news conversion may have been removed.</p>
        <Button onClick={() => navigate('/library')}>Back to Library</Button>
      </div>
    )
  }

  const categoryLabel = conversion.category
    ? conversion.category.charAt(0).toUpperCase() + conversion.category.slice(1)
    : 'General'

  // Split content into paragraphs for newspaper-style rendering
  const paragraphs = (conversion.kid_content || '').split('\n').filter(p => p.trim())

  return (
    <div className="news-detail-page max-w-3xl mx-auto space-y-5 pb-8">
      {/* Newspaper masthead */}
      <motion.header
        className="news-detail-header"
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="flex items-center justify-between mb-4">
          <button
            onClick={() => navigate(-1)}
            className="text-sm text-gray-400 hover:text-gray-600 transition-colors"
            style={{ fontFamily: "'Georgia', 'Noto Serif SC', serif" }}
          >
            ← Back
          </button>
          <span className="text-xs text-gray-400" style={{ fontFamily: "'Georgia', serif" }}>
            {new Date(conversion.created_at).toLocaleDateString('en-US', {
              weekday: 'long',
              year: 'numeric',
              month: 'long',
              day: 'numeric',
            })}
          </span>
        </div>

        {/* Divider line */}
        <div className="border-t-2 border-b border-gray-800 py-1 mb-4">
          <div className="border-b border-gray-800" />
        </div>

        {/* Headline */}
        <h1 className="news-detail-headline">
          {conversion.kid_title}
        </h1>

        {/* Byline */}
        <div className="flex items-center gap-3 mt-3">
          <span className="text-xs font-semibold uppercase tracking-wider px-2 py-0.5 border border-gray-300 text-gray-600">
            {categoryLabel}
          </span>
          <span className="text-xs text-gray-400 italic" style={{ fontFamily: "'Georgia', serif" }}>
            Adapted for {conversion.age_group} readers
          </span>
        </div>

        {/* Thin rule */}
        <div className="border-b border-gray-200 mt-4" />
      </motion.header>

      {/* Audio player */}
      {conversion.audio_url && (
        <motion.div
          className="news-audio-bar"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.1 }}
        >
          <span className="text-sm font-medium text-gray-600">Listen to this article</span>
          <audio controls className="w-full mt-2" src={conversion.audio_url} />
        </motion.div>
      )}

      {/* Main article body */}
      <motion.article
        className="news-article-body"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.15 }}
      >
        {paragraphs.map((para, idx) => (
          <p key={idx} className={idx === 0 ? 'first-news-para' : ''}>
            {para}
          </p>
        ))}
      </motion.article>

      {/* Why care — editorial callout */}
      {conversion.why_care && (
        <motion.div
          className="news-callout"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <h2>Why Should I Care?</h2>
          <p>{conversion.why_care}</p>
        </motion.div>
      )}

      {/* Key concepts */}
      {conversion.key_concepts && conversion.key_concepts.length > 0 && (
        <motion.div
          className="news-concepts"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
        >
          <h2>Key Concepts</h2>
          <div className="news-concepts-grid">
            {conversion.key_concepts.map((concept) => (
              <div key={concept.term} className="news-concept-card">
                <span className="news-concept-emoji">{concept.emoji}</span>
                <div>
                  <span className="news-concept-term">{concept.term}</span>
                  {concept.explanation && (
                    <span className="news-concept-explanation"> — {concept.explanation}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Interactive questions */}
      {conversion.interactive_questions && conversion.interactive_questions.length > 0 && (
        <motion.div
          className="news-questions"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <h2>Think About It</h2>
          {conversion.interactive_questions.map((q, idx) => (
            <div key={idx} className="news-question-item">
              <span className="news-question-emoji">{q.emoji}</span>
              <div>
                <p className="news-question-text">{q.question}</p>
                {q.hint && <p className="news-question-hint">Hint: {q.hint}</p>}
              </div>
            </div>
          ))}
        </motion.div>
      )}

      {/* Source */}
      {conversion.original_url && (
        <div className="text-center pt-4 border-t border-gray-200">
          <p className="text-xs text-gray-400" style={{ fontFamily: "'Georgia', serif" }}>
            Source:{' '}
            <a
              href={conversion.original_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-gray-500 hover:underline"
            >
              {conversion.original_url}
            </a>
          </p>
        </div>
      )}
    </div>
  )
}

export default NewsDetailPage
