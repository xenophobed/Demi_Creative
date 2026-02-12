import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import Button from '@/components/common/Button'
import Card from '@/components/common/Card'
import { authService } from '@/api/services/authService'
import { getErrorMessage } from '@/api/client'
import useAuthStore from '@/store/useAuthStore'

type AuthMode = 'login' | 'register'

function LoginPage() {
  const navigate = useNavigate()
  const { setAuth } = useAuthStore()

  // Form mode
  const [mode, setMode] = useState<AuthMode>('login')

  // Form state — pre-fill credentials in dev mode for convenience
  const isDev = import.meta.env.DEV
  const [username, setUsername] = useState(isDev ? 'demi2014@proton.me' : '')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState(isDev ? '$!$Ymd@2022' : '')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [displayName, setDisplayName] = useState('')

  // UI state
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Validation
  const validateForm = (): string | null => {
    if (mode === 'login') {
      if (!username.trim()) return 'Please enter your username or email'
      if (!password) return 'Please enter your password'
    } else {
      if (!username.trim()) return 'Please enter a username'
      if (!email.trim()) return 'Please enter your email'
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return 'Please enter a valid email'
      if (!password) return 'Please enter a password'
      if (password.length < 6) return 'Password must be at least 6 characters'
      if (password !== confirmPassword) return 'Passwords do not match'
    }
    return null
  }

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    const validationError = validateForm()
    if (validationError) {
      setError(validationError)
      return
    }

    setIsLoading(true)

    try {
      let response
      if (mode === 'login') {
        response = await authService.login({
          username_or_email: username.trim(),
          password,
        })
      } else {
        response = await authService.register({
          username: username.trim(),
          email: email.trim().toLowerCase(),
          password,
          display_name: displayName.trim() || undefined,
        })
      }

      // Store auth data
      setAuth(response.user, response.token.access_token)

      // Navigate to home
      navigate('/')
    } catch (err) {
      const message = getErrorMessage(err)
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }

  // Switch between login and register
  const switchMode = () => {
    setMode(mode === 'login' ? 'register' : 'login')
    setError(null)
    setPassword('')
    setConfirmPassword('')
  }

  return (
    <div className="min-h-screen gradient-bg flex items-center justify-center p-4">
      {/* Decorative background elements */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <motion.div
          className="absolute top-20 left-10 text-6xl"
          animate={{ y: [0, -20, 0], rotate: [0, 10, 0] }}
          transition={{ duration: 5, repeat: Infinity }}
        >
          🎨
        </motion.div>
        <motion.div
          className="absolute top-40 right-20 text-5xl"
          animate={{ y: [0, 15, 0], rotate: [0, -10, 0] }}
          transition={{ duration: 4, repeat: Infinity, delay: 0.5 }}
        >
          ✨
        </motion.div>
        <motion.div
          className="absolute bottom-32 left-20 text-5xl"
          animate={{ y: [0, -15, 0] }}
          transition={{ duration: 3, repeat: Infinity, delay: 1 }}
        >
          📚
        </motion.div>
        <motion.div
          className="absolute bottom-20 right-10 text-6xl"
          animate={{ y: [0, 20, 0], rotate: [0, -5, 5, 0] }}
          transition={{ duration: 6, repeat: Infinity, delay: 0.3 }}
        >
          🌟
        </motion.div>
      </div>

      <motion.div
        className="w-full max-w-md relative z-10"
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        {/* Logo */}
        <motion.div
          className="text-center mb-8"
          initial={{ scale: 0.8 }}
          animate={{ scale: 1 }}
          transition={{ delay: 0.2, type: 'spring', stiffness: 200 }}
        >
          <Link to="/" className="inline-block">
            <motion.span
              className="text-6xl inline-block"
              whileHover={{ rotate: [0, -10, 10, 0] }}
              transition={{ duration: 0.5 }}
            >
              🎨
            </motion.span>
            <h1 className="text-3xl font-bold text-gradient mt-2">Creative Workshop</h1>
          </Link>
          <p className="text-gray-600 mt-2">
            {mode === 'login' ? 'Welcome back!' : 'Join the creative fun!'}
          </p>
        </motion.div>

        {/* Form Card */}
        <Card variant="elevated" padding="lg" className="backdrop-blur-sm bg-white/95">
          <AnimatePresence mode="wait">
            <motion.form
              key={mode}
              onSubmit={handleSubmit}
              initial={{ opacity: 0, x: mode === 'login' ? -20 : 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: mode === 'login' ? 20 : -20 }}
              transition={{ duration: 0.3 }}
              className="space-y-4"
            >
              {/* Error message */}
              <AnimatePresence>
                {error && (
                  <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className="bg-red-50 border border-red-200 rounded-xl p-3 text-red-600 text-sm flex items-center gap-2"
                  >
                    <span>❌</span>
                    <span>{error}</span>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Username field */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {mode === 'login' ? 'Username or Email' : 'Username'}
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
                    👤
                  </span>
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder={mode === 'login' ? 'Enter username or email' : 'Choose a username'}
                    className="input-kid pl-10"
                    autoComplete="username"
                  />
                </div>
              </div>

              {/* Email field (register only) */}
              {mode === 'register' && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                >
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Email
                  </label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
                      📧
                    </span>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="your@email.com"
                      className="input-kid pl-10"
                      autoComplete="email"
                    />
                  </div>
                </motion.div>
              )}

              {/* Display name (register only) */}
              {mode === 'register' && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                >
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Display Name <span className="text-gray-400">(optional)</span>
                  </label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
                      ✏️
                    </span>
                    <input
                      type="text"
                      value={displayName}
                      onChange={(e) => setDisplayName(e.target.value)}
                      placeholder="How should we call you?"
                      className="input-kid pl-10"
                    />
                  </div>
                </motion.div>
              )}

              {/* Password field */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Password
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
                    🔒
                  </span>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={mode === 'register' ? 'At least 6 characters' : 'Enter your password'}
                    className="input-kid pl-10"
                    autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  />
                </div>
              </div>

              {/* Confirm password (register only) */}
              {mode === 'register' && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                >
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Confirm Password
                  </label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
                      🔒
                    </span>
                    <input
                      type="password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="Confirm your password"
                      className="input-kid pl-10"
                      autoComplete="new-password"
                    />
                  </div>
                </motion.div>
              )}

              {/* Submit button */}
              <Button
                type="submit"
                variant="primary"
                size="lg"
                className="w-full mt-6"
                isLoading={isLoading}
                leftIcon={<span>{mode === 'login' ? '🚀' : '✨'}</span>}
              >
                {mode === 'login' ? 'Sign In' : 'Create Account'}
              </Button>
            </motion.form>
          </AnimatePresence>

          {/* Divider */}
          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-200" />
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-4 bg-white text-gray-500">or</span>
            </div>
          </div>

          {/* Switch mode button */}
          <motion.button
            type="button"
            onClick={switchMode}
            className="w-full py-3 text-center text-gray-600 hover:text-primary transition-colors"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            {mode === 'login' ? (
              <>
                Don't have an account? <span className="font-semibold text-primary">Sign Up</span>
              </>
            ) : (
              <>
                Already have an account? <span className="font-semibold text-primary">Sign In</span>
              </>
            )}
          </motion.button>
        </Card>

        {/* Back to home link */}
        <motion.div
          className="text-center mt-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
        >
          <Link
            to="/"
            className="text-gray-500 hover:text-primary transition-colors inline-flex items-center gap-2"
          >
            <span>←</span>
            <span>Back to Home</span>
          </Link>
        </motion.div>
      </motion.div>
    </div>
  )
}

export default LoginPage
