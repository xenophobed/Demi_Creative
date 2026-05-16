import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion, AnimatePresence, useSpring, useTransform } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import FeatureTile from '@/components/common/FeatureTile'
import TiltCard from '@/components/depth/TiltCard'
import { FloatingElement } from '@/components/depth/ParallaxContainer'
import { DepthLayer } from '@/components/depth/DepthLayer'
import { useStreamVisualizationContext } from '@/providers/StreamVisualizationProvider'
import useAuthStore from '@/store/useAuthStore'
import useDailyTaskStore from '@/store/useDailyTaskStore'
import { libraryService, type LibraryItem } from '@/api/services/libraryService'
import { StoryCard } from '@/components/story/StoryDisplay'
import InspirationDaily from '@/components/daily/InspirationDaily'
import { fetchDailyInspiration, toDailyContent } from '@/api/services/inspirationService'
import TearAnimation from '@/components/daily/TearAnimation'
import StarFlyAnimation from '@/components/daily/StarFlyAnimation'
import { useNavRef } from '@/contexts/NavRefContext'

const TIPS = [
  { icon: '🎨', tip: 'The more colorful and detailed your artwork, the more magical your story! Try drawing your favorite animals, characters, or imaginary worlds~' },
  { icon: '🎭', tip: 'In interactive tales, every choice you make leads to a different adventure! Try being brave and see what happens~' },
  { icon: '📰', tip: 'Kids News turns real-world events into fun, easy-to-understand stories! Pick a topic you are curious about~' },
]

function getItemRoute(item: LibraryItem): string {
  switch (item.type) {
    case 'art-story': return `/story/${item.id}`
    case 'interactive': return `/interactive?session=${item.id}`
    case 'morning-show': return `/kids-daily/${item.id}`
    default: return `/kids-daily/${item.id}`
  }
}

interface StarPosition {
  top: number
  left: number
  duration: number
  emoji: string
}

function FloatingStar({
  star,
  index,
  mouseXSpring,
  mouseYSpring,
}: {
  star: StarPosition
  index: number
  mouseXSpring: ReturnType<typeof useSpring>
  mouseYSpring: ReturnType<typeof useSpring>
}) {
  const x = useTransform(mouseXSpring, [-1, 1], [-15 * (1 - index * 0.1), 15 * (1 - index * 0.1)])
  const y = useTransform(mouseYSpring, [-1, 1], [-10 * (1 - index * 0.1), 10 * (1 - index * 0.1)])

  return (
    <motion.span
      className="absolute text-2xl pointer-events-none select-none"
      style={{
        top: `${star.top}%`,
        left: `${star.left}%`,
        x,
        y,
      }}
      animate={{
        y: [0, -15, 0],
        opacity: [0.3, 0.8, 0.3],
        scale: [0.8, 1.1, 0.8],
        rotate: [0, 10, -10, 0],
      }}
      transition={{
        duration: star.duration,
        repeat: Infinity,
        delay: index * 0.2,
      }}
    >
      {star.emoji}
    </motion.span>
  )
}

