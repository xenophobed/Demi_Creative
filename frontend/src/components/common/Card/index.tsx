import { motion, HTMLMotionProps } from 'framer-motion'
import { forwardRef, useMemo } from 'react'
import { useTilt } from '@/hooks/useParallax'
import type { TiltConfig } from '@/types/streaming'

export interface CardProps extends Omit<HTMLMotionProps<'div'>, 'ref'> {
  variant?: 'default' | 'elevated' | 'outlined' | 'colorful'
  colorScheme?: 'primary' | 'secondary' | 'accent'
  hover?: boolean
  padding?: 'none' | 'sm' | 'md' | 'lg'
  // 2.5D depth props
  enableTilt?: boolean
  tiltConfig?: Partial<TiltConfig>
  depth?: 'flat' | 'raised' | 'floating'
}

const Card = forwardRef<HTMLDivElement, CardProps>(
  (
    {
      variant = 'default',
      colorScheme = 'primary',
      hover = true,
      padding = 'md',
      enableTilt = false,
      tiltConfig,
      depth = 'flat',
      className = '',
      children,
      style,
      ...props
    },
    ref
  ) => {
    // Tilt effect hook
    const tilt = useTilt(tiltConfig)

    const baseStyles = 'rounded-card overflow-hidden'

    const variants = {
      default: 'bg-white shadow-card',
      elevated: 'bg-white shadow-lg',
      outlined: 'bg-white border-2 border-gray-200',
      colorful: getColorfulStyles(colorScheme),
    }

    const paddings = {
      none: '',
      sm: 'p-4',
      md: 'p-6',
      lg: 'p-8',
    }

    // Depth-specific styling
    const depthStyles = useMemo(() => {
      switch (depth) {
        case 'raised':
          return {
            boxShadow: '0 8px 30px rgba(0, 0, 0, 0.08)',
            transform: 'translateZ(10px)',
          }
        case 'floating':
          return {
            boxShadow: '0 15px 40px rgba(0, 0, 0, 0.1)',
            transform: 'translateZ(20px)',
          }
        default:
          return {}
      }
    }, [depth])

    const hoverAnimation = hover
      ? {
          whileHover: { y: -4, boxShadow: '0 12px 40px rgba(0, 0, 0, 0.12)' },
          transition: { duration: 0.2 },
        }
      : {}

    // Apply tilt if enabled
    const tiltStyle = enableTilt && tilt.isEnabled
      ? {
          rotateX: tilt.rotateX,
          rotateY: tilt.rotateY,
          scale: tilt.scale,
        }
      : {}

    const tiltHandlers = enableTilt && tilt.isEnabled ? tilt.handlers : {}

    return (
      <motion.div
        ref={ref}
        className={`${baseStyles} ${variants[variant]} ${paddings[padding]} ${enableTilt ? 'preserve-3d' : ''} ${className}`}
        style={{
          ...depthStyles,
          ...tiltStyle,
          ...style,
        }}
        {...hoverAnimation}
        {...tiltHandlers}
        {...props}
      >
        {children}
      </motion.div>
    )
  }
)

Card.displayName = 'Card'

function getColorfulStyles(colorScheme: string): string {
  const schemes = {
    primary: 'bg-gradient-to-br from-primary/10 to-primary/5 border-2 border-primary/20',
    secondary: 'bg-gradient-to-br from-secondary/10 to-secondary/5 border-2 border-secondary/20',
    accent: 'bg-gradient-to-br from-accent/20 to-accent/10 border-2 border-accent/30',
  }
  return schemes[colorScheme as keyof typeof schemes] || schemes.primary
}

// Card sub-components
export function CardHeader({ className = '', children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`mb-4 ${className}`} {...props}>
      {children}
    </div>
  )
}

export function CardTitle({ className = '', children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3 className={`text-xl font-bold text-gray-800 ${className}`} {...props}>
      {children}
    </h3>
  )
}

export function CardContent({ className = '', children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`text-gray-600 ${className}`} {...props}>
      {children}
    </div>
  )
}

export function CardFooter({ className = '', children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`mt-4 pt-4 border-t border-gray-100 ${className}`} {...props}>
      {children}
    </div>
  )
}

export default Card
