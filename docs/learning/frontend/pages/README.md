# Frontend Pages

**Source**: `frontend/src/pages/`

## What Pages Are

**Explorer**: Pages are full screens of the app — like pages in a book. The home page is the cover, the upload page is where you create, and the library page is where you keep your stories. When you click a link, the app flips to a different page.

**Maker**: Pages are top-level React components mapped to URL routes via React Router. Each page is lazy-loaded (code-split) to minimize initial bundle size. Pages compose smaller components, connect to stores/hooks for state, and call API services for data. All pages except LoginPage are rendered inside `PageContainer` (which provides the navigation bar).

## Page Map

### HomePage (`/`)
**Source**: `pages/HomePage/index.tsx`

The landing page with:
- **Feature tiles**: Quick-access cards to Upload, Interactive Story, News, Library (via `FeatureTile` component)
- **Daily reward**: `InspirationDaily` newspaper card with `TearAnimation` — tear to collect stars
- **Recent creations**: Last 6 items from the library (mixed types: stories, interactive, news)
- **Rotating tips**: Helpful suggestions that cycle with animation
- **Floating stars**: Mouse-responsive parallax star decorations

Key patterns: Uses `useQuery` to fetch recent library items, `useDailyTaskStore` for reward state, `TiltCard` for 2.5D depth effects.

---

### UploadPage (`/upload`)
**Source**: `pages/UploadPage/index.tsx`

Drawing upload + story generation setup:
- **Image upload**: Drag-and-drop or file picker (`ImageUploader` component)
- **Image preview**: Shows the uploaded drawing with style transfer options (`ImagePreview`)
- **Setup form**: Age group selector, interest tags, art style picker, voice picker, theme input
- **Generation**: Calls `useStoryGeneration` hook → streams progress via `StreamingVisualizer`
- **Redirect**: After generation completes, navigates to `/story/:storyId`

Key patterns: Form state managed locally (`useState`), generation orchestrated by `storyGenerationManager`, art themes filtered by age (younger kids see fewer options).

---

### StoryPage (`/story/:storyId`)
**Source**: `pages/StoryPage/index.tsx`

Displays a generated story with:
- **Book container**: Story text in a book-like layout (`BookContainer`)
- **Floating image**: Child's original drawing + styled version (`FloatingImage`)
- **Audio player**: TTS narration with play/pause controls
- **Educational tags**: Themes and concepts from the story (`EducationalTags`)
- **Safety badge**: Content safety score indicator (`SafetyBadge`)
- **Share/Save**: Save to library, share options

Key patterns: Loads story via `useQuery` with `storyId` from URL params. `AgeAwareContent` adapts display (audio-first for 3-5, text-first for 9-12).

---

### InteractiveStoryPage (`/interactive`)
**Source**: `pages/InteractiveStoryPage/index.tsx`

Choose-your-own-adventure with three states:
- **Setup**: Age group, interests, theme, **story length mode** (short/medium/unlimited)
- **Playing**: Story segments with choice buttons, progress indicator, streaming visualizer, "End My Story" button (unlimited mode)
- **Completed**: Full story timeline, educational summary, save/replay buttons

Key patterns: State machine (`setup → playing → completed`) via `useInteractiveStory` hook. Segments accumulate in `useInteractiveStoryStore`. SSE streaming via `interactiveStoryGenerationManager`. Resume from URL param `?session=`.

---

### LibraryPage (`/library`)
**Source**: `pages/LibraryPage/index.tsx`

Unified content library with:
- **Tabs**: All, Art Stories, Interactive, News, Favorites
- **Cards**: Mixed-type content cards with thumbnails, titles, dates
- **Growth dashboard**: Stats chart showing creation activity over time
- **Empty states**: Per-tab encouragement with CTAs to create content

Key patterns: `useQuery` with filter params, `useLibraryPreferences` hook for tab persistence, infinite scroll or pagination.

---

### LoginPage (`/login`)
**Source**: `pages/LoginPage/index.tsx`

Dual-mode auth form:
- **Login**: Email + password → `authService.login()`
- **Register**: Username + email + password + confirm → `authService.register()`
- **Email confirmation**: Shows pending state with resend button
- **Referral**: Captures `?ref=` query param for referral tracking
- **Error handling**: Friendly error messages via `friendlyAuthError()` mapper

Key patterns: No `PageContainer` wrapper (standalone page). Animated background emojis. Dev mode pre-fills test credentials. Bilingual error messages.

---

### NewsPage (`/news`)
**Source**: `pages/NewsPage/index.tsx`

Morning Show subscription management:
- **Topic cards**: 8 news categories (space, animals, tech, science, nature, culture, sports, general)
- **Subscribe/Unsubscribe**: Toggle topic subscriptions (max 5)
- **Listen Now**: On-demand episode generation per topic
- **Onboarding**: First-time wizard for new users (3 steps)

Key patterns: `useQuery` for subscriptions, optimistic updates via `queryClient.invalidateQueries`, rate limit handling with countdown timer.

---

### MorningShowPage (`/morning-show/:episodeId`)
**Source**: `pages/MorningShowPage/index.tsx`

Podcast episode player:
- **Audio player**: Full episode playback with progress bar
- **Dialogue display**: Scrolling conversation between Mimi and Duo
- **Playback events**: 25/50/75% progress tracking

---

### NewsDetailPage (`/news/:conversionId`)
**Source**: `pages/NewsDetailPage/index.tsx`

Single news article view with newspaper-style layout:
- **Headline + body**: Serif newspaper typography
- **Key concepts**: Vocabulary terms with definitions
- **Discussion questions**: Thinking prompts for the reader
- **Callout boxes**: Important facts highlighted

---

### ProfilePage (`/profile`)
**Source**: `pages/ProfilePage/index.tsx`

User profile with:
- **Avatar**: Animal emoji picker with backend validation
- **Stats**: Creation counts by type, referral status
- **Star jar**: Collected stars from daily rewards (fly animation to nav)
- **Character gallery**: Recurring characters from stories (`CharacterGallery.tsx`)
- **Preference summary**: Topic and theme preferences (`PreferenceSummary.tsx`)

---

## Common Page Patterns

### Auth Guard
Most pages check authentication and show `LoginPrompt` if not logged in:
```tsx
if (!isAuthenticated) {
  return <LoginPrompt feature="play interactive stories" />
}
```

### Loading States
Pages use `isLoading` from hooks/queries to show loading indicators:
```tsx
{isLoading && <StreamingVisualizer phase="thinking" message="Creating story..." />}
```

### Error Handling
Non-quota errors show inline banners. Quota errors show `QuotaExceededOverlay`:
```tsx
<QuotaExceededOverlay show={isQuotaError(error)} message={error} onDismiss={...} />
```

## Thinking Question

Every page is lazy-loaded (`React.lazy`), which means each page's code is a separate JavaScript file downloaded on first visit. What happens if a user is on a slow connection and clicks a link — do they see a blank screen? How does the `<Suspense fallback={<Loading />}>` wrapper prevent this, and what trade-off exists between eager loading (everything upfront) and lazy loading (on demand)?
