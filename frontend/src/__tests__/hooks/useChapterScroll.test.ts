import { describe, it, expect } from 'vitest'
import { computeScrollProgress } from '@/hooks/useChapterScroll'

const fakeNode = (centerY: number, height = 100) => ({
  getBoundingClientRect: () =>
    ({
      top: centerY - height / 2,
      height,
      left: 0,
      right: 0,
      bottom: centerY + height / 2,
      width: 0,
      x: 0,
      y: centerY - height / 2,
      toJSON: () => ({}),
    }) as DOMRect,
})

describe('computeScrollProgress', () => {
  it('returns 0 for an empty list', () => {
    expect(computeScrollProgress([], 100)).toBe(0)
  })

  it('returns 0 for a single-node list regardless of position', () => {
    expect(computeScrollProgress([fakeNode(0)], 500)).toBe(0)
    expect(computeScrollProgress([fakeNode(1000)], 500)).toBe(0)
    expect(computeScrollProgress([fakeNode(500)], 500)).toBe(0)
  })

  it('returns the exact index when one node is centered on targetY', () => {
    // Two nodes; targetY sits exactly on the second node's center.
    const nodes = [fakeNode(100), fakeNode(300)]
    expect(computeScrollProgress(nodes, 300)).toBe(1)
    expect(computeScrollProgress(nodes, 100)).toBe(0)
  })

  it('interpolates to 0.5 at the midpoint between two node centers', () => {
    const nodes = [fakeNode(100), fakeNode(300)]
    expect(computeScrollProgress(nodes, 200)).toBe(0.5)
  })

  it('interpolates to 0.25 at the quarter point between two node centers', () => {
    const nodes = [fakeNode(100), fakeNode(300)]
    expect(computeScrollProgress(nodes, 150)).toBe(0.25)
  })

  it('returns the highest above-index when all nodes are above targetY', () => {
    // All centers above (smaller than) targetY=1000.
    const nodes = [fakeNode(100), fakeNode(300), fakeNode(500)]
    expect(computeScrollProgress(nodes, 1000)).toBe(2)
  })

  it('returns the lowest below-index when all nodes are below targetY', () => {
    // All centers below (larger than) targetY=0.
    const nodes = [fakeNode(100), fakeNode(300), fakeNode(500)]
    expect(computeScrollProgress(nodes, 0)).toBe(0)
  })

  it('is monotonic across a synthetic scroll sweep', () => {
    // Three nodes at centers 100, 500, 900. As targetY moves down (0 → 1000),
    // progress should never decrease. Note that as targetY increases, nodes
    // appear to move "up" relative to the line, so progress climbs from
    // index 0 toward index 2.
    const nodes = [fakeNode(100), fakeNode(500), fakeNode(900)]
    let prev = -Infinity
    for (let targetY = 0; targetY <= 1000; targetY += 50) {
      const next = computeScrollProgress(nodes, targetY)
      expect(next).toBeGreaterThanOrEqual(prev)
      prev = next
    }
  })
})
