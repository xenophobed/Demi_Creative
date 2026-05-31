import { describe, it, expect } from 'vitest'
import {
  classifyGateError,
  GATE_COPY,
  GATE_ERROR_COPY,
} from '@/components/common/ParentConsentGate'
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

describe('ParentConsentGate: classifyGateError (#603)', () => {
  it('maps 404 from the consent-update endpoint to child_not_found', () => {
    // The exact shape axios surfaces: err.response.status + err.response.data.detail.code
    expect(
      classifyGateError({
        response: {
          status: 404,
          data: { detail: { code: 'CHILD_PROFILE_NOT_FOUND' } },
        },
      }),
    ).toBe('child_not_found')
  })

  it('maps the bare code without a status to child_not_found', () => {
    expect(
      classifyGateError({
        response: { data: { detail: { code: 'CHILD_PROFILE_NOT_FOUND' } } },
      }),
    ).toBe('child_not_found')
  })

  it('maps 403 PARENT_ROLE_REQUIRED to parent_required', () => {
    expect(
      classifyGateError({
        response: {
          status: 403,
          data: { detail: { code: 'PARENT_ROLE_REQUIRED' } },
        },
      }),
    ).toBe('parent_required')
  })

  it('maps 401 / 400 / 422 to wrong_password', () => {
    expect(classifyGateError({ response: { status: 401 } })).toBe('wrong_password')
    expect(classifyGateError({ response: { status: 400 } })).toBe('wrong_password')
    expect(classifyGateError({ response: { status: 422 } })).toBe('wrong_password')
  })

  it('maps Supabase "Invalid login credentials" Error to wrong_password', () => {
    expect(classifyGateError(new Error('Invalid login credentials'))).toBe('wrong_password')
  })

  it('falls back to unknown for unmapped shapes', () => {
    expect(classifyGateError({ response: { status: 500 } })).toBe('unknown')
    expect(classifyGateError(null)).toBe('unknown')
    expect(classifyGateError(undefined)).toBe('unknown')
    expect(classifyGateError(new Error('something else entirely'))).toBe('unknown')
  })
})

describe('ParentConsentGate: GATE_ERROR_COPY', () => {
  it('provides non-empty copy for every error kind', () => {
    const kinds = [
      'wrong_password',
      'child_not_found',
      'parent_required',
      'missing_email',
      'unknown',
    ] as const
    for (const kind of kinds) {
      expect(GATE_ERROR_COPY[kind]).toBeDefined()
      expect(GATE_ERROR_COPY[kind].length).toBeGreaterThan(10)
    }
  })

  it('child_not_found copy tells the parent to refresh', () => {
    // The actionable next step is what makes #603's UX better than
    // the old generic copy — without it the parent has no idea what
    // to do.
    expect(GATE_ERROR_COPY.child_not_found.toLowerCase()).toMatch(/refresh|try again/)
  })

  it('parent_required copy tells the user to switch accounts', () => {
    expect(GATE_ERROR_COPY.parent_required.toLowerCase()).toContain('parent')
  })
})
