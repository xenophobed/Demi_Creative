import { describe, expect, it } from 'vitest'
import { CAMERA_ERROR_COPY, classifyCameraError } from '@/hooks/cameraErrors'

describe('classifyCameraError', () => {
  it('maps NotAllowedError → permission_denied', () => {
    expect(classifyCameraError({ name: 'NotAllowedError' })).toBe('permission_denied')
  })

  it('maps SecurityError → permission_denied (older Safari)', () => {
    expect(classifyCameraError({ name: 'SecurityError' })).toBe('permission_denied')
  })

  it('maps NotFoundError → no_device', () => {
    expect(classifyCameraError({ name: 'NotFoundError' })).toBe('no_device')
  })

  it('maps NotReadableError → device_busy', () => {
    expect(classifyCameraError({ name: 'NotReadableError' })).toBe('device_busy')
  })

  it('maps TrackStartError → device_busy (legacy)', () => {
    expect(classifyCameraError({ name: 'TrackStartError' })).toBe('device_busy')
  })

  it('maps OverconstrainedError → overconstrained', () => {
    expect(classifyCameraError({ name: 'OverconstrainedError' })).toBe('overconstrained')
  })

  it('maps AbortError → aborted', () => {
    expect(classifyCameraError({ name: 'AbortError' })).toBe('aborted')
  })

  it('falls back to unknown for unmapped errors', () => {
    expect(classifyCameraError({ name: 'TotallyMadeUpError' })).toBe('unknown')
    expect(classifyCameraError(new Error('boom'))).toBe('unknown')
  })

  it('handles null and primitives without throwing', () => {
    expect(classifyCameraError(null)).toBe('unknown')
    expect(classifyCameraError(undefined)).toBe('unknown')
    expect(classifyCameraError('a string')).toBe('unknown')
  })
})

describe('CAMERA_ERROR_COPY', () => {
  it('provides a non-empty user-facing message for every error kind', () => {
    const kinds = [
      'permission_denied',
      'no_device',
      'device_busy',
      'overconstrained',
      'unsupported',
      'aborted',
      'unknown',
    ] as const
    for (const kind of kinds) {
      expect(CAMERA_ERROR_COPY[kind]).toBeDefined()
      expect(CAMERA_ERROR_COPY[kind].length).toBeGreaterThan(10)
    }
  })

  it('permission_denied copy mentions browser permission', () => {
    expect(CAMERA_ERROR_COPY.permission_denied.toLowerCase()).toContain('permission')
  })
})
