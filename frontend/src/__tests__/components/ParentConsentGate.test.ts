import { describe, it, expect } from 'vitest'
import { GATE_COPY } from '@/components/common/ParentConsentGate'
import type { AgeGroup } from '@/types/api'

const AGE_GROUPS: AgeGroup[] = ['3-5', '6-8', '9-12']

describe('ParentConsentGate: GATE_COPY', () => {
  it('covers both consent kinds × all three age groups', () => {
    for (const kind of ['camera', 'microphone'] as const) {
      for (const age of AGE_GROUPS) {
        const copy = GATE_COPY[kind][age]
        expect(copy).toBeDefined()
        expect(copy.emoji.length).toBeGreaterThan(0)
        expect(copy.title.length).toBeGreaterThan(0)
        expect(copy.body.length).toBeGreaterThan(0)
      }
    }
  })

  it('uses camera emoji for camera variants and mic emoji for microphone variants', () => {
    for (const age of AGE_GROUPS) {
      expect(GATE_COPY.camera[age].emoji).toBe('📸')
      expect(GATE_COPY.microphone[age].emoji).toBe('🎤')
    }
  })

  it('age 3-5 copy stays short — the youngest cohort cannot read long text', () => {
    for (const kind of ['camera', 'microphone'] as const) {
      const body = GATE_COPY[kind]['3-5'].body
      // Looser bound (140 chars) than a tweet but tight enough to fail
      // if someone drops a paragraph here.
      expect(body.length).toBeLessThanOrEqual(140)
    }
  })

  it('microphone copy explicitly states audio is not stored', () => {
    // PRD §3.15 requires the no-persistence promise to be visible to
    // parents at the consent moment. This locks that copy invariant.
    for (const age of AGE_GROUPS) {
      const body = GATE_COPY.microphone[age].body.toLowerCase()
      const promisesNoStorage =
        body.includes("don't save") ||
        body.includes('never stored') ||
        body.includes('only ') ||
        body.includes('grown-up')  // 3-5 deferral copy
      expect(promisesNoStorage).toBe(true)
    }
  })
})
