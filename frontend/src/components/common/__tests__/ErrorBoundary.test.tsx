import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { ErrorInfo } from 'react'
import ErrorBoundary from '../ErrorBoundary'

/**
 * Logic-only tests for the global ErrorBoundary.
 *
 * The project does not ship @testing-library/react, so instead of rendering
 * we exercise the class lifecycle directly. This is sufficient because the
 * behavior contract is encoded in `getDerivedStateFromError` (state
 * transition) and `componentDidCatch` (logging side effect) — neither
 * requires a DOM to verify.
 */
describe('ErrorBoundary', () => {
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    consoleErrorSpy.mockRestore()
  })

  it('initializes with hasError=false and no error', () => {
    // Construct without rendering: state defaults are the contract.
    const instance = new ErrorBoundary({ children: null })
    expect(instance.state.hasError).toBe(false)
    expect(instance.state.error).toBeNull()
  })

  it('getDerivedStateFromError flips hasError=true and stores the error', () => {
    const boom = new Error('kaboom')
    const next = ErrorBoundary.getDerivedStateFromError(boom)
    expect(next).toEqual({ hasError: true, error: boom })
  })

  it('recognizes the transient stream-provider bootstrap error', () => {
    expect(
      ErrorBoundary.isTransientBootstrapError(
        new Error('useStreamVisualizationContext must be used within a StreamVisualizationProvider'),
      ),
    ).toBe(true)
    expect(ErrorBoundary.isTransientBootstrapError(new Error('unrelated render failure'))).toBe(false)
  })

  it('componentDidCatch logs the error and errorInfo to console.error', () => {
    const instance = new ErrorBoundary({ children: null })
    const err = new Error('render exploded')
    const info: ErrorInfo = { componentStack: '\n  in Component' }

    instance.componentDidCatch(err, info)

    expect(consoleErrorSpy).toHaveBeenCalledTimes(1)
    expect(consoleErrorSpy).toHaveBeenCalledWith(
      'ErrorBoundary caught an error:',
      err,
      info,
    )
  })

  it('retries a transient bootstrap failure only once within the recovery window', () => {
    const values = new Map<string, string>()
    const reload = vi.fn()
    vi.stubGlobal('window', {
      sessionStorage: {
        getItem: (key: string) => values.get(key) ?? null,
        setItem: (key: string, value: string) => values.set(key, value),
        removeItem: (key: string) => values.delete(key),
      },
      location: { reload },
    })

    const instance = new ErrorBoundary({ children: null })
    const error = new Error(
      'useStreamVisualizationContext must be used within a StreamVisualizationProvider',
    )
    const info: ErrorInfo = { componentStack: '' }

    instance.componentDidCatch(error, info)
    instance.componentDidCatch(error, info)

    expect(reload).toHaveBeenCalledTimes(1)
    vi.unstubAllGlobals()
  })

  it('handleReload invokes the onReload override when provided', () => {
    const onReload = vi.fn()
    const instance = new ErrorBoundary({ children: null, onReload })
    instance.handleReload()
    expect(onReload).toHaveBeenCalledTimes(1)
  })
})
