import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import Card from '@/components/common/Card'
import Button from '@/components/common/Button'
import useChildStore from '@/store/useChildStore'
import { storyService } from '@/api/services/storyService'
import type { NewsCategory } from '@/types/api'

const TOPIC_CARDS: Array<{ topic: NewsCategory; titleZh: string; titleEn: string; icon: string; description: string }> = [
  { topic: 'space', titleZh: '太空', titleEn: 'Space', icon: '🚀', description: 'Planets, stars, and space discoveries.' },
  { topic: 'animals', titleZh: '动物', titleEn: 'Animals', icon: '🐼', description: 'Wildlife stories and animal science.' },
  { topic: 'technology', titleZh: '机器人', titleEn: 'Robots/Tech', icon: '🤖', description: 'Inventors, robots, and new technology.' },
  { topic: 'science', titleZh: '科学', titleEn: 'Science', icon: '🔬', description: 'Experiments and explainers for curious kids.' },
  { topic: 'nature', titleZh: '自然', titleEn: 'Nature', icon: '🌿', description: 'Forests, oceans, weather, and ecosystems.' },
  { topic: 'culture', titleZh: '文化', titleEn: 'Culture', icon: '🎭', description: 'Arts, traditions, and stories from around the world.' },
  { topic: 'sports', titleZh: '体育', titleEn: 'Sports', icon: '⚽', description: 'Kid-friendly sports highlights and teamwork lessons.' },
  { topic: 'general', titleZh: '综合', titleEn: 'General', icon: '📰', description: 'A balanced mix of trending kid-safe topics.' },
]

const MAX_SUBSCRIPTIONS = 5
const ONBOARD_KEY = 'morning_show_onboarding_done'

