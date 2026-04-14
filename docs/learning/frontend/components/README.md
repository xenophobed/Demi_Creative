# Frontend Components

**Source**: `frontend/src/components/`

## What Components Are

**Explorer**: Components are like LEGO pieces. A Button is one piece, a Card is another, an AudioPlayer is another. You snap them together to build pages — the same Button piece can be used on every page without rebuilding it each time.

**Maker**: Components are reusable React function components that encapsulate UI and behavior. They follow a composition pattern — small primitives (`Button`, `Card`) compose into larger units (`StoryDisplay`, `StreamingVisualizer`) which compose into pages. Components receive data via props and manage local state with `useState`/`useReducer`.

## Component Groups

### `common/` — Reusable UI Primitives

| Component | Purpose | Used By |
|-----------|---------|---------|
| **Button** | Universal button with variants (primary, secondary, outline, ghost), loading state, icons | Every page |
| **Card** | Container with variants (elevated, colorful), padding options, border styles | Every page |
| **AudioPlayer** | Full audio playback with progress bar, play/pause, speed control | StoryPage, MorningShowPage |
| **MiniPlayer** | Compact audio bar for background playback | PageContainer (nav) |
| **AgeAwareContent** | Adapts display by age: audio-first (3-5), side-by-side (6-8), text-first (9-12) | StoryPage, InteractiveStoryPage |
| **Loading** | Spinner with optional message, supports fullScreen mode | App Suspense fallback |
| **LoginPrompt** | "Please log in" card with link to /login | All auth-gated pages |
| **QuotaExceededOverlay** | Modal overlay when daily quota is used up | Upload, Interactive, News pages |
| **VoicePicker** | Voice selection grid — shows available TTS voices with preview | UploadPage |
| **SuggestedThemes** | Theme suggestion chips from recommendation engine | UploadPage, InteractiveStoryPage |
| **FeatureTile** | Homepage card linking to a feature (upload, interactive, news) | HomePage |
| **AvatarDisplay** | Renders the user's animal emoji avatar | ProfilePage, Nav |

### `daily/` — Daily Reward System

| Component | Purpose |
|-----------|---------|
| **InspirationDaily** | Newspaper-style card with daily creative content. Dual mode: locked (unauthenticated) vs claimable (authenticated). Uses serif font for newspaper aesthetic. |
| **TearAnimation** | Drag-to-tear interaction — user drags across a dashed line to "tear" the newspaper and claim the reward. Falls back to tap on reduced-motion. |
| **StarFlyAnimation** | Star emoji flies from the torn newspaper to the nav bar avatar — visual reward feedback. |
| **StarPiggyBank** | Star collection display on profile page — shows total stars earned. |
| **MysteryBagOverlay** | Fullscreen gamification overlay — pick a bag, tear open, confetti, reveal tool emoji, "放入百宝箱" CTA. Uses `createPortal` for fullscreen rendering. |

### `interactive/` — Interactive Story UI

| Component | Purpose |
|-----------|---------|
| **ChoiceButtons** | Renders 2-3 story choices as animated buttons with emojis. Disabled during loading. |
| **ProgressIndicator** | Progress bar + segment dots (short/medium) or "Endless Adventure" label (unlimited). Adapts per `storyLengthMode`. |
| **StorySegmentDisplay** | Renders a single story segment with text reveal animation. |

### `story/` — Story Display

| Component | Purpose |
|-----------|---------|
| **StoryDisplay** | Main story viewer with text, image, and metadata. Also exports `StoryCard` for library grid. |
| **BookContainer** | Book-style layout with page-like borders and shadows. |
| **FloatingImage** | Child's drawing that floats alongside the story text with parallax effect. |
| **EducationalTags** | Themed badges showing what the story teaches (courage, friendship, etc.). |
| **SafetyBadge** | Green/yellow/red indicator showing content safety score. |
| **TabbedMetadata** | Tab bar for story metadata (characters, themes, educational value). |

### `streaming/` — AI Generation Visualization

| Component | Purpose |
|-----------|---------|
| **StreamingVisualizer** | Card showing AI generation progress — animated particles, status messages, thinking content. Supports `card` and `inline` layouts. |
| **ThinkingBubble** | Shows AI reasoning text in a chat-bubble style. |
| **StatusCard** | Simple status card with icon, message, and optional progress bar. |
| **ToolIndicator** | Shows which MCP tool the agent is currently using ("Checking content safety..."). |
| **LottieStatus** | Lottie animation placeholder for status indicators. |

### `effects/` — Visual Effects

| Component | Purpose |
|-----------|---------|
| **Confetti** | Celebration confetti burst — used on story completion and daily reward claim. Configurable count, colors, origin, spread. Respects `prefers-reduced-motion`. |
| **ParticleEmitter** | Generic particle system for ambient effects. |
| **Sparkles** | Twinkling sparkle overlay for magical moments. |

### `depth/` — 2.5D Parallax Effects

| Component | Purpose |
|-----------|---------|
| **PerspectiveContainer** | Wraps content with CSS perspective for 3D tilt effects. |
| **TiltCard** | Card that tilts toward mouse cursor — used on homepage feature tiles. |
| **ParallaxContainer** | Multi-layer parallax scrolling. Also exports `FloatingElement` for mouse-responsive decorations. |
| **AnimatedBackground** | Gradient background with subtle animation. |
| **DepthLayer** | Single layer in a parallax stack with configurable depth multiplier. |

### `upload/` — Image Upload

| Component | Purpose |
|-----------|---------|
| **ImageUploader** | Drag-and-drop zone + file picker button. Validates file type and size. |
| **ImagePreview** | Shows the uploaded image with overlay controls (style picker, remove button). |

### `layout/` — Page Structure

| Component | Purpose |
|-----------|---------|
| **PageContainer** | Outer shell for all pages (except LoginPage). Renders the navigation bar, `MiniPlayer`, `ConfettiController`, and `<Outlet>` for nested routes. |
| **GenerationStatusBar** | Top-of-page bar showing active generation progress (visible during background generation). |

### `library/` — Library-Specific

| Component | Purpose |
|-----------|---------|
| **GrowthTimeline** | Bar chart showing creation activity over time (stories, interactive, news per week). |

## Design Patterns

### Controlled vs Uncontrolled
Most components are **controlled** — the parent passes state via props:
```tsx
<AudioPlayer audioUrl={story.audio_url} autoPlay={ageGroup === "3-5"} />
```

### Composition over Configuration
Instead of one mega-component with many boolean flags, we compose smaller pieces:
```tsx
<AgeAwareContent ageGroup={ageGroup} audioUrl={url} textContent={<StoryDisplay />} />
```

### Motion Variants
Animation components use Framer Motion's `AnimatePresence` for enter/exit transitions:
```tsx
<AnimatePresence mode="wait">
  {showConfetti && <Confetti active count={60} />}
</AnimatePresence>
```

## Thinking Question

The `AgeAwareContent` component shows audio-first for ages 3-5 and text-first for ages 9-12. But what if a 4-year-old is a strong reader, or a 10-year-old prefers listening? Should this be a preference the child can override, or should the age-based default always win? Think about: user autonomy vs age-appropriate defaults, how preference data could be collected without frustrating the child, and whether A/B testing could inform the default.
