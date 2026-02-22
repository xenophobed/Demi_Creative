/**
 * TiltCard Component
 * Interactive 3D card with tilt effects based on mouse position
 * Creates an immersive 2.5D experience
 */

import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion'
import { useRef, type ReactNode, type CSSProperties, type MouseEvent } from 'react'

interface TiltCardProps {
  children: ReactNode
  className?: string
  style?: CSSProperties
  /** Maximum rotation angle in degrees */
  maxTilt?: number
  /** Perspective distance in pixels */
  perspective?: number
  /** Scale on hover */
  hoverScale?: number
  /** Enable glare effect */
  glare?: boolean
  /** Enable glow effect on edges */
  glow?: boolean
  /** Glow color */
  glowColor?: string
  /** Enable shadow that responds to tilt */
  dynamicShadow?: boolean
  /** Spring stiffness for smooth animation */
  springStiffness?: number
  /** Spring damping */
  springDamping?: number
  /** Disable all effects */
  disabled?: boolean
  /** Click handler */
  onClick?: () => void
}

export function TiltCard({
  children,
  className = '',
  style,
  maxTilt = 15,
  perspective = 1000,
  hoverScale = 1.02,
  glare = true,
  glow = false,
  glowColor = 'rgba(255, 107, 107, 0.4)',
  dynamicShadow = true,
  springStiffness = 300,
  springDamping = 30,
  disabled = false,
  onClick,
}: TiltCardProps) {
  const cardRef = useRef<HTMLDivElement>(null)

  // Motion values for tilt
  const rotateX = useMotionValue(0)
  const rotateY = useMotionValue(0)
  const glareX = useMotionValue(50)
  const glareY = useMotionValue(50)
  const glareOpacity = useMotionValue(0)

  // Smooth spring animations
  const springConfig = { stiffness: springStiffness, damping: springDamping }
  const rotateXSpring = useSpring(rotateX, springConfig)
  const rotateYSpring = useSpring(rotateY, springConfig)
  const glareXSpring = useSpring(glareX, springConfig)
  const glareYSpring = useSpring(glareY, springConfig)
  const glareOpacitySpring = useSpring(glareOpacity, springConfig)
  const glareBackground = useTransform(
    [glareXSpring, glareYSpring],
    ([x, y]) => `radial-gradient(circle at ${x}% ${y}%, rgba(255,255,255,0.3) 0%, transparent 50%)`
  )

  // Dynamic shadow based on tilt
  const shadowX = useTransform(rotateYSpring, [-maxTilt, maxTilt], [20, -20])
  const shadowY = useTransform(rotateXSpring, [-maxTilt, maxTilt], [-20, 20])

  const handleMouseMove = (e: MouseEvent<HTMLDivElement>) => {
    if (disabled || !cardRef.current) return

    const rect = cardRef.current.getBoundingClientRect()
    const centerX = rect.left + rect.width / 2
    const centerY = rect.top + rect.height / 2

    // Calculate rotation based on mouse position relative to center
    const mouseX = e.clientX - centerX
    const mouseY = e.clientY - centerY

    // Normalize to -1 to 1 range
    const normalizedX = mouseX / (rect.width / 2)
    const normalizedY = mouseY / (rect.height / 2)

    // Set rotation (inverted for natural feel)
    rotateY.set(normalizedX * maxTilt)
    rotateX.set(-normalizedY * maxTilt)

    // Glare position (percentage)
    const glareXPos = ((e.clientX - rect.left) / rect.width) * 100
    const glareYPos = ((e.clientY - rect.top) / rect.height) * 100
    glareX.set(glareXPos)
    glareY.set(glareYPos)
    glareOpacity.set(0.15)
  }

  const handleMouseLeave = () => {
    rotateX.set(0)
    rotateY.set(0)
    glareOpacity.set(0)
  }

  return (
    <motion.div
      ref={cardRef}
      className={`tilt-card-container ${className}`}
      style={{
        perspective: `${perspective}px`,
        ...style,
      }}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      onClick={onClick}
    >
      <motion.div
        className="tilt-card-inner preserve-3d"
        style={{
          rotateX: rotateXSpring,
          rotateY: rotateYSpring,
          transformStyle: 'preserve-3d',
        }}
        whileHover={disabled ? {} : { scale: hoverScale }}
        transition={{ type: 'spring', stiffness: 400, damping: 25 }}
      >
        {/* Main content */}
        <div className="tilt-card-content relative">
          {children}

          {/* Glare overlay */}
          {glare && !disabled && (
            <motion.div
              className="tilt-card-glare absolute inset-0 pointer-events-none rounded-inherit overflow-hidden"
              style={{
                background: glareBackground,
                opacity: glareOpacitySpring,
              }}
            />
          )}

          {/* Glow effect */}
          {glow && !disabled && (
            <motion.div
              className="tilt-card-glow absolute -inset-1 rounded-inherit pointer-events-none -z-10"
              style={{
                boxShadow: `0 0 30px 10px ${glowColor}`,
                opacity: glareOpacitySpring,
              }}
            />
          )}
        </div>

        {/* Dynamic shadow */}
        {dynamicShadow && !disabled && (
          <motion.div
            className="tilt-card-shadow absolute inset-0 -z-20 rounded-inherit"
            style={{
              x: shadowX,
              y: shadowY,
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
              opacity: 0.3,
            }}
          />
        )}
      </motion.div>
    </motion.div>
  )
}

export default TiltCard
