import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { AnimatedBackground } from '@/components/depth/AnimatedBackground'
import { ConfettiController } from '@/components/effects/Confetti'
import GenerationStatusBar from '@/components/layout/GenerationStatusBar'
import useGenerationNavigator from '@/hooks/useGenerationNavigator'
import useAuthStore from '@/store/useAuthStore'
import { authService } from '@/api/services/authService'

function PageContainer() {
  const location = useLocation()
  const navigate = useNavigate()
  const { isAuthenticated, user, logout } = useAuthStore()

  useGenerationNavigator()

  const handleLogout = async () => {
    try {
      await authService.logout()
    } catch {
      // Ignore logout errors
    }
    logout()
    navigate('/')
  }

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
                Creative Workshop
              </span>
            </Link>

            {/* Navigation links */}
            <div className="flex items-center gap-4">
              <NavLink to="/history" icon="📚" label="My Stories" />

              {/* Auth section */}
              {isAuthenticated ? (
                <div className="flex items-center gap-3 ml-2 pl-4 border-l border-gray-200">
                  <Link to="/profile">
                    <motion.div
                      className="flex items-center gap-2 text-gray-600"
                      whileHover={{ scale: 1.02 }}
                    >
                      <span className="text-xl">
                        {user?.avatar_url ? (
                          <img
                            src={user.avatar_url}
                            alt="avatar"
                            className="w-7 h-7 rounded-full object-cover"
                          />
                        ) : (
                          '👤'
                        )}
                      </span>
                      <span className="text-sm font-medium hidden sm:inline">
                        {user?.display_name || user?.username}
                      </span>
                    </motion.div>
                  </Link>
                  <motion.button
                    onClick={handleLogout}
                    className="text-gray-500 hover:text-red-500 transition-colors p-2"
                    whileHover={{ scale: 1.1 }}
                    whileTap={{ scale: 0.95 }}
                    title="Sign Out"
                  >
                    🚪
                  </motion.button>
                </div>
              ) : (
                <Link to="/login">
                  <motion.div
                    className="flex items-center gap-1.5 px-4 py-2 rounded-btn font-medium bg-secondary text-white shadow-button"
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                  >
                    <span>👤</span>
                    <span>Sign In</span>
                  </motion.div>
                </Link>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* Generation progress bar (visible when generating on other pages) */}
      <GenerationStatusBar />

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
