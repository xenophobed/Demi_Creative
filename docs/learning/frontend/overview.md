# Frontend Overview

**Source**: `frontend/src/`

## What This Is

**Explorer**: The frontend is everything you see and touch — buttons, pages, animations, and pictures. When you click "Start Story" or pick an adventure choice, the frontend draws it on screen and sends your request to the backend brain.

**Maker**: The frontend is a React 18 SPA (Single Page Application) built with TypeScript, Vite, and Tailwind CSS. State management uses Zustand (lightweight stores) and TanStack Query (server state caching). Routing is handled by React Router v6 with lazy-loaded pages. The app communicates with the backend via REST API calls and SSE streaming.

## Architecture

```
main.tsx (entry point)
  └─ Provider Stack (wraps entire app):
      QueryClientProvider  ← TanStack Query (server state cache)
       └─ AuthProvider     ← Supabase auth event listener
           └─ StreamVisualizationProvider  ← Confetti, particles
               └─ BrowserRouter  ← React Router
                   └─ App.tsx  ← Route definitions
                       └─ PageContainer  ← Nav bar, layout
                           └─ Pages (lazy loaded)
                               └─ Components + Hooks + Stores
```

## Route Map

| Path | Page | Auth Required | Purpose |
|------|------|---------------|---------|
| `/` | `HomePage` | No | Landing page with feature tiles, daily reward |
| `/login` | `LoginPage` | No | Login/register form (no PageContainer) |
| `/upload` | `UploadPage` | Yes | Upload drawing for story generation |
| `/story/:storyId` | `StoryPage` | Yes | View generated story with audio |
| `/interactive` | `InteractiveStoryPage` | Yes | Choose-your-own-adventure |
| `/library` | `LibraryPage` | Yes | My Library — all saved content |
| `/news` | `NewsPage` | Yes | Kids Morning Show subscriptions + episodes |
| `/news/:conversionId` | `NewsDetailPage` | Yes | Read a single news article |
| `/morning-show/:episodeId` | `MorningShowPage` | Yes | Listen to a podcast episode |
| `/profile` | `ProfilePage` | Yes | User profile, avatar, stats, characters |

## Tech Stack

| Concern | Technology | Why |
|---------|-----------|-----|
| UI Framework | React 18 | Component model, large ecosystem, TypeScript support |
| Language | TypeScript | Type safety catches bugs before runtime |
| Build Tool | Vite | Fast dev server with HMR, optimized production builds |
| Styling | Tailwind CSS | Utility classes — no separate CSS files per component |
| State (client) | Zustand | Minimal boilerplate, persist to localStorage |
| State (server) | TanStack Query | Automatic caching, refetching, loading states |
| Routing | React Router v6 | Nested routes, lazy loading, URL params |
| Animation | Framer Motion | Declarative spring animations, gestures |
| HTTP Client | Axios + fetch | Axios for JSON APIs, fetch for SSE streams |

## Directory Map

| Directory | Purpose | Key Files |
|-----------|---------|-----------|
| `pages/` | Full-screen views (one per route) | 10 page components |
| `components/common/` | Reusable UI primitives | Button, Card, AudioPlayer, LoginPrompt |
| `components/daily/` | Daily reward system | InspirationDaily, MysteryBagOverlay, StarPiggyBank |
| `components/interactive/` | Interactive story UI | ChoiceButtons, ProgressIndicator, StorySegmentDisplay |
| `components/story/` | Story display | BookContainer, StoryDisplay, FloatingImage |
| `components/streaming/` | AI generation visualization | StreamingVisualizer, ThinkingBubble |
| `components/effects/` | Visual effects | Confetti, ParticleEmitter, Sparkles |
| `components/depth/` | 2.5D parallax effects | PerspectiveContainer, TiltCard, ParallaxContainer |
| `components/upload/` | Image upload | ImageUploader, ImagePreview |
| `store/` | Zustand state stores | Auth, child profile, stories, daily tasks |
| `hooks/` | Custom React hooks | useInteractiveStory, useAudioPlayer, useStoryGeneration |
| `api/` | Backend communication | HTTP client, auth utils, service modules |
| `services/` | Generation orchestrators | storyGenerationManager, interactiveStoryGenerationManager |
| `providers/` | React context providers | AuthProvider, StreamVisualizationProvider |
| `types/` | TypeScript type definitions | api.ts, auth.ts, streaming.ts |
| `config/` | App configuration | ageConfig, animationPresets |
| `styles/` | Global CSS | globals.css (Tailwind + custom styles) |

## Key Patterns

### Lazy Loading
Pages load on demand — the user only downloads the code for the page they're visiting:
```tsx
const InteractiveStoryPage = lazy(() => import("./pages/InteractiveStoryPage"))
```
This keeps the initial bundle small (~200 KB) instead of loading everything upfront.

### Zustand + Persist
Client state (auth, story progress) persists to `localStorage` so the user doesn't lose their session on page refresh:
```tsx
const useAuthStore = create(persist((set) => ({ ... }), { name: 'auth-storage' }))
```

### SSE Streaming
Long-running AI generations stream progress to the UI instead of making the user wait:
```
Frontend sends POST /story/interactive/start/stream
Backend yields SSE events: status → thinking → tool_use → result → complete
Frontend updates StreamingVisualizer in real-time
```

### Age-Aware Content
The `AgeAwareContent` component adapts the display based on age group:
- 3-5: Audio plays automatically, text is secondary
- 6-8: Audio and text side by side
- 9-12: Text first, audio on-demand

## Connections

- **Backend**: All data comes from `api/services/*.ts` calling FastAPI endpoints
- **Auth**: `lib/supabase.ts` → `AuthProvider` → `useAuthStore` manages the full auth lifecycle
- **Streaming**: `services/*GenerationManager.ts` handles SSE parsing and store updates
- **Styles**: `styles/globals.css` defines Tailwind config, custom utilities, newspaper styles

## Thinking Question

The app uses both Zustand (client state) and TanStack Query (server state). Why two different state managers instead of one? Think about: what data comes from the server vs what exists only in the browser, how caching works, and what happens when two browser tabs show the same data.
