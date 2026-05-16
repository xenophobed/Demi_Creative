/**
 * Pure state transitions for the responsive mobile navbar drawer.
 *
 * The drawer is only visible on viewports < 768px (Tailwind's `md` breakpoint).
 * Keeping the transitions as plain functions lets us unit-test the contract
 * without needing @testing-library/react. The component (PageContainer)
 * stores `open` in useState and applies these helpers in event handlers.
 *
 * Invariants (locked by tests):
 *   - openMenu()  -> always returns true
 *   - closeMenu() -> always returns false
 *   - toggleMenu(prev) -> returns !prev
 *
 * If a future change accidentally inverts toggle semantics or breaks the
 * close-on-link-click behaviour, the tests should flip red before users do.
 */
export type MobileMenuState = boolean

export const openMenu = (): MobileMenuState => true
export const closeMenu = (): MobileMenuState => false
export const toggleMenu = (prev: MobileMenuState): MobileMenuState => !prev
