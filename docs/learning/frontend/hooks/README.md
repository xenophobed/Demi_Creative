# Custom Hooks

**Source**: `frontend/src/hooks/`

## What Hooks Are

**Explorer**: Hooks are shared recipes that pages use. Instead of every page writing its own code for "play audio" or "generate a story," they all use the same hook — like everyone in a kitchen using the same recipe book.

**Maker**: Custom hooks extract reusable logic from components. They compose React's built-in hooks (`useState`, `useEffect`, `useCallback`) with store access and API calls into domain-specific interfaces. Hooks follow the naming convention `use<Feature>` and can only be called inside React components or other hooks.

## Hook Map

### `useInteractiveStory` — Interactive Story Controller
**File**: `hooks/useInteractiveStory.ts`

The main interface for the interactive story feature. Wraps the Zustand store and generation manager into a clean API:

```typescript
const {
  sessionId, storyTitle, ageGroup, storyLengthMode,
  currentSegment, segments, choiceHistory, progress,
  isLoading, error, isCompleted, streaming,
  startStoryStream, makeChoiceStream, endStory, resumeSession, reset,
} = useInteractiveStory()
```

**Why a hook instead of using the store directly?** The hook composes multiple concerns: store state + generation manager + error handling + loading state. Components get one clean interface instead of importing 3 modules.

---

### `useStoryGeneration` — Image-to-Story Controller
**File**: `hooks/useStoryGeneration.ts`

Manages the upload → generate → navigate flow for image-to-story. Coordinates file upload, option selection, SSE streaming, and navigation to the result page.

---

### `useAudioPlayer` — Audio Playback
**File**: `hooks/useAudioPlayer.ts`

Wraps the HTML5 `<audio>` element API with React state:
- Play/pause/seek controls
- Progress tracking (current time, duration, percentage)
- Speed control (0.5x to 2x)
- Auto-play option (used for 3-5 age group)

---

### `useStreamVisualization` — Stream Effects
**File**: `hooks/useStreamVisualization.ts`

Interface to the `StreamVisualizationProvider` for triggering visual effects:
- `triggerConfetti()` — fires confetti burst on story completion
- `triggerSparkles()` — sparkle effect during tool use

---

### `useLibraryPreferences` — Library Filtering
**File**: `hooks/useLibraryPreferences.ts`

Remembers which tab and sort order the user last used in the library, persisted to localStorage.

---

### `useMemoryApi` — Memory System
**File**: `hooks/useMemoryApi.ts`

TanStack Query wrapper for the memory endpoints — fetches child preferences and character data with automatic caching.

---

### `useParallax` — Parallax Effect
**File**: `hooks/useParallax.ts`

Tracks mouse position and converts it to parallax offset values for the 2.5D depth components.

---

### `useSoundEffects` — Sound Effects
**File**: `hooks/useSoundEffects.ts`

Manages UI sound effects (tear sound, star collection, etc.) with preloading and reduced-motion respect.

---

### `useGenerationNavigator` — Post-Generation Routing
**File**: `hooks/useGenerationNavigator.ts`

Handles navigation after a generation completes — redirects to the story page, interactive story session, or episode player.

## Key Pattern: Hook Composition

Hooks compose simpler hooks into richer interfaces:

```
useInteractiveStory
  ├── useInteractiveStoryStore (Zustand — state)
  ├── interactiveStoryGenerationManager (SSE — side effects)
  ├── useState (local loading/error state)
  └── useCallback (memoized actions)
```

This layered approach means:
- **Store** = pure state (testable without React)
- **Manager** = side effects (SSE streams, API calls)
- **Hook** = glue (composes store + manager + local state)
- **Component** = UI (renders what the hook provides)

## Thinking Question

The `useInteractiveStory` hook returns both `isLoading` and `streaming.isStreaming`. Why two different loading indicators? Think about: what happens during the initial HTTP request (before SSE starts), what happens during SSE streaming (events are flowing), and what the UI should show in each case.
