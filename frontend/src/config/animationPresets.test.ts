import { describe, it, expect } from 'vitest'
import { defaultParallaxConfig, defaultTiltConfig } from './animationPresets'

/**
 * Issue #735 — replace heavy mouse-tracking 3D with subtle CSS micro-interactions.
 *
 * These defaults are the global lever consumed by useParallax / useTilt /
 * PerspectiveContainer / Card. Keeping them disabled (and the residual angles
 * small) guarantees we don't reintroduce full-3D tilt on every card and button.
 */
describe('animation defaults — subtle by default (#735)', () => {
  it('disables mouse-tracking card tilt by default', () => {
    expect(defaultTiltConfig.enabled).toBe(false)
  })

  it('disables mouse-tracking parallax rotation by default', () => {
    expect(defaultParallaxConfig.enabled).toBe(false)
  })

  it('keeps any residual tilt gentle (<= 4 degrees)', () => {
    expect(defaultTiltConfig.maxTilt).toBeLessThanOrEqual(4)
    expect(defaultParallaxConfig.maxRotation).toBeLessThanOrEqual(4)
  })
})
