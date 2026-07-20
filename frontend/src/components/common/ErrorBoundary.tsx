import { Component, ErrorInfo, ReactNode } from 'react'
import Button from './Button'
import Card, { CardTitle, CardContent, CardFooter } from './Card'

interface ErrorBoundaryProps {
  children: ReactNode
  /** Optional override for the reload action — primarily used in tests. */
  onReload?: () => void
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

const BOOTSTRAP_RECOVERY_KEY = 'creative-workshop:bootstrap-recovery'
const BOOTSTRAP_RECOVERY_WINDOW_MS = 30_000

/**
 * This error was observed during a transient production bundle/bootstrap
 * mismatch. A single automatic retry lets the browser recover from a stale
 * document without creating an infinite reload loop.
 */
function isTransientBootstrapError(error: Error): boolean {
  return error.message.includes(
    'useStreamVisualizationContext must be used within a StreamVisualizationProvider',
  )
}

function attemptBootstrapRecovery(): boolean {
  if (typeof window === 'undefined' || typeof window.sessionStorage === 'undefined') {
    return false
  }

  try {
    const previousAttempt = Number(window.sessionStorage.getItem(BOOTSTRAP_RECOVERY_KEY))
    if (Number.isFinite(previousAttempt) && Date.now() - previousAttempt < BOOTSTRAP_RECOVERY_WINDOW_MS) {
      return false
    }

    window.sessionStorage.setItem(BOOTSTRAP_RECOVERY_KEY, String(Date.now()))
    window.location.reload()
    return true
  } catch {
    // Storage and reload can be unavailable in privacy-restricted contexts.
    return false
  }
}

/**
 * Global ErrorBoundary.
 *
 * React error boundaries MUST be class components because the
 * `getDerivedStateFromError` and `componentDidCatch` lifecycle hooks
 * have no functional-component equivalent. Wrapping `<App />` at the
 * top of `main.tsx` ensures any uncaught render-phase error in the
 * tree falls back to a kid-friendly screen instead of a blank page.
 *
 * Scope (per issue #426):
 *  - Catch render-phase errors anywhere in the tree
 *  - Show warm, encouraging copy (no scary tech jargon)
 *  - Offer a "Try Again" button that reloads the page
 *  - Log the error to console so developers can debug
 *
 * Out of scope:
 *  - Sentry / remote error reporting
 *  - Recovering from async errors thrown outside React render
 */
class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  static isTransientBootstrapError = isTransientBootstrapError

  state: ErrorBoundaryState = {
    hasError: false,
    error: null,
  }

  componentDidMount(): void {
    // A successful mount proves that any prior bootstrap retry recovered.
    try {
      window.sessionStorage.removeItem(BOOTSTRAP_RECOVERY_KEY)
    } catch {
      // Ignore storage failures; the boundary still provides its fallback.
    }
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    // Update state so the next render shows the fallback UI.
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Log so developers can debug. No remote reporting (out of scope).
    console.error('ErrorBoundary caught an error:', error, errorInfo)

    if (isTransientBootstrapError(error)) {
      attemptBootstrapRecovery()
    }
  }

  handleReload = (): void => {
    if (this.props.onReload) {
      this.props.onReload()
      return
    }
    if (typeof window !== 'undefined') {
      window.location.reload()
    }
  }

  render(): ReactNode {
    if (!this.state.hasError) {
      return this.props.children
    }

    return (
      <div
        role="alert"
        className="min-h-screen flex items-center justify-center p-6 bg-gradient-to-br from-primary/5 to-accent/10"
      >
        <Card variant="elevated" padding="lg" hover={false} className="max-w-md w-full text-center">
          <div className="text-6xl mb-4" aria-hidden="true">
            🎨
          </div>
          <CardTitle className="text-2xl">Oops! Something went wrong</CardTitle>
          <CardContent className="mt-3 text-base">
            <p>Don&apos;t worry — these things happen sometimes.</p>
            <p className="mt-2">Let&apos;s try that again together!</p>
          </CardContent>
          <CardFooter className="flex justify-center">
            <Button variant="primary" size="lg" onClick={this.handleReload}>
              Try Again
            </Button>
          </CardFooter>
        </Card>
      </div>
    )
  }
}

export default ErrorBoundary
