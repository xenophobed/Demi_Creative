/**
 * Kids Daily on-demand generation state (#727).
 *
 * Holds the "which topic is generating + status line" out of KidsDailyPage
 * component state so a navigation away (and back) doesn't drop the
 * in-flight episode. The fetch + completion navigation are driven by
 * `kidsDailyGenerationManager`, which owns the AbortController at module
 * scope. This mirrors the proven `useStoryStore` + `storyGenerationManager`
 * split already used by Image-to-Story.
 */
import { create } from "zustand";
import type { NewsCategory } from "@/types/api";

interface KidsDailyGenerationState {
  /** Topic whose episode is generating right now, or null when idle. */
  generatingTopic: NewsCategory | null;
  /** Kid-friendly progress line shown in the generation overlay. */
  generationMessage: string | null;

  begin: (topic: NewsCategory, message: string) => void;
  setMessage: (message: string | null) => void;
  clear: () => void;
}

const useKidsDailyGenerationStore = create<KidsDailyGenerationState>((set) => ({
  generatingTopic: null,
  generationMessage: null,

  begin: (topic, message) =>
    set({ generatingTopic: topic, generationMessage: message }),
  setMessage: (message) => set({ generationMessage: message }),
  clear: () => set({ generatingTopic: null, generationMessage: null }),
}));

export default useKidsDailyGenerationStore;
