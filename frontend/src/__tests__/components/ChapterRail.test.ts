import { describe, it, expect } from 'vitest'
import {
  computeDotSize,
  computeDotOpacity,
} from '@/components/interactive/ChapterRail'

describe('computeDotSize', () => {
  it('returns the default max (16) at distance 0', () => {
    expect(computeDotSize(0)).toBe(16)
  })

  it('returns the default min (6) at the falloff edge (distance 4)', () => {
    expect(computeDotSize(4)).toBe(6)
  })

  it('clamps to the default min (6) beyond the falloff distance', () => {
    expect(computeDotSize(10)).toBe(6)
  })

  it('returns the linear midpoint (11) at distance 2 with default opts', () => {
    expect(computeDotSize(2)).toBe(11)
  })

  it('mirrors negative distances on absolute value', () => {
    expect(computeDotSize(-2)).toBe(computeDotSize(2))
  })

  it('honors custom max at distance 0', () => {
    expect(computeDotSize(0, { min: 4, max: 20, falloff: 8 })).toBe(20)
  })

  it('honors custom min at the custom falloff edge', () => {
    expect(computeDotSize(8, { min: 4, max: 20, falloff: 8 })).toBe(4)
  })
})

describe('computeDotOpacity', () => {
  it('returns the default max (1.0) at distance 0', () => {
    expect(computeDotOpacity(0)).toBe(1)
  })

  it('returns the default min (0.4) at the falloff edge (distance 4)', () => {
    expect(computeDotOpacity(4)).toBe(0.4)
  })

  it('returns ~0.7 at the linear midpoint (distance 2)', () => {
    // Floating-point tolerance: 0.4 + (1 - 0.4) * (1 - 2/4) = 0.7.
    expect(computeDotOpacity(2)).toBeCloseTo(0.7, 5)
  })

  it('is monotonically non-increasing as |distance| grows from 0 to 6', () => {
    let prev = Infinity
    for (let d = 0; d <= 6; d += 0.5) {
      const next = computeDotOpacity(d)
      expect(next).toBeLessThanOrEqual(prev)
      prev = next
    }
  })
})
