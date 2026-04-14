# Context Providers

**Source**: `frontend/src/providers/`, `frontend/src/contexts/`

## What Providers Are

**Explorer**: Providers are like invisible wires that connect all parts of the app. Instead of passing information from parent to child to grandchild (like a game of telephone), providers let any component anywhere in the app grab what it needs directly.

**Maker**: React Context providers wrap the component tree to share state and callbacks without prop drilling. The app uses providers for cross-cutting concerns (auth events, audio playback, visual effects) that many unrelated components need access to. Zustand stores handle most state — providers are used only when React lifecycle integration is needed (e.g., `useEffect` for event listeners).

## Provider Stack (from `main.tsx`)

```
QueryClientProvider          ← TanStack Query cache
  └─ AuthProvider            ← Supabase auth event listener
      └─ StreamVisualizationProvider  ← Effect triggers (confetti, particles)
          └─ BrowserRouter   ← React Router
              └─ AudioProvider  ← Global audio playback context (inside App.tsx)
                  └─ App     ← Routes + Pages
```

Order matters — each provider can only access providers above it in the tree.

## Provider Details

### `AuthProvider`
**File**: `providers/AuthProvider.tsx`

**Purpose**: Listens to Supabase auth state changes and syncs to the Zustand auth store.

**How it works**:
1. On mount, registers `supabase.auth.onAuthStateChange()` listener
2. Handles four event types:
   - `INITIAL_SESSION` — catches sessions from email confirmation redirect (code exchange happened before mount)
   - `SIGNED_IN` — normal login flow
   - `TOKEN_REFRESHED` — updates stored access token
   - `SIGNED_OUT` — clears all auth state
3. `syncAndRedirect()` calls `GET /users/me` to sync Supabase user to backend, then redirects home for email confirmations

**Key trick**: `hadCallbackParams` is captured at **module load time** (before React renders) to detect email confirmation redirects. The Supabase SDK may exchange the URL code before `useEffect` runs.

**Renders**: Just `{children}` — no visible UI.

---

### `StreamVisualizationProvider`
**File**: `providers/StreamVisualizationProvider.tsx`

**Purpose**: Global effect trigger system for confetti, particles, and sparkles.

**Provides**:
- `prefersReducedMotion` — respects user's accessibility preference
- `triggerConfetti()` — fires confetti burst (used on story completion)
- `registerEffectCallback()` — lets `ConfettiController` subscribe to effect events

**Used by**: `useStreamVisualization` hook, `Confetti` component, `InteractiveStoryPage` (on completion).

---

### `AudioProvider`
**File**: `contexts/AudioContext.tsx`

**Purpose**: Global audio playback state — ensures only one audio source plays at a time across the entire app.

**Provides**:
- Current playing URL and state
- Play/pause/stop controls
- Prevents two audio players from playing simultaneously (MiniPlayer in nav + full player on page)

---

### `NavRefContext`
**File**: `contexts/NavRefContext.tsx`

**Purpose**: Shares a ref to the navigation bar's avatar element. Used by `StarFlyAnimation` to animate stars flying from the daily reward to the nav avatar.

## Why Providers vs Zustand?

| Use Case | Providers | Zustand |
|----------|-----------|---------|
| Event listeners (auth, audio) | Yes — needs `useEffect` lifecycle | No — stores don't have lifecycle |
| Cross-component state (cart, theme) | Possible but verbose | Yes — simpler API |
| Ref sharing (DOM elements) | Yes — refs are React-specific | No — stores hold serializable data |
| Persistence to localStorage | Manual | Built-in `persist` middleware |

Rule of thumb: Use providers when you need React lifecycle integration (`useEffect`, refs, event listeners). Use Zustand stores for plain state that components read/write.

## Thinking Question

The `AuthProvider` renders nothing visible — it's purely a side-effect container. Some developers argue this is an anti-pattern: "if it doesn't render anything, it shouldn't be a component." An alternative is using Zustand's `subscribe()` outside of React. What are the trade-offs? Think about: cleanup on unmount, access to other React hooks inside the listener, and testability.
