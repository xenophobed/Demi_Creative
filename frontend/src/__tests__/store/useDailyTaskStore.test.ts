import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import useDailyTaskStore from '../../store/useDailyTaskStore'

function resetStore() {
  useDailyTaskStore.setState({ claimHistory: [], totalStars: 0, lastClaimTimestamp: null })
}

describe('useDailyTaskStore', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-04-08T10:00:00'))
    localStorage.clear()
    resetStore()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('fresh state', () => {
    it('canClaimToday returns true', () => {
      expect(useDailyTaskStore.getState().canClaimToday()).toBe(true)
    })

    it('totalStars is 0', () => {
      expect(useDailyTaskStore.getState().totalStars).toBe(0)
    })

    it('claimHistory is empty', () => {
      expect(useDailyTaskStore.getState().claimHistory).toEqual([])
    })
  })

  describe('claimStar', () => {
    it('marks today as claimed and records timestamp', () => {
      useDailyTaskStore.getState().claimStar()
      const state = useDailyTaskStore.getState()
      expect(state.canClaimToday()).toBe(false)
      expect(state.totalStars).toBe(1)
      expect(state.claimHistory).toContain('2026-04-08')
      expect(state.lastClaimTimestamp).toBe(Date.now())
    })

    it('is idempotent — second call on same day is a no-op', () => {
      useDailyTaskStore.getState().claimStar()
      useDailyTaskStore.getState().claimStar()
      const state = useDailyTaskStore.getState()
      expect(state.totalStars).toBe(1)
      expect(state.claimHistory).toEqual(['2026-04-08'])
    })

    it('allows claiming on a new day', () => {
      useDailyTaskStore.getState().claimStar()
      vi.setSystemTime(new Date('2026-04-09T10:00:00'))
      expect(useDailyTaskStore.getState().canClaimToday()).toBe(true)
      useDailyTaskStore.getState().claimStar()
      expect(useDailyTaskStore.getState().totalStars).toBe(2)
    })
  })

  describe('getWeekProgress', () => {
    it('returns 0/7 with no claims', () => {
      expect(useDailyTaskStore.getState().getWeekProgress()).toEqual({
        claimed: 0,
        target: 7,
      })
    })

    it('counts claims in current Mon-Sun week', () => {
      // 2026-04-06 is Monday, 2026-04-08 is Wednesday
      vi.setSystemTime(new Date('2026-04-06T10:00:00'))
      useDailyTaskStore.getState().claimStar()

      vi.setSystemTime(new Date('2026-04-07T10:00:00'))
      useDailyTaskStore.getState().claimStar()

      vi.setSystemTime(new Date('2026-04-08T10:00:00'))
      useDailyTaskStore.getState().claimStar()

      expect(useDailyTaskStore.getState().getWeekProgress()).toEqual({
        claimed: 3,
        target: 7,
      })
    })

    it('does not count claims from previous week', () => {
      // 2026-04-05 is Sunday (previous week)
      vi.setSystemTime(new Date('2026-04-05T10:00:00'))
      useDailyTaskStore.getState().claimStar()

      // 2026-04-06 is Monday (current week)
      vi.setSystemTime(new Date('2026-04-06T10:00:00'))
      useDailyTaskStore.getState().claimStar()

      expect(useDailyTaskStore.getState().getWeekProgress()).toEqual({
        claimed: 1,
        target: 7,
      })
    })
  })

  describe('getStreak', () => {
    it('returns 0 with no claims', () => {
      expect(useDailyTaskStore.getState().getStreak()).toBe(0)
    })

    it('returns 1 after claiming today', () => {
      useDailyTaskStore.getState().claimStar()
      expect(useDailyTaskStore.getState().getStreak()).toBe(1)
    })

    it('counts consecutive days', () => {
      vi.setSystemTime(new Date('2026-04-06T10:00:00'))
      useDailyTaskStore.getState().claimStar()
      vi.setSystemTime(new Date('2026-04-07T10:00:00'))
      useDailyTaskStore.getState().claimStar()
      vi.setSystemTime(new Date('2026-04-08T10:00:00'))
      useDailyTaskStore.getState().claimStar()
      expect(useDailyTaskStore.getState().getStreak()).toBe(3)
    })

    it('resets streak when a day is skipped', () => {
      vi.setSystemTime(new Date('2026-04-06T10:00:00'))
      useDailyTaskStore.getState().claimStar()
      // skip April 7
      vi.setSystemTime(new Date('2026-04-08T10:00:00'))
      useDailyTaskStore.getState().claimStar()
      expect(useDailyTaskStore.getState().getStreak()).toBe(1)
    })

    it('includes yesterday if today is not yet claimed', () => {
      vi.setSystemTime(new Date('2026-04-07T10:00:00'))
      useDailyTaskStore.getState().claimStar()
      vi.setSystemTime(new Date('2026-04-08T10:00:00'))
      // not claimed today, but yesterday counts
      expect(useDailyTaskStore.getState().getStreak()).toBe(1)
    })

    it('returns 0 if last claim was 2+ days ago', () => {
      vi.setSystemTime(new Date('2026-04-05T10:00:00'))
      useDailyTaskStore.getState().claimStar()
      vi.setSystemTime(new Date('2026-04-08T10:00:00'))
      expect(useDailyTaskStore.getState().getStreak()).toBe(0)
    })
  })

  describe('persistence', () => {
    it('writes to daily-task-storage key in localStorage', () => {
      useDailyTaskStore.getState().claimStar()
      const stored = localStorage.getItem('daily-task-storage')
      expect(stored).not.toBeNull()
      const parsed = JSON.parse(stored!)
      expect(parsed.state.claimHistory).toContain('2026-04-08')
      expect(parsed.state.totalStars).toBe(1)
    })
  })
})
