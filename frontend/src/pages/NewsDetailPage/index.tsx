import { useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import Card from '@/components/common/Card'
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

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">{conversion.kid_title}</h1>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-accent/10 text-accent">
              {categoryLabel}
            </span>
            <span className="text-sm text-gray-500">
              {conversion.age_group} age group
            </span>
            <span className="text-sm text-gray-400">
              {new Date(conversion.created_at).toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
              })}
            </span>
          </div>
        </div>
        <Button variant="ghost" size="sm" onClick={() => navigate('/library')}>
          Back to Library
        </Button>
      </div>

      {/* Audio player */}
      {conversion.audio_url && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Card>
            <h2 className="text-base font-bold text-gray-800 mb-2">Listen</h2>
            <audio controls className="w-full" src={conversion.audio_url} />
          </Card>
        </motion.div>
      )}

      {/* Main content */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
      >
        <Card>
          <div className="prose prose-sm max-w-none text-gray-700 leading-relaxed whitespace-pre-line">
            {conversion.kid_content}
          </div>
        </Card>
      </motion.div>

      {/* Why care */}
      {conversion.why_care && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <Card>
            <h2 className="text-base font-bold text-gray-800 mb-2">Why Should I Care?</h2>
            <p className="text-sm text-gray-600 leading-relaxed">{conversion.why_care}</p>
          </Card>
        </motion.div>
      )}

      {/* Key concepts */}
      {conversion.key_concepts && conversion.key_concepts.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
        >
          <Card>
            <h2 className="text-base font-bold text-gray-800 mb-2">Key Concepts</h2>
            <div className="space-y-2">
              {conversion.key_concepts.map((concept) => (
                <div key={concept.term} className="text-sm bg-gray-50 rounded-lg p-2">
                  <span className="font-semibold text-gray-800">
                    {concept.emoji} {concept.term}:
                  </span>{' '}
                  <span className="text-gray-600">{concept.explanation}</span>
                </div>
              ))}
            </div>
          </Card>
        </motion.div>
      )}

      {/* Interactive questions */}
      {conversion.interactive_questions && conversion.interactive_questions.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <Card>
            <h2 className="text-base font-bold text-gray-800 mb-2">Think About It</h2>
            <div className="space-y-2">
              {conversion.interactive_questions.map((q, idx) => (
                <div
                  key={idx}
                  className="text-sm bg-primary/5 border border-primary/15 rounded-lg p-2"
                >
                  <p className="text-gray-700">
                    {q.emoji} {q.question}
                  </p>
                  {q.hint && (
                    <p className="text-gray-400 text-xs mt-1">Hint: {q.hint}</p>
                  )}
                </div>
              ))}
            </div>
          </Card>
        </motion.div>
      )}

      {/* Original URL */}
      {conversion.original_url && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
        >
          <Card>
            <p className="text-xs text-gray-400">
              Original source:{' '}
              <a
                href={conversion.original_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                {conversion.original_url}
              </a>
            </p>
          </Card>
        </motion.div>
      )}
    </div>
  )
}

export default NewsDetailPage
