import { useEffect } from 'react'
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { shouldRedirectToOnboarding } from './requireOnboarded'
import { AnimatedBackground } from '@/components/depth/AnimatedBackground'
import { ConfettiController } from '@/components/effects/Confetti'
import GenerationStatusBar from '@/components/layout/GenerationStatusBar'
import useGenerationNavigator from '@/hooks/useGenerationNavigator'
import AvatarDisplay from '@/components/common/AvatarDisplay'
import useAuthStore from '@/store/useAuthStore'
import useDailyTaskStore from '@/store/useDailyTaskStore'
import { authService } from '@/api/services/authService'
import { performFullLogout } from '@/utils/logout'
import { NavRefProvider, useNavRef } from '@/contexts/NavRefContext'

function PageContainer() {
  return (
    <NavRefProvider>
      <PageContainerInner />
    </NavRefProvider>
  )
}

function PageContainerInner() {
  const location = useLocation()
  const navigate = useNavigate()
  const { isAuthenticated, user } = useAuthStore()
  const { setProfileAvatarEl } = useNavRef()
  const totalStars = useDailyTaskStore((s) => s.totalStars)

  useGenerationNavigator()

  // RequireOnboarded gate (#444): when an authenticated user has not yet
  // finished onboarding (no users.onboarded_at), funnel them to /my-agent
  // so they meet their buddy and parent grants consent before the rest
  // of the app is available. The gate predicate is extracted to
  // requireOnboarded.ts so it's unit-testable.
  useEffect(() => {
    if (
      !shouldRedirectToOnboarding({
        isAuthenticated,
        onboardedAt: user?.onboarded_at,
        pathname: location.pathname,
      })
    ) {
      return
    }
    const ret = encodeURIComponent(location.pathname + location.search)
    navigate(`/my-agent?return=${ret}`, { replace: true })
  }, [
    isAuthenticated,
    user?.onboarded_at,
    location.pathname,
    location.search,
    navigate,
  ])

  const handleLogout = async () => {
    try {
      await authService.logout()
    } catch {
      // Ignore logout errors
    }
    performFullLogout()
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
              <NavLink to="/library" icon="📚" label="My Library" />
              <NavLink to="/my-agent" icon="🦊" label="My Agent" />
              <NavLink to="/content-hub" icon="🌐" label="Content Hub" />

              {/* Auth section */}
              {isAuthenticated ? (
                <div className="flex items-center gap-3 ml-2 pl-4 border-l border-gray-200">
                  <Link to="/profile">
                    <div ref={setProfileAvatarEl} className="relative">
                      <motion.div
                        className="flex items-center gap-2 text-gray-600"
                        whileHover={{ scale: 1.02 }}
                      >
                        <AvatarDisplay avatarUrl={user?.avatar_url} size="sm" />
                        {totalStars > 0 && (
                          <span className="absolute -top-1.5 -right-1.5 min-w-[18px] h-[18px] flex items-center justify-center text-[10px] font-bold text-white bg-gradient-to-r from-yellow-400 to-orange-400 rounded-full shadow-sm px-1 leading-none">
                            {totalStars > 99 ? '99+' : totalStars}
                          </span>
                        )}
                        <span className="text-sm font-medium hidden sm:inline">
                          {user?.display_name || user?.username}
                        </span>
                      </motion.div>
                    </div>
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
