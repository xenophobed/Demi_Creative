# API Client Layer

**Source**: `frontend/src/api/`

## What This Is

**Explorer**: The API client is the messenger between the frontend and backend. When you click "Start Story," the messenger carries your request to the backend server, waits for the response, and brings it back to show on screen.

**Maker**: The API client layer provides typed HTTP communication with the backend. It includes an Axios HTTP client with auth header injection, per-feature service modules, SSE stream consumption, and auth utility functions. All backend communication is centralized here — components never call `fetch()` directly.

## File Map

### `client.ts` — HTTP Client Configuration
The shared Axios instance used by all service modules:
- **Base URL**: Reads `VITE_API_BASE_URL` or defaults to `http://localhost:8000/api/v1`
- **Auth interceptor**: `applyStoredAuthHeader()` from `authUtils.ts` — reads the Zustand auth token from localStorage and sets `Authorization: Bearer <token>` on every request
- **Error handling**: `getErrorMessage()` extracts human-readable error messages from Axios errors

### `authUtils.ts` — Auth Utilities
- `readStoredToken()` — reads the JWT from localStorage's `auth-storage` key
- `applyStoredAuthHeader()` — Axios request interceptor that adds the Bearer token
- `hasAuthCallbackParams()` — checks if the URL contains Supabase email confirmation params (`code=`, `type=signup`, etc.)

### `services/` — Feature Service Modules

| File | Purpose | Key Methods |
|------|---------|-------------|
| **authService.ts** | Login, register, logout, profile | `login()`, `register()`, `resendConfirmation()`, `_syncUser()` |
| **storyService.ts** | Story generation, interactive stories, morning show | `startInteractiveStoryStream()`, `makeChoiceStream()`, `endStoryStream()`, `generateMorningShowOnDemand()` |
| **libraryService.ts** | Library CRUD, favorites, stats | `getLibrary()`, `getLibraryStats()`, `toggleFavorite()` |
| **memoryService.ts** | Preferences, characters | `getPreferences()`, `getCharacters()` |
| **inspirationService.ts** | Daily inspiration content | `fetchDailyInspiration()`, `toDailyContent()` |

### `utils/sseStream.ts` — SSE Stream Consumer
Parses Server-Sent Events from `fetch()` responses:

```typescript
interface StreamCallbacks {
  onStatus: (data: SSEStatusData) => void
  onThinking: (data: SSEThinkingData) => void
  onToolUse: (data: SSEToolUseData) => void
  onResult: (data: any) => void
  onComplete: () => void
  onError: (data: any) => void
}
```

The `consumeSSEStream()` function reads the response body as a stream, splits on `\n\n` boundaries, parses `event:` and `data:` lines, and dispatches to the matching callback.

## Data Flow

```
Component clicks "Start Story"
  │
  ▼
useInteractiveStory hook
  │
  ▼
interactiveStoryGenerationManager.startStory()
  │
  ▼
storyService.startInteractiveStoryStream(params, callbacks, signal)
  │
  ├─ fetch(url, { method: "POST", headers: { Authorization: Bearer <token> }, body })
  │
  ▼
consumeSSEStream(response, callbacks)
  │
  ├─ onStatus → store.updateStreamStatus()  → UI shows "Creating story..."
  ├─ onThinking → store.updateThinking()    → UI shows AI reasoning
  ├─ onResult → store.setSession()          → UI renders the story
  └─ onComplete → store.stopStreaming()     → UI hides loading
```

## Why Axios + fetch?

- **Axios** for regular JSON API calls — automatic JSON parsing, request/response interceptors, better error handling
- **fetch** for SSE streaming — Axios doesn't support streaming response bodies. Raw `fetch()` + `ReadableStream` is needed to read events as they arrive

## Key Concepts

**Request Interceptor**: A function that runs before every HTTP request. Our interceptor adds `Authorization: Bearer <token>` to every request so individual service methods don't have to.

**SSE (Server-Sent Events)**: A protocol where the server pushes events over a single HTTP connection. Unlike WebSockets (bidirectional), SSE is server-to-client only — perfect for "watch this long-running operation" patterns.

**Service Module Pattern**: Each feature area gets its own service file. This keeps API calls organized by domain instead of having one giant API file with 50 methods.

## Thinking Question

The auth interceptor reads the token from localStorage on every request. What if the Supabase token expires mid-session (after 1 hour)? The `AuthProvider` listens for `TOKEN_REFRESHED` events and updates the store, but there's a race condition: what if a request is sent in the milliseconds between token expiry and refresh? How would you add a retry-with-refresh mechanism?
