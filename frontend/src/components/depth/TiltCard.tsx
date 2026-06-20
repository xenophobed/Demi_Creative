/**
 * TiltCard Component
 *
 * Previously a mouse-tracking 3D tilt card. As of #735 it is a calm, CSS-driven
 * micro-interaction: the card lifts and scales slightly on hover with a soft
 * shadow — no perspective, no per-frame rotation following the cursor.
 *
 * The original prop surface is kept so existing call sites compile unchanged;
 * the 3D-specific props (maxTilt, perspective, glare, glow, dynamicShadow,
 * spring*) are accepted but intentionally inert.
 */

import { motion } from 'framer-motion'
import type { ReactNode, CSSProperties } from 'react'

interface TiltCardProps {
  children: ReactNode
  className?: string
  style?: CSSProperties
  /** @deprecated 3D tilt removed in #735 — kept for API compatibility */
  maxTilt?: number
  /** @deprecated 3D perspective removed in #735 — kept for API compatibility */
  perspective?: number
  /** Scale on hover */
  hoverScale?: number
  /** @deprecated glare overlay removed in #735 — kept for API compatibility */
  glare?: boolean
  /** @deprecated glow overlay removed in #735 — kept for API compatibility */
  glow?: boolean
  /** @deprecated glow color removed in #735 — kept for API compatibility */
  glowColor?: string
  /** @deprecated dynamic shadow removed in #735 — kept for API compatibility */
  dynamicShadow?: boolean
  /** @deprecated spring stiffness removed in #735 — kept for API compatibility */
  springStiffness?: number
  /** @deprecated spring damping removed in #735 — kept for API compatibility */
  springDamping?: number
  /** Disable the hover lift */
  disabled?: boolean
  /** Click handler */
  onClick?: () => void
}

export function TiltCard({
  children,
  className = '',
  style,
  hoverScale = 1.02,
  disabled = false,
  onClick,
}: TiltCardProps) {
  return (
    <motion.div
      className={`tilt-card-container ${className}`}
      style={style}
      onClick={onClick}
      whileHover={disabled ? undefined : { y: -4, scale: hoverScale }}
      transition={{ type: 'spring', stiffness: 400, damping: 30 }}
    >
      {children}
    </motion.div>
  )
}

export default TiltCard
