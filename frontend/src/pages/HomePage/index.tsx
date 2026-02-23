import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { motion, useSpring, useTransform } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import Button from '@/components/common/Button'
import TiltCard from '@/components/depth/TiltCard'
import { FloatingElement } from '@/components/depth/ParallaxContainer'
import { DepthLayer } from '@/components/depth/DepthLayer'
import { useStreamVisualizationContext } from '@/providers/StreamVisualizationProvider'
import useStoryStore from '@/store/useStoryStore'
import useChildStore from '@/store/useChildStore'
import { storyService } from '@/api/services/storyService'
import { StoryCard } from '@/components/story/StoryDisplay'

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
  const { storyHistory } = useStoryStore()
  const { currentChild, defaultChildId } = useChildStore()
  const { mousePosition, prefersReducedMotion } = useStreamVisualizationContext()

  const childId = currentChild?.child_id || defaultChildId

  // Fetch stories from server (persisted child_id survives refresh)
  const { data: serverStories } = useQuery({
    queryKey: ['child-stories', childId],
    queryFn: () => storyService.getStoryHistory(childId),
    enabled: !!childId,
  })

  // Use server stories, fall back to in-memory store
  const recentStories = (serverStories ?? storyHistory).slice(0, 3)

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
                className="flex flex-col sm:flex-row gap-3 mt-2"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 }}
              >
                <Link to="/upload">
                  <Button
                    size="lg"
                    rightIcon={<span>🖼️</span>}
                    className="shadow-lg hover:shadow-xl transition-shadow w-full sm:w-auto"
                  >
                    Art to Story
                  </Button>
                </Link>
                <Link to="/interactive">
                  <Button
                    size="lg"
                    variant="secondary"
                    rightIcon={<span>🎭</span>}
                    className="shadow-lg hover:shadow-xl transition-shadow w-full sm:w-auto"
                  >
                    Interactive Tales
                  </Button>
                </Link>
                <Link to="/news">
                  <Button
                    size="lg"
                    variant="outline"
                    rightIcon={<span>📰</span>}
                    className="shadow-lg hover:shadow-xl transition-shadow w-full sm:w-auto"
                  >
                    News to Kids
                  </Button>
                </Link>
              </motion.div>
            </div>
          </div>
        </DepthLayer>
      </motion.div>

      {/* Recent Stories */}
      {recentStories.length > 0 && (
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
              Recent Stories
            </h2>
            <Link
              to="/history"
              className="text-primary hover:underline text-sm font-medium"
            >
              View all →
            </Link>
          </div>

          <div className="space-y-3">
            {recentStories.map((story, index) => (
              <motion.div
                key={story.story_id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.6 + index * 0.1 }}
              >
                <StoryCard
                  title={`Story #${story.story_id.slice(0, 6)}`}
                  preview={story.story.text.slice(0, 100) + '...'}
                  createdAt={story.created_at}
                  imageUrl={story.image_url}
                  onClick={() => navigate(`/story/${story.story_id}`)}
                />
              </motion.div>
            ))}
          </div>
        </motion.section>
      )}

      {/* Empty state with floating animation */}
      {recentStories.length === 0 && (
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
            📝
          </motion.div>
          <p className="text-gray-500">
            No stories yet, upload your first artwork to get started!
          </p>
        </motion.div>
      )}

      {/* Tips section with depth */}
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
              <div>
                <p className="font-semibold text-gray-800 mb-1">Tips</p>
                <p className="text-gray-600 text-sm">
                  The more colorful and detailed your artwork, the more magical your
                  story! Try drawing your favorite animals, characters, or imaginary
                  worlds~
                </p>
              </div>
            </div>
          </div>
        </TiltCard>
      </motion.div>
    </div>
  )
}

export default HomePage
