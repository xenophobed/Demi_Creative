/**
 * Centralized logout — resets all Zustand stores and clears persisted storage.
 *
 * Called on explicit logout AND on 401 responses so that in-memory
 * Zustand state stays in sync with what the server considers valid.
 */

import useAuthStore from '@/store/useAuthStore'
import useChildStore from '@/store/useChildStore'
import useInteractiveStoryStore from '@/store/useInteractiveStoryStore'

export function performFullLogout(): void {
  // 1. Reset every Zustand store that holds user-scoped data
  useAuthStore.getState().logout()
  useChildStore.getState().clearChild()
  useInteractiveStoryStore.getState().reset()

  // 2. Belt-and-suspenders: remove the persisted storage keys directly
  //    in case a store's persist middleware doesn't fire synchronously.
  localStorage.removeItem('auth-storage')
  localStorage.removeItem('child-storage')
  sessionStorage.removeItem('interactive-story-session')
}
