import { useState, useCallback, useRef, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import Button from '@/components/common/Button'
import Card from '@/components/common/Card'
import { storyService } from '@/api/services/storyService'
import useAuthStore from '@/store/useAuthStore'
import useChildStore from '@/store/useChildStore'
import type { NewsCategory } from '@/types/api'
import LoginPrompt from '@/components/common/LoginPrompt'

const ALL_TOPICS: Array<{ topic: NewsCategory; label: string; icon: string; tagline: string }> = [
  { topic: 'space', label: 'Space', icon: '\ud83d\ude80', tagline: 'Rockets, planets & stars' },
  { topic: 'animals', label: 'Animals', icon: '\ud83d\udc3c', tagline: 'Cute, wild & amazing' },
  { topic: 'technology', label: 'Robots', icon: '\ud83e\udd16', tagline: 'Inventions & gadgets' },
  { topic: 'science', label: 'Science', icon: '\ud83d\udd2c', tagline: 'Experiments & discoveries' },
  { topic: 'nature', label: 'Nature', icon: '\ud83c\udf3f', tagline: 'Oceans, forests & weather' },
  { topic: 'culture', label: 'Culture', icon: '\ud83c\udfad', tagline: 'Art, music & stories' },
  { topic: 'sports', label: 'Sports', icon: '\u26bd', tagline: 'Goals, records & teamwork' },
  { topic: 'general', label: 'General', icon: '\ud83d\udcf0', tagline: 'A bit of everything' },
]

const LOADING_MESSAGES = [
  'Finding cool news...',
  'Reading the headlines...',
  'Writing the script...',
  'Mimi and Duo are rehearsing...',
  'Recording voices...',
  'Almost ready...',
]

/** Bouncing dots animation for loading states */
function BouncingDots() {
  return (
    <span className="inline-flex gap-0.5 ml-1">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="inline-block w-1.5 h-1.5 rounded-full bg-current"
          animate={{ y: [0, -5, 0] }}
          transition={{ duration: 0.5, repeat: Infinity, delay: i * 0.15 }}
        />
      ))}
    </span>
  )
}

/** Full-card overlay shown while generating a podcast */
function GeneratingOverlay({ icon, topic, onCancel }: { icon: string; topic: string; onCancel: () => void }) {
  const [msgIndex, setMsgIndex] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => {
      setMsgIndex((prev) => (prev + 1) % LOADING_MESSAGES.length)
    }, 3000)
    return () => clearInterval(timer)
  }, [])

  return (
    <motion.div
      className="absolute inset-0 z-10 flex flex-col items-center justify-center rounded-2xl bg-gradient-to-br from-primary/90 to-violet-500/90 backdrop-blur-sm text-white p-4"
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 1.1 }}
    >
      {/* Spinning topic icon */}
      <motion.div
        className="text-5xl mb-3"
        animate={{ rotate: 360 }}
        transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
      >
        {icon}
      </motion.div>

      {/* Pulsing ring */}
      <motion.div
        className="absolute w-20 h-20 rounded-full border-4 border-white/30"
        animate={{ scale: [1, 1.6, 1], opacity: [0.5, 0, 0.5] }}
        transition={{ duration: 1.5, repeat: Infinity }}
      />

      {/* Topic name */}
      <div className="font-bold text-lg mb-1">{topic}</div>

      {/* Cycling status message */}
      <AnimatePresence mode="wait">
        <motion.div
          key={msgIndex}
          className="text-sm text-white/90 text-center"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.3 }}
        >
          {LOADING_MESSAGES[msgIndex]}
          <BouncingDots />
        </motion.div>
      </AnimatePresence>

      {/* Cancel button */}
      <motion.button
        className="mt-3 px-4 py-1.5 rounded-full text-sm font-medium bg-white/20 hover:bg-white/30 active:bg-white/40 text-white border border-white/30 transition-colors"
        onClick={(e) => { e.stopPropagation(); onCancel() }}
        whileTap={{ scale: 0.9 }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1 }}
      >
        Stop
      </motion.button>
    </motion.div>
  )
}

/** Sparkle burst when subscribing succeeds */
function SubscribeSuccessBurst() {
  return (
    <motion.div
      className="absolute inset-0 pointer-events-none z-10 flex items-center justify-center"
      initial={{ opacity: 1 }}
      animate={{ opacity: 0 }}
      transition={{ duration: 0.8, delay: 0.2 }}
    >
      {[...Array(6)].map((_, i) => (
        <motion.span
          key={i}
          className="absolute text-xl"
          initial={{ scale: 0, x: 0, y: 0 }}
          animate={{
            scale: [0, 1.2, 0],
            x: Math.cos((i * Math.PI * 2) / 6) * 40,
            y: Math.sin((i * Math.PI * 2) / 6) * 40,
          }}
          transition={{ duration: 0.6 }}
        >
          {['✨', '⭐', '🌟', '💫', '✨', '⭐'][i]}
        </motion.span>
      ))}
    </motion.div>
  )
}

