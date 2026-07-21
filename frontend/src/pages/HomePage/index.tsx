import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowRight,
  BookOpen,
  Globe2,
  ImagePlus,
  MessageCircle,
  Newspaper,
  Sparkles,
} from 'lucide-react'
import { DepthLayer } from '@/components/depth/DepthLayer'
import useAuthStore from '@/store/useAuthStore'
import useDailyTaskStore from '@/store/useDailyTaskStore'
import { libraryService, type LibraryItem } from '@/api/services/libraryService'
import { fetchDailyInspiration, toDailyContent } from '@/api/services/inspirationService'
import StarFlyAnimation from '@/components/daily/StarFlyAnimation'
import { useNavRef } from '@/contexts/NavRefContext'
import { resolveMediaUrl } from '@/utils/mediaUrl'

const FEATURE_SHOWCASE = [
  {
    to: '/upload',
    icon: ImagePlus,
    title: 'Art to Story',
    description: "Turn a child's drawing into a narrated picture-book adventure.",
    accent: 'from-primary/20 to-primary/5 border-primary/20 text-primary',
  },
  {
    to: '/interactive',
    icon: BookOpen,
    title: 'Interactive Tales',
    description: 'Let kids choose what happens next and shape the story as they go.',
    accent: 'from-secondary/20 to-secondary/5 border-secondary/25 text-teal-700',
  },
  {
    to: '/my-agent',
    icon: MessageCircle,
    title: 'My Agent',
    description: 'A creative buddy that remembers interests and helps launch new ideas.',
    accent: 'from-purple-100 to-purple-50 border-purple-200 text-purple-700',
  },
  {
    to: '/content-hub',
    icon: Globe2,
    title: 'Content Hub',
    description: 'Share finished creations in groups with kid-safe attribution.',
    accent: 'from-sky-100 to-sky-50 border-sky-200 text-sky-700',
  },
  {
    to: '/kids-daily',
    icon: Newspaper,
    title: 'Kids Daily',
    description: 'Make real-world topics simple, warm, and age-aware.',
    accent: 'from-accent/35 to-accent/10 border-accent/40 text-yellow-700',
  },
]

const WORKSPACE_CREATION_FEATURES = FEATURE_SHOWCASE.filter((feature) =>
  ['/upload', '/interactive', '/kids-daily'].includes(feature.to),
)

const HERO_ACTIONS = [
  {
    to: '/upload',
    icon: ImagePlus,
    label: 'Start with a drawing',
  },
  {
    to: '/my-agent',
    icon: MessageCircle,
    label: 'Chat with My Agent',
  },
  {
    to: '/interactive',
    icon: BookOpen,
    label: 'Make an interactive tale',
  },
  {
    to: '/kids-daily',
    icon: Newspaper,
    label: 'Explore Kids Daily',
  },
]

const HERO_IMAGES = [
  {
    src: '/images/hero-agentic-kid.jpg',
    alt: 'A cheerful child creating with an AI buddy',
  },
  {
    src: '/images/hero-agentic-girl.jpg',
    alt: 'A cheerful girl drawing with an AI buddy',
  },
  {
    src: '/images/hero-agentic-boy.jpg',
    alt: 'A cheerful boy sketching with an AI buddy',
  },
]

function getItemRoute(item: LibraryItem): string {
  switch (item.type) {
    case 'art-story': return `/story/${item.id}`
    case 'interactive': return `/interactive?session=${item.id}`
    case 'kids-daily':
    case 'kids-news':
    case 'morning-show': return `/kids-daily/${item.id}`
    default: return `/kids-daily/${item.id}`
  }
}

function getItemTypeLabel(item: LibraryItem): string {
  switch (item.type) {
    case 'art-story': return 'Art Story'
    case 'interactive': return 'Interactive'
    case 'kids-daily':
    case 'kids-news':
    case 'morning-show': return 'Kids Daily'
    default: return 'Kids Daily'
  }
}

