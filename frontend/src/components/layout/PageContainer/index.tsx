import { useEffect, useState } from 'react'
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { shouldRedirectToOnboarding } from './requireOnboarded'
import { closeMenu, toggleMenu } from './mobileMenu'
import { AnimatedBackground } from '@/components/depth/AnimatedBackground'
import { ConfettiController } from '@/components/effects/Confetti'
import GenerationStatusBar from '@/components/layout/GenerationStatusBar'
import useGenerationNavigator from '@/hooks/useGenerationNavigator'
import AvatarDisplay from '@/components/common/AvatarDisplay'
import useAuthStore from '@/store/useAuthStore'
import useDailyTaskStore from '@/store/useDailyTaskStore'
import useChildStore from '@/store/useChildStore'
import { authService } from '@/api/services/authService'
import { performFullLogout } from '@/utils/logout'
import { NavRefProvider, useNavRef } from '@/contexts/NavRefContext'

const CHILD_SELECTION_PATHS = new Set([
  '/upload',
  '/interactive',
  '/kids-daily',
  '/my-agent',
])

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
  const {
    childProfiles,
    currentChild,
    loadChildProfiles,
    switchActiveChild,
  } = useChildStore()
  const [mobileOpen, setMobileOpen] = useState(false)
  const activeProfiles = childProfiles.filter((child) => !child.archived_at)
  const shouldPickActiveChild =
    isAuthenticated &&
    user?.role === 'parent' &&
    activeProfiles.length > 1 &&
    !currentChild &&
    CHILD_SELECTION_PATHS.has(location.pathname)

  useGenerationNavigator()

  useEffect(() => {
    if (!isAuthenticated || user?.role !== 'parent') return
    loadChildProfiles().catch((err) => {
      console.error('Failed to hydrate child profiles:', err)
    })
  }, [isAuthenticated, user?.role, loadChildProfiles])

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

  // Auto-close the mobile drawer on route change so navigation never leaves
  // the menu open over fresh page content.
  useEffect(() => {
    setMobileOpen(closeMenu())
  }, [location.pathname])

  const handleLogout = async () => {
    try {
      await authService.logout()
    } catch {
      // Ignore logout errors
    }
    performFullLogout()
    navigate('/')
  }

  const handleCloseMobile = () => setMobileOpen(closeMenu())
  const handleToggleMobile = () => setMobileOpen((prev) => toggleMenu(prev))

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

            {/* Desktop navigation links — unchanged on >= 768px */}
            <div className="hidden md:flex items-center gap-4">
              <NavLink to="/library" icon="📚" label="My Library" />
              <NavLink to="/my-agent" icon="🤖" label="My Agent" />
              <NavLink to="/content-hub" icon="🌐" label="Content Hub" />

              {/* Auth section */}
              {isAuthenticated ? (
                <div className="flex items-center gap-3 ml-2 pl-4 border-l border-gray-200">
                  <ActiveChildSwitcher
                    profiles={activeProfiles}
                    activeChildId={currentChild?.child_id ?? null}
                    onSelect={switchActiveChild}
                  />
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

            {/* Mobile hamburger button — visible on < 768px */}
            <button
              type="button"
              onClick={handleToggleMobile}
              aria-label={mobileOpen ? 'Close navigation menu' : 'Open navigation menu'}
              aria-expanded={mobileOpen}
              aria-controls="mobile-nav-drawer"
              className="md:hidden inline-flex items-center justify-center min-h-[44px] min-w-[44px] rounded-btn text-gray-700 hover:bg-gray-100 transition-colors"
            >
              {/* Hamburger / close icon (SVG, no new deps) */}
              <svg
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                {mobileOpen ? (
                  <>
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </>
                ) : (
                  <>
                    <line x1="3" y1="6" x2="21" y2="6" />
                    <line x1="3" y1="12" x2="21" y2="12" />
                    <line x1="3" y1="18" x2="21" y2="18" />
                  </>
                )}
              </svg>
            </button>
          </div>
        </div>
      </nav>

      {/* Mobile slide-out drawer + backdrop (only mounts when open) */}
      <AnimatePresence>
        {mobileOpen && (
          <div className="md:hidden fixed inset-0 z-50">
            {/* Backdrop: tap to close */}
            <motion.div
              className="absolute inset-0 bg-black/40"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              onClick={handleCloseMobile}
              aria-hidden="true"
            />

            {/* Drawer panel */}
            <motion.div
              id="mobile-nav-drawer"
              role="dialog"
              aria-modal="true"
              aria-label="Mobile navigation"
              className="absolute inset-y-0 right-0 w-72 max-w-[85vw] bg-white shadow-xl flex flex-col"
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ type: 'tween', duration: 0.25 }}
            >
              {/* Drawer header with close button */}
              <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
                <span className="text-lg font-bold text-gradient">Menu</span>
                <button
                  type="button"
                  onClick={handleCloseMobile}
                  aria-label="Close navigation menu"
                  className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] rounded-btn text-gray-700 hover:bg-gray-100 transition-colors"
                >
                  <svg
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              </div>

              {/* Drawer nav links */}
              <div className="flex-1 overflow-y-auto px-3 py-4 flex flex-col gap-1">
                <MobileNavLink
                  to="/library"
                  icon="📚"
                  label="My Library"
                  onNavigate={handleCloseMobile}
                />
                <MobileNavLink
                  to="/my-agent"
                  icon="🤖"
                  label="My Agent"
                  onNavigate={handleCloseMobile}
                />
                <MobileNavLink
                  to="/content-hub"
                  icon="🌐"
                  label="Content Hub"
                  onNavigate={handleCloseMobile}
                />
              </div>

              {/* Drawer footer: auth */}
              <div className="border-t border-gray-200 px-3 py-4">
                {isAuthenticated ? (
                  <div className="flex flex-col gap-2">
                    <ActiveChildSwitcher
                      profiles={activeProfiles}
                      activeChildId={currentChild?.child_id ?? null}
                      onSelect={switchActiveChild}
                      compact={false}
                    />
                    <Link
                      to="/profile"
                      onClick={handleCloseMobile}
                      className="flex items-center gap-3 px-3 py-3 rounded-btn min-h-[44px] text-gray-700 hover:bg-gray-100 transition-colors"
                    >
                      <AvatarDisplay avatarUrl={user?.avatar_url} size="sm" />
                      <span className="text-sm font-medium">
                        {user?.display_name || user?.username || 'Profile'}
                      </span>
                      {totalStars > 0 && (
                        <span className="ml-auto min-w-[20px] h-[20px] flex items-center justify-center text-[11px] font-bold text-white bg-gradient-to-r from-yellow-400 to-orange-400 rounded-full px-1.5">
                          {totalStars > 99 ? '99+' : totalStars}
                        </span>
                      )}
                    </Link>
                    <button
                      type="button"
                      onClick={() => {
                        handleCloseMobile()
                        handleLogout()
                      }}
                      className="flex items-center gap-3 px-3 py-3 rounded-btn min-h-[44px] text-gray-500 hover:bg-gray-100 hover:text-red-500 transition-colors text-left"
                    >
                      <span aria-hidden="true">🚪</span>
                      <span className="text-sm font-medium">Sign Out</span>
                    </button>
                  </div>
                ) : (
                  <Link
                    to="/login"
                    onClick={handleCloseMobile}
                    className="flex items-center justify-center gap-2 min-h-[44px] px-4 py-3 rounded-btn font-medium bg-secondary text-white shadow-button"
                  >
                    <span aria-hidden="true">👤</span>
                    <span>Sign In</span>
                  </Link>
                )}
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

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
            {shouldPickActiveChild ? (
              <ActiveChildPicker
                profiles={activeProfiles}
                onSelect={switchActiveChild}
              />
            ) : (
              <Outlet />
            )}
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

function ActiveChildPicker({
  profiles,
  onSelect,
}: {
  profiles: Array<{
    child_id: string
    name: string
    age_group?: string
    interests?: string[]
    avatar?: string | null
  }>
  onSelect: (childId: string) => void
}) {
  return (
    <section className="mx-auto max-w-2xl rounded-card border border-gray-200 bg-white/90 p-6 shadow-card backdrop-blur">
      <div className="mb-5">
        <p className="text-sm font-bold uppercase tracking-wide text-primary">
          Who's creating today?
        </p>
        <h1 className="mt-1 text-2xl font-bold text-gray-800">
          Pick the active child profile
        </h1>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {profiles.map((child) => (
          <button
            key={child.child_id}
            type="button"
            className="min-h-[120px] rounded-card border border-gray-200 bg-white p-4 text-left transition hover:border-primary/50 hover:shadow-card focus:outline-none focus:ring-2 focus:ring-primary/40"
            onClick={() => onSelect(child.child_id)}
          >
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-full bg-primary/10 text-2xl">
                {avatarLabel(child)}
              </span>
              <div className="min-w-0">
                <h2 className="truncate text-base font-bold text-gray-800">
                  {child.name}
                </h2>
                {child.age_group && (
                  <p className="text-sm text-gray-500">{child.age_group}</p>
                )}
              </div>
            </div>
            {child.interests && child.interests.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {child.interests.slice(0, 3).map((interest) => (
                  <span
                    key={interest}
                    className="rounded-lg bg-gray-100 px-2 py-1 text-xs font-semibold text-gray-600"
                  >
                    {interest}
                  </span>
                ))}
              </div>
            )}
          </button>
        ))}
      </div>

      <Link
        to="/profile?tab=children"
        className="mt-5 inline-flex text-sm font-bold text-primary hover:text-primary/80"
      >
        Manage child profiles
      </Link>
    </section>
  )
}