function NewsPage() {
  const { isAuthenticated } = useAuthStore()
  const { currentChild, defaultChildId } = useChildStore()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const childId = currentChild?.child_id || defaultChildId
  const ageGroup = currentChild?.age_group || '6-8'

  const [generatingTopic, setGeneratingTopic] = useState<NewsCategory | null>(null)
  const [pendingSubscribe, setPendingSubscribe] = useState<NewsCategory | null>(null)
  const [justSubscribed, setJustSubscribed] = useState<NewsCategory | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [rateLimitRetry, setRateLimitRetry] = useState<{ topic: NewsCategory; seconds: number } | null>(null)
  const retryTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const { data: subsData } = useQuery({
    queryKey: ['morning-show-subscriptions', childId],
    queryFn: () => storyService.getSubscriptions(childId),
    enabled: !!childId && isAuthenticated,
  })

  const activeTopics = new Set(
    (subsData?.items ?? []).filter((s) => s.is_active).map((s) => s.topic),
  )

  const handleSubscribe = useCallback(async (topic: NewsCategory) => {
    if (!childId || pendingSubscribe) return
    setError(null)
    setPendingSubscribe(topic)
    try {
      await storyService.subscribeTopic({ child_id: childId, topic })
      setJustSubscribed(topic)
      setTimeout(() => setJustSubscribed(null), 1000)
      await queryClient.invalidateQueries({ queryKey: ['morning-show-subscriptions', childId] })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Oops, something went wrong!')
    } finally {
      setPendingSubscribe(null)
    }
  }, [childId, pendingSubscribe, queryClient])

  const handleUnsubscribe = useCallback(async (topic: NewsCategory) => {
    if (!childId || pendingSubscribe) return
    setError(null)
    setPendingSubscribe(topic)
    try {
      await storyService.unsubscribeTopic(childId, topic)
      await queryClient.invalidateQueries({ queryKey: ['morning-show-subscriptions', childId] })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Oops, something went wrong!')
    } finally {
      setPendingSubscribe(null)
    }
  }, [childId, pendingSubscribe, queryClient])

  const handleListenNow = useCallback(async (topic: NewsCategory) => {
    if (!childId || generatingTopic) return
    setError(null)
    setGeneratingTopic(topic)

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const result = await storyService.generateMorningShowOnDemand(
        { child_id: childId, category: topic, age_group: ageGroup },
        controller.signal,
      )
      navigate(`/morning-show/${result.episode.episode_id}`)
    } catch (err: unknown) {
      if (controller.signal.aborted) return // user cancelled — do nothing

      const status = (err as { response?: { status?: number } })?.response?.status
      const data = (err as { response?: { data?: { message?: string; retry_after?: number } } })?.response?.data

      if (status === 429 && data?.retry_after) {
        // Per-topic rate limit (3/hour)
        const retryAfter = data.retry_after
        setRateLimitRetry({ topic, seconds: retryAfter })
        if (retryTimerRef.current) clearInterval(retryTimerRef.current)
        retryTimerRef.current = setInterval(() => {
          setRateLimitRetry((prev) => {
            if (!prev || prev.seconds <= 1) {
              if (retryTimerRef.current) clearInterval(retryTimerRef.current)
              return null
            }
            return { ...prev, seconds: prev.seconds - 1 }
          })
        }, 1000)
      } else if (status === 429) {
        // Daily quota exceeded
        setError("You've used all your listens for today - come back tomorrow!")
      } else if (status === 502) {
        setError('No fresh news right now - try again in a minute!')
      } else {
        setError('Something went wrong - try again!')
      }
    } finally {
      abortRef.current = null
      setGeneratingTopic(null)
    }
  }, [childId, ageGroup, generatingTopic, navigate])

  const handleCancelGeneration = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setGeneratingTopic(null)
  }, [])

  if (!isAuthenticated) {
    return (
      <div className="max-w-lg mx-auto mt-12">
        <LoginPrompt feature="listen to kids news" />
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <motion.div
        className="text-center"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <motion.span
          className="text-5xl inline-block"
          animate={{ scale: [1, 1.15, 1], rotate: [0, -5, 5, 0] }}
          transition={{ duration: 3, repeat: Infinity }}
        >
          🌍
        </motion.span>
        <h1 className="text-2xl md:text-3xl font-bold text-gray-800 mt-2">
          News of all topics!
        </h1>
        <p className="text-gray-600 mt-1">
          Pick what you love, then listen anytime
        </p>
      </motion.div>

      {/* Error display */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.95 }}
          >
            <Card className="border border-red-200 bg-red-50 text-red-700 text-center">
              <p className="text-sm">{error}</p>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {/* All topic cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        {ALL_TOPICS.map((item, index) => {
          const subscribed = activeTopics.has(item.topic)
          const isGenerating = generatingTopic === item.topic
          const isSubscribing = pendingSubscribe === item.topic
          const isRateLimited = rateLimitRetry?.topic === item.topic
          const showBurst = justSubscribed === item.topic

          return (
            <motion.div
              key={item.topic}
              className="relative"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: Math.min(index * 0.05, 0.3) }}
              whileHover={!isGenerating ? { scale: 1.03 } : {}}
              whileTap={!isGenerating ? { scale: 0.97 } : {}}
            >
              <Card
                className={`h-full text-center transition-all relative overflow-hidden ${
                  subscribed
                    ? 'border-2 border-primary bg-primary/5 shadow-md'
                    : 'border border-gray-200 hover:border-primary/40'
                }`}
              >
                <div className="space-y-2">
                  {/* Icon + label */}
                  <motion.div
                    className="text-4xl"
                    animate={subscribed ? { scale: [1, 1.1, 1] } : {}}
                    transition={{ duration: 0.4 }}
                  >
                    {item.icon}
                  </motion.div>
                  <div className="font-bold text-gray-800">{item.label}</div>
                  <p className="text-xs text-gray-500 leading-snug">{item.tagline}</p>

                  {/* Buttons */}
                  {subscribed ? (
                    <div className="space-y-1.5 pt-1">
                      {/* Listen Now */}
                      <motion.button
                        className={`w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-sm font-semibold text-white transition-colors ${
                          isGenerating
                            ? 'bg-primary/70 cursor-wait'
                            : isRateLimited
                              ? 'bg-amber-400 cursor-not-allowed'
                              : 'bg-primary hover:bg-primary/90 active:bg-primary/80'
                        }`}
                        disabled={generatingTopic !== null || isRateLimited}
                        onClick={() => handleListenNow(item.topic)}
                        whileTap={!isGenerating && !isRateLimited ? { scale: 0.95 } : {}}
                      >
                        {isRateLimited ? (
                          <>
                            <motion.span
                              animate={{ rotate: [0, 180] }}
                              transition={{ duration: 1, repeat: Infinity }}
                            >
                              ⏳
                            </motion.span>
                            {rateLimitRetry!.seconds}s
                          </>
                        ) : (
                          <>
                            <span>&#9654;</span>
                            Listen Now
                          </>
                        )}
                      </motion.button>

                      {/* Kids Daily */}
                      <Link
                        to={`/morning-show/episodes?topic=${item.topic}`}
                        className="block"
                      >
                        <Button size="sm" variant="outline" className="w-full text-xs">
                          Kids Daily
                        </Button>
                      </Link>

                      {/* Unsubscribe */}
                      <button
                        className="text-xs text-gray-400 hover:text-red-400 transition-colors w-full"
                        disabled={isSubscribing}
                        onClick={() => handleUnsubscribe(item.topic)}
                      >
                        {isSubscribing ? '...' : 'Unsubscribe'}
                      </button>
                    </div>
                  ) : (
                    <div className="pt-1">
                      <motion.button
                        className={`w-full flex items-center justify-center gap-1 px-3 py-2 rounded-xl text-sm font-medium border-2 transition-colors ${
                          isSubscribing
                            ? 'border-primary/50 bg-primary/10 text-primary'
                            : 'border-gray-200 text-gray-700 hover:border-primary hover:text-primary hover:bg-primary/5'
                        }`}
                        disabled={isSubscribing}
                        onClick={() => handleSubscribe(item.topic)}
                        whileTap={{ scale: 0.93 }}
                      >
                        {isSubscribing ? (
                          <>
                            <motion.span
                              animate={{ rotate: 360 }}
                              transition={{ duration: 0.8, repeat: Infinity, ease: 'linear' }}
                            >
                              ✨
                            </motion.span>
                            Following
                            <BouncingDots />
                          </>
                        ) : (
                          '+ Follow'
                        )}
                      </motion.button>
                    </div>
                  )}
                </div>

                {/* Generating overlay */}
                <AnimatePresence>
                  {isGenerating && (
                    <GeneratingOverlay icon={item.icon} topic={item.label} onCancel={handleCancelGeneration} />
                  )}
                </AnimatePresence>
              </Card>

              {/* Subscribe sparkle burst */}
              <AnimatePresence>
                {showBurst && <SubscribeSuccessBurst />}
              </AnimatePresence>
            </motion.div>
          )
        })}
      </div>

      {/* Footer link */}
      <div className="text-center pb-4">
        <Link to="/morning-show/subscriptions">
          <Button variant="outline" size="sm">
            Manage my channels
          </Button>
        </Link>
      </div>
    </div>
  )
}

export default NewsPage
