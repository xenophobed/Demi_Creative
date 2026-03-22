import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'

const ACCENT_STYLES = {
  primary: {
    bg: 'bg-gradient-to-br from-primary/15 to-primary/5',
    border: 'border-primary/20',
    iconBg: 'bg-primary/20',
    hoverShadow: '0 8px 25px rgba(255, 107, 107, 0.25)',
  },
  secondary: {
    bg: 'bg-gradient-to-br from-secondary/15 to-secondary/5',
    border: 'border-secondary/20',
    iconBg: 'bg-secondary/20',
    hoverShadow: '0 8px 25px rgba(78, 205, 196, 0.25)',
  },
  accent: {
    bg: 'bg-gradient-to-br from-accent/25 to-accent/10',
    border: 'border-accent/30',
    iconBg: 'bg-accent/30',
    hoverShadow: '0 8px 25px rgba(255, 230, 109, 0.35)',
  },
} as const

type AccentColor = keyof typeof ACCENT_STYLES

interface FeatureTileProps {
  to: string
  icon: string
  label: string
  accentColor: AccentColor
  description?: string
}

function FeatureTile({ to, icon, label, accentColor, description }: FeatureTileProps) {
  const style = ACCENT_STYLES[accentColor]

  return (
    <Link to={to} className="block">
      <motion.div
        className={`${style.bg} ${style.border} border rounded-card p-5 shadow-card text-center cursor-pointer`}
        whileHover={{
          scale: 1.05,
          y: -4,
          boxShadow: style.hoverShadow,
        }}
        whileTap={{ scale: 0.97 }}
        transition={{ type: 'spring', stiffness: 300, damping: 20 }}
      >
        <div
          className={`${style.iconBg} w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-3`}
        >
          <span className="text-2xl">{icon}</span>
        </div>
        <span className="font-bold text-gray-800 text-sm block">{label}</span>
        {description && (
          <span className="text-xs text-gray-500 mt-1 block">{description}</span>
        )}
      </motion.div>
    </Link>
  )
}

export default FeatureTile
