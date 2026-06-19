/**
 * Kids Daily generation manager (#727).
 *
 * Owns the AbortController and post-completion navigation at *module*
 * scope so an on-demand episode keeps generating — and still opens when
 * it finishes — even if the user navigates away from KidsDailyPage mid
 * generation. Progress state lives in `useKidsDailyGenerationStore`.
 *
 * Mirrors `storyGenerationManager`: React Router's navigate is registered
 * once (via `useGenerationNavigator`) and a completion that fires while no
 * navigate is registered is queued in `pendingNavigation`.
 */
import useKidsDailyGenerationStore from "@/store/useKidsDailyGenerationStore";

type NavigateFn = (path: string) => void

let abortController: AbortController | null = null
let navigateFn: NavigateFn | null = null
let pendingNavigation: string | null = null

export const kidsDailyGenerationManager = {
  registerNavigate(fn: NavigateFn) {
    navigateFn = fn
    if (pendingNavigation) {
      const path = pendingNavigation
      pendingNavigation = null
      fn(path)
    }
  },

  isGenerating(): boolean {
    return useKidsDailyGenerationStore.getState().generatingTopic !== null
  },

  /** Abort any prior run, arm a fresh controller, return its signal. */
  beginGeneration(): AbortSignal {
    abortController?.abort()
    abortController = new AbortController()
    return abortController.signal
  },

  /** Navigate now if possible, otherwise queue until navigate registers. */
  navigateToEpisode(path: string) {
    if (navigateFn) {
      navigateFn(path)
    } else {
      pendingNavigation = path
    }
  },

  /** True only if `signal` still owns the active run (not superseded). */
  isCurrent(signal: AbortSignal): boolean {
    return abortController?.signal === signal
  },

  /** Finish the run that owns `signal`; clears progress + controller. */
  finish(signal: AbortSignal) {
    if (abortController?.signal !== signal) return
    abortController = null
    useKidsDailyGenerationStore.getState().clear()
  },

  /** User pressed cancel — abort and reset progress. */
  cancel() {
    abortController?.abort()
    abortController = null
    useKidsDailyGenerationStore.getState().clear()
  },
}

export default kidsDailyGenerationManager
