import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import Button from '@/components/common/Button'
import Card from '@/components/common/Card'
import { authService } from '@/api/services/authService'
import { getErrorMessage } from '@/api/client'
import useAuthStore from '@/store/useAuthStore'
import useChildStore, { DEFAULT_INTERESTS, generateChildId } from '@/store/useChildStore'
import type { AgeGroup } from '@/types/api'
import { isValidRegistrationUsername } from './validation'

type AuthMode = 'login' | 'register'
type RegistrationRole = 'parent' | 'child'

/** Map raw auth errors to child/parent-friendly messages. */
function friendlyAuthError(raw: string, mode: AuthMode): string {
  const lower = raw.toLowerCase()
  // Wrong credentials (Supabase + legacy backend)
  if (lower.includes('invalid login credentials') || lower.includes('invalid credentials')
      || lower.includes('incorrect password') || lower.includes('user not found'))
    return 'Incorrect email or password. Please try again.'
  if (lower.includes('account has been disabled'))
    return 'This account has been disabled. Please contact support.'
  if (lower.includes('email not confirmed') || lower.includes('please check your email'))
    return 'Please click the confirmation link in your email first, then come back to log in.'
  if (lower.includes('user already registered') || lower.includes('already exists'))
    return 'This email is already registered. Try signing in instead?'
  if (lower.includes('too many requests') || lower.includes('rate limit'))
    return 'Too many attempts. Please wait a moment and try again.'
  if (lower.includes('network') || lower.includes('fetch') || lower.includes('timeout'))
    return 'Network issue detected. Please check your connection and try again.'
  if (lower.includes('request failed with status code'))
    return mode === 'login' ? 'Login failed. Please check your email and password.' : 'Registration failed. Please try again later.'
  if (mode === 'login')
    return `Login error: ${raw}`
  return `Registration error: ${raw}`
}

/** Pick icon based on error content: 📬 for email-related, 🔑 for credentials. */
function errorIcon(message: string): string {
  return message.includes('confirmation link') ? '📬' : '🔑'
}

function LoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const referralCode = searchParams.get('ref') || undefined
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
  const [registrationRole, setRegistrationRole] = useState<RegistrationRole>('parent')
  const [parentEmail, setParentEmail] = useState('')
  const [childName, setChildName] = useState('')
  const [childAgeGroup, setChildAgeGroup] = useState<AgeGroup>('6-8')
  const [childInterests, setChildInterests] = useState<string[]>(['Animals', 'Space'])

  // UI state
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pendingParentApproval, setPendingParentApproval] = useState<{
    parentEmail: string
    approvalUrl?: string | null
  } | null>(null)
  const [confirmationPending, setConfirmationPending] = useState(false)
  const [emailConfirmation, setEmailConfirmation] = useState(false)
  const [confirmationEmail, setConfirmationEmail] = useState('')
  const [confirmationNotice, setConfirmationNotice] = useState<string | null>(null)
  const [isResendingConfirmation, setIsResendingConfirmation] = useState(false)

  // Validation
  const validateForm = (): string | null => {
    if (mode === 'login') {
      if (!username.trim()) return 'Please enter your email'
      if (!password) return 'Please enter your password'
    } else {
      if (!username.trim()) return 'Please enter a username'
      if (!isValidRegistrationUsername(username))
        return 'Username can only contain letters, numbers, underscores, and hyphens'
      if (!email.trim()) return 'Please enter your email'
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return 'Please enter a valid email'
      if (registrationRole === 'parent') {
        if (!childName.trim()) return 'Please add a child nickname'
      } else {
        if (!parentEmail.trim()) return 'Please enter a parent or guardian email'
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(parentEmail)) return 'Please enter a valid parent or guardian email'
      }
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
    setConfirmationNotice(null)

    const validationError = validateForm()
    if (validationError) {
      setError(validationError)
      return
    }

    const normalizedLoginEmail = username.trim().toLowerCase()
    const normalizedRegisterEmail = email.trim().toLowerCase()

    setIsLoading(true)

    try {
      let response
      if (mode === 'login') {
        response = await authService.login({
          username_or_email: normalizedLoginEmail,
          password,
        })
      } else {
        const initialChildId = registrationRole === 'parent' ? generateChildId() : undefined
        const result = await authService.register({
          username: username.trim(),
          email: normalizedRegisterEmail,
          password,
          display_name: displayName.trim() || undefined,
          referral_code: referralCode,
          role: registrationRole,
          parent_email: registrationRole === 'child'
            ? parentEmail.trim().toLowerCase()
            : undefined,
          child_id: initialChildId,
          child_name: registrationRole === 'parent' ? childName.trim() : undefined,
          child_age_group: registrationRole === 'parent' ? childAgeGroup : undefined,
          child_interests: registrationRole === 'parent' ? childInterests : undefined,
        })

        if ('pendingConfirmation' in result) {
          setConfirmationPending(true)
          setConfirmationEmail(result.email)
          return
        }

        response = result
      }

      // Store auth data
      setAuth(response.user, response.token.access_token)

      if (mode === 'register' && response.user.role === 'child') {
        const approval = await authService.resendParentApproval()
        setPendingParentApproval({
          parentEmail: approval.parent_email || parentEmail.trim().toLowerCase(),
          approvalUrl: approval.approval_url,
        })
        return
      }

      if (mode === 'register' && response.user.role === 'parent') {
        await useChildStore.getState().loadChildProfiles()
        navigate('/my-agent')
        return
      }

      navigate('/')
    } catch (err: any) {
      if (err?.code === 'EMAIL_CONFIRMATION_REQUIRED') {
        setEmailConfirmation(true)
        setConfirmationEmail(normalizedRegisterEmail)
        setConfirmationNotice('账号已创建，请去邮箱点击确认链接后再回来登录。')
        setError(null)
      } else {
        const raw = getErrorMessage(err)
        if (raw.toLowerCase().includes('email not confirmed')) {
          setEmailConfirmation(true)
          setConfirmationEmail(mode === 'login' ? normalizedLoginEmail : normalizedRegisterEmail)
          setConfirmationNotice('这个账号还没有完成邮箱验证。可以先重发确认邮件。')
          setError(null)
        } else {
          setError(friendlyAuthError(raw, mode))
        }
      }
    } finally {
      setIsLoading(false)
    }
  }

  const handleResendConfirmation = async () => {
    if (!confirmationEmail) return

    setIsResendingConfirmation(true)
    setError(null)

    try {
      await authService.resendConfirmation(confirmationEmail)
      setConfirmationNotice('确认邮件已重新发送。请检查收件箱、垃圾邮件和推广邮件文件夹。')
    } catch (err) {
      const raw = getErrorMessage(err)
      setError(friendlyAuthError(raw, 'register'))
    } finally {
      setIsResendingConfirmation(false)
    }
  }

  // Switch between login and register
  const switchMode = () => {
    const nextMode = mode === 'login' ? 'register' : 'login'
    setMode(nextMode)
    setError(null)
    setConfirmationPending(false)
    setEmailConfirmation(false)
    setConfirmationEmail('')
    setConfirmationNotice(null)
    if (nextMode === 'register' && username.includes('@')) setUsername('')
    setPassword('')
    setConfirmPassword('')
    setParentEmail('')
    setChildName('')
    setChildAgeGroup('6-8')
    setChildInterests(['Animals', 'Space'])
    setPendingParentApproval(null)
  }

  const toggleChildInterest = (interest: string) => {
    setChildInterests((current) => {
      if (current.includes(interest)) {
        return current.filter((item) => item !== interest)
      }
      return [...current, interest].slice(0, 8)
    })
  }

  const handleResendParentApproval = async () => {
    if (!pendingParentApproval) return
    setIsLoading(true)
    setError(null)
    try {
      const approval = await authService.resendParentApproval()
      setPendingParentApproval({
        parentEmail: approval.parent_email || pendingParentApproval.parentEmail,
        approvalUrl: approval.approval_url,
      })
      setConfirmationNotice('Parent approval request refreshed.')
    } catch (err) {
      setError(friendlyAuthError(getErrorMessage(err), 'register'))
    } finally {
      setIsLoading(false)
    }
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
          <Link to="/" className="inline-flex flex-col items-center gap-1 sm:gap-2">
            <motion.span
              className="text-5xl sm:text-6xl inline-block"
              whileHover={{ rotate: [0, -10, 10, 0] }}
              transition={{ duration: 0.5 }}
            >
              🎨
            </motion.span>
            <h1 className="text-2xl sm:text-3xl font-bold text-gradient">Creative Workshop</h1>
          </Link>
          <p className="text-gray-600 mt-2">
            {mode === 'login' ? 'Welcome back!' : 'Join the creative fun!'}
          </p>
        </motion.div>

        {/* Email confirmation success card */}
        {pendingParentApproval && (
          <Card variant="elevated" padding="lg" className="backdrop-blur-sm bg-white/95">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="text-center space-y-4 py-4"
            >
              <div className="text-5xl">📬</div>
              <h2 className="text-xl font-bold text-gray-800">Parent approval needed</h2>
              <p className="text-gray-500 text-sm">
                We sent an approval request to your parent or guardian. You can come back after they approve it.
              </p>
              <p className="text-gray-400 text-xs break-all">{pendingParentApproval.parentEmail}</p>
              {pendingParentApproval.approvalUrl && (
                <a
                  href={pendingParentApproval.approvalUrl}
                  className="block rounded-lg bg-gray-50 px-3 py-2 text-xs font-medium text-primary hover:bg-primary/10"
                >
                  Open approval link
                </a>
              )}
              {confirmationNotice && (
                <p className="text-xs text-green-700">{confirmationNotice}</p>
              )}
              <Button
                type="button"
                variant="secondary"
                size="md"
                isLoading={isLoading}
                onClick={handleResendParentApproval}
              >
                Resend Approval Request
              </Button>
              <div>
                <button
                  type="button"
                  onClick={() => navigate('/')}
                  className="text-sm text-gray-500 hover:text-primary transition-colors"
                >
                  Back to Home
                </button>
              </div>
            </motion.div>
          </Card>
        )}

        {confirmationPending && (
          <Card variant="elevated" padding="lg" className="backdrop-blur-sm bg-white/95">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="text-center space-y-4 py-4"
            >
              <div className="text-5xl">📬</div>
              <h2 className="text-xl font-bold text-gray-800">Registration successful! Please check your email for a confirmation link.</h2>
              <p className="text-gray-500 text-sm">You can log in once confirmed.</p>
              <p className="text-gray-400 text-xs">{confirmationEmail}</p>
              <Button
                type="button"
                variant="secondary"
                size="md"
                isLoading={isResendingConfirmation}
                onClick={handleResendConfirmation}
              >
                Resend Confirmation Email
              </Button>
              <div>
                <button
                  type="button"
                  onClick={() => { setConfirmationPending(false); setMode('login') }}
                  className="text-sm text-gray-500 hover:text-primary transition-colors"
                >
                  Back to Login
                </button>
              </div>
            </motion.div>
          </Card>
        )}

        {/* Form Card */}
        {!confirmationPending && !pendingParentApproval && (
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
              {/* Email confirmation success */}
              <AnimatePresence>
                {emailConfirmation && (
                  <motion.div
                    initial={{ opacity: 0, y: -10, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -10, scale: 0.95 }}
                    className="bg-green-50 border border-green-200 rounded-2xl p-4 text-green-700 text-sm text-center space-y-3"
                  >
                    <div className="text-2xl">📬</div>
                    <p className="font-medium">
                      {confirmationNotice || 'Account created! Please check your email to verify your account, then come back and sign in.'}
                    </p>
                    {confirmationEmail && (
                      <p className="text-xs break-all text-green-800/80">
                        {confirmationEmail}
                      </p>
                    )}
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      onClick={handleResendConfirmation}
                      isLoading={isResendingConfirmation}
                      className="w-full"
                    >
                      Resend Confirmation Email
                    </Button>
                    <p className="text-xs text-green-800/70">
                      If you still don&apos;t receive it, check spam or try a different email provider.
                    </p>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Error message */}
              <AnimatePresence>
                {error && (
                  <motion.div
                    initial={{ opacity: 0, y: -10, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -10, scale: 0.95 }}
                    className="bg-amber-50 border border-amber-200 rounded-2xl p-4 text-amber-700 text-sm text-center space-y-1"
                  >
                    <div className="text-2xl">{errorIcon(error)}</div>
                    <p className="font-medium">{error}</p>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Username / Email field */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {mode === 'login' ? 'Email' : 'Username'}
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
                    👤
                  </span>
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder={mode === 'login' ? 'Enter your email' : 'Choose a username'}
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

              {/* Account setup role (register only) */}
              {mode === 'register' && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="space-y-2"
                >
                  <label className="block text-sm font-medium text-gray-700">
                    Who is setting this up?
                  </label>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    {([
                      ['parent', 'Parent / guardian', 'Manage child profiles and consent'],
                      ['child', 'Kid with parent email', 'Parent approval required'],
                    ] as const).map(([value, label, helper]) => {
                      const selected = registrationRole === value
                      return (
                        <button
                          key={value}
                          type="button"
                          onClick={() => setRegistrationRole(value)}
                          className={`rounded-lg border px-3 py-2 text-left transition-colors ${
                            selected
                              ? 'border-primary bg-primary/10 text-gray-900'
                              : 'border-gray-200 bg-white text-gray-600 hover:border-primary/40'
                          }`}
                        >
                          <span className="block text-sm font-semibold">{label}</span>
                          <span className="block text-xs text-gray-500">{helper}</span>
                        </button>
                      )
                    })}
                  </div>
                </motion.div>
              )}

              {/* Parent child setup (parent register only) */}
              {mode === 'register' && registrationRole === 'parent' && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="space-y-3 rounded-lg border border-primary/20 bg-primary/5 p-3"
                >
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Child Nickname
                    </label>
                    <input
                      type="text"
                      value={childName}
                      onChange={(e) => setChildName(e.target.value)}
                      placeholder="Little Artist"
                      className="input-kid"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Age Group
                    </label>
                    <select
                      value={childAgeGroup}
                      onChange={(e) => setChildAgeGroup(e.target.value as AgeGroup)}
                      className="input-kid"
                    >
                      <option value="3-5">3-5</option>
                      <option value="6-8">6-8</option>
                      <option value="9-12">9-12</option>
                    </select>
                  </div>
                  <div>
                    <span className="block text-sm font-medium text-gray-700 mb-2">
                      Interests
                    </span>
                    <div className="flex flex-wrap gap-2">
                      {DEFAULT_INTERESTS.slice(0, 8).map((interest) => {
                        const selected = childInterests.includes(interest)
                        return (
                          <button
                            key={interest}
                            type="button"
                            onClick={() => toggleChildInterest(interest)}
                            className={`rounded-lg border px-3 py-1.5 text-xs font-semibold transition-colors ${
                              selected
                                ? 'border-primary bg-primary/10 text-primary'
                                : 'border-gray-200 bg-white text-gray-600 hover:border-primary/40'
                            }`}
                          >
                            {interest}
                          </button>
                        )
                      })}
                    </div>
                  </div>
                </motion.div>
              )}

              {/* Parent email (child-started register only) */}
              {mode === 'register' && registrationRole === 'child' && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                >
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Parent / Guardian Email
                  </label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
                      📬
                    </span>
                    <input
                      type="email"
                      value={parentEmail}
                      onChange={(e) => setParentEmail(e.target.value)}
                      placeholder="parent@email.com"
                      className="input-kid pl-10"
                      autoComplete="email"
                    />
                  </div>
                  <p className="mt-1 text-xs text-gray-500">
                    A parent or guardian must approve before protected features are enabled.
                  </p>
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
        )}

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
