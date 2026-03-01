import { useState, useCallback } from 'react'

export type ViewMode = 'grid' | 'list'

const STORAGE_KEY = 'library-view-mode'

function getStoredViewMode(): ViewMode {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'grid' || stored === 'list') return stored
  } catch {
    // localStorage unavailable
  }
  return 'grid'
}

export function useLibraryPreferences() {
  const [viewMode, setViewModeState] = useState<ViewMode>(getStoredViewMode)

  const setViewMode = useCallback((mode: ViewMode) => {
    setViewModeState(mode)
    try {
      localStorage.setItem(STORAGE_KEY, mode)
    } catch {
      // localStorage unavailable
    }
  }, [])

  const toggleViewMode = useCallback(() => {
    setViewMode(viewMode === 'grid' ? 'list' : 'grid')
  }, [viewMode, setViewMode])

  return { viewMode, setViewMode, toggleViewMode }
}