function RecentCreationCard({ item, onClick }: { item: LibraryItem; onClick: () => void }) {
  const imageUrl = item.thumbnail_url || item.image_url
  const [imageFailed, setImageFailed] = useState(false)
  const FallbackIcon =
    item.type === 'interactive' ? BookOpen : item.type === 'art-story' ? ImagePlus : Newspaper

  return (
    <motion.div
      className="card-kid w-full min-w-0 cursor-pointer"
      onClick={onClick}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
    >
      <div className="flex gap-4">
        <div className="flex h-16 w-16 flex-shrink-0 items-center justify-center overflow-hidden rounded-lg bg-gradient-to-br from-primary/20 to-secondary/20">
          {imageUrl && !imageFailed ? (
            <img
              src={resolveMediaUrl(imageUrl) || ''}
              alt=""
              className="h-full w-full object-cover"
              onError={() => setImageFailed(true)}
            />
          ) : (
            <FallbackIcon className="text-primary" size={28} />
          )}
        </div>

        <div className="min-w-0 flex-1">
          <div className="mb-1 flex items-center gap-2">
            <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-semibold text-primary">
              {getItemTypeLabel(item)}
            </span>
          </div>
          <h3 className="mb-1 truncate font-bold text-gray-800">{item.title}</h3>
          <p className="line-clamp-2 text-sm text-gray-500">{item.preview}</p>
          <p className="mt-2 text-xs text-gray-400">
            {new Date(item.created_at).toLocaleDateString('zh-CN', {
              month: 'short',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            })}
          </p>
        </div>

        <div className="flex flex-shrink-0 items-center text-gray-400">
          <motion.span animate={{ x: [0, 4, 0] }} transition={{ duration: 1.5, repeat: Infinity }}>
            →
          </motion.span>
        </div>
      </div>
    </motion.div>
  )
}

function WorkspaceFeatureCard({
  feature,
  onClick,
}: {
  feature: (typeof FEATURE_SHOWCASE)[number]
  onClick: () => void
}) {
  const Icon = feature.icon

  return (
    <button
      type="button"
      onClick={onClick}
      className={`min-h-[150px] rounded-lg border bg-gradient-to-br p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-card ${feature.accent}`}
    >
      <Icon size={26} className="mb-4" />
      <h3 className="mb-1 text-base font-bold text-gray-900">{feature.title}</h3>
      <p className="text-sm leading-snug text-gray-600">{feature.description}</p>
    </button>
  )
}

