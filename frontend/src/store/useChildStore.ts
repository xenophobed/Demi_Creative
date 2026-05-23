import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { childProfileService } from '@/api/services/childProfileService'
import type {
  AgeGroup,
  ChildProfile,
  ChildProfileCreateRequest,
  ChildProfileUpdateRequest,
} from '@/types/api'

interface ChildState {
  // Current child profile
  currentChild: ChildProfile | null

  // Server-backed profiles for parent accounts
  childProfiles: ChildProfile[]

  // Active child ID selected by this browser/session
  activeChildId: string | null

  // Default child ID (simplified version, can support multiple children)
  defaultChildId: string

  isLoading: boolean
  error: string | null

  // Actions
  setCurrentChild: (child: ChildProfile) => void
  configureChildProfile: (child: ChildProfile) => void
  updateChildProfile: (updates: Partial<ChildProfile>) => void
  setAgeGroup: (ageGroup: AgeGroup) => void
  setInterests: (interests: string[]) => void
  addInterest: (interest: string) => void
  removeInterest: (interest: string) => void
  clearChild: () => void
  // Hydrate defaultChildId from a server-side source (e.g. user.default_child_id
  // returned by GET /me). Only applied when the incoming id differs — never
  // clobbers an existing localStorage value with a null/undefined input. (#455)
  setDefaultChildId: (childId: string | null | undefined) => void
  setChildProfiles: (profiles: ChildProfile[]) => void
  loadChildProfiles: () => Promise<void>
  createChildProfile: (payload: ChildProfileCreateRequest) => Promise<ChildProfile>
  saveChildProfile: (childId: string, payload: ChildProfileUpdateRequest) => Promise<ChildProfile>
  archiveChildProfile: (childId: string) => Promise<ChildProfile>
  setDefaultChildProfile: (childId: string) => Promise<ChildProfile>
  switchActiveChild: (childId: string) => void
}

// Generate simple unique ID
export function generateChildId(): string {
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
      childProfiles: [],
      activeChildId: null,
      defaultChildId: generateChildId(),
      isLoading: false,
      error: null,

      setCurrentChild: (child) => set({
        currentChild: child,
        activeChildId: child.child_id,
        defaultChildId: child.is_default ? child.child_id : get().defaultChildId,
      }),

      configureChildProfile: (child) => set({
        currentChild: child,
        activeChildId: child.child_id,
        defaultChildId: child.child_id,
        childProfiles: mergeProfile(get().childProfiles, child),
      }),

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
        childProfiles: [],
        activeChildId: null,
        defaultChildId: generateChildId(),
        error: null,
      }),

      setDefaultChildId: (childId) => {
        if (!childId) return
        if (get().defaultChildId === childId) return
        const matchingProfile = get().childProfiles.find((child) => child.child_id === childId)
        set({
          defaultChildId: childId,
          currentChild: matchingProfile ?? get().currentChild,
          activeChildId: matchingProfile ? childId : get().activeChildId,
        })
      },

      setChildProfiles: (profiles) => {
        const activeProfiles = profiles.filter((profile) => !profile.archived_at)
        const state = get()
        const selected = selectActiveChild(
          activeProfiles,
          state.activeChildId,
          state.currentChild?.child_id,
          state.defaultChildId,
        )
        const defaultProfile = activeProfiles.find((profile) => profile.is_default)

        set({
          childProfiles: profiles,
          currentChild: selected,
          activeChildId: selected?.child_id ?? null,
          defaultChildId: defaultProfile?.child_id ?? state.defaultChildId,
          error: null,
        })
      },

      loadChildProfiles: async () => {
        set({ isLoading: true, error: null })
        try {
          const response = await childProfileService.list()
          get().setChildProfiles(response.items)
        } catch (err) {
          const message = err instanceof Error ? err.message : 'Unable to load child profiles'
          set({ error: message })
          throw err
        } finally {
          set({ isLoading: false })
        }
      },

      createChildProfile: async (payload) => {
        const created = await childProfileService.create(payload)
        const profiles = mergeProfile(get().childProfiles, created)
        get().setChildProfiles(profiles)
        if (profiles.filter((profile) => !profile.archived_at).length === 1 || created.is_default) {
          get().switchActiveChild(created.child_id)
        }
        return created
      },

      saveChildProfile: async (childId, payload) => {
        const updated = await childProfileService.update(childId, payload)
        get().setChildProfiles(mergeProfile(get().childProfiles, updated))
        return updated
      },

      archiveChildProfile: async (childId) => {
        const archived = await childProfileService.archive(childId)
        get().setChildProfiles(mergeProfile(get().childProfiles, archived))
        return archived
      },

      setDefaultChildProfile: async (childId) => {
        const updated = await childProfileService.setDefault(childId)
        const profiles = get().childProfiles.map((profile) => ({
          ...profile,
          is_default: profile.child_id === updated.child_id,
        }))
        get().setChildProfiles(mergeProfile(profiles, updated))
        get().switchActiveChild(updated.child_id)
        return updated
      },

      switchActiveChild: (childId) => {
        const child = get().childProfiles.find(
          (profile) => profile.child_id === childId && !profile.archived_at,
        )
        if (!child) return
        set({ currentChild: child, activeChildId: child.child_id })
      },
    }),
    {
      name: 'child-storage',
      partialize: (state) => ({
        currentChild: state.currentChild,
        childProfiles: state.childProfiles,
        activeChildId: state.activeChildId,
        defaultChildId: state.defaultChildId,
      }),
    }
  )
)

export default useChildStore

function mergeProfile(profiles: ChildProfile[], profile: ChildProfile): ChildProfile[] {
  const found = profiles.some((item) => item.child_id === profile.child_id)
  if (!found) return [...profiles, profile]
  return profiles.map((item) => item.child_id === profile.child_id ? profile : item)
}

function selectActiveChild(
  activeProfiles: ChildProfile[],
  activeChildId: string | null,
  currentChildId: string | undefined,
  defaultChildId: string,
): ChildProfile | null {
  if (activeProfiles.length === 0) return null
  if (activeProfiles.length === 1) return activeProfiles[0]

  const preferredId = activeChildId || currentChildId
  const preferred = preferredId
    ? activeProfiles.find((profile) => profile.child_id === preferredId)
    : null
  if (preferred) return preferred

  const serverDefault = activeProfiles.find((profile) => profile.is_default)
  if (serverDefault) return serverDefault

  const localDefault = activeProfiles.find((profile) => profile.child_id === defaultChildId)
  return localDefault ?? activeProfiles[0]
}
