import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { AgeGroup, ChildProfile } from '@/types/api'

interface ChildState {
  // Current child profile
  currentChild: ChildProfile | null

  // Default child ID (simplified version, can support multiple children)
  defaultChildId: string

  // Actions
  setCurrentChild: (child: ChildProfile) => void
  updateChildProfile: (updates: Partial<ChildProfile>) => void
  setAgeGroup: (ageGroup: AgeGroup) => void
  setInterests: (interests: string[]) => void
  addInterest: (interest: string) => void
  removeInterest: (interest: string) => void
  clearChild: () => void
}

// Generate simple unique ID
function generateChildId(): string {
  return `child_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
}

// Default interest tags
export const DEFAULT_INTERESTS = [
  'Animals',
  'Dinosaurs',
  'Princess',
  'Space',
  'Ocean',
  'Forest',
  'Magic',
  'Superheroes',
  'Robots',
  'Music',
  'Sports',
  'Food',
]

const useChildStore = create<ChildState>()(
  persist(
    (set, get) => ({
      currentChild: null,
      defaultChildId: generateChildId(),

      setCurrentChild: (child) => set({ currentChild: child }),

      updateChildProfile: (updates) => {
        const current = get().currentChild
        if (current) {
          set({ currentChild: { ...current, ...updates } })
        }
      },

      setAgeGroup: (ageGroup) => {
        const current = get().currentChild
        if (current) {
          set({ currentChild: { ...current, age_group: ageGroup } })
        } else {
          // Create new child profile
          set({
            currentChild: {
              child_id: get().defaultChildId,
              name: 'Little Artist',
              age_group: ageGroup,
              interests: [],
            }
          })
        }
      },

      setInterests: (interests) => {
        const current = get().currentChild
        if (current) {
          set({ currentChild: { ...current, interests } })
        }
      },

      addInterest: (interest) => {
        const current = get().currentChild
        if (current && !current.interests.includes(interest)) {
          set({
            currentChild: {
              ...current,
              interests: [...current.interests, interest].slice(0, 5), // Max 5
            }
          })
        }
      },

      removeInterest: (interest) => {
        const current = get().currentChild
        if (current) {
          set({
            currentChild: {
              ...current,
              interests: current.interests.filter(i => i !== interest),
            }
          })
        }
      },

      clearChild: () => set({
        currentChild: null,
        defaultChildId: generateChildId(),
      }),
    }),
    {
      name: 'child-storage',
    }
  )
)

export default useChildStore
