import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface DailyTaskState {
  // Persisted state
  claimHistory: string[]  // ISO date strings: ["2026-04-08", "2026-04-09"]
  totalStars: number

  // Actions
  canClaimToday: () => boolean
  claimStar: () => void
  getWeekProgress: () => { claimed: number; target: number }
  getStreak: () => number
}

function toDateStr(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function getToday(): string {
  return toDateStr(new Date())
}

/**
 * Returns the Monday of the week containing the given date string.
 * Week runs Mon–Sun.
 */
function getWeekStart(dateStr: string): string {
  const date = new Date(dateStr + 'T00:00:00')
  const day = date.getDay()
  // JS getDay(): 0=Sun, 1=Mon...6=Sat → offset to Monday
  const offset = day === 0 ? 6 : day - 1
  date.setDate(date.getDate() - offset)
  return toDateStr(date)
}

const useDailyTaskStore = create<DailyTaskState>()(
  persist(
    (set, get) => ({
      claimHistory: [],
      totalStars: 0,

      canClaimToday: () => {
        const today = getToday()
        return !get().claimHistory.includes(today)
      },

      claimStar: () => {
        const today = getToday()
        const { claimHistory, totalStars } = get()
        if (claimHistory.includes(today)) return // idempotent
        set({
          claimHistory: [...claimHistory, today],
          totalStars: totalStars + 1,
        })
      },

      getWeekProgress: () => {
        const today = getToday()
        const weekStart = getWeekStart(today)
        const claimed = get().claimHistory.filter(
          (date) => date >= weekStart && date <= today
        ).length
        return { claimed, target: 7 }
      },

      getStreak: () => {
        const { claimHistory } = get()
        if (claimHistory.length === 0) return 0

        const sorted = [...claimHistory].sort().reverse()
        const today = getToday()

        // Streak must include today or yesterday to be active
        const yesterday = new Date()
        yesterday.setDate(yesterday.getDate() - 1)
        const yesterdayStr = toDateStr(yesterday)

        if (sorted[0] !== today && sorted[0] !== yesterdayStr) return 0

        let streak = 1
        for (let i = 1; i < sorted.length; i++) {
          const prev = new Date(sorted[i - 1] + 'T00:00:00')
          const curr = new Date(sorted[i] + 'T00:00:00')
          const diffDays = (prev.getTime() - curr.getTime()) / (1000 * 60 * 60 * 24)
          if (diffDays === 1) {
            streak++
          } else {
            break
          }
        }
        return streak
      },
    }),
    {
      name: 'daily-task-storage',
      partialize: (state) => ({
        claimHistory: state.claimHistory,
        totalStars: state.totalStars,
      }),
    }
  )
)

export default useDailyTaskStore