function HomePage() {
  const navigate = useNavigate()
  const { isAuthenticated, user } = useAuthStore()
  const { mousePosition, prefersReducedMotion } = useStreamVisualizationContext()

  // Daily task system
  const canClaim = useDailyTaskStore((s) => s.canClaimToday())
  const claimStar = useDailyTaskStore((s) => s.claimStar)
  const lastClaimTimestamp = useDailyTaskStore((s) => s.lastClaimTimestamp)
  const { profileAvatarRef } = useNavRef()
  const newspaperRef = useRef<HTMLDivElement>(null)
  const [starFlying, setStarFlying] = useState(false)

  // Hide newspaper 5 minutes after claiming today
  const HIDE_AFTER_MS = 5 * 60 * 1000
  const [newspaperVisible, setNewspaperVisible] = useState(true)

  useEffect(() => {
    if (canClaim) {
      // New day — show newspaper
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

    // Still within 5 min window — show claimed state, then auto-hide
    setNewspaperVisible(true)
    const timer = setTimeout(() => setNewspaperVisible(false), HIDE_AFTER_MS - elapsed)
    return () => clearTimeout(timer)
  }, [canClaim, lastClaimTimestamp, HIDE_AFTER_MS])

  const handleTearComplete = useCallback(() => {
    setStarFlying(true)
  }, [])

  const handleStarArrived = useCallback(() => {
    setStarFlying(false)
    claimStar()
  }, [claimStar])

  // Fetch latest 3 items from unified library API (all content types)
  const currentUserId = user?.user_id ?? 'anonymous'

  const { data: libraryData } = useQuery({
    queryKey: ['homepage-recent', currentUserId],
    queryFn: () => libraryService.getLibrary({ sort: 'newest', limit: 3 }),
    enabled: isAuthenticated,
  })
  const recentItems = libraryData?.items ?? []

  // Fetch daily inspiration from API (falls back to seed bank inside component)
  const { data: inspirationContent } = useQuery({
    queryKey: ['inspiration-daily'],
    queryFn: async () => {
      const resp = await fetchDailyInspiration('6-8')
      return resp ? toDailyContent(resp) : null
    },
    staleTime: 1000 * 60 * 60, // 1 hour
    retry: false,
  })

  // Rotating tips
  const [tipIndex, setTipIndex] = useState(0)
  useEffect(() => {
    const timer = setInterval(() => {
      setTipIndex((i) => (i + 1) % TIPS.length)
    }, 5000)
    return () => clearInterval(timer)
  }, [])

  // Mouse springs for parallax
  const mouseXSpring = useSpring(mousePosition.x, { stiffness: 80, damping: 25 })
  const mouseYSpring = useSpring(mousePosition.y, { stiffness: 80, damping: 25 })

  // Memoize star positions to prevent recalculation on every render
  const starPositions = useMemo(
      () =>
        [...Array(8)].map((_, i) => ({
          top: 15 + Math.random() * 70,
          left: 5 + Math.random() * 90,
          duration: 2 + Math.random() * 2,
          emoji: ['⭐', '✨', '🌟', '💫'][i % 4],
        })),
    []
  )

  return (
    <div className="space-y-8 perspective-1500">
      {/* Star fly animation — flies from newspaper to profile avatar in nav */}
      <StarFlyAnimation
        active={starFlying}
        fromRef={newspaperRef}
        toRef={profileAvatarRef}
        onComplete={handleStarArrived}
      />

      {/* Hero Banner with 2.5D depth layers */}
      <motion.div
        className="hero-banner relative overflow-hidden rounded-card preserve-3d"
        initial={{ opacity: 0, y: 30, rotateX: 10 }}
        animate={{ opacity: 1, y: 0, rotateX: 0 }}
        transition={{ duration: 0.6, type: 'spring', stiffness: 100 }}
      >
        {/* Background gradient layer - moves slower */}
        <DepthLayer config={{ layer: 'background', parallaxFactor: 0.3 }}>
          <div className="absolute inset-0 bg-gradient-to-br from-primary/20 via-secondary/10 to-accent/20" />
        </DepthLayer>

        {/* Floating background decorations */}
        <div className="absolute inset-0 pointer-events-none">
          <FloatingElement depth="far" delay={0} className="absolute top-4 right-8">
            <span className="text-6xl opacity-20">🎨</span>
          </FloatingElement>
          <FloatingElement depth="far" delay={0.5} className="absolute bottom-8 left-4">
            <span className="text-4xl opacity-20">✨</span>
          </FloatingElement>
          <FloatingElement depth="mid" delay={1} className="absolute top-1/2 right-4">
            <span className="text-3xl opacity-15">🌈</span>
          </FloatingElement>
        </div>

        {/* Floating stars with parallax */}
        {!prefersReducedMotion &&
          starPositions.map((star, i) => (
            <FloatingStar
              key={i}
              star={star}
              index={i}
              mouseXSpring={mouseXSpring}
              mouseYSpring={mouseYSpring}
            />
          ))}

        {/* Main content layer - moves faster (foreground) */}
        <DepthLayer config={{ layer: 'foreground', parallaxFactor: 0.7 }}>
          <div className="relative z-10 flex flex-col md:flex-row items-center gap-6 p-8 md:p-12">
            {/* Mascot with 3D hover effect */}
            <motion.div
              className="mascot-container preserve-3d"
              style={{
                rotateY: useTransform(mouseXSpring, [-1, 1], [-15, 15]),
                rotateX: useTransform(mouseYSpring, [-1, 1], [10, -10]),
              }}
              animate={{
                y: [0, -15, 0],
              }}
              transition={{
                duration: 3,
                repeat: Infinity,
                ease: 'easeInOut',
              }}
            >
              <motion.span
                className="text-8xl block"
                animate={{
                  rotate: [0, 5, -5, 0],
                  scale: [1, 1.05, 1],
                }}
                transition={{
                  duration: 4,
                  repeat: Infinity,
                  ease: 'easeInOut',
                }}
                whileHover={{
                  scale: 1.2,
                  rotate: 15,
                  transition: { duration: 0.3 },
                }}
              >
                🎪
              </motion.span>
              {/* Shadow under mascot */}
              <motion.div
                className="absolute -bottom-2 left-1/2 -translate-x-1/2 w-16 h-4 bg-black/10 rounded-full blur-sm"
                animate={{
                  scale: [1, 0.9, 1],
                  opacity: [0.3, 0.2, 0.3],
                }}
                transition={{
                  duration: 3,
                  repeat: Infinity,
                  ease: 'easeInOut',
                }}
              />
            </motion.div>

            <div className="text-center md:text-left">
              <motion.h1
                className="text-3xl md:text-4xl font-bold text-gray-800 mb-3"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.2 }}
              >
                Welcome to{' '}
                <motion.span
                  className="text-gradient inline-block"
                  animate={{
                    backgroundPosition: ['0% 50%', '100% 50%', '0% 50%'],
                  }}
                  transition={{
                    duration: 5,
                    repeat: Infinity,
                  }}
                  style={{
                    backgroundSize: '200% 200%',
                  }}
                >
                  Creative Workshop
                </motion.span>
              </motion.h1>
              <motion.p
                className="text-lg text-gray-600 mb-4"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.3 }}
              >
                Transform your artwork into magical stories!
              </motion.p>
              <motion.div
                className="grid grid-cols-3 gap-3 mt-2 w-full"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 }}
              >
                <FeatureTile
                  to="/upload"
                  icon="🖼️"
                  label="Art to Story"
                  accentColor="primary"
                  description="Draw & narrate"
                />
                <FeatureTile
                  to="/interactive"
                  icon="🎭"
                  label="Interactive Tales"
                  accentColor="secondary"
                  description="Choose your path"
                />
                <FeatureTile
                  to="/kids-daily"
                  icon="📰"
                  label="Kids Daily"
                  accentColor="accent"
                  description="World made simple"
                />
              </motion.div>
            </div>
          </div>
        </DepthLayer>
      </motion.div>

      {/* Daily Inspiration — newspaper tear card */}
      <AnimatePresence>
        {newspaperVisible && (
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10, transition: { duration: 0.4 } }}
            transition={{ delay: 0.45 }}
          >
            <div ref={newspaperRef}>
              <TearAnimation onTearComplete={handleTearComplete} disabled={!canClaim}>
                <InspirationDaily content={inspirationContent ?? undefined} isAuthenticated={isAuthenticated} />
              </TearAnimation>
            </div>
          </motion.section>
        )}
      </AnimatePresence>

      {/* Recent Creations */}
      {recentItems.length > 0 && (
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
        >
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-gray-800 flex items-center gap-2">
              <FloatingElement depth="near" float floatDistance={5}>
                <span>📖</span>
              </FloatingElement>
              Recent Creations
            </h2>
            <Link
              to="/library"
              className="text-primary hover:underline text-sm font-medium"
            >
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
                <StoryCard
                  title={item.title}
                  preview={item.preview}
                  createdAt={item.created_at}
                  imageUrl={item.image_url}
                  onClick={() => navigate(getItemRoute(item))}
                  className="relative"
                />
              </motion.div>
            ))}
          </div>
        </motion.section>
      )}

      {/* Empty state */}
      {recentItems.length === 0 && (
        <motion.div
          className="text-center py-12 preserve-3d"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.5 }}
        >
          <motion.div
            className="text-6xl mb-4"
            animate={{
              y: [0, -10, 0],
              rotate: [0, 5, -5, 0],
            }}
            transition={{
              duration: 3,
              repeat: Infinity,
              ease: 'easeInOut',
            }}
          >
            🌟
          </motion.div>
          <p className="text-gray-500">
            Start creating! Pick a feature above to begin your first adventure.
          </p>
        </motion.div>
      )}

      {/* Rotating tips section */}
      <motion.div
        className="relative overflow-hidden"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.7 }}
      >
        <TiltCard
          maxTilt={8}
          glare
          glow
          glowColor="rgba(255, 230, 109, 0.3)"
          className="w-full"
        >
          <div className="bg-accent/20 rounded-card p-4 border border-accent/30">
            <div className="flex items-start gap-3">
              <FloatingElement depth="near" float floatDistance={8}>
                <span className="text-2xl">💡</span>
              </FloatingElement>
              <div className="flex-1 min-h-[3rem]">
                <p className="font-semibold text-gray-800 mb-1">Tips</p>
                <AnimatePresence mode="wait">
                  <motion.div
                    key={tipIndex}
                    className="flex items-start gap-2"
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.3 }}
                  >
                    <span className="text-lg flex-shrink-0">{TIPS[tipIndex].icon}</span>
                    <p className="text-gray-600 text-sm">{TIPS[tipIndex].tip}</p>
                  </motion.div>
                </AnimatePresence>
              </div>
            </div>
          </div>
        </TiltCard>
      </motion.div>

    </div>
  )
}

export default HomePage