function HomePage() {
  const navigate = useNavigate()
  const { isAuthenticated, user } = useAuthStore()
  const canClaim = useDailyTaskStore((s) => s.canClaimToday())
  const claimStar = useDailyTaskStore((s) => s.claimStar)
  const lastClaimTimestamp = useDailyTaskStore((s) => s.lastClaimTimestamp)
  const { profileAvatarRef } = useNavRef()
  const newspaperRef = useRef<HTMLDivElement>(null)
  const [starFlying, setStarFlying] = useState(false)
  const [newspaperVisible, setNewspaperVisible] = useState(true)
  const [heroActionIndex, setHeroActionIndex] = useState(0)
  const [heroImageIndex, setHeroImageIndex] = useState(0)

  const HIDE_AFTER_MS = 5 * 60 * 1000

  useEffect(() => {
    if (!isAuthenticated) {
      setNewspaperVisible(false)
      return
    }

    if (canClaim) {
      setNewspaperVisible(true)
      return
    }

    if (!lastClaimTimestamp) {
      setNewspaperVisible(false)
      return
    }

    const elapsed = Date.now() - lastClaimTimestamp
    if (elapsed >= HIDE_AFTER_MS) {
      setNewspaperVisible(false)
      return
    }

    setNewspaperVisible(true)
    const timer = setTimeout(() => setNewspaperVisible(false), HIDE_AFTER_MS - elapsed)
    return () => clearTimeout(timer)
  }, [canClaim, isAuthenticated, lastClaimTimestamp, HIDE_AFTER_MS])

  const handleTearComplete = useCallback(() => {
    setStarFlying(true)
  }, [])

  const handleStarArrived = useCallback(() => {
    setStarFlying(false)
    claimStar()
  }, [claimStar])

  const currentUserId = user?.user_id ?? 'anonymous'
  const { data: libraryData } = useQuery({
    queryKey: ['homepage-recent', currentUserId],
    queryFn: () => libraryService.getLibrary({ sort: 'newest', limit: 3 }),
    enabled: isAuthenticated,
  })
  const recentItems = libraryData?.items ?? []

  const { data: inspirationContent } = useQuery({
    queryKey: ['inspiration-daily'],
    queryFn: async () => {
      const resp = await fetchDailyInspiration('6-8')
      return resp ? toDailyContent(resp) : null
    },
    enabled: isAuthenticated,
    staleTime: 1000 * 60 * 60,
    retry: false,
  })

  useEffect(() => {
    const timer = setInterval(() => {
      setHeroActionIndex((i) => (i + 1) % HERO_ACTIONS.length)
    }, 3000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    const timer = setInterval(() => {
      setHeroImageIndex((i) => (i + 1) % HERO_IMAGES.length)
    }, 4200)
    return () => clearInterval(timer)
  }, [])

  const heroAction = HERO_ACTIONS[heroActionIndex]
  const HeroActionIcon = heroAction.icon
  const heroImage = HERO_IMAGES[heroImageIndex]
  const displayName = user?.display_name || user?.username || 'creator'
  const dailyCard = inspirationContent ?? {
    headline: 'Today’s creative spark',
    body: 'Open Kids Daily for a gentle curiosity prompt made for young creators.',
    illustration: '',
    weather: 'Ready for ideas',
    weatherEmoji: '',
    miniAd: '',
    cta_route: '/kids-daily' as const,
    creative_prompt: 'What would you like to imagine today?',
  }

  if (isAuthenticated) {
    return (
      <div className="space-y-8">
        <StarFlyAnimation
          active={starFlying}
          fromRef={newspaperRef}
          toRef={profileAvatarRef}
          onComplete={handleStarArrived}
        />

        <motion.section
          className="overflow-hidden rounded-lg border border-white/70 bg-white/85 shadow-sm backdrop-blur"
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45 }}
        >
          <div className="grid gap-6 p-6 md:grid-cols-[1.25fr_0.75fr] md:p-8">
            <div>
              <p className="mb-2 text-sm font-bold uppercase tracking-wide text-primary">
                Creative Workspace
              </p>
              <h1 className="text-3xl font-extrabold text-gray-900 sm:text-4xl">
                Welcome back, {displayName}.
              </h1>
              <p className="mt-3 max-w-2xl text-base leading-relaxed text-gray-600">
                Pick up a story, start from a drawing, ask your agent for ideas, or explore today&apos;s curiosity.
              </p>
            </div>

            <div className="grid content-start gap-3 rounded-lg border border-gray-200 bg-gray-50 p-4">
              <Link to="/upload" className="k12-button-primary min-h-[44px]">
                <ImagePlus size={18} />
                New art story
              </Link>
              <Link to="/my-agent" className="k12-button-secondary min-h-[44px]">
                <MessageCircle size={18} />
                Open My Agent
              </Link>
              <Link to="/library" className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-bold text-gray-700 transition hover:bg-gray-100">
                <BookOpen size={18} />
                Continue from library
              </Link>
            </div>
          </div>
        </motion.section>

        <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <section className="space-y-4">
            <div>
              <h2 className="text-xl font-bold text-gray-900">Start Something</h2>
              <p className="text-sm text-gray-600">Fast entry points for today&apos;s creative session.</p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {WORKSPACE_CREATION_FEATURES.map((feature) => (
                <WorkspaceFeatureCard
                  key={feature.to}
                  feature={feature}
                  onClick={() => navigate(feature.to)}
                />
              ))}
            </div>
          </section>

          <section className="space-y-4">
            <div>
              <h2 className="text-xl font-bold text-gray-900">Today</h2>
              <p className="text-sm text-gray-600">Daily inspiration and recent work stay close at hand.</p>
            </div>

            <AnimatePresence>
              {newspaperVisible ? (
                <motion.div
                  ref={newspaperRef}
                  className="rounded-lg border border-gray-200 bg-white/90 p-5 shadow-sm"
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                >
                  <div className="flex items-start gap-4">
                    <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-lg bg-accent/30 text-2xl">
                      <Newspaper className="text-yellow-700" size={24} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        <span className="rounded-full bg-secondary/10 px-2.5 py-1 text-xs font-bold text-teal-700">
                          Kids Daily
                        </span>
                        <span className="text-xs font-semibold text-gray-400">
                          {dailyCard.weather}
                        </span>
                      </div>
                      <h3 className="text-lg font-bold text-gray-900">{dailyCard.headline}</h3>
                      <p className="mt-2 line-clamp-4 text-sm leading-relaxed text-gray-600">
                        {dailyCard.creative_prompt || dailyCard.body}
                      </p>
                      <div className="mt-4 flex flex-wrap gap-2">
                        <Link
                          to={dailyCard.cta_route ?? '/kids-daily'}
                          className="k12-button-primary"
                        >
                          <Newspaper size={16} />
                          Open Kids Daily
                        </Link>
                        <button
                          type="button"
                          onClick={handleTearComplete}
                          disabled={!canClaim}
                          className="k12-button-secondary disabled:opacity-50"
                        >
                          {canClaim ? 'Claim spark' : 'Spark claimed'}
                        </button>
                      </div>
                    </div>
                  </div>
                </motion.div>
              ) : (
                <motion.div
                  className="rounded-lg border border-gray-200 bg-white/85 p-5 shadow-sm"
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                >
                  <h3 className="text-base font-bold text-gray-900">Kids Daily is ready when curiosity strikes.</h3>
                  <p className="mt-1 text-sm text-gray-600">
                    Explore gentle, age-aware world topics with your child profile.
                  </p>
                  <Link to="/kids-daily" className="mt-4 inline-flex text-sm font-bold text-primary hover:text-primary/80">
                    Open Kids Daily →
                  </Link>
                </motion.div>
              )}
            </AnimatePresence>
          </section>
        </div>

        <section>
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-gray-900">Recent Creations</h2>
              <p className="text-sm text-gray-600">Your latest stories, sessions, and Kids Daily episodes.</p>
            </div>
            <Link to="/library" className="text-sm font-bold text-primary hover:text-primary/80">
              View library →
            </Link>
          </div>

          {recentItems.length > 0 ? (
            <div className="grid gap-3 lg:grid-cols-3">
              {recentItems.map((item) => (
                <RecentCreationCard
                  key={item.id}
                  item={item}
                  onClick={() => navigate(getItemRoute(item))}
                />
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-gray-200 bg-white/80 p-6 text-center shadow-sm">
              <p className="text-gray-500">No creations yet. Start with a drawing or ask My Agent for a first idea.</p>
            </div>
          )}
        </section>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <StarFlyAnimation
        active={starFlying}
        fromRef={newspaperRef}
        toRef={profileAvatarRef}
        onComplete={handleStarArrived}
      />

      <motion.section
        className="hero-banner relative min-h-[540px] overflow-hidden rounded-card sm:min-h-[520px]"
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, type: 'spring', stiffness: 100 }}
      >
        <DepthLayer config={{ layer: 'background', parallaxFactor: 0.3 }}>
          <div className="absolute inset-0 bg-[linear-gradient(135deg,#fff7f0_0%,#ffffff_46%,#e9fbf7_100%)]" />
        </DepthLayer>

        <div className="pointer-events-none absolute inset-0">
          <div className="absolute left-0 top-0 h-32 w-32 rounded-full bg-primary/10 blur-3xl" />
          <div className="absolute bottom-0 right-0 h-40 w-40 rounded-full bg-secondary/10 blur-3xl" />
          <div className="absolute inset-x-8 bottom-0 h-px bg-gradient-to-r from-transparent via-gray-200 to-transparent" />
        </div>

        <DepthLayer config={{ layer: 'foreground', parallaxFactor: 0.7 }}>
          <div className="relative z-10 grid min-h-[540px] items-center gap-8 p-7 sm:min-h-[520px] sm:p-10 md:grid-cols-[1.02fr_0.98fr] md:p-12">
            <div className="max-w-2xl text-center md:text-left">
              <motion.div
                className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/70 bg-white/80 px-3 py-1.5 text-xs font-bold text-primary shadow-sm backdrop-blur"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.12 }}
              >
                <Sparkles size={14} />
                Imagination-first creation for kids
              </motion.div>
              <motion.h1
                className="mb-4 text-4xl font-extrabold leading-tight text-gray-900 sm:text-5xl"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.2 }}
              >
                Let every child&apos;s imagination fly.
              </motion.h1>
              <motion.p
                className="mx-auto mb-6 max-w-xl text-base leading-relaxed text-gray-600 sm:text-lg md:mx-0"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.3 }}
              >
                Creative Workshop turns drawings, ideas, choices, and curiosities into
                safe AI stories kids can read, hear, continue, and share.
              </motion.p>
              <motion.div
                className="flex flex-col gap-3 sm:flex-row sm:justify-center md:justify-start"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.38 }}
              >
                <Link
                  to={heroAction.to}
                  className="btn-primary inline-flex min-h-[50px] min-w-[230px] items-center justify-center gap-2"
                >
                  <AnimatePresence mode="wait">
                    <motion.span
                      key={heroAction.label}
                      className="inline-flex items-center gap-2"
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -8 }}
                      transition={{ duration: 0.22 }}
                    >
                      <HeroActionIcon size={18} />
                      {heroAction.label}
                      <ArrowRight size={18} />
                    </motion.span>
                  </AnimatePresence>
                </Link>
              </motion.div>
            </div>

            <motion.div
              className="relative mx-auto w-full max-w-[380px]"
              initial={{ opacity: 0, scale: 0.96, y: 18 }}
              animate={{ opacity: 1, scale: 1, y: [0, -8, 0] }}
              transition={{
                opacity: { delay: 0.22, duration: 0.45 },
                scale: { delay: 0.22, duration: 0.45 },
                y: { duration: 5, repeat: Infinity, ease: 'easeInOut' },
              }}
            >
              <div className="absolute inset-x-10 bottom-2 h-12 rounded-full bg-gray-900/10 blur-2xl" />
              <div className="relative overflow-hidden rounded-lg border border-white/70 bg-white/50 shadow-kid-lg backdrop-blur">
                <AnimatePresence mode="wait">
                  <motion.img
                    key={heroImage.src}
                    src={heroImage.src}
                    alt={heroImage.alt}
                    className="aspect-[4/5] h-auto w-full object-cover object-center"
                    initial={{ opacity: 0, scale: 1.02 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.98 }}
                    transition={{ duration: 0.45 }}
                  />
                </AnimatePresence>
              </div>
            </motion.div>
          </div>
        </DepthLayer>
      </motion.section>

      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.42 }}
      >
        <div className="mb-4 flex items-end justify-between gap-3">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">What kids can create here</h2>
            <p className="text-sm text-gray-600">A quick overview of the creative paths inside the workshop.</p>
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {FEATURE_SHOWCASE.map((feature, index) => {
            const Icon = feature.icon
            return (
              <motion.div
                key={feature.to}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.48 + index * 0.05 }}
              >
                <article
                  className={`h-full rounded-lg border bg-gradient-to-br p-4 shadow-sm ${feature.accent}`}
                >
                  <Icon size={26} className="mb-4" />
                  <h3 className="mb-1 text-base font-bold text-gray-900">{feature.title}</h3>
                  <p className="text-sm leading-snug text-gray-600">{feature.description}</p>
                </article>
              </motion.div>
            )
          })}
        </div>
      </motion.section>

      {!isAuthenticated && (
        <motion.section
          id="membership"
          className="rounded-lg border border-secondary/25 bg-white/90 p-5 shadow-sm"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.52 }}
        >
          <div className="grid gap-5 md:grid-cols-[1fr_auto] md:items-center">
            <div>
              <h2 className="text-xl font-bold text-gray-900">Explore Kids Daily with a family account</h2>
              <p className="mt-1 text-sm text-gray-600">
                Sign in to unlock the daily newspaper, topic subscriptions, and saved episodes for each child profile.
              </p>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row md:justify-end">
              <Link
                to="/login"
                className="btn-primary inline-flex min-h-[48px] items-center justify-center gap-2 px-5"
              >
                <Newspaper size={18} />
                Start Kids Daily
              </Link>
              <Link
                to="/about-us"
                className="btn-secondary inline-flex min-h-[48px] items-center justify-center gap-2 px-5"
              >
                About Creative Workshop
              </Link>
            </div>
          </div>
        </motion.section>
      )}

      {isAuthenticated && recentItems.length > 0 && (
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
        >
          <div className="mb-4 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-xl font-bold text-gray-800">
              Recent Creations
            </h2>
            <Link to="/library" className="text-sm font-medium text-primary hover:underline">
              More →
            </Link>
          </div>

          <div className="space-y-3">
            {recentItems.map((item, index) => (
              <motion.div
                key={item.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.6 + index * 0.1 }}
              >
                <RecentCreationCard item={item} onClick={() => navigate(getItemRoute(item))} />
              </motion.div>
            ))}
          </div>
        </motion.section>
      )}

      {isAuthenticated && recentItems.length === 0 && (
        <motion.div
          className="rounded-lg border border-gray-200 bg-white/80 p-6 text-center shadow-sm"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.5 }}
        >
          <p className="text-gray-500">Start creating! Pick a doorway above to begin your first adventure.</p>
        </motion.div>
      )}
    </div>
  )
}

export default HomePage
