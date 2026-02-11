import { useState } from 'react'
import { motion, useSpring, useTransform } from 'framer-motion'
import { useStreamVisualizationContext } from '@/providers/StreamVisualizationProvider'

interface FloatingImageProps {
  src: string
  alt?: string
  caption?: string
  className?: string
  /** Enable parallax movement based on mouse */
  parallax?: boolean
  /** Parallax intensity in pixels */
  parallaxIntensity?: number
  /** Enable 3D tilt effect */
  tilt?: boolean
  /** Enable floating animation */
  float?: boolean
}

/**
 * FloatingImage - Polaroid-style floating image with 2.5D parallax effects
 *
 * Features:
 * - Mouse-based parallax movement (appears to float in 3D space)
 * - Subtle 3D tilt based on mouse position
 * - CSS float for text wrapping (desktop)
 * - Polaroid-style frame with dynamic shadow
 * - Gentle floating animation
 */
function FloatingImage({
  src,
  alt = 'Your artwork',
  caption = 'Your artwork',
  className = '',
  parallax = true,
  parallaxIntensity = 25,
  tilt = true,
  float = true,
}: FloatingImageProps) {
  const [hasError, setHasError] = useState(false)
  const { mousePosition, prefersReducedMotion } = useStreamVisualizationContext()

  // Spring smoothed mouse position
  const springConfig = { stiffness: 100, damping: 25 }
  const mouseXSpring = useSpring(mousePosition.x, springConfig)
  const mouseYSpring = useSpring(mousePosition.y, springConfig)

  // Parallax movement
  const x = useTransform(
    mouseXSpring,
    [-1, 1],
    parallax ? [-parallaxIntensity, parallaxIntensity] : [0, 0]
  )
  const y = useTransform(
    mouseYSpring,
    [-1, 1],
    parallax ? [-parallaxIntensity * 0.6, parallaxIntensity * 0.6] : [0, 0]
  )

  // 3D tilt
  const rotateX = useTransform(mouseYSpring, [-1, 1], tilt ? [8, -8] : [0, 0])
  const rotateY = useTransform(mouseXSpring, [-1, 1], tilt ? [-8, 8] : [0, 0])

  // Dynamic shadow based on tilt
  const shadowX = useTransform(mouseXSpring, [-1, 1], [10, -10])
  const shadowY = useTransform(mouseYSpring, [-1, 1], [-5, 15])

  // Image scale based on mouse (depth effect)
  const imageScale = useTransform(
    [mouseXSpring, mouseYSpring],
    ([mx, my]: number[]) =>
      prefersReducedMotion ? 1 : 1 + (Math.abs(mx) + Math.abs(my)) * 0.02
  )

  // Glare overlay gradient
  const glareBackground = useTransform(
    [mouseXSpring, mouseYSpring],
    ([mx, my]: number[]) => {
      const glareX = ((mx + 1) / 2) * 100
      const glareY = ((my + 1) / 2) * 100
      return `radial-gradient(circle at ${glareX}% ${glareY}%, rgba(255,255,255,0.2) 0%, transparent 50%)`
    }
  )

  // Float animation variants
  const floatAnimation = float && !prefersReducedMotion
    ? {
        y: [0, -8, 0],
        rotate: [-1, 1, -1],
      }
    : {}

  const floatTransition = float && !prefersReducedMotion
    ? {
        duration: 4,
        repeat: Infinity,
        ease: 'easeInOut',
      }
    : {}

  return (
    <motion.figure
      className={`floating-artwork perspective-800 ${className}`}
      initial={{ opacity: 0, x: -30, rotateY: -15 }}
      animate={{ opacity: 1, x: 0, rotateY: 0 }}
      transition={{ duration: 0.6, delay: 0.2, type: 'spring', stiffness: 100 }}
    >
      <motion.div
        className="floating-artwork-wrapper preserve-3d"
        style={{
          x: prefersReducedMotion ? 0 : x,
          y: prefersReducedMotion ? 0 : y,
          rotateX: prefersReducedMotion ? 0 : rotateX,
          rotateY: prefersReducedMotion ? 0 : rotateY,
        }}
        animate={floatAnimation}
        transition={floatTransition}
        whileHover={
          prefersReducedMotion
            ? {}
            : {
                scale: 1.05,
                rotateY: 5,
                transition: { duration: 0.3 },
              }
        }
      >
        {/* Dynamic shadow */}
        {!prefersReducedMotion && (
          <motion.div
            className="floating-artwork-shadow absolute inset-0 -z-10"
            style={{
              x: shadowX,
              y: shadowY,
              background: 'rgba(0, 0, 0, 0.2)',
              filter: 'blur(20px)',
              transform: 'translateZ(-30px) scale(0.9)',
              borderRadius: '8px',
            }}
          />
        )}

        {/* Polaroid-style frame */}
        <div className="floating-artwork-frame">
          {/* Image container with depth effect */}
          <div className="floating-artwork-image-container relative overflow-hidden rounded">
            {hasError ? (
              <div
                className="floating-artwork-image flex flex-col items-center justify-center gap-2 text-center"
                style={{
                  background: 'linear-gradient(135deg, #f0e6ff 0%, #e0f0ff 100%)',
                  aspectRatio: '1',
                }}
              >
                <span className="text-3xl">🖼️</span>
                <span className="text-sm text-gray-500">Image unavailable</span>
              </div>
            ) : (
              <>
                <motion.img
                  src={src}
                  alt={alt}
                  className="floating-artwork-image"
                  loading="eager"
                  onError={() => setHasError(true)}
                  style={{
                    scale: imageScale,
                  }}
                />

                {/* Shine/glare overlay */}
                {!prefersReducedMotion && (
                  <motion.div
                    className="absolute inset-0 pointer-events-none"
                    style={{
                      background: glareBackground,
                    }}
                  />
                )}
              </>
            )}
          </div>
        </div>

        {/* Caption with floating effect */}
        <motion.figcaption
          className="floating-artwork-caption"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
        >
          <motion.span
            className="caption-icon"
            animate={
              prefersReducedMotion
                ? {}
                : {
                    rotate: [0, 10, -10, 0],
                    scale: [1, 1.1, 1],
                  }
            }
            transition={{
              duration: 3,
              repeat: Infinity,
              delay: 1,
            }}
          >
            🎨
          </motion.span>
          <span className="caption-text">{caption}</span>
        </motion.figcaption>

        {/* Decorative corner sparkles */}
        {!prefersReducedMotion && (
          <>
            <motion.span
              className="absolute -top-2 -right-2 text-lg pointer-events-none"
              animate={{
                opacity: [0.5, 1, 0.5],
                scale: [0.8, 1, 0.8],
                rotate: [0, 15, 0],
              }}
              transition={{ duration: 2, repeat: Infinity }}
            >
              ✨
            </motion.span>
            <motion.span
              className="absolute -bottom-1 -left-1 text-sm pointer-events-none"
              animate={{
                opacity: [0.3, 0.7, 0.3],
                scale: [0.9, 1.1, 0.9],
              }}
              transition={{ duration: 2.5, repeat: Infinity, delay: 0.5 }}
            >
              ⭐
            </motion.span>
          </>
        )}
      </motion.div>
    </motion.figure>
  )
}

export default FloatingImage
