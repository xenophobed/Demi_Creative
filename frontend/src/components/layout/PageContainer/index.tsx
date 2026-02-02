import { Outlet, Link, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { AnimatedBackground } from '@/components/depth/AnimatedBackground'
import { ConfettiController } from '@/components/effects/Confetti'

function PageContainer() {
  const location = useLocation()

  return (
    <div className="min-h-screen gradient-bg relative">
      {/* Animated background with parallax */}
      <AnimatedBackground />

      {/* Global confetti controller for celebrations */}
      <ConfettiController />
      {/* Navigation bar */}
      <nav className="bg-white/80 backdrop-blur-md shadow-sm sticky top-0 z-40 relative">
        <div className="max-w-4xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            {/* Logo */}
            <Link to="/" className="flex items-center gap-2 group">
              <motion.span
                className="text-3xl"
                whileHover={{ rotate: [0, -10, 10, 0] }}
                transition={{ duration: 0.5 }}
              >
                🎨
              </motion.span>
              <span className="text-xl font-bold text-gradient">
                Creative Studio
              </span>
            </Link>

            {/* Navigation links */}
            <div className="flex items-center gap-4">
              <NavLink to="/upload" icon="✏️" label="Create" />
              <NavLink to="/history" icon="📚" label="My Stories" />
            </div>
          </div>
        </div>
      </nav>

      {/* Main content area */}
      <main className="max-w-4xl mx-auto px-4 py-8 relative z-10">
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3 }}
          >
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </main>

      {/* Footer decoration */}
      <footer className="py-8 text-center relative z-10">
        <div className="flex justify-center gap-4 text-4xl mb-4">
          <motion.span
            animate={{ y: [0, -5, 0] }}
            transition={{ duration: 2, repeat: Infinity, delay: 0 }}
          >
            🌟
          </motion.span>
          <motion.span
            animate={{ y: [0, -5, 0] }}
            transition={{ duration: 2, repeat: Infinity, delay: 0.3 }}
          >
            🎈
          </motion.span>
          <motion.span
            animate={{ y: [0, -5, 0] }}
            transition={{ duration: 2, repeat: Infinity, delay: 0.6 }}
          >
            🌈
          </motion.span>
        </div>
        <p className="text-gray-500 text-sm">
          Paint your imagination, light up childhood with stories
        </p>
      </footer>
    </div>
  )
}

function NavLink({
  to,
  icon,
  label,
}: {
  to: string
  icon: string
  label: string
}) {
  const location = useLocation()
  const isActive = location.pathname === to

  return (
    <Link to={to}>
      <motion.div
        className={`flex items-center gap-1.5 px-4 py-2 rounded-btn font-medium
          ${isActive
            ? 'bg-primary text-white shadow-button'
            : 'text-gray-600 hover:bg-gray-100'
          }`}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
      >
        <span>{icon}</span>
        <span>{label}</span>
      </motion.div>
    </Link>
  )
}

export default PageContainer
