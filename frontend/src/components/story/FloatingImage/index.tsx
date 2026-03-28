import { useState, type ReactNode } from 'react'
import { motion } from 'framer-motion'

interface FloatingImageProps {
  src: string
  alt?: string
  caption?: string
  className?: string
  children?: ReactNode
}

/**
 * FloatingImage - Storybook illustration style
 *
 * Clean, elegant image presentation that feels like an illustration
 * in a children's book. No gimmicky animations — just a beautiful
 * rounded image with a soft border and gentle fade-in.
 */
function FloatingImage({
  src,
  alt = 'Your artwork',
  caption,
  className = '',
  children,
}: FloatingImageProps) {
  const [hasError, setHasError] = useState(false)

  return (
    <motion.figure
      className={`floating-artwork ${className}`}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.2 }}
    >
      <div className="floating-artwork-frame">
        {hasError ? (
          <div className="floating-artwork-image floating-artwork-fallback">
            <span className="text-4xl">🖼️</span>
          </div>
        ) : (
          <img
            src={src}
            alt={alt}
            className="floating-artwork-image"
            loading="eager"
            onError={() => setHasError(true)}
          />
        )}
      </div>

      {children}

      {caption && (
        <figcaption className="floating-artwork-caption">
          {caption}
        </figcaption>
      )}
    </motion.figure>
  )
}

export default FloatingImage