function MorningShowSubscriptionsPage() {
  const queryClient = useQueryClient()
  const { currentChild, defaultChildId } = useChildStore()
  const childId = currentChild?.child_id || defaultChildId

  const [pendingTopic, setPendingTopic] = useState<NewsCategory | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [showOnboarding, setShowOnboarding] = useState(false)
  const [onboardingStep, setOnboardingStep] = useState(0)
  const [draftTopics, setDraftTopics] = useState<Set<NewsCategory>>(new Set())
  const [onboardingBusy, setOnboardingBusy] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['morning-show-subscriptions', childId],
    queryFn: () => storyService.getSubscriptions(childId),
    enabled: !!childId,
  })

  const activeTopics = useMemo(() => {
    return new Set((data?.items ?? []).filter((item) => item.is_active).map((item) => item.topic))
  }, [data])

  const activeCount = activeTopics.size

  useEffect(() => {
    if (isLoading || !childId) return
    const onboardingDone = localStorage.getItem(ONBOARD_KEY) === 'true'
    if (!onboardingDone && activeCount === 0) {
      setShowOnboarding(true)
      setOnboardingStep(0)
    }
  }, [isLoading, activeCount, childId])

  const toggleTopic = async (topic: NewsCategory) => {
    if (!childId || pendingTopic) return

    setError(null)
    setPendingTopic(topic)

    try {
      if (activeTopics.has(topic)) {
        await storyService.unsubscribeTopic(childId, topic)
      } else {
        if (activeCount >= MAX_SUBSCRIPTIONS) {
          setError(`You can subscribe to up to ${MAX_SUBSCRIPTIONS} topics.`)
          setPendingTopic(null)
          return
        }
        await storyService.subscribeTopic({ child_id: childId, topic })
      }

      await queryClient.invalidateQueries({ queryKey: ['morning-show-subscriptions', childId] })
      await queryClient.invalidateQueries({ queryKey: ['library'] })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update subscription'
      setError(message)
    } finally {
      setPendingTopic(null)
    }
  }

  const toggleDraftTopic = (topic: NewsCategory) => {
    setDraftTopics((prev) => {
      const next = new Set(prev)
      if (next.has(topic)) {
        next.delete(topic)
      } else if (next.size < 3) {
        next.add(topic)
      }
      return next
    })
  }

  const finishOnboarding = async (skip: boolean) => {
    if (!childId) return
    setOnboardingBusy(true)
    setError(null)

    try {
      if (!skip) {
        for (const topic of Array.from(draftTopics)) {
          await storyService.subscribeTopic({ child_id: childId, topic })
        }
      }
      localStorage.setItem(ONBOARD_KEY, 'true')
      setShowOnboarding(false)
      await queryClient.invalidateQueries({ queryKey: ['morning-show-subscriptions', childId] })
      await queryClient.invalidateQueries({ queryKey: ['library'] })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to complete onboarding'
      setError(message)
    } finally {
      setOnboardingBusy(false)
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Morning Show Channels</h1>
          <p className="text-sm text-gray-500">Pick up to five channels for Daily Drop episodes.</p>
        </div>
        <div className="flex items-center gap-2">
          <div className={`text-sm px-3 py-1 rounded-full ${activeCount >= MAX_SUBSCRIPTIONS ? 'bg-amber-100 text-amber-700' : 'bg-gray-100 text-gray-600'}`}>
            {activeCount}/{MAX_SUBSCRIPTIONS} selected
          </div>
          <Link to="/library">
            <Button variant="outline" size="sm">Back to Library</Button>
          </Link>
        </div>
      </div>

      {error && (
        <Card className="border border-red-200 bg-red-50 text-red-700">
          <p className="text-sm">{error}</p>
        </Card>
      )}

      {isLoading ? (
        <div className="text-center py-12 text-gray-500">Loading topic channels...</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {TOPIC_CARDS.map((card, index) => {
            const active = activeTopics.has(card.topic)
            const busy = pendingTopic === card.topic
            const disabled = !active && activeCount >= MAX_SUBSCRIPTIONS

            return (
              <motion.div
                key={card.topic}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: Math.min(index * 0.04, 0.25) }}
              >
                <Card className={`h-full border ${active ? 'border-primary bg-primary/5' : 'border-gray-200'}`}>
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="text-3xl">{card.icon}</div>
                        <h2 className="text-lg font-bold text-gray-800 mt-2">{card.titleZh}</h2>
                        <p className="text-sm text-gray-500">{card.titleEn}</p>
                      </div>
                      {active && (
                        <div className="px-2 py-1 rounded-full bg-emerald-100 text-emerald-700 text-xs font-semibold">
                          ✓ Active
                        </div>
                      )}
                    </div>

                    <p className="text-sm text-gray-600 min-h-[48px]">{card.description}</p>

                    <Button
                      size="sm"
                      variant={active ? 'outline' : 'primary'}
                      className="w-full"
                      isLoading={busy}
                      disabled={busy || disabled}
                      onClick={() => toggleTopic(card.topic)}
                    >
                      {active ? 'Unsubscribe' : 'Subscribe'}
                    </Button>
                  </div>
                </Card>
              </motion.div>
            )
          })}
        </div>
      )}

      {showOnboarding && (
        <div className="fixed inset-0 z-50 bg-black/40 p-4 flex items-center justify-center">
          <Card className="w-full max-w-2xl">
            {onboardingStep === 0 && (
              <div className="space-y-4">
                <h2 className="text-2xl font-bold text-gray-800">Welcome to Morning Show</h2>
                <p className="text-gray-600">Pick your favorite topic channels and we will prepare a Daily Drop episode for tomorrow morning.</p>
                <div className="flex gap-2 justify-end">
                  <Button variant="outline" onClick={() => finishOnboarding(true)} isLoading={onboardingBusy}>Skip</Button>
                  <Button onClick={() => setOnboardingStep(1)}>Start Setup</Button>
                </div>
              </div>
            )}

            {onboardingStep === 1 && (
              <div className="space-y-4">
                <h2 className="text-2xl font-bold text-gray-800">Choose 1-3 Topics</h2>
                <p className="text-gray-600">Selected: {draftTopics.size}/3</p>
                <div className="grid grid-cols-2 gap-2">
                  {TOPIC_CARDS.map((card) => {
                    const selected = draftTopics.has(card.topic)
                    return (
                      <button
                        key={card.topic}
                        className={`text-left rounded-xl border px-3 py-2 transition-colors ${selected ? 'border-primary bg-primary/10' : 'border-gray-200 hover:border-primary/40'}`}
                        onClick={() => toggleDraftTopic(card.topic)}
                      >
                        <div className="text-lg">{card.icon} {card.titleZh}</div>
                        <div className="text-xs text-gray-500">{card.titleEn}</div>
                      </button>
                    )
                  })}
                </div>
                <div className="flex gap-2 justify-end">
                  <Button variant="outline" onClick={() => finishOnboarding(true)} isLoading={onboardingBusy}>Skip</Button>
                  <Button disabled={draftTopics.size === 0} onClick={() => setOnboardingStep(2)}>Continue</Button>
                </div>
              </div>
            )}

            {onboardingStep === 2 && (
              <div className="space-y-4">
                <h2 className="text-2xl font-bold text-gray-800">You&apos;re all set</h2>
                <p className="text-gray-600">Your first Morning Show episode will be ready tomorrow morning. You can update channels anytime.</p>
                <div className="flex flex-wrap gap-2">
                  {Array.from(draftTopics).map((topic) => {
                    const card = TOPIC_CARDS.find((item) => item.topic === topic)
                    return (
                      <span key={topic} className="text-sm px-2 py-1 rounded-full bg-primary/10 text-primary">
                        {card?.icon} {card?.titleEn}
                      </span>
                    )
                  })}
                </div>
                <div className="flex gap-2 justify-end">
                  <Button variant="outline" onClick={() => setOnboardingStep(1)}>Back</Button>
                  <Button onClick={() => finishOnboarding(false)} isLoading={onboardingBusy}>Finish Setup</Button>
                </div>
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  )
}

export default MorningShowSubscriptionsPage