function ActiveChildSwitcher({
  profiles,
  activeChildId,
  onSelect,
  compact = true,
}: {
  profiles: Array<{ child_id: string; name: string; avatar?: string | null }>
  activeChildId: string | null
  onSelect: (childId: string) => void
  compact?: boolean
}) {
  if (profiles.length <= 1) return null

  return (
    <label
      className={
        compact
          ? 'flex flex-col gap-0.5 rounded-btn bg-gray-50 px-2.5 py-1.5 text-xs font-bold leading-tight text-gray-500'
          : 'flex flex-col gap-1 rounded-btn bg-gray-50 px-3 py-2 text-xs font-bold text-gray-500'
      }
    >
      <span>{compact ? 'Child' : 'Creating as'}</span>
      <select
        value={activeChildId ?? ''}
        onChange={(event) => onSelect(event.target.value)}
        className="max-w-[120px] rounded-lg border border-gray-200 bg-white px-2 py-1 text-sm font-semibold text-gray-700 focus:outline-none focus:ring-2 focus:ring-primary/40"
      >
        {!activeChildId && (
          <option value="" disabled>
            Pick child
          </option>
        )}
        {profiles.map((child) => (
          <option key={child.child_id} value={child.child_id}>
            {avatarLabel(child)} {child.name}
          </option>
        ))}
      </select>
    </label>
  )
}

function avatarLabel(child: { avatar?: string | null }) {
  if (child.avatar?.startsWith('emoji:')) {
    return child.avatar.replace('emoji:', '')
  }
  return '🎨'
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

function MobileNavLink({
  to,
  icon,
  label,
  onNavigate,
}: {
  to: string
  icon: string
  label: string
  onNavigate: () => void
}) {
  const location = useLocation()
  const isActive = location.pathname === to

  return (
    <Link
      to={to}
      onClick={onNavigate}
      className={`flex items-center gap-3 px-4 py-3 rounded-btn font-medium min-h-[44px]
        ${
          isActive
            ? 'bg-primary text-white shadow-button'
            : 'text-gray-700 hover:bg-gray-100'
        }`}
    >
      <span aria-hidden="true" className="text-xl">
        {icon}
      </span>
      <span>{label}</span>
    </Link>
  )
}

export default PageContainer
