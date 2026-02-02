import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion'
import { useRef, type ReactNode, type MouseEvent } from 'react'
import { useStreamVisualizationContext } from '@/providers/StreamVisualizationProvider'
import { FloatingElement } from '@/components/depth/ParallaxContainer'

interface BookContainerProps {
  children: ReactNode
  className?: string
  /** Enable 3D tilt effect on mouse move */
  enableTilt?: boolean
  /** Enable page turn reveal animation */
  pageReveal?: boolean
}

/**
 * BookContainer - Immersive storybook container with 2.5D effects
 *
 * Creates a book-like experience with:
 * - Soft paper texture background with depth layers
 * - 3D perspective tilt based on mouse position
 * - Book spine shadow effect with parallax
 * - Floating decorative elements
 * - Page turn reveal animation
 */
function BookContainer({
  children,
  className = '',
  enableTilt = true,
  pageReveal = true,
}: BookContainerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const { mousePosition, prefersReducedMotion } = useStreamVisualizationContext()

  // Tilt motion values
  const rotateX = useMotionValue(0)
  const rotateY = useMotionValue(0)

  // Spring smoothing
  const springConfig = { stiffness: 150, damping: 20 }
  const rotateXSpring = useSpring(rotateX, springConfig)
  const rotateYSpring = useSpring(rotateY, springConfig)

  // Mouse parallax for depth layers
  const mouseXSpring = useSpring(mousePosition.x, { stiffness: 100, damping: 30 })
  const mouseYSpring = useSpring(mousePosition.y, { stiffness: 100, damping: 30 })

  // Subtle parallax movement for book
  const bookX = useTransform(mouseXSpring, [-1, 1], [-5, 5])
  const bookY = useTransform(mouseYSpring, [-1, 1], [-3, 3])

  // Dynamic shadow based on tilt
  const shadowX = useTransform(rotateYSpring, [-8, 8], [15, -15])
  const shadowY = useTransform(rotateXSpring, [-8, 8], [-10, 10])
  const shadowBlur = useTransform(
    [rotateXSpring, rotateYSpring],
    ([rx, ry]: number[]) => 30 + Math.abs(rx) + Math.abs(ry)
  )

  const handleMouseMove = (e: MouseEvent<HTMLDivElement>) => {
    if (prefersReducedMotion || !enableTilt || !containerRef.current) return

    const rect = containerRef.current.getBoundingClientRect()
    const centerX = rect.left + rect.width / 2
    const centerY = rect.top + rect.height / 2

    const mouseX = e.clientX - centerX
    const mouseY = e.clientY - centerY

    const normalizedX = mouseX / (rect.width / 2)
    const normalizedY = mouseY / (rect.height / 2)

    // Subtle tilt (max 8 degrees)
    rotateY.set(normalizedX * 8)
    rotateX.set(-normalizedY * 4)
  }

  const handleMouseLeave = () => {
    rotateX.set(0)
    rotateY.set(0)
  }

  // Page reveal animation variants
  const pageRevealVariants = {
    hidden: {
      rotateY: -90,
      opacity: 0,
      transformOrigin: 'left center',
    },
    visible: {
      rotateY: 0,
      opacity: 1,
      transition: {
        type: 'spring',
        stiffness: 100,
        damping: 20,
        delay: 0.2,
      },
    },
  }

  return (
    <motion.div
      ref={containerRef}
      className={`book-container-wrapper perspective-1000 ${className}`}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6 }}
    >
      {/* Floating decorative elements - background layer */}
      <div className="book-decorations absolute inset-0 pointer-events-none overflow-hidden">
        <FloatingElement depth="far" delay={0} className="absolute top-4 left-4">
          <span className="text-3xl opacity-20">📖</span>
        </FloatingElement>
        <FloatingElement depth="far" delay={0.5} className="absolute top-8 right-8">
          <span className="text-2xl opacity-15">✨</span>
        </FloatingElement>
        <FloatingElement depth="far" delay={1} className="absolute bottom-12 left-8">
          <span className="text-2xl opacity-15">🌟</span>
        </FloatingElement>
        <FloatingElement depth="mid" delay={1.5} className="absolute bottom-4 right-4">
          <span className="text-xl opacity-20">📚</span>
        </FloatingElement>
      </div>

      {/* Main book with 3D transforms */}
      <motion.div
        className="book-container preserve-3d"
        style={{
          rotateX: prefersReducedMotion ? 0 : rotateXSpring,
          rotateY: prefersReducedMotion ? 0 : rotateYSpring,
          x: prefersReducedMotion ? 0 : bookX,
          y: prefersReducedMotion ? 0 : bookY,
        }}
      >
        {/* Dynamic shadow layer */}
        {!prefersReducedMotion && (
          <motion.div
            className="book-shadow absolute inset-0 -z-10 rounded-inherit"
            style={{
              x: shadowX,
              y: shadowY,
              filter: useTransform(shadowBlur, (blur) => `blur(${blur}px)`),
              background: 'rgba(0, 0, 0, 0.15)',
              transform: 'translateZ(-50px)',
            }}
          />
        )}

        {/* Book spine effect - left edge shadow */}
        <div className="book-spine absolute left-0 top-0 bottom-0 w-8 pointer-events-none z-10">
          <div className="absolute inset-0 bg-gradient-to-r from-black/10 to-transparent" />
          <div className="absolute left-1 top-0 bottom-0 w-[2px] bg-gradient-to-r from-black/20 to-transparent" />
        </div>

        {/* Page content with optional reveal animation */}
        <motion.div
          className="book-content relative"
          variants={pageReveal && !prefersReducedMotion ? pageRevealVariants : undefined}
          initial={pageReveal && !prefersReducedMotion ? 'hidden' : undefined}
          animate={pageReveal && !prefersReducedMotion ? 'visible' : undefined}
          style={{ transformStyle: 'preserve-3d' }}
        >
          {children}

          {/* Page curl decoration (bottom right) */}
          <div className="page-curl-effect absolute bottom-0 right-0 w-16 h-16 pointer-events-none overflow-hidden">
            <motion.div
              className="absolute bottom-0 right-0 w-24 h-24"
              style={{
                background: 'linear-gradient(135deg, transparent 50%, #F5EDE0 50%, #E8DFD0 100%)',
                transformOrigin: 'bottom right',
              }}
              animate={{
                rotate: [0, 2, 0],
                scale: [1, 1.02, 1],
              }}
              transition={{
                duration: 4,
                repeat: Infinity,
                ease: 'easeInOut',
              }}
            />
          </div>
        </motion.div>

        {/* Glare effect on hover */}
        {!prefersReducedMotion && enableTilt && (
          <motion.div
            className="book-glare absolute inset-0 pointer-events-none rounded-inherit overflow-hidden"
            style={{
              background: useTransform(
                [mouseXSpring, mouseYSpring],
                ([x, y]: number[]) => {
                  const glareX = ((x + 1) / 2) * 100
                  const glareY = ((y + 1) / 2) * 100
                  return `radial-gradient(circle at ${glareX}% ${glareY}%, rgba(255,255,255,0.08) 0%, transparent 50%)`
                }
              ),
            }}
          />
        )}
      </motion.div>
    </motion.div>
  )
}

export default BookContainer
