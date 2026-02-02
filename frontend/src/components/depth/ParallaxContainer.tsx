/**
 * ParallaxContainer Component
 * Provides scroll-based and mouse-based parallax effects for children
 * Creates depth and immersion in the 2.5D interface
 */

import { motion, useScroll, useTransform, useSpring } from 'framer-motion'
import { useRef, type ReactNode, type CSSProperties } from 'react'
import { useStreamVisualizationContext } from '@/providers/StreamVisualizationProvider'

interface ParallaxContainerProps {
  children: ReactNode
  className?: string
  style?: CSSProperties
  /** Parallax speed factor (0 = no parallax, 1 = full scroll speed, -1 = reverse) */
  speed?: number
  /** Enable mouse-based parallax */
  mouseParallax?: boolean
  /** Mouse parallax intensity (pixels of movement) */
  mouseIntensity?: number
  /** Enable scale effect on scroll */
  scaleOnScroll?: boolean
  /** Scale range [min, max] */
  scaleRange?: [number, number]
  /** Enable opacity fade on scroll */
  fadeOnScroll?: boolean
  /** Offset range for scroll effects [start, end] as percentage of viewport */
  scrollRange?: [string, string]
  /** Direction of parallax movement */
  direction?: 'vertical' | 'horizontal' | 'both'
}

export function ParallaxContainer({
  children,
  className = '',
  style,
  speed = 0.5,
  mouseParallax = true,
  mouseIntensity = 20,
  scaleOnScroll = false,
  scaleRange = [1, 1.1],
  fadeOnScroll = false,
  scrollRange = ['start start', 'end start'],
  direction = 'vertical',
}: ParallaxContainerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const { mousePosition, prefersReducedMotion } = useStreamVisualizationContext()

  // Scroll-based parallax
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: scrollRange as ["start start", "end start"],
  })

  // Calculate scroll-based transforms
  const yParallax = useTransform(
    scrollYProgress,
    [0, 1],
    direction !== 'horizontal' ? [0, 100 * speed] : [0, 0]
  )
  const xParallax = useTransform(
    scrollYProgress,
    [0, 1],
    direction !== 'vertical' ? [0, 100 * speed] : [0, 0]
  )
  const scale = useTransform(scrollYProgress, [0, 1], scaleRange)
  const opacity = useTransform(scrollYProgress, [0, 0.5, 1], [1, 1, fadeOnScroll ? 0 : 1])

  // Spring smooth the scroll transforms
  const ySpring = useSpring(yParallax, { stiffness: 100, damping: 30 })
  const xSpring = useSpring(xParallax, { stiffness: 100, damping: 30 })

  // Mouse-based parallax with springs
  const mouseXSpring = useSpring(mousePosition.x, { stiffness: 100, damping: 30 })
  const mouseYSpring = useSpring(mousePosition.y, { stiffness: 100, damping: 30 })

  const mouseX = useTransform(
    mouseXSpring,
    [-1, 1],
    mouseParallax ? [-mouseIntensity, mouseIntensity] : [0, 0]
  )
  const mouseY = useTransform(
    mouseYSpring,
    [-1, 1],
    mouseParallax ? [-mouseIntensity, mouseIntensity] : [0, 0]
  )

  // If reduced motion, render without effects
  if (prefersReducedMotion) {
    return (
      <div ref={containerRef} className={className} style={style}>
        {children}
      </div>
    )
  }

  return (
    <div ref={containerRef} className={`parallax-wrapper ${className}`} style={style}>
      <motion.div
        className="parallax-content preserve-3d gpu-accelerated w-full h-full"
        style={{
          x: direction !== 'vertical' ? xSpring : mouseX,
          y: direction !== 'horizontal' ? ySpring : mouseY,
          scale: scaleOnScroll ? scale : 1,
          opacity: fadeOnScroll ? opacity : 1,
        }}
      >
        {children}
      </motion.div>
    </div>
  )
}

/**
 * FloatingElement - Individual floating element with its own parallax
 */
interface FloatingElementProps {
  children: ReactNode
  className?: string
  style?: CSSProperties
  /** Depth layer (affects parallax intensity) */
  depth?: 'near' | 'mid' | 'far'
  /** Custom float animation */
  float?: boolean
  /** Float animation duration */
  floatDuration?: number
  /** Float distance in pixels */
  floatDistance?: number
  /** Rotation during float */
  floatRotation?: number
  /** Delay for staggered animations */
  delay?: number
}

export function FloatingElement({
  children,
  className = '',
  style,
  depth = 'mid',
  float = true,
  floatDuration = 3,
  floatDistance = 10,
  floatRotation = 5,
  delay = 0,
}: FloatingElementProps) {
  const { mousePosition, prefersReducedMotion } = useStreamVisualizationContext()

  // Depth-based parallax intensity
  const depthConfig = {
    near: { parallax: 0.8, scale: 1 },
    mid: { parallax: 0.5, scale: 1 },
    far: { parallax: 0.2, scale: 0.95 },
  }

  const config = depthConfig[depth]
  const parallaxAmount = 15 * config.parallax

  const mouseXSpring = useSpring(mousePosition.x, { stiffness: 80, damping: 25 })
  const mouseYSpring = useSpring(mousePosition.y, { stiffness: 80, damping: 25 })

  const x = useTransform(mouseXSpring, [-1, 1], [-parallaxAmount, parallaxAmount])
  const y = useTransform(mouseYSpring, [-1, 1], [-parallaxAmount, parallaxAmount])

  if (prefersReducedMotion) {
    return (
      <div className={className} style={style}>
        {children}
      </div>
    )
  }

  return (
    <motion.div
      className={`floating-element preserve-3d ${className}`}
      style={{
        x,
        y,
        scale: config.scale,
        ...style,
      }}
      animate={
        float
          ? {
              y: [0, -floatDistance, 0],
              rotate: [0, floatRotation, -floatRotation, 0],
            }
          : {}
      }
      transition={{
        duration: floatDuration,
        repeat: Infinity,
        delay,
        ease: 'easeInOut',
      }}
    >
      {children}
    </motion.div>
  )
}

export default ParallaxContainer
