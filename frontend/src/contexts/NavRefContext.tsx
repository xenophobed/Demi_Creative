import { createContext, useContext, useRef, useCallback, type RefObject } from 'react'

interface NavRefContextValue {
  profileAvatarRef: RefObject<HTMLDivElement | null>
  setProfileAvatarEl: (el: HTMLDivElement | null) => void
}

const NavRefContext = createContext<NavRefContextValue | null>(null)

export function NavRefProvider({ children }: { children: React.ReactNode }) {
  const profileAvatarRef = useRef<HTMLDivElement | null>(null)
  const setProfileAvatarEl = useCallback((el: HTMLDivElement | null) => {
    profileAvatarRef.current = el
  }, [])
  return (
    <NavRefContext.Provider value={{ profileAvatarRef, setProfileAvatarEl }}>
      {children}
    </NavRefContext.Provider>
  )
}

export function useNavRef() {
  const ctx = useContext(NavRefContext)
  if (!ctx) throw new Error('useNavRef must be used within NavRefProvider')
  return ctx
}
