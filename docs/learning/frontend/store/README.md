# State Management (Zustand Stores)

**Source**: `frontend/src/store/`

## What Stores Are

**Explorer**: Stores are the app's memory. When you log in, the app remembers who you are (auth store). When you're in the middle of an interactive story, it remembers where you are (story store). Even if you refresh the page, the stores remember — they save to your browser's memory.

**Maker**: Zustand stores manage client-side state with a minimal API. Each store is a hook created with `create()`, optionally wrapped in `persist()` middleware to sync to `localStorage`. Stores hold data that exists purely in the browser (auth tokens, UI state, generation progress) — server data uses TanStack Query instead.

## Store Map

### `useAuthStore` — Authentication State
**File**: `store/useAuthStore.ts`

| Field | Type | Purpose |
|-------|------|---------|
| `user` | `User \| null` | Current user profile |
| `token` | `string \| null` | Bearer token (Supabase JWT or legacy) |
| `isAuthenticated` | `boolean` | Quick auth check |
| `isLoading` | `boolean` | Auth operation in progress |

**Actions**: `setAuth(user, token)`, `logout()`, `setLoading()`

**Persistence**: Yes — `localStorage` key `auth-storage`. Persists `user`, `token`, `isAuthenticated` so login survives page refresh. Loading state is transient (not persisted).

**Used by**: `AuthProvider` (writes), every page (reads `isAuthenticated`), `api/client.ts` (reads `token` for Authorization header).

---

### `useChildStore` — Child Profile
**File**: `store/useChildStore.ts`

| Field | Type | Purpose |
|-------|------|---------|
| `currentChild` | `ChildProfile \| null` | Active child's profile |
| `defaultChildId` | `string` | Fallback child ID (derived from user) |

**Exports**: `DEFAULT_INTERESTS` — array of interest tags for setup forms.

**Used by**: UploadPage, InteractiveStoryPage, NewsPage — to populate `child_id` and `age_group` in API requests.

---

### `useInteractiveStoryStore` — Interactive Story Session
**File**: `store/useInteractiveStoryStore.ts`

| Field | Type | Purpose |
|-------|------|---------|
| `sessionId` | `string \| null` | Active session ID |
| `storyTitle` | `string` | Current story title |
| `ageGroup` | `AgeGroup \| null` | Selected age group |
| `storyLengthMode` | `StoryLengthMode` | short / medium / unlimited |
| `currentSegment` | `StorySegment \| null` | Latest segment with choices |
| `segments` | `StorySegment[]` | All segments so far |
| `choiceHistory` | `string[]` | IDs of chosen options |
| `progress` | `number` | 0-1 completion ratio |
| `status` | `StoryStatus` | idle / playing / completed |
| `streaming` | `StreamingState` | SSE progress tracking |

**Actions**: `setSession()`, `addSegment()`, `restoreSession()`, `complete()`, `startStreaming()`, `stopStreaming()`

**Persistence**: Yes — `localStorage` key `interactive-story-session`. Everything except `streaming` state is persisted. This enables resuming a story after browser close.

**Used by**: `useInteractiveStory` hook (primary consumer), `interactiveStoryGenerationManager` (writes during SSE).

---

### `useStoryStore` — Image-to-Story State
**File**: `store/useStoryStore.ts`

Tracks the current image-to-story generation flow: uploaded image, selected options, generation progress, and result.

**Used by**: `useStoryGeneration` hook, `storyGenerationManager`.

---

### `useDailyTaskStore` — Daily Reward System
**File**: `store/useDailyTaskStore.ts`

| Field | Type | Purpose |
|-------|------|---------|
| `lastClaimDate` | `string \| null` | ISO date of last reward claim |
| `streak` | `number` | Consecutive days claimed |
| `totalStars` | `number` | Lifetime stars earned |

**Method**: `canClaimToday()` — returns `true` if `lastClaimDate` is not today.

**Used by**: `InspirationDaily` component (checks if reward is claimable), `HomePage` (shows reward card).

---

## Why Zustand?

Compared to alternatives:
- **vs Redux**: No boilerplate (no actions, reducers, dispatch). A store is ~30 lines.
- **vs React Context**: No provider wrapper needed per store. No re-render of entire tree on updates — Zustand uses selectors for surgical re-renders.
- **vs useState**: State survives across component unmount/remount and can be shared across unrelated components.

## Key Pattern: Persist Middleware

```tsx
const useAuthStore = create(
  persist(
    (set) => ({ user: null, token: null, ... }),
    {
      name: 'auth-storage',  // localStorage key
      partialize: (state) => ({  // only persist these fields
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
        // isLoading is NOT persisted — it's transient
      }),
    }
  )
)
```

The `partialize` function controls what gets saved. Transient state (loading flags, streaming progress) is excluded because it would be stale on reload.

## Thinking Question

The interactive story store persists the full `segments` array to localStorage. For a 50-segment unlimited story, that's a lot of data in localStorage (which typically has a 5-10 MB limit per origin). What would happen if a child plays many long stories? How would you implement a cleanup strategy — delete old sessions? Compress the data? Move to IndexedDB which has larger limits?
