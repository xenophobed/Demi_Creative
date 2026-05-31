import { describe, it, expect } from 'vitest'
import { TOUCH_DEVICE_QUERY } from '@/components/upload/ImageUploader'

describe('ImageUploader: TOUCH_DEVICE_QUERY', () => {
  it('matches the PRD §3.15 acceptance criterion exactly', () => {
    expect(TOUCH_DEVICE_QUERY).toBe('(pointer: coarse) and (max-width: 1024px)')
  })

  it('targets touch-input devices via pointer: coarse', () => {
    expect(TOUCH_DEVICE_QUERY).toContain('pointer: coarse')
  })

  it('excludes large desktop displays via max-width breakpoint', () => {
    expect(TOUCH_DEVICE_QUERY).toContain('max-width: 1024px')
  })
})
