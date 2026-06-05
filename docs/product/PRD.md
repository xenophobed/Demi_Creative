# Kids Creative Workshop - Product Requirements Document (PRD)

> **Scope**: This document focuses on product feature definitions. For technical implementation see [ARCHITECTURE.md](ARCHITECTURE.md), for domain background see [DOMAIN.md](DOMAIN.md)

---

## 1. Product Overview

### 1.1 Product Positioning
Kids Creative Workshop is an AI Agent-powered creative content generation platform that provides safe, fun, and educational content creation services for children aged 3-12.

### 1.2 Core Value Propositions
- **Inspire Creativity**: AI transforms children's drawings into vivid stories
- **Interactive Engagement**: Multi-branch interactive stories let children become story creators
- **Personalized Experience**: Remembers each child's creation history and maintains story continuity
- **Knowledge Sharing**: Dual-character on-demand podcast (Kids Daily) transforms complex news into fun conversational experiences for children, generated anytime on demand
- **Safety Assurance**: All content undergoes strict review and meets children's content standards

---

## 2. Target Users

### 2.1 User Personas

**Xiaoming (Age 7) - Young Artist**
- Loves drawing and wants to see drawings "come to life"
- Interested in dinosaurs, space, and animals
- Attention span: 15-20 minutes

**Mrs. Li (Age 35) - Parent**
- Concerned about children's education and content safety
- Wants children exposed to educational content
- Worried about inappropriate content on the internet

**Teacher Zhang - Educator**
- Needs engaging teaching materials
- Wants to inspire students' creativity
- Looking for age-appropriate content

---

## 3. Core Features

### 3.1 Image-to-Story [Near Complete]

#### Feature Description
Children upload drawings, and the AI Agent analyzes the drawing content to generate personalized stories.

#### User Scenario
```
Xiaoming draws a puppy playing in the park
  ↓
Uploads to the system
  ↓
AI identifies: puppy, trees, sun, happy mood
AI discovers: Xiaoming drew this same dog last week, named "Lightning"
  ↓
Generates story: "Lightning the puppy came to its favorite park again today..."
  ↓
Output: text story + audio narration
```

#### Input
- **Required**: Drawing image (PNG/JPG, max 10MB)
- **Optional**: Child's age, interest tags

#### Output
- Story text (200-500 words, adjusted by age)
- Audio narration (voice options: gentle grandma, playful sprite, etc.)
- Educational highlights summary

#### Key Features
- **Character Memory**: Recognizes recurring characters (e.g. "Lightning the puppy") and maintains story continuity
- **Age Adaptation**: Ages 3-5 short stories (100-200 words), ages 6-8 medium (200-400 words), ages 9-12 longer (400-800 words)
- **Safety Review**: Automatically filters content inappropriate for children

#### Acceptance Criteria
- [ ] Story length follows age group rules: ages 3-5 (100-200 words), ages 6-8 (200-400 words), ages 9-12 (400-800 words)
- [x] Safety score >= 0.85 required for delivery
- [ ] Response time < 10 seconds
- [x] Character memory: recognizes recurring characters
- [x] Sync path: complete provenance tracking
- [ ] Streaming path: provenance tracking aligned with sync path
- [ ] Streaming path: character sync to character table
- [ ] Contract tests covering agent output schema and API response format
- [ ] Happy-path API test assertions enabled

#### 3.1.1 Art Style Transfer [Phase 2]

##### Feature Description
After uploading a drawing, children can choose an art style (cartoon, oil painting, watercolor, pixel art, anime, crayon, storybook). The system uses AI image transformation to convert the drawing into the selected style. The stylized image serves as the story cover while providing additional creative context for story generation. The original drawing is always preserved.

##### User Scenario
```
Xiaoming draws a puppy playing in the park
  ↓
Uploads drawing, selects "cartoon" style
  ↓
AI converts the drawing to cartoon style (preserving core elements: puppy and park)
  ↓
Cartoon version becomes the story cover
AI generates a more creative story incorporating the cartoon style
  ↓
Output: cartoon cover + text story + audio narration
```

##### Technical Implementation
- **Model**: `black-forest-labs/flux-kontext-pro` (Replicate, SDK already in `requirements.txt`)
- **New MCP tool server**: `image_style_server.py`, tool name `mcp__image-style__transform_art_style`
- **Pipeline change**: `upload → vision_analysis → [style_transfer if theme ≠ none] → [image_safety_check] → vector_search → story_gen → safety_check → tts`
- **Safety gate**: Stylized images verified for child-appropriateness via Vision API; fails fall back to original drawing
- **Original preservation**: Original drawing is never overwritten or deleted

##### Available Styles (ArtTheme)
| Style | English ID | Prompt Template Example |
|-------|-----------|------------------------|
| Cartoon | `cartoon` | "Make this a colorful cartoon illustration" |
| Oil Painting | `oil_painting` | "Transform this into an oil painting style" |
| Watercolor | `watercolor` | "Make this a soft watercolor painting" |
| Pixel Art | `pixel_art` | "Convert this to pixel art style" |
| Anime | `anime` | "Make this in anime illustration style" |
| Crayon | `crayon` | "Make this look like a crayon drawing" |
| Storybook | `storybook` | "Transform this into a storybook illustration" |
| Keep Original | `none` | (skip transformation) |

##### Age Adaptation
| Age Group | Available Styles | Notes |
|-----------|-----------------|-------|
| Ages 3-5 | cartoon, crayon, watercolor, storybook | Soft, simple styles only |
| Ages 6-8 | All | Full style catalog |
| Ages 9-12 | All | Full style catalog |

##### Content Safety Requirements
- Every stylized image must pass Vision API safety verification before use
- On verification failure, silently fall back to original drawing and log a warning
- Safety scores recorded in the provenance chain

##### Edge Cases
- **No style selected**: Skip transformation entirely, backward compatible
- **Replicate API failure**: Fall back to original drawing, log warning, continue story generation
- **Generated image inappropriate**: Fall back to original drawing, flag for review
- **Large image (>5MB)**: Auto-scale before transformation

##### Acceptance Criteria
- [ ] `ArtTheme` enum contains 8 values (including `none`)
- [ ] `POST /api/v1/image-to-story` accepts optional `art_theme` parameter
- [ ] `image_style_server.py` MCP tool uses `flux-kontext-pro` model
- [ ] Style transformation completes within 15 seconds
- [ ] Core elements of original drawing preserved after stylization
- [ ] Stylized image passes Vision API safety verification
- [ ] Ages 3-5 only see 4 soft styles
- [ ] Pipeline behavior unchanged when no style is selected
- [ ] Contract tests cover `transform_art_style` MCP tool
- [ ] Stylized image displayed as story cover
- [ ] Frontend UploadPage adds style selection step (visual cards)

##### Out of Scope
- Custom style prompts (user free-text style descriptions)
- Multiple style stacking (only one style per transformation)
- Style preview (real-time preview requires extra API calls, too costly)
- Style application to interactive stories or news content

> **Parent Epic**: #40 | **Phase**: 2 | **Milestone**: Phase 2 — Interactive + Memory + News

#### Known Gaps (Remaining Gaps)
1. No runtime validation for story length — LLM-generated content may exceed age group target range
2. Streaming path lacks provenance tracking and character sync (sync path is complete)
3. No contract tests locking agent output schema
4. Happy-path API test assertions are commented out, CI cannot catch regressions

---

### 3.2 Interactive Story Generator [In Progress]

#### Feature Description
Generates multi-branch interactive stories based on children's interests, allowing children to make choices at key points that influence the story's direction.

#### User Scenario
```
Xiaohong wants to hear a dinosaur story
  ↓
AI generates opening: "The little dinosaur discovered a mysterious cave..."
  ↓
Presents choices:
  A. Bravely walk inside 🏔️
  B. Go home first and bring friends 👫
  ↓
Xiaohong chooses A
  ↓
AI generates next segment: "The little dinosaur entered the cave and found a glowing fossil..."
  ↓
Continues for 2-4 rounds, reaching the ending
  ↓
Summarizes educational highlights: courage, spirit of scientific exploration
```

#### Two Modes

**Linear Mode** (Traditional) [Not Started]
- Generates complete story at once
- Suitable for bedtime stories, reading practice
- 300-800 words

**Interactive Mode** [Complete — core flow]
- Generated in segments, 100-300 words each
- 2-4 decision points, 2-3 options each
- All branches lead to "good endings" (never punish children's choices)
- SSE streaming for opening and choices
- Age-based audio strategy (audio-first for 3-5, simultaneous for 6-9, text-first for 10-12)
- Preference tracking on story completion
- Save completed stories to My Library

#### Input
- **Required**: Child's age, interest tags (1-5)
- **Optional**: Story theme, educational goals, interactive mode

#### Output
- Story segments + audio narration
- Interactive options (with emoji)
- Educational highlights summary
- Session ID (for multi-turn conversation)

#### Key Features
- **Personalized Recommendations**: Adjusts themes based on historical preferences
- **Educational Integration**: Naturally incorporates STEAM and character education
- **Language Adaptation**: Automatically adjusts vocabulary and sentence complexity based on age

#### What's Built
- ✅ Core interactive mode: start → choose → progress → ending
- ✅ SSE streaming for all generation endpoints
- ✅ Age-based configuration (word count, complexity, segment count, audio mode)
- ✅ Safety check integration via MCP tool
- ✅ TTS audio generation with age-appropriate voice/speed
- ✅ Vector search for similar content
- ✅ Preference storage on completion (themes, concepts, interests, choices)
- ✅ Session management (create, track progress, expire)
- ✅ Full frontend: setup → playing → completed states with 2.5D visual effects
- ✅ Story save to My Library on completion
- ✅ Educational summary display with tags

#### Phase 2 Enhancements (Planned)
- ✅ **Preference-Aware Generation**: Injects children's accumulated preferences (themes, concepts, recent_choices) into opening prompts. `_fetch_preference_context()` reads themes, interests, and recent choices and injects them into story opening and branch continuation prompts
- 🔲 **Character Continuity**: Cross-session search and reuse of recurring characters (e.g. "Lightning the puppy" continues appearing in interactive stories); currently only image-to-story has character memory
- 🔲 **Theme Recommendations**: Recommend story themes based on preference history, replacing current manual-only input
- 🔲 **Session Recovery**: List active sessions and support resuming after interruption; backend `list_sessions` exists but no API route exposed
- 🔲 **Story Replay**: Re-read completed interactive stories (with full branch paths); currently saved as concatenated text only
- 🔲 **Choice Trait Tracking**: Track personality traits revealed by choices (courage, friendship, etc.); prompts are defined but Pydantic model lacks `trait` field
- 🔲 **Linear Mode**: Add one-click full story generation mode, suitable for bedtime reading
- 🔲 **Story Map Visualization**: Display the choice branch tree, letting children see their adventure path
- 🔲 **Cross-Session Story Universe**: Reference characters and events from previous sessions ("Remember Lightning the puppy's adventure last time?")
- 🔲 **Chapter Progress Rail Redesign**: Replace the fully-expanded chapter sidebar with a dot-based progress rail. Only the active chapter shows full details (chapter number, arrived-via choice, ending badge); other chapters render as bare dots that scale and fade by proximity to the current scroll position, driven by a continuous `scrollProgress` signal. Mobile pill row mirrors the same logic horizontally. Reduces visual noise on long stories (15-30+ segments in `unlimited` mode) and gives readers a calm, focused-but-alive sense of pacing. Respects `prefers-reduced-motion`.

#### Known Technical Debt
- Opening and continuation prompts are duplicated between regular/streaming functions; should be extracted into shared functions
- Interactive story domain lacks contract tests (`backend/tests/contracts/`)

> **GitHub Epic**: #41 | **Phase**: 2 (core flow complete, enhancements in Phase 2) | **Milestone**: Phase 2 — Interactive + Memory + News

---

### 3.3 Kids Daily [Phase 2]

> Upgraded from the original "News-to-Kids Converter", evolving from single-article text conversion to an immersive dual-character podcast experience with visual animations and daily auto-delivery. The original manual conversion feature is retained as "manual mode".

#### 3.3.1 Kids Daily Dialogue Mode

##### Feature Description
LLM rewrites news as a dual-character dialogue script: "Curious Kid" asks questions children would ask, and "Fun Expert" answers with vivid metaphors and stories. If a child has created recurring characters in image-to-story or interactive stories (e.g. "Lightning the puppy"), that character can join the dialogue as a "special guest host".

##### User Scenario
```
System generates Kids Daily from SpaceX news:

Curious Kid: Hey! I heard someone launched a super huge bus to the moon?
Fun Expert: That's right! Scientists built a giant rocket, taller than a 30-story building!
Curious Kid: Wow, that's taller than our school! How did it fly up there?
Fun Expert: It used super powerful engines that shot out blue and orange flames...
[Lightning the Puppy, Special Guest]: Woof woof! I want to ride a rocket to the moon too! Are there bones on the moon?
Fun Expert: Haha, there are no bones on the moon, but there are lots of craters...
```

##### Technical Implementation
- Uses Claude Agent SDK to generate structured dialogue scripts (JSON format, annotated with characters and lines)
- Queries Memory System for child's recurring characters and injects them into dialogue as guests
- Uses OpenAI TTS with multiple calls (different voice parameters) to generate audio for each character
- Audio assembled into complete podcast (frontend plays sequentially)
- All content passes safety review (safety_score >= 0.85)

#### 3.3.2 Visual Animatic Experience

##### Feature Description
During podcast playback, the screen displays 3-4 AI-generated news-themed illustrations with pan, zoom, and other 2.5D animation effects plus audio visualization when characters speak. The effect resembles video but only requires the cost of images + audio.

##### Technical Implementation
- Generates 3-4 illustrations based on news themes and dialogue content (using image generation API)
- Frontend uses CSS animations for pan/zoom (Ken Burns effect)
- Character avatars display audio waveform animation when speaking
- Illustration transitions synchronized with dialogue segments (via timestamp markers)

#### 3.3.3 Daily Drop

##### Feature Description
Children can subscribe to news channels of interest (space, dinosaurs, animals, robots, etc.). The system automatically generates personalized podcasts daily and delivers them to "My Library".

##### User Scenario
```
A parent subscribes Xiaoming to "Space" and "Animals" channels
  ↓
System automatically runs each day at dawn:
  1. Fetches latest child-friendly news
  2. Generates dual-character dialogue script
  3. Renders multi-character audio
  4. Generates accompanying illustrations
  5. Packages into complete daily news episode
  ↓
Xiaoming opens the app in the morning and finds new episodes waiting in "My Library"
```

##### Technical Implementation
- Backend scheduled task (configurable time, defaults to 2:00 AM)
- Batch generation by user subscription channels
- Generated results saved as story_type = "morning_show", appearing in My Library
- On generation failure, skip that channel without blocking others
- Rate limit: maximum 1 episode per subscription channel per day

#### 3.3.5 On-Demand Generation

##### Feature Description
Children don't need to wait for the next day's Daily Drop. They can press a "Listen Now" button anytime, and the system fetches the latest news in real time to generate a personalized podcast episode. This upgrades "Daily News" to "anytime listening" (Kids Daily), lowering the usage barrier so children can get content immediately whenever they want to hear news.

##### User Scenario
```
Xiaoming comes home from school and wants to hear space news
  ↓
Opens the "Kids News" page and sees subscription channel cards
  ↓
Clicks the "Listen Now" button on the "Space" channel
  ↓
System in real time:
  1. Fetches latest space-related child-friendly news via Tavily
  2. Generates dual-character dialogue script
  3. Renders multi-character audio
  4. Generates accompanying illustrations
  ↓
Within 30 seconds, player launches and Xiaoming starts listening
```

##### Technical Implementation
- New `POST /api/v1/morning-show/generate-now` endpoint, accepting `child_id`, `category`, `age_group`
- Extract `_fetch_news_text()` from Daily Drop scheduler into shared module `news_headline_fetcher.py` for use by both scheduler and on-demand endpoint
- New SSE streaming variant `POST /api/v1/morning-show/generate-now/stream` to push generation progress
- Rate limit: maximum 3 on-demand generations per child per hour (Daily Drop does not count toward limit)
- Exceeding limit returns 429 + friendly message: "You've listened to a lot today! Come back in X minutes"
- Generated episodes saved as `story_type = "morning_show"`, marked `is_new = true`
- Reuses existing safety pipeline: `check_content_safety` (safety_score >= 0.85) + fail-closed fallback on failure

##### Frontend Interaction
- Subscription management page: each channel card adds a "Listen Now" button, showing loading animation on click
- News center Kids Daily mode: channel cards also provide "Listen Now" action
- Auto-navigate to player page after generation completes
- First-use onboarding copy updated: from "New episodes tomorrow morning" to "Click any channel to start listening anytime"

##### Rate Limiting and Cost Control
- On-demand generation involves Claude Agent SDK + Tavily + OpenAI TTS + optional illustration generation, which is costly
- 3 per hour cap balances user experience with cost
- When rate-limited, display friendly countdown and guide children to replay past episodes

##### Edge Cases
| Scenario | Expected Behavior |
|----------|-------------------|
| Tavily unavailable/returns empty results | Show error message: "Can't find fresh news right now, try again in a few minutes!" |
| Claude Agent SDK generation fails | Fall back to deterministic mock dialogue, mark `is_degraded = true` |
| Child has no subscriptions but accesses generate-now | Return 400 prompting to subscribe to a channel first |
| Rate limit exceeded | Return 429 + `retry_after` header + friendly message |
| Same child, same channel, concurrent requests | Allowed (generates different episode_id), rate limiting prevents abuse |

#### 3.3.4 Unified News Hub

##### Feature Description
The frontend merges "manual news conversion" and "daily news" into a single "Kids News" entry point with two mode options. Home navigation and library tabs are unified into one entry, reducing cognitive load for children.

##### User Scenario
```
Child/parent clicks "Kids News" card on homepage
  ↓
Enters News Hub page with mode toggle at top:
  - Quick Read: paste news text/URL → get simplified article
  - Kids Daily: generate full dialogue podcast + illustrations + audio
  ↓
In the library, "Kids News" tab displays both types uniformly:
  - Daily news episodes: showing play button, duration
  - Quick Read: showing text preview
  ↓
Sorted by creation time (newest first), no need to switch between tabs
```

##### Technical Implementation
- Frontend homepage merges into one "Kids News" navigation card
- `NewsPage` refactored into News Hub with Quick Read / Kids Daily mode toggle
- `MorningShowPage` retained as episode player (navigated from News Hub or library)
- Library `ContentTab` merges `news_to_kids` + `morning_show` into unified `kids-news` tab
- Backend library API supports `content_type=kids-news` returning both `story_type` values
- Existing deep links `/news` and `/morning-show/:id` continue working (redirects or aliases)

##### Age Adaptation
- Consistent with §3.3 age adaptation table; mode toggle UI uses icons instead of text for ages 3-5

#### Input
- **On-demand mode**: Subscription channels + child's age + one-click trigger (On-Demand Generation)
- **Automatic mode**: Subscription channels + child's age + preference memory (Daily Drop)
- **Manual mode**: News URL/text + age (retains original conversion feature)

#### Output
- Dual-character dialogue script (JSON + readable text)
- Multi-character audio (segmented playback, different voices per character)
- 3-4 themed illustrations (with Ken Burns animation)
- Child-friendly title, why it matters, key concepts, interactive questions (retains original outputs)

#### Age Adaptation

| Age Group | Episode Duration | Illustrations | Dialogue Style | Voice Config |
|-----------|-----------------|---------------|----------------|-------------|
| Ages 3-5 | 1 minute | 2 | Curious Kid asks "why", Expert gives one-sentence answers | nova + shimmer, 0.9x speed, audio auto-play |
| Ages 6-8 | 2 minutes | 3 | Curious Kid asks "how" and "what if", Expert explains with metaphors | shimmer + fable, 1.0x speed, text+audio sync |
| Ages 9-12 | 3 minutes | 4 | Curious Kid challenges with "but...", Expert provides in-depth analysis | echo + fable, 1.1x speed, text-first+audio toggle |

#### Content Safety Requirements
- All dialogue scripts pass `check_content_safety` (safety_score >= 0.85) before TTS generation
- News source pre-filtering: skip articles involving violence, death, war, sex, political controversy, or casualty disasters
- Guest character dialogue undergoes separate safety check (user-created characters may have unexpected names/traits)
- Subscription channels are a curated allowlist (NewsCategory enum), no free-text support
- Daily Drop includes a safety gate: failed episode generations are discarded and replaced with backup fun-fact topics

#### What's Built
- ✅ Claude Agent SDK integration: `_generate_with_sdk()` calls Claude to generate structured dialogue scripts (PR #129)
- ✅ Daily news prompt: `backend/src/prompts/morning-show.md` defines dual-character dialogue format
- ✅ `DialogueScript` / `DialogueScriptOutput` Pydantic models parse SDK JSON responses
- ✅ Monotonically increasing timestamp normalization + character name standardization + guest line injection
- ✅ Memory System integration: queries recurring characters by `child_id` and injects as guests
- ✅ Multi-character TTS: each character uses different voice+speed combinations (OpenAI TTS)
- ✅ Visual animation: AI illustrations + Ken Burns pan/zoom + audio waveform
- ✅ Player page split view: illustrations+dialogue text+audio controls+character avatars
- ✅ Episodes displayed as "morning_show" type in My Library
- ✅ Auto-fallback to deterministic mock mode when SDK is unavailable
- ✅ Age adaptation: `_AGE_CONFIG` configures dialogue lines, duration, and voice per age group

#### Remaining Gaps
- ✅ **Safety score extraction**: `_generate_with_sdk()` extracts real `safety_score` from SDK structured output (#135)
- ✅ **SDK real-time generation**: `_generate_with_sdk()` uses real Claude SDK to generate structured dialogue scripts (PR #129, #107)
- 🔲 **SDK path contract tests**: Only mock path has tests; SDK response parsing/normalization/guest injection have no test coverage (#137)
- 🔲 **Explicit mock environment flag**: Missing `MORNING_SHOW_FORCE_MOCK` environment variable; currently relies only on pytest detection (#137)
- 🔲 **Character naming**: Acceptance criteria require Duo + Mimi character names; current code uses `curious_kid` / `fun_expert` (#140)
- 🔲 **News conversion lacks audio narration**: News-to-Kids manual conversion mode accepts `enable_audio` parameter but ignores it; the only core feature without TTS audio
- 🔲 **Daily Drop scheduler not auto-started**: `morning_show_scheduler.start()` is never called at application startup; subscription channels won't auto-generate episodes
- 🔲 **Safety check fails silently**: `_check_story_safety()` returns 0.0 score when MCP tool is unavailable, potentially allowing unsafe content to bypass the review threshold

#### Acceptance Criteria
- [x] Kids Daily Agent generates dual-character dialogue scripts from news articles (Curious Kid + Fun Expert)
- [x] Memory System integration: child's recurring characters can be injected as "special guest hosts"
- [x] Multi-character TTS: each character uses different voice+speed combinations (OpenAI TTS voices)
- [x] Visual animation: 3-4 AI illustrations per episode with Ken Burns pan/zoom animation
- [x] Character avatars display audio waveform when speaking
- [x] Unified news center: single "Kids News" entry on homepage, News Hub page provides Quick Read / Kids Daily mode toggle
- [x] Library merged tabs: `kids-news` tab displays both `news_to_kids` + `morning_show` content types
- [x] Library API supports `content_type=kids-news` combined query
- [ ] Channel subscription CRUD: subscribe/unsubscribe/list subscriptions
- [ ] Daily Drop scheduled task: backend auto-generates episodes for subscription channels, saves to My Library
- [ ] On-demand generation endpoint: `POST /generate-now` auto-fetches news and generates episodes without requiring URL
- [ ] On-demand generation SSE streaming variant: real-time generation progress pushed to frontend
- [ ] Rate limiting: max 3 on-demand generations per child per hour, friendly message on limit exceeded
- [ ] Frontend "Listen Now" button: one-click on-demand generation from both subscription page and news center
- [ ] Onboarding copy update: from "New episodes tomorrow" to "Click anytime to listen"
- [x] Episodes displayed as new content type "morning_show" in My Library
- [x] Player page supports split view: illustrations+dialogue text+audio controls+character avatars
- [ ] First-use onboarding: illustrated channel subscription selection wizard
- [ ] Preference tracking: subscription channels and listening completion fed back to Memory System
- [ ] Episode generation latency: script+audio+4 illustrations < 60 seconds (excluding queue wait)

#### Edge Cases
- **No subscriptions**: Show friendly onboarding page: "Subscribe to channels you like, and new episodes will be waiting for you every morning!"
- **Generation failure**: Fall back to basic news conversion text mode, log failure
- **No available news**: Skip that channel, fill with built-in fun-fact knowledge base "tips"
- **First-time use**: Guide children to select 1-3 subscription channels
- **No recurring characters**: If Memory System has no child characters, use built-in default characters (e.g. "Professor Owl", "Captain Comet")
- **Unauthenticated user**: Daily news requires authentication (subscriptions are user-specific); unauthenticated users see sample/preview episodes

#### Out of Scope
- Full AI video generation (using static illustrations + CSS animation instead of Sora/Veo)
- Automated news crawling/scraping (initial version uses curated sources or manual input)
- Character voice cloning (guests use existing OpenAI TTS voices; voice cloning is Phase 3)
- Social/sharing features (COPPA privacy considerations)
- Parent analytics dashboard (Phase 3)
- Push notifications (Daily Drop creates episodes in library; push requires notification service)
- Background music/sound effects (sound design pipeline enhanced separately under TTS epic #45)

> **GitHub Epic**: #44 (upgraded) | **Phase**: 2 | **Milestone**: Phase 2 — Interactive + Memory + News

---

### 3.4 Content Safety System (Safety Check) [Complete]

#### Feature Description
Performs automatic safety review on all generated content to ensure compliance with children's content standards.

#### Review Dimensions

**Negative Content Filtering** (Prohibited)
- Violence: fighting, blood, weapons
- Horror: ghosts, darkness, thriller elements
- Inappropriate language: profanity, insults, discrimination
- Adult topics: sex, drugs, political controversy

**Positive Value Guidance** (Encouraged)
- Gender equality: avoid stereotypes (e.g. doctors always being male)
- Cultural diversity: represent different cultures and racial backgrounds
- Character education: friendship, courage, honesty, empathy
- Environmental awareness: caring for nature, protecting animals

#### Output
- Safety score (0.0-1.0)
- Issue list (if any)
- Modification suggestions (if any)

#### Safety Standards
- Score < 0.7: Content does not pass, needs modification
- Score 0.7-0.85: Warning, modification recommended
- Score > 0.85: Pass

---

### 3.5 Memory Management System [In Progress]

> Cross-reference: §3.11 My Agent introduces the buddy persona that the memory system addresses the child with ("Remember when *you and Sparkle* met the dragon?"). Treat the buddy as the second-person voice anchor for any future memory-recall surface.

#### Feature Description
Remembers each child's creation history and preferences to enable content continuity. Dual-layer storage architecture: SQLite manages structured data (character profiles, preference counts), ChromaDB manages semantic search (drawing similarity, story deduplication).

#### Memory Types

**Character Memory**
- Recognize recurring characters: e.g. a child draws "Lightning the puppy" repeatedly
- Maintain consistency: "Lightning the puppy"'s traits persist across different stories
- Character growth: over time, characters can "grow"
- Structured storage: SQLite `characters` table records character names, visual features, personality tags, appearance counts

**Preference Memory**
- Interest tracking: records topics children enjoy (dinosaurs, space, etc.)
- Interaction records: tracks children's choice preferences in interactive stories
- Learning progress: adjusts content difficulty based on feedback

**Story Associations**
- Historical references: "Do you remember Lightning the puppy's last adventure?"
- Theme continuity: prioritizes recommending topics children enjoy
- Deduplication: ChromaDB `story_embeddings` collection performs semantic deduplication to prevent generating near-duplicate stories

#### Implementation — Dual-Layer Storage Architecture

| Data Type | Storage Layer | Reason |
|-----------|--------------|--------|
| Character profiles (name, features, appearances) | SQLite `characters` table | Requires precise queries, counting, CRUD |
| Character semantic matching (cross-drawing recognition) | ChromaDB `children_drawings` | Embedding similarity matching, already implemented |
| Preference and interest counts | SQLite `child_preferences` | Structured counters, already implemented |
| Story deduplication | ChromaDB `story_embeddings` | Semantic similarity detection for near-duplicate stories |
| Cross-story reference context | SQLite `stories` table | Query recent stories by child_id, table already exists |

#### What's Built
- ✅ ChromaDB vector search: `search_similar_drawings` + `store_drawing_embedding` (drawing embeddings + character metadata)
- ✅ Preference repository: `PreferenceRepository` tracks themes/concepts/interests/recent_choices/morning_show engagement
- ✅ Preference-aware generation: `_fetch_preference_context()` injects preferences into interactive story opening and continuation prompts
- ✅ Daily news guest character injection: queries recurring characters in ChromaDB by child_id
- ✅ Multi-pipeline preference updates: image-to-story, interactive story, news conversion, and daily news all update preference data

#### Remaining Gaps
- ✅ **Character structured storage**: `characters` SQLite table + `CharacterRepository` CRUD implemented; image-to-story and interactive story auto-sync characters on completion
- 🔲 **Character data richness**: `upsert_character` only passes name/description, not visual_features/traits (schema supports them but they're not populated)
- 🔲 **CharacterRepository user_id scoping**: CharacterRepository only isolates by child_id, not using user_id:child_id composite key (inconsistent with PreferenceRepository, creates cross-user data leakage risk)
- 🔲 **Story deduplication**: `store_story_embedding` and `search_similar_stories` MCP tools are implemented, but no agent code calls them — no dedup check before generation, no embedding storage after generation
- ✅ **Cross-story memory**: `story_memory.py` injects recent 3 story summaries into agent prompts, supporting cross-story references
- ✅ **Memory API exposure**: `GET/DELETE /api/v1/memory/preferences/{child_id}` and `GET /api/v1/memory/characters/{child_id}` implemented
- 🔲 **Frontend memory consumption**: Frontend does not call memory APIs; no character gallery, no preference display, no theme recommendations
- ✅ **Buddy memory wiring (§3.11)**: `my_agent_proxy` now injects episodic memory (story_memory) and factual memory (preferences) into every buddy chat turn so the buddy can say "Remember when you and Sparkle went to the moon?" — closing the §3.5 ↔ §3.11 promise.
- ✅ **Contract test coverage**: PreferenceRepository, preference scoping, preference retention, story memory, and interactive memory contract tests implemented
- ✅ **Privacy compliance**: `recent_choices` capped at 50 entries, theme scores decay after 6 months, DELETE endpoint clears SQLite + ChromaDB data
- 🔲 **Theme recommendation engine**: Preference data has been accumulated but no recommendation algorithm exists; no personalized theme suggestions shown to users
- 🔲 **Character growth and difficulty progression**: Character traits accumulate over time, reading difficulty adapts with usage (P3 enhancement)
- 🔲 **Hybrid search across drawings + stories**: Today retrieval is either pure SQL key-lookup (recent N) or pure pgvector cosine. Neither lets the buddy answer "find my Lightning Dog story" — exact-name and fuzzy-concept must both count. Hybrid search (BM25 + vector via Reciprocal Rank Fusion) closes this gap on the existing `drawing_embeddings` and `story_embeddings_pg` tables — no new store. Depends on local-dev pgvector migration landing first.

#### Hybrid Retrieval Approach (Phase 2)

The memory system uses **two retrieval styles**, picked per call:

| Style | Where it runs today | Where hybrid extends it |
|---|---|---|
| General SQL (`WHERE … ORDER BY counter DESC`) | session, episodic-by-recency, factual, characters-by-appearance, procedural | unchanged |
| Vector cosine (`embedding <=> ?::vector`) | drawing recognition + story dedup (specialists only) | replaced by Reciprocal Rank Fusion of BM25 (Postgres `tsvector`) + vector cosine |
| **Hybrid (BM25 + vector, RRF)** | not yet used | drawing recognition, story dedup, AND a new `search_my_stories(query)` MCP tool the buddy can call from chat |

**Why RRF (not weighted score blend)**: rank-based fusion is robust without needing to normalize raw scores from two different scoring functions (BM25 raw vs. cosine distance). One additional `tsvector` column + GIN index on each embedding table; no new store.

#### Graph RAG — Out of Scope Today

Graph traversal + vector retrieval (e.g., FalkorDB as a lightweight Cypher backend) would unlock multi-hop queries like *"characters that share a story with Sparkle"* or *"themes preferred by kids in my group"*. **Deferred until a real Inspiration Daily (§3.10) or Content Hub (§3.12) user story demands cross-entity recommendation that hybrid search alone cannot serve.** Trigger condition: an explicit recall miss attributable to flat-counter limitations.

#### Content Safety Requirements
- Privacy protection: only stores creative content, not personal sensitive information
- COPPA compliance: provides parent-accessible data deletion endpoint
- Preference data minimization: `recent_choices` limited to most recent 50 entries, expired theme scores auto-decay

#### Acceptance Criteria
- [x] `characters` SQLite table: child_id, name, description, visual_features, traits, appearance_count, first/last_seen
- [x] `CharacterRepository` service: CRUD + list characters by child_id + sort by appearance count
- [x] Auto-sync characters to `characters` table on image-to-story and interactive story completion
- [ ] `CharacterRepository` uses user_id:child_id composite key for isolation (consistent with PreferenceRepository)
- [ ] `upsert_character` calls pass visual_features and traits (extracted from visual analysis results)
- [ ] ChromaDB `story_embeddings` collection: query semantically similar stories before generation, trigger dedup at similarity > 0.9
- [x] Generation prompts inject recent 3 story summaries, supporting cross-story references
- [x] `GET /api/v1/memory/preferences/{child_id}` returns preference data
- [x] `GET /api/v1/memory/characters/{child_id}` returns character list
- [x] `DELETE /api/v1/memory/preferences/{child_id}` clears preference data (including ChromaDB cleanup)
- [x] `PreferenceRepository` and `vector_search_server` contract test coverage
- [x] `recent_choices` capped at 50 entries, theme scores auto-decay after 6 months without update
- [ ] Frontend ProfilePage displays character gallery, preference summary, theme recommendations
- [ ] Theme recommendation engine: recommends personalized themes based on preference history
- [ ] `my_agent_proxy` injects `**Story Memory**` (episodic) and `**What I Know About You**` (factual + semantic) sections into the buddy chat prompt; both empty-safe and prompt-size bounded
- [ ] Buddy chat replies that reference memory still pass `check_content_safety` ≥ 0.85 via the safety-review subagent
- [ ] `drawing_embeddings` and `story_embeddings_pg` each have a `tsvector` column + GIN index; hybrid search (BM25 + cosine via RRF) replaces vector-only retrieval in `search_similar_drawings` and `search_similar_stories`
- [ ] New `search_my_stories(query)` MCP tool: the buddy can answer "find my X story" on `/my-agent` using hybrid retrieval, with `user_id:child_id` scope enforced

#### Out of Scope
- Character growth mechanism (traits evolving over time) — Phase 3
- Reading difficulty adaptation (per-child reading_level) — Phase 3
- Cross-child character sharing

> **GitHub Epic**: #42 | **Phase**: 2 | **Milestone**: Phase 2 — Interactive + Memory + News

---

### 3.6 My Library [Implemented]

> Cross-reference: §3.12 Content Hub provides the *public* sharing surface; My Library remains private. Library cards now display the child's buddy byline (§3.11) alongside the title, so children see consistent authorship between their library and any public posts they make.

#### Feature Description
A unified content library where children can browse, search, bookmark, and revisit all creative outputs: art stories, interactive narratives, and kids news. The library adapts its display by age group, functioning like a "personal magic bookshelf" that grows with the child's creations.

#### User Scenario
```
Child opens "My Library"
  ↓
Sees all creations, sorted by newest by default
  ↓
Uses tab filters by type (Art Stories / Interactive / News)
  ↓
Optional: search by keyword, sort by date or bookmarks
  ↓
Clicks star to bookmark favorite stories
  ↓
Clicks card to revisit story, or clicks audio icon to listen directly in the library
  ↓
Parent switches to "Growth" view to see creation timeline
```

#### Features
- **Unified Browsing**: All content types in one view, each type with dedicated card design
- **Search**: Full-text search across story text, titles, themes, and character names
- **Bookmarks**: Bookmark/star system for quick access to favorite content
- **Sorting**: Sort by date (newest/oldest) and bookmarks-first
- **Audio Preview**: Play story audio directly on library cards without navigating away
- **Grid/List Toggle**: Switch between compact grid and detailed list views
- **Age Adaptation**: UI complexity adapts to age group
- **Growth Timeline**: Visual chart showing creation frequency over time (see "Growth Timeline" subsection below)

#### Growth Timeline

##### Feature Description
Parents and children aged 9-12 can switch to a "Growth" view at the top of the library to see a simple chart of creation frequency over time. Helps parents understand their child's creative habits while giving older children a sense of achievement about their progress.

##### User Scenario
```
Parent/older child opens "My Library"
  ↓
Clicks "Growth" toggle button at top of library
  ↓
Sees bar/line chart of creation counts grouped by week (default) or month
  ↓
Toggles week/month dimension to view trends at different time scales
  ↓
New users see an encouraging empty state: "Start creating! Your growth story begins with your first drawing!"
```

##### Technical Implementation
- **Backend**: `GET /api/v1/library/stats?group_by=week|month` returns time-period-aggregated creation counts with `period`, `count`, and optional `content_type` breakdown
- **Frontend**: Lightweight chart component (pure SVG or small library like recharts-lite), no heavy dependencies
- **Data Source**: Aggregates from existing library database table by `created_at`, no new storage needed

##### Age and Permissions
| Condition | Visibility |
|-----------|-----------|
| Ages 3-5 | Growth view entry not shown |
| Ages 6-8 | Growth view entry not shown |
| Ages 9-12 | Growth toggle button and chart shown |
| Parent role | Always visible (regardless of child's age group) |

##### Acceptance Criteria
- [x] `GET /api/v1/library/stats` returns creation count JSON grouped by week/month
- [x] Response includes `period` (date string), `count` (integer), optional `by_type` (breakdown by content type)
- [x] Frontend chart component renders bar or line chart with week/month toggle
- [x] Library top has toggle button switching between content view and growth view
- [x] Only ages 9-12 and parent role can see growth view entry
- [x] Encouraging empty state message when no creation records exist
- [x] Chart is responsively adapted for mobile viewports
- [x] No personal privacy data exposed — aggregated counts only

##### Out of Scope
- Separate trend charts by content type (only total count provided, `by_type` is optional extension)
- Comparison/leaderboard with other children (privacy and educational philosophy constraints)
- Export chart as image/PDF

#### Age Adaptation

| Age Group | Display Style |
|-----------|--------------|
| Ages 3-5 | Large card layout (max 2 per row), prominent audio play button, minimal text, emoji tags, no search bar (parents can search), colorful backgrounds |
| Ages 6-8 | Medium cards (2-3 per row), search bar visible, simple sort dropdown, star bookmarks, theme tags visible |
| Ages 9-12 | Compact grid (3-4 per row), full search+sort+filter controls, word count and reading stats visible, growth timeline accessible, list/grid toggle |

#### Content Safety Requirements
- Library only displays content that passed safety review (safety_score >= 0.85)
- Bookmark operations do not require re-safety-check (content was checked at creation time)
- Search does not expose intermediate/archived unsafe content — only published/candidate lifecycle states are queryable

#### Acceptance Criteria
- [x] Library displays all three content types (art stories, interactive sessions, news) with unified card design
- [x] Tab filtering works: "All", "Art Stories", "Interactive", "Kids News" (merged news_to_kids + morning_show)
- [x] Search input filters by title, story text preview, themes, and character names
- [x] Sort options: "Newest first" (default), "Oldest first", "Bookmarks first"
- [x] Each library card has a bookmark/unbookmark toggle, persisted to backend
- [x] Grid view toggle (grid shows larger thumbnails)
- [x] Pagination for all content types ("Load more")
- [x] Audio mini-player on library cards: click play/pause without leaving library
- [x] Library UI age-adapted (3-5: large cards; 6-8: balanced; 9-12: compact grid+data)
- [x] Growth timeline view (detailed acceptance criteria in "Growth Timeline" subsection above)
- [x] Authenticated users see server data; unauthenticated users fall back to local storage

#### Profile Stats

##### Feature Description
Profile page displays creation counts for each content type, replacing the current "recent stories/sessions" lists. Stats stay in sync with the library — deleting content in the library immediately updates profile counts.

##### Stat Categories
| Stat Card | Data Source | Corresponding Library Tab |
|-----------|-----------|--------------------------|
| Art Stories | `stories WHERE story_type = 'image_to_story'` | Art Stories |
| Interactive Tales | `sessions` | Interactive |
| Kids News | `stories WHERE story_type IN ('news_to_kids', 'morning_show')` | Kids News |

##### Acceptance Criteria
- [x] Profile page shows 3 stat cards (Art Stories, Interactive Tales, Kids News), each with accurate count
- [x] No longer shows "recent stories" and "recent sessions" lists
- [x] Deleting content in library immediately updates profile counts (React Query cache invalidation)
- [x] Each stat card is clickable, navigating to library with corresponding tab filter
- [x] Gracefully displays "0" when count is zero

#### Profile Tabs & Parent/Child Organization [Phase 3]

##### Feature Description
The profile page should be reorganized into tabbed aspects so parents and children can find the right surface without scrolling through unrelated account, memory, reward, and referral controls. The page remains a single `/profile` route, but it uses tabs to separate account-level settings from child-scoped growth and memory data.

##### Tabs
| Tab | Primary Audience | Contents |
|---|---|---|
| Overview | Parent + child | Active child summary, creation stats, achievements, star collection |
| Children | Parent | Child profile list, active child switcher, add/edit child profile entrypoints |
| Memory | Parent + older children | Character gallery, preference summary, selective memory deletion |
| Rewards | Child | Star jar, badges, streaks, age-adapted achievement surfaces |
| Account | Parent | Display name/avatar, referral invite, membership/quota details, privacy controls |

##### Behavior
- The selected tab is reflected in the URL (`/profile?tab=children`) so profile sections can be linked directly.
- Parent-only controls are hidden or disabled for child-role accounts.
- Child-scoped tabs read from the active child profile rather than only `users.default_child_id`.
- Mobile renders tabs as a horizontally scrollable segmented control; desktop renders tabs as compact top navigation.

##### Acceptance Criteria
- [ ] `/profile` renders tab navigation with stable URL query state
- [ ] Overview tab shows active child, stats, achievements, and stars without unrelated account controls
- [ ] Children tab is visible to parent-role users and lists all child profiles on the account
- [ ] Memory tab scopes characters/preferences to the active child profile
- [ ] Account tab contains display name/avatar, referral, and privacy controls
- [ ] Child-role users cannot access parent-only child management actions
- [ ] Mobile tab labels do not truncate or overlap

#### Homepage Recent Stories & Tips

##### Feature Description
Homepage displays the user's 3 most recent creations (across all types: art stories, interactive stories, kids news), using the unified library API as data source. Tips rotate among the three features.

##### Recent Stories
- Data source: `GET /api/v1/library?sort=newest&limit=3`
- Cards display content type labels; clicking navigates to correct page based on type
- "More" button below list links to `/library`

##### Rotating Tips
| Feature | Tip Text | Icon |
|---------|----------|------|
| Art to Story | The more colorful your artwork, the more magical your story! | 🎨 |
| Interactive Tales | Every choice leads to a different adventure! Try being brave~ | 🎭 |
| Kids News | Real-world events turned into fun, easy-to-understand stories! | 📰 |

##### Acceptance Criteria
- [x] Homepage shows 3 most recent mixed-type creations, sorted by newest
- [x] Each card has type label and correct navigation route
- [x] "More" button navigates to library
- [x] Generic empty state message when no content exists
- [x] Tips rotate every 5 seconds with crossfade animation

#### Out of Scope
- Sharing/social features (involves privacy and COPPA compliance)
- Collections/folder organization (Phase 3 consideration)
- Batch operations (keep it simple for children)
- Full parent analytics dashboard (Phase 3)
- Export/download as PDF (Phase 3)
- Custom image upload for avatars (involves content moderation)

> **GitHub Epic**: #49 | **Phase**: MVP | **Milestone**: MVP — Core Story Flow

---

### 3.7 Artifact Lifecycle [In Progress]

#### Feature Description
Every piece of AI-generated content in the system (image analysis, story text, audio, video) is tracked as an "Artifact", forming a complete generation provenance chain. This enables content safety auditing, version management, and automated cleanup.

#### Core Concepts

**Artifact**
Any content unit generated by the system: uploaded images, generated story text, TTS audio, safety review results, etc. Each artifact has a unique ID, type, lifecycle state, and provenance information.

**Run**
A complete content generation process (e.g. one image-to-story session). Contains multiple steps (AgentStep), each producing one or more artifacts.

**Lineage**
The complete artifact relationship graph from original input to final output. Supports `derived_from`, `variant_of`, `bundled_with`, and other relationship types.

**Lifecycle States**
- `intermediate` — Intermediate products during generation (e.g. drafts that failed safety review)
- `candidate` — Candidate outputs that passed safety review
- `published` — Final content delivered to the user
- `archived` — Archived, awaiting cleanup

#### Provenance Coverage

| Content Pipeline | Provenance Status | Notes |
|-----------------|-------------------|-------|
| Image-to-Story | ✅ Implemented | Complete Run/Step/Artifact records, artifacts linked to stories |
| Interactive Story | 🔲 Pending | Branch text and audio not recorded as artifacts |
| Kids News / Daily News | 🔲 Pending | Dialogue scripts and audio segments not recorded as artifacts |

#### Retention Policy

| Lifecycle State | Retention Period | Notes |
|----------------|-----------------|-------|
| intermediate | 30 days | Intermediate products auto-cleaned |
| candidate | 90 days | Unpublished candidate content |
| archived | 7 days | Archived content cleaned quickly |
| published | Permanent | Published content never auto-deleted |

Retention policy is enforced automatically via scheduled tasks, protecting published and canonical artifacts from accidental deletion.

#### Content Safety Requirements
- Artifact system records safety scores for each artifact, enabling admins to query content below threshold across all pipelines via `/admin/artifacts/safety-flagged` endpoint
- Provenance chain makes safety incidents traceable to specific generation steps and inputs
- My Library only displays artifacts with `published` or `candidate` lifecycle states

#### Acceptance Criteria
- [x] Artifact data model and database tables (6 tables with indexes and migrations)
- [x] Repository layer CRUD, lineage traversal, search, storage statistics
- [x] ProvenanceTracker service: complete lifecycle orchestration for runs/steps/artifacts
- [x] Retention policy definitions and admin cleanup endpoint
- [x] Complete provenance integration for image-to-story pipeline
- [x] My Library cover thumbnails resolved through artifact system
- [ ] Provenance integration for interactive story pipeline
- [ ] Provenance integration for kids news / daily news pipeline
- [ ] Retention cleanup scheduled task auto-runs
- [ ] Story text artifacts can link to story characters (STORY_TEXT role)

#### Out of Scope
- Frontend artifact browser (admin tool, Phase 3 consideration)
- Artifact version comparison (diff view)
- Cross-user artifact sharing

> **GitHub Epic**: #43 | **Phase**: MVP | **Milestone**: MVP — Core Story Flow

---

### 3.8 TTS & Audio Pipeline [Implemented — sound design deferred]

#### Feature Description

A pluggable multi-provider TTS engine supporting expressive voice narration, scene style matching, and sound design. Provides unified high-quality voice generation capabilities for all content pipelines (image-to-story, interactive story, daily news).

#### Core Capabilities

**Multi-Provider Abstraction Layer**

- `TTSProvider` protocol interface supporting hot-swapping and automatic fallback
- Current providers: OpenAI `tts-1` (baseline), Replicate minimax (emotion control), ElevenLabs (SOTA expressiveness)
- Three-tier fallback chain: ElevenLabs → Replicate → OpenAI, ensuring audio generation never fails

**Expressive Voice Control**

- Emotion parameters: `emotion` (happy, sad, neutral, surprised, disgusted), filtered by age group
- Voice settings: `stability`, `similarity_boost`, `style` (ElevenLabs specific)
- Base parameters: `voice`, `speed`, `pitch`, `volume`

**Scene Profiles**

- `bedtime` — Low stability, slow speed, gentle voice (suitable for bedtime stories)
- `adventure` — High expressiveness, normal speed, energetic voice (suitable for adventure stories)
- `spooky` — Medium stability, slightly slow, deep voice (suitable for mystery stories, ages 9-12)
- `educational` — High stability, clear, neutral voice (suitable for educational content)

**Sound Design Pipeline** [Phase 2+]

- Optional ambient sound base + event sound effect mixing (ducking narration)
- Can be enabled/disabled per request, configurable intensity levels

#### Provider Comparison

| Provider | Model | Strengths | Latency | Voices |
|----------|-------|-----------|---------|--------|
| OpenAI | tts-1 | Stable baseline, low cost | ~200ms | 6 |
| Replicate | minimax/speech-02-turbo | Emotion/tone control | ~300ms | 16 |
| ElevenLabs | eleven_flash_v2_5 | SOTA expressiveness, large voice library | ~75ms | 8 (curated) |

#### Age Adaptation

| Age Group | Default Speed | Available Emotions | Visible Voices | Scene Presets |
|-----------|--------------|-------------------|----------------|---------------|
| Ages 3-5 | 0.9x | happy, neutral | Max 4 (friendly labels) | bedtime, adventure |
| Ages 6-8 | 1.0x | happy, sad, surprised, neutral | Full catalog (simple labels) | All |
| Ages 9-12 | 1.1x | All (except angry/fearful) | Full catalog (with provider info) | All |

#### What's Built

- ✅ `TTSProvider` protocol interface + `OpenAITTSProvider` + `ReplicateTTSProvider` + `ElevenLabsTTSProvider` (#149, #243)
- ✅ Emotion parameters + age filtering (`AGE_EMOTION_MAP`)
- ✅ ElevenLabs → OpenAI and Replicate → OpenAI fallback with retry and latency logging
- ✅ `list_available_voices` MCP tool (merged OpenAI + Replicate + ElevenLabs catalogs)
- ✅ `generate_audio_batch` MCP tool (multi-segment batch generation)
- ✅ Multi-character TTS orchestration (daily news)
- ✅ On-demand audio generation API (`/api/v1/audio/generate`)
- ✅ Voice catalog REST API (`GET /api/v1/audio/voices`)
- ✅ Voice preview playback (`GET /api/v1/audio/preview`) with disk cache, provider validation, rate limiting, and frontend Howl playback
- ✅ Voice provider passthrough from frontend selection to image-to-story generation
- ✅ Scene profile presets (`bedtime`, `adventure`, `spooky`, `educational`) with age-aware spooky fallback
- ✅ Evaluation harness and provider decision fixtures for golden story benchmarking
- ✅ Contract tests: provider protocol shape, emotion filtering, backward compatibility

#### Deferred Gaps

- 🔲 **Sound design**: Ambient sound + sound effect mixing pipeline remains Phase 2+.
- 🔲 **Streaming TTS**: Play-as-you-generate remains deferred; current generation is file-based with provider fallback.
- 🔲 **Production SLO proof**: 99.9% availability requires production metrics over time; implementation logs provider, fallback, and latency for measurement.

#### Acceptance Criteria

- [x] Provider interface supports at least 3 providers (OpenAI + Replicate + ElevenLabs)
- [x] API supports emotion parameters without breaking existing clients
- [x] Scene style presets can be specified per request or auto-inferred from story type
- [x] At least 5 story samples per age group benchmarked across providers
- [x] P95 generation latency and provider fallback are tracked in logs/metrics payloads
- [x] Frontend voice picker displays age-adapted voice catalog + 3-5 second preview
- [ ] Sound design mode can be enabled/disabled per request
- [ ] Three-tier fallback chain has implementation support; 99.9% availability remains a production SLO to validate with live metrics

#### Out of Scope

- Full custom voice cloning (→ #150, Phase 3)
- Fully automated soundtrack generation
- ~~Real-time voice conversation (non-TTS scenario)~~ → moved in-scope under §3.16 Talk to Buddy

> **GitHub Epic**: #45 | **Phase**: 2 | **Milestone**: Phase 2 — Interactive + Memory + News

---

## 4. User Journeys

### 4.1 First-Time Use

```
Step 1: Parent registers an account as the parent/guardian owner
  ↓
Step 2: Creates or confirms a child profile (age, interests, buddy identity)
  ↓
Step 3: Child uploads first drawing
  ↓
Step 4: AI generates the first story
  ↓
Step 5: Child listens to the story (text + audio)
  ↓
Step 6: System records: drawing content, interest tags, interaction feedback
```

### 4.2 Daily Use

```
Scenario A: Image-to-Story
  Child draws → uploads → 5-10 second generation → listens to story

Scenario B: Interactive Story
  Select theme → start story → make choices → continue story → ending (2-4 rounds)

Scenario C: Kids News (unified entry)
  Click "Kids News" card → enter News Hub
  → Quick Read mode: parent pastes news → AI simplifies → read together with child
  → Kids Daily mode: generate dialogue podcast → listen to Curious Kid and Fun Expert chat
  → Lightning the puppy appears as guest → learn new knowledge
  → Library "Kids News" tab for unified viewing of all news content
```

### 4.3 Long-Term Use

```
Week 1: Creates 3 stories, system identifies interests: animals, adventure
  ↓
Week 2: System recommends related themes, child creates character "Lightning the puppy"
  ↓
Week 3: System remembers "Lightning the puppy", continues using it in new stories
  ↓
Week 4: Character "grows", Lightning the puppy learns new skills
  ↓
Month 3: Child has created 20+ stories, forming their own "story universe"
```

---

## 5. Feature Priority

### MVP (Minimum Viable Product) - Phase 1

**Must Have**:
- ✅ Image-to-Story (core feature)
- ✅ Linear story generation
- ✅ Content safety review
- ✅ Audio narration (TTS)
- ✅ Basic memory (recurring character recognition)
- 🔲 My Library (unified content browsing, search, bookmarks)

### Phase 2 (Launch Gate — §3.9)

**Production Launch Prerequisites (blocks public launch)**:
- 🔲 Per-user daily generation quota + usage tracking (§3.9.1)
- 🔲 Email registration + email verification (§3.9.2)
- 🔲 Railway backend deployment + Vercel frontend deployment (§3.9.3)
- 🔲 Referral-Based Membership (§3.9.4)

**Should Have**:
- ✅ Interactive story generation (multi-branch) — core flow complete, enhancements in §3.2
- 🔲 Interactive story enhancements (✅ preference-aware generation, 🔲 character continuity, 🔲 session recovery, 🔲 story replay)
- 🔲 Kids Daily (dual-character dialogue podcast + visual animation + daily delivery) — see §3.3
- 🔲 Advanced memory (character structured storage, story dedup, memory API, privacy compliance)
- 🔲 TTS & audio pipeline upgrade (ElevenLabs SOTA provider + scene presets + voice picker) — see §3.8
- 🔲 Channel subscription system (Daily Drop auto-generation)
- 🔲 Inspiration Daily (creative spark feed with seed bank + AI-augmented content) — see §3.10

### Cross-Phase — Responsive UI Polish [In Progress]

**Must Have** (MVP quality gate):
- 🔲 Global navbar mobile adaptation (hamburger menu or icon-based)
- 🔲 Library filter tabs horizontal scroll (no truncation on mobile)
- 🔲 Library card title two-line truncation (avoid over-truncation)
- 🔲 Upload page step ordering fix (CTA button position)
- 🔲 Login page mobile logo clipping fix
- 🔲 Profile page mobile layout fix (Edit Profile button overlap)
- 🔲 UploadPage React hook order fix (useState called after conditional return, violates React rules, may cause state corruption)
- 🔲 ImageUploader camera capture on tablets/phones (§3.15)

**Should Have**:
- 🔲 Library "New" badge expiry rule (auto-disappear after 7 days from creation)
- 🔲 Library word count label humanization (`60w` → `~1 min` or `60 words`)
- 🔲 Upload voice picker collapse/pagination (28 options too long)
- 🔲 React Router v7 future flag migration
- 🔲 Upload page DOM nesting validation error fix
- 🔲 StoryPage success banner conditional display (only appears when `justGenerated === true`, not when opened from Library)
- 🔲 LibraryPage per-tab empty state UI (with CTA guiding to corresponding creation page)
- 🔲 Voice input on Interactive Story theme + buddy chat (§3.15)

**Could Have**:
- 🔲 Library/Profile card hover feedback (desktop lift effect)
- 🔲 UploadPage art style picker visual cards (color blocks/gradient backgrounds) — completes §3.1.1 acceptance criterion "visual cards"
- 🔲 AvatarDisplay component deduplication (unify to directory version, sibling file changed to re-export or deleted)

### Phase 3

**Productization Track**:
- Dynamic picture book and story video experience (see §3.14.1)
- Parent creativity dashboard (see §3.14.2)
- Achievement badge system (see §3.14.3)
- Phase 3 positioning and pitch alignment (see §3.14.4)

**Could Have**:
- Multi-language support

---

## 6. Success Metrics (KPIs)

### Usage Metrics
- **Activity**: Children use the platform 3+ times per week
- **Completion Rate**: Interactive story completion rate > 80%
- **Creation Volume**: Average 2+ stories per user per week

### Quality Metrics
- **Parent Satisfaction**: > 4.5/5.0
- **Content Safety**: Inappropriate content pass-through rate < 0.1%
- **Response Speed**: Story generation < 10 seconds

### Educational Outcomes
- **Creativity**: Children's proactive creation frequency increases 30%
- **Reading Interest**: Reading time increases 50%
- **Knowledge Acquisition**: Children can explain new concepts in their own words

---

## 7. User Feedback & Iteration

### Collection Channels
- Parent ratings and reviews
- Children's interaction behavior analysis (clicks, completion rate)
- A/B testing different story styles

### Iteration Directions
- Adjust content complexity by age group
- Optimize interactive branch design
- Expand interest topic library
- Improve safety review accuracy

---

## 3.9 Production Launch & Cost Sustainability [Phase 2 — Launch Gate]

Goal: deploy the product to a public URL so real users can register and use it, while keeping AI API costs predictable.

### 3.9.1 Per-User Generation Quota

Every authenticated user has a daily generation quota (default: **3 AI generations per day**, resets midnight UTC).
Quota covers: image-to-story, interactive story opening, morning show episode generation.

**Acceptance Criteria:**
- [ ] `usage_repository` tracks (user_id, date, feature, count) in database (SQLite dev / PostgreSQL prod)
- [ ] Quota middleware returns HTTP 429 with `{"quota_remaining": 0, "resets_at": "..."}` when exceeded
- [ ] Frontend shows "X / 3 generations used today" on UploadPage and InteractiveStory start screen
- [ ] Quota is configurable via env var `DAILY_GENERATION_QUOTA` (default 3)

### 3.9.2 Email-Based Account Registration

Users register with email + password. A verification email must be confirmed before AI features are accessible.
Prevents throwaway accounts that drain quota.

**Acceptance Criteria:**
- [ ] Registration requires email + password (min 8 chars)
- [ ] Verification email sent on signup; unverified accounts blocked from AI endpoints
- [ ] Password reset flow (email link)
- [ ] Implementation: Supabase Auth (free tier) or self-hosted with FastAPI + email via SendGrid free tier

### 3.9.3 Production Hosting

| Layer | Service | Dev (local) | Prod (deployed) |
|-------|---------|-------------|-----------------|
| Frontend | Vercel (free) | Vite dev server | Auto-deploys from `main` |
| Backend | Railway ($5–7/month) | `uvicorn` local | FastAPI on Railway |
| Database | Supabase (free tier) | SQLite (aiosqlite) | PostgreSQL (asyncpg) |
| Vector Search | Supabase pgvector | ChromaDB (local) | pgvector extension in Supabase PostgreSQL |
| File Storage | Supabase Storage | Local disk (`data/`) | Supabase Storage buckets (CDN URLs) |
| Domain | Optional Cloudflare | localhost | ~$10/year |

**Architecture:**
- Database adapter abstraction with factory pattern: reads `DATABASE_URL` env var to select driver (aiosqlite vs asyncpg)
- pgvector replaces ChromaDB in production using same embedding model (all-MiniLM-L6-v2, 384 dimensions) for search parity
- Supabase Storage replaces local `StaticFiles` mounts for uploads, audio, videos, and styled images
- All SQL translated for dual compatibility: SQLite (dev) and PostgreSQL (prod)

**Acceptance Criteria:**
- [ ] Database adapter supports both SQLite and PostgreSQL via `DATABASE_URL` env var
- [ ] All 16 tables created correctly in Supabase PostgreSQL
- [ ] All repository queries work identically on both drivers
- [ ] pgvector stores drawing + story embeddings with similarity search parity to ChromaDB
- [ ] File uploads stored in Supabase Storage in prod, local disk in dev
- [ ] Backend live at a stable public URL with all env vars set
- [ ] Frontend live on Vercel pointing to backend URL via `VITE_API_BASE_URL`
- [ ] CORS configured for production frontend origin
- [ ] Health check endpoint returns 200
- [ ] Migration script moves existing SQLite + ChromaDB data to Supabase (idempotent)

### 3.9.4 Referral-Based Membership

A referral-based growth and membership tier system. Growth is driven by user referrals — users share the platform with friends and earn upgraded quotas.

#### Membership Tiers

| Tier | How to Get | Daily Quota | Badge |
|------|-----------|-------------|-------|
| Free | Default on registration | 3 generations/day | — |
| Plus | Refer 10 verified users | 9 generations/day (3×) | ⭐ Plus |

#### Referral Mechanics

- Every user gets a unique 8-character referral code on registration (e.g. `ABC12345`)
- Share link format: `https://<app-domain>/login?ref=<code>`
- A referral counts as "qualified" only when the referred user verifies their email
- When a referrer reaches 10 qualified referrals, their account auto-upgrades to Plus tier
- Upgrade is permanent (does not expire or downgrade)

#### Data Model

- `users` table: add `membership_tier` (free/plus), `referral_code` (unique), `referred_by` (nullable)
- New `referrals` table: tracks referrer → referred mapping, qualification status, timestamps

#### Acceptance Criteria

- [ ] `users` table has `membership_tier`, `referral_code`, `referred_by` columns
- [ ] `referrals` table tracks referrer/referred pairs with qualification status
- [ ] `referral_code` auto-generated on user creation (unique, 8-char alphanumeric)
- [ ] Registration accepts optional `referral_code` query param; creates referral record
- [ ] Referral qualifies when referred user\'s email is verified
- [ ] Auto-upgrade to Plus when qualified referral count >= 10
- [ ] `GET /api/v1/users/me/referrals` returns referral status
- [ ] Quota middleware reads `membership_tier` to determine per-user daily limit
- [ ] Frontend captures `?ref=` param on login/register page
- [ ] Profile page shows referral link, progress, and tier badge
- [ ] QuotaExceededOverlay includes "share to get more" CTA
- [ ] No child personal information exposed in share links

#### Known Gaps (Supabase Auth Path)

The referral feature was built and tested against the legacy auth path. With Supabase Auth enabled in production, three gaps prevent referrals from working:

1. **Registration drops referral code**: `authService.register()` does not pass `referral_code` to `supabase.auth.signUp()` metadata. The code is captured from `?ref=` but never reaches the backend.
2. **Auto-create ignores referral**: `_get_or_create_supabase_user()` in `deps.py` creates the local user row with `referred_by=None` and does not create a referral record.
3. **Qualification never triggers**: `qualify_and_maybe_upgrade()` exists in `user_service.py` but no code path calls it. No Supabase webhook handles email verification events.

**Fix**: Pass `referral_code` in Supabase signUp metadata → read it in `_get_or_create_supabase_user` → create referral record → qualify inline when `email_confirmed=True`.

#### Out of Scope

- Paid tiers or payment integration
- Multi-level / recursive referral rewards
- Admin dashboard for referral analytics (Phase 3)

---

### 3.10 Inspiration Daily — Creative Spark Feed [Phase 2]

> Replaces the static "fake news" newspaper card with a daily creative inspiration feed. Each day surfaces one real-world creative project, art idea, or young inventor story from around the globe — adapted for the child's age group — with a "Try This!" call-to-action that routes directly into the app's creation tools.

#### 3.10.1 Product Vision

**Core purpose**: Inspire children to create by showing them what other kids and creators are doing worldwide. The daily card answers: *"What cool thing can I try today?"*

**How it differs from Kids Daily (§3.3)**:

| Dimension | Inspiration Daily | Kids Daily |
|-----------|------------------|------------|
| Goal | Spark creativity — "I want to try that!" | Inform — "I understand the world" |
| Content | Creative projects, art ideas, inventions | Current events, news stories |
| Format | Single card, 10-second read | Full podcast, 2-3 min listen |
| Output | Routes to creation tools (draw/story) | Self-contained media |
| Cost | Low (text only) | High (TTS + illustrations + dialogue) |

#### 3.10.2 Daily Inspiration Card

##### Feature Description
Each day the homepage displays one creative inspiration card featuring a real-world creative project, art technique, invention, or DIY activity sourced from around the world. Content is rewritten by Claude into age-appropriate language with a clear creative prompt.

##### User Scenario
```
Child (age 7) opens the app in the morning
  ↓
Sees today's Inspiration Card:
  Title: "Bubble Painting Magic!"
  Body: "Kids in Brazil discovered you can make amazing art
         by blowing paint bubbles onto paper!"
  Prompt: "Try mixing soap, water, and paint — blow bubbles
           onto paper to make your own bubble art!"
  ↓
Taps "Try This!" → routed to /upload with creative context
  ↓
Draws their bubble painting → generates a story about it
```

##### Content Schema (InspirationCard)
- `title` — short, exciting headline
- `summary` — 1-2 sentences about the real-world project
- `source_hint` — anonymized origin (e.g. "A school in São Paulo")
- `creative_prompt` — actionable "try this" instruction
- `category` — art_project | invention | recycling | science_craft | performance
- `age_adaptations` — separate text for 3-5, 6-8, 9-12
- `illustration_emoji` — visual representation
- `cta_type` — draw | story | explore
- `cta_route` — target page path

#### 3.10.3 Content Sourcing Strategy

Three-layer approach:

1. **Seed Bank (launch)**: 50+ hand-curated creative project entries stored in the repo as structured data. Serves as fallback and bootstrap content.
2. **AI-Augmented Daily (Phase 2)**: Scheduled job queries external sources (Tavily) for topics like "kids creative projects", "children art activities", "young inventors". Claude rewrites the best result into an InspirationCard. Cached in database.
3. **Editorial Curation (Phase 3)**: Community-submitted projects, RSS from maker/education sites, parent-submitted ideas.

#### 3.10.4 Age Adaptation

Each InspirationCard provides three variants following existing AGE_RULES:
- **Ages 3-5**: Simple language, basic activities (no sharp tools, no unsupervised steps)
- **Ages 6-8**: Moderate detail, guided activities with household materials
- **Ages 9-12**: Full detail, more challenging projects, basic science/engineering concepts

#### 3.10.5 Integration with Creation Flow

The "Try This!" CTA button routes children to creation tools:
- `cta_type: "draw"` → `/upload` page (draw the inspired project)
- `cta_type: "story"` → `/interactive` page (create a story about it)
- `cta_type: "explore"` → `/news` page (learn more via Kids Daily)

Creative prompt text is optionally passed as context to pre-fill theme/interest tags.

#### 3.10.6 Gamification Integration

The existing tear-to-claim-star mechanic (Epic #371) is preserved:
- Child tears the newspaper card → earns daily star
- Star claiming is independent of content source
- Tear animation unchanged

#### Acceptance Criteria
- [ ] API endpoint `GET /api/v1/inspiration-daily?age_group=6-8` returns today's InspirationCard
- [ ] Content changes daily (not the same as yesterday)
- [ ] All content passes safety check (safety_score >= 0.85)
- [ ] Age adaptation returns appropriate variant for each age group
- [ ] Fallback to seed bank if live generation fails
- [ ] "Try This!" CTA routes to correct creation page
- [ ] Tear-to-claim-star mechanic continues to work
- [ ] No real children's names in content (anonymized to "a kid in [country]")
- [ ] No dangerous activities for ages 3-5 (sharp tools, fire, unsupervised)
- [ ] Cultural diversity: content rotates through different countries/cultures

#### Out of Scope (Phase 2)
- User-submitted creative projects
- RSS feed integration
- Editorial curation dashboard
- Commenting or rating on inspiration cards
- Sharing inspiration cards externally

---

### 3.11 My Agent — Personal Creative Buddy [Phase 2]

> Each child has a customized AI companion ("creative buddy") that serves as their personal creative assistant and as the public byline whenever they share work in Content Hub (§3.12). The buddy is the privacy primitive: real names, usernames, and emails are never shown publicly — only the buddy the child crafted.

#### 3.11.1 Product Vision

**Core purpose**: Give every child a stable, customized creative companion that grows with them. The buddy answers: *"Who's making this with me, and who do I show up as when I share?"*

**Why this exists**:
- Children's creative work is most engaging when it has a *narrator* and a *who*. A buddy gives both.
- Public sharing of children's content normally leaks PII (real name, username, email). The buddy persona is a structural privacy layer — no PII is ever joined to public reads.
- The buddy is a natural anchor for future Memory features (§3.5): "Remember when you and Sparkle the Brave Lion went to the moon?"

#### 3.11.2 First-Login Onboarding

Registration is parent-owned by default. The primary path is a parent/guardian creating the account, then configuring one child profile inside that account. Child-started registration is allowed only when a parent/guardian email is supplied, and the account remains in `pending_parent_consent` until a parent approves.

After successful login or registration, a returning user with `onboarded_at = NULL` is redirected to `/my-agent`, where an onboarding modal opens automatically.

The flow has these steps:

1. **Greeting** — the buddy introduces itself: *"Hi! I'm your creative buddy. I'm going to help you make stories together. Want to give me a name?"*
2. **Name + nickname** — the child names the buddy, optionally enters their own nickname for in-app display.
3. **Avatar** — the child picks one of the 20 animal emojis from the existing avatar set (shared with `/profile`).
4. **Title** — the child picks from a curated list of 20 buddy titles (e.g. "Story Wizard", "Brave Lion"); free-text titles are allowed for ages 9–12 only and must pass safety check.
5. **Parent-consent gate** — before completion, a parent-role account confirms they're OK with the buddy being shown publicly when stories are shared. Child-role accounts cannot self-consent.

`POST /api/v1/me/onboarding/complete` requires a parent-role account, an agent, and parent consent before flipping `users.onboarded_at`.

##### Registration Ownership

| Setup path | Required fields | Account role | Consent state | Notes |
|---|---|---|---|---|
| Parent / guardian setup | Parent email, password | `parent` | `not_required` | Primary supported path. Parent can access parent dashboard and configure child profiles. |
| Child-started setup | Child account email + parent/guardian email | `child` | `pending_parent_consent` | Protected features that require adult consent stay blocked until parent approval is implemented. |

For MVP, the product should steer users toward parent-owned registration. Child-started signup exists to capture intent safely, not to bypass adult approval.

##### Child Profile Selection & Switching [Phase 3]

Parent-owned registration creates the first child profile, but the child still needs an explicit entry point to choose *who is creating today*. The system must support multiple child profiles under one parent account and keep every child-scoped surface bound to the selected profile.

###### Child Profile Model
| Field | Description | Notes |
|---|---|---|
| `child_id` | Stable profile id within the parent account | Server-generated or accepted from trusted registration setup |
| `user_id` | Parent account owner | Required ownership boundary |
| `name` | Child-facing nickname | No real full name required; safety/PII validation applies |
| `age_group` | `3-5`, `6-8`, `9-12` | Drives age adaptation across creation flows |
| `interests` | Initial interest tags | Seed memory and recommendations |
| `avatar` | Optional child profile avatar | Whitelisted emoji/avatar only in v1 |
| `is_default` | Parent-selected default profile | Used when no active child session is set |

###### Entry Points
- **After parent registration**: route to child profile confirmation, then My Agent setup for that child.
- **After parent login**: if the account has multiple child profiles, show "Who's creating today?" before creation surfaces.
- **Navigation/Profile**: always expose the active child profile and a switcher.
- **Parent dashboard/Profile Children tab**: parent can add/edit/archive child profiles and set the default.

###### Active Child Contract
- Frontend stores the active child profile in `useChildStore`.
- Backend persists child profiles and validates ownership on every child-scoped endpoint.
- `users.default_child_id` remains a compatibility pointer, but the canonical profile data lives in a `child_profiles` table.
- My Agent, Library, Kids Daily, Interactive Story, Image-to-Story, Achievements, Memory, and Parent Dashboard all use the same active child profile contract.

###### Acceptance Criteria
- [ ] Parent accounts can create at least one child profile after registration
- [ ] Parent accounts can add a second child profile from `/profile?tab=children`
- [ ] A "Who's creating today?" picker appears when a parent account has multiple active child profiles and no active child is selected
- [ ] Selecting a child updates the active child profile used by My Agent, Library, Kids Daily, Interactive Story, Image-to-Story, Achievements, and Memory
- [ ] Backend rejects child-scoped requests for profiles not owned by the authenticated parent account
- [ ] Child-role accounts cannot create sibling profiles or change parent-owned profile settings
- [ ] Archived child profiles no longer appear in pickers but remain available for historical content scoping

##### Age-Gated Onboarding Variants

| Ages 3–5 | Ages 6–8 | Ages 9–12 |
|---|---|---|
| Avatar-only step. Buddy name auto-suggested ("Sunny", "Bubbles") with a shuffle button. No title step. | Full flow: name (with 3 suggestions), avatar, title from curated dropdown only. Free-text title disabled. | Full flow with free-text title and an optional "tell me about you" nickname step. |

##### Parent-Consent Copy

```
Title:    Meet your child's creative buddy
Body:     This buddy is the name and animal your child picks to show on
          stories they share publicly in Content Hub. We never show your
          child's real name, email, or username — only the buddy.

          You can change the buddy any time from "My Agent". Past stories
          keep the buddy that posted them, so your child's creative timeline
          stays consistent.

          Note: We re-check the buddy's name and title for safety every
          time it's edited.

Buttons:  [I'm a parent and I'm OK with this]   [Not now]
```

The "Not now" path lets the child use the rest of the app but blocks Content Hub posting until consent is given.

#### 3.11.3 Customization Fields

Stored in `user_agents` keyed on `(user_id, child_id)` (one buddy per child profile in v1; schema designed to allow many later).

| Field | Source | Validation |
|---|---|---|
| `agent_name` | Free text | `check_content_safety` ≥ 0.85, server-side PII regex, max 32 chars |
| `agent_avatar_id` | Whitelist (20 animal emojis) | Must match server-mirrored list |
| `agent_title` | Curated dropdown OR free text (9–12 only) | If free, `check_content_safety` ≥ 0.85, max 32 chars |
| `nickname` | Free text on user, optional | `check_content_safety` ≥ 0.85, no emails/phone numbers |

##### Curated Title List (v1)

```
Story Wizard          Brave Lion          Galaxy Explorer
Dragon Friend         Magic Painter       Forest Guardian
Ocean Adventurer      Star Dreamer        Dance Captain
Inventor              Riddle Master       Cloud Surfer
Tiny Hero             Silly Scientist     Music Maker
Treasure Hunter       Kindness Knight     Robot Buddy
Time Traveler         Sunshine Maker
```

20 titles to match the 20-emoji avatar set (1:1 visual symmetry, easy first pick).

#### 3.11.4 Editing the Buddy

`PUT /api/v1/me/agent` is upsert-style. Edits re-run safety checks. **Edits never rewrite history** — buddy snapshots persisted on prior `hub_posts` rows are immutable. This means a child can rename their buddy freely, and existing posts keep the byline they were published under.

#### 3.11.5 Buddy as Byline

When a story is shared to Content Hub (§3.12), the server attaches the buddy persona snapshot to the post row. The hub feed reads the snapshot fields, not the user table. This is the COPPA invariant — enforced by contract test, not convention.

#### 3.11.6 Where the Buddy Appears

- `/my-agent` — view + edit
- `/library` — buddy byline shown on user's own story cards ("By Sparkle the Brave Lion")
- `/content-hub/*` — buddy byline shown on every public post
- (Future, §3.5) — buddy is the second-person voice the memory system addresses the child with

#### 3.11.7 Multi-Agent Orchestration & Page Launcher [Phase 2]

The buddy is also a **conversational launcher** built on Claude Agent SDK
subagent delegation. It holds one chat conversation, detects creative intent,
and routes work to the right specialist while keeping the existing standalone
pages untouched.

##### Architecture

| Layer | Role |
|---|---|
| Proxy agent (`backend/src/agents/my_agent_proxy.py`) | Holds the chat conversation, detects intent, delegates via SDK `Agent` tool, streams SSE |
| `image-story-specialist` | Creates a story from an uploaded drawing (wraps `image_to_story_agent`) |
| `interactive-story-specialist` | Starts or continues branching stories (wraps `interactive_story_agent`) |
| `kids-daily-specialist` | Creates child-friendly news episodes (wraps `kids_daily_agent`) |
| `safety-review-specialist` | Reviews every buddy chat reply for §3.4 compliance before delivery |

All four specialists share an MCP server (`my-agent-tools`) that exposes the
underlying agent functions as tools. Skill gating (the `enabled_skills` field
on `user_agents`) is enforced inside each tool — not just in the prompt.

##### Two Response Modes

Each turn the proxy picks one of two modes:

1. **Launch mode (default for creation requests)** — emits a `launch_flow`
   SSE event:
   ```json
   {"target": "image-to-story", "prefill": {"child_id": "...", "age_group": "6-8"}}
   ```
   The frontend handler routes to the existing page with prefill query params.
   The standalone page UI (upload widget, age picker, theme picker) handles
   the rest.

2. **Inline mode** — when context is sufficient (image already in chat,
   chat-only question, safety check on a buddy title, etc.), the specialist
   generates the result directly and returns it in the buddy's reply.

The `launch_flow` `target` field is **enum-validated server-side** to a closed
list (`image-to-story`, `interactive-story`, `kids-daily`). The model cannot
inject arbitrary routes — this is the safety primitive that protects against
prompt-injection-driven navigation.

##### Intent Routing Examples

| Child says | Mode | Subagent | Target |
|---|---|---|---|
| "Make a story from my drawing" | launch | image-story | `/image-to-story` |
| "Tell me about today's news" | launch | kids-daily | `/kids-daily` |
| "Continue our story" | launch | interactive-story | `/interactive-story` |
| "What did we make yesterday?" | inline | (proxy itself) | — |
| "Is 'Dragon Slayer' a good buddy title?" | inline | safety-review | — |

##### Age-Adapted Routing

| Ages 3–5 | Ages 6–8 | Ages 9–12 |
|---|---|---|
| Vague utterances ("story?") default to image-to-story. Safety threshold raised to 0.90. | Default behavior. One disambiguation question allowed for unclear intent. | Multiple specialists may be suggested in one reply ("I can do A or B — which?"). |

##### Backwards Compatibility (Non-Negotiable)

The multi-agent layer is purely additive. Users who never visit `/my-agent`
see zero behavior change:

- `image_to_story()`, `generate_story_opening()`, `generate_next_segment()`,
  and `generate_kids_daily_episode()` signatures are unchanged.
- `/api/v1/image-to-story`, `/api/v1/interactive-story`, `/api/v1/kids-daily`
  keep their current contracts.
- A user with `agent.enabled_skills = []` sees a polite chat-only buddy that
  never launches anything.

##### Why Claude Agent SDK (and not direct API calls)

The SDK provides subagent definitions, MCP tool servers, session resume, and
the `Agent` delegation tool out of the box. Reimplementing this on top of
`anthropic.AsyncAnthropic()` would mean rebuilding tool-use loops,
multi-agent routing, and session resume from scratch — work that delivers no
user value. Reliability issues (e.g. memory pressure on serverless) are
addressed inside the SDK via model selection and `effort` tuning, not by
removing it.

#### Acceptance Criteria
- [ ] First-login user is redirected to `/my-agent` and the onboarding modal auto-opens
- [ ] `users.onboarded_at` is non-null only after both an agent exists AND `parent_consent_at` is set
- [ ] `PUT /me/agent` rejects names with `check_content_safety` score < 0.85
- [ ] `agent_avatar_id` is rejected unless it matches the server-side whitelist
- [ ] Editing the buddy does not mutate prior `hub_posts.agent_*_snapshot` rows (locked by contract test)
- [ ] `GET /api/v1/me` returns `has_agent: bool` and `onboarded_at: string | null` so the frontend can drive the route gate without a second request
- [ ] Each child profile on the same account has its own buddy (per-child, not per-user — see closed bug #200 for the precedent)
- [ ] Age-gated onboarding variants render the correct steps for the active child's age group
- [ ] Buddy chat detects creation intent and emits `launch_flow` SSE events with enum-validated targets
- [ ] `launch_flow` events route the frontend to the matching standalone page with prefill query params
- [ ] Every buddy chat reply passes `check_content_safety` ≥ 0.85 before being delivered
- [ ] Disabled skills (per `user_agents.enabled_skills`) are blocked server-side, not just in prompts
- [ ] Existing standalone routes (`/image-to-story`, `/interactive-story`, `/kids-daily`) pass their pre-existing contract tests unchanged
- [ ] SDK session resumes across buddy chat turns via `chat_session.sdk_session_id`

#### Out of Scope (Phase 2)
- Multiple buddies per child profile (table designed to allow this in v3)
- Buddy deletion / reset (only edit in v1 — deletion deferred until snapshot policy is finalized)
- Buddy memory of past stories — moved **in scope** under the Buddy Memory Wiring epic; the proxy will consume `story_memory`, `PreferenceRepository`, and `CharacterRepository` so the buddy can say "Remember when you and Sparkle went to the moon?". Procedural memory (how the buddy behaves) stays configuration-only, not learned from chat history
- Buddy voice / TTS persona — neither buddy edits nor chat replies use a buddy voice in v1; current TTS uses fixed voices
- Custom buddy avatars (image upload) — closed whitelist only in v1
- Replacing standalone pages with chat-only flows (launcher pattern only in v1)
- Inline image upload from inside the chat textbox (deferred — large UI surface, low value)
- Multi-turn negotiation in buddy chat ("which kind of story?") — buddy asks at most once, otherwise picks a default

#### 3.11.8 Multi-Topic Chat Sessions [Phase 2]

> A child often wants to chat about more than one topic with their buddy — bedtime questions one night, a dinosaur story the next. Today every page mount silently starts a new session and the child can never get back to a prior topic. This section adds visible session management on top of the existing `agent_chat_sessions` table.

##### Product Vision

The buddy chat becomes a **multi-topic surface** with a sidebar list of past sessions. The child can: (a) tap a row to resume that topic with full history, (b) hit "New chat" to start a clean session, (c) rename a session ("Dinosaur story"), and (d) delete sessions they no longer want. Parents retain destructive control via the existing Memory tab.

Sessions are scoped by `(user_id, child_id)` — switching the active child profile shows that child's own sessions, never another child's.

##### Core Capabilities

| Capability | Description |
|---|---|
| Session list | Sidebar / drawer of past sessions sorted by most-recent activity, with title + last-message preview + relative timestamp |
| New chat | One-tap button creates a fresh empty session keyed by `(user_id, child_id)` |
| Resume session | Tapping a row loads its full message history; new turns append to that session and resume the SDK conversation via `sdk_session_id` |
| Title auto-gen | First user message becomes the session title (truncated to ~60 chars); editable later |
| Rename | Pencil/kebab action; title passes `check_content_safety ≥ 0.85` like agent persona text |
| Archive / Delete | Hard delete cascades to `agent_chat_messages` via existing FK; archive is a soft-hide for the list |
| Cross-user isolation | All endpoints filter by `user_id` server-side; cross-tenant requests return 404 (IDs stay unguessable) |

##### Architecture

| Layer | Change |
|---|---|
| Schema | Add `title TEXT`, `last_message_preview TEXT`, `archived_at TEXT` columns to `agent_chat_sessions` via idempotent ALTER migration |
| Repository | New `list_sessions_for_user`, `list_messages`, `rename_session`, `archive_session`, `delete_session` on `AgentChatRepository`; `add_message` keeps `last_message_preview` in sync |
| API | `GET /me/agent/sessions`, `GET /me/agent/sessions/{id}/messages`, `POST /me/agent/sessions`, `PATCH /me/agent/sessions/{id}`, `DELETE /me/agent/sessions/{id}` |
| Proxy | `stream_my_agent_chat` sets `title = message[:60]` on the first user turn when `title==""`; updates `last_message_preview` after the safety-passed reply |
| Frontend | New `useAgentChatStore` (Zustand), `AgentSessionListSidebar.tsx`, `AgentChatPanel` reads sessionId + messages from the store |

##### Age Adaptation

| Ages 3-5 | Ages 6-8 | Ages 9-12 |
|---|---|---|
| Large tappable rows. Rename / Archive / Delete hidden behind parent gate. | Full kebab menu. Delete shows confirmation dialog. | Same as 6-8 plus keyboard shortcuts in v2. |

##### Acceptance Criteria

- [ ] Schema migration adds `title`, `last_message_preview`, `archived_at` columns idempotently
- [ ] `GET /me/agent/sessions` returns sessions for the calling user only, paginated, sorted by `updated_at DESC`
- [ ] `GET /me/agent/sessions/{id}/messages` returns chronological history; cross-user request returns 404
- [ ] `POST /me/agent/sessions` creates an empty session keyed by `(user_id, child_id)`
- [ ] `PATCH /me/agent/sessions/{id}` rejects titles failing `check_content_safety < 0.85`
- [ ] `DELETE /me/agent/sessions/{id}` cascades to `agent_chat_messages`
- [ ] First user message sets the session title automatically when title is empty
- [ ] `last_message_preview` updates after every safety-passed assistant reply
- [ ] `AgentChatPanel` reads sessionId + messages from the new store; selecting a sidebar row swaps the visible history
- [ ] Switching the active child profile clears the current session and re-fetches that child's session list
- [ ] In-flight stream is cancelled (existing AbortController) when switching sessions; partial assistant message is not committed to the old session
- [ ] Empty state: "No chats yet — say hi to start one" when the list is empty

##### Content Safety Requirements

- All rename inputs pass through the existing `check_content_safety` MCP at threshold 0.85 (same as agent persona)
- Replayed history is already post-safety text (proxy gates before persist) — no new safety logic on read
- Titles render as plain text (no HTML interpretation)
- Destructive actions (Delete) are gated by the existing parent-only UI surface for child accounts

##### Out of Scope (v1)

- LLM-generated titles (we use first-message truncation; can be upgraded later)
- Full-text search across sessions
- Multi-buddy sessions (one buddy per child stays in #3.11.3)
- Cross-device session sync beyond what `users.user_id` already provides
- Export / download history
- Pinning sessions to the top of the list

> **GitHub Epic**: TBD (Multi-Topic Chat Sessions) | **Phase**: 2 | **Milestone**: Phase 2 — Interactive + Memory + News

---

### 3.12 Content Hub — Group-Based Community Sharing [Phase 2]

> A Reddit-Lite community where children share their stories to **public** themed groups (anyone can join) or **private** groups (one creator per theme, others join by invite link). Stories are posted under the child's buddy persona (§3.11), never under their human identity. No free-text comments — reactions only.

#### 3.12.1 Product Vision

**Core purpose**: Let children see what other kids are creating and feel part of a creative community, without exposing PII. The hub answers: *"What are other kids making, and how can I show them mine?"*

**Why groups, not a global feed**:
- A global feed has weak signal — every theme competes for the same surface, and children can't tell whether a post is "for them".
- Groups give natural taxonomy ("Dragons", "Space Adventures", "My Cousin's Club") and let children opt into the contexts they care about.
- Public + private split lets a child make a club for their friends without exposing the room to strangers.

**How it differs from My Library (§3.6)**:

| Dimension | My Library | Content Hub |
|---|---|---|
| Audience | Private (your stories only) | Public/private groups |
| Identity | None shown (it's yours) | Buddy persona byline |
| Reactions | None | ❤️ 🌟 🤩 toggle, no comments |
| Discoverability | Personal | Group feeds, group directory |
| PII exposure | Server-trusted | Structurally zero |

#### 3.12.2 Group Model

Two visibilities:

- **Public** — anyone (with completed onboarding) can join with one click; post visibility = anyone authenticated.
- **Private** — created by any user, others join via a one-time/multi-use invite token. Owner can post + invite; members can post + view.

Groups have: `name`, `slug`, `description`, `theme`, `visibility`, `created_by_user_id`, `member_count`. Slugs are server-generated from the name with a numeric suffix on collision.

#### 3.12.3 Posting Flow

The "Share to Content Hub" CTA replaces the current static "Share with your family!" line on `StoryPage` and the end-of-story screen of `InteractiveStoryPage`.

```
User completes a story
  ↓
Tap "Share to Content Hub"
  ↓
[Onboarding gate: if !onboarded_at → redirect to /my-agent with return-to]
  ↓
Group picker modal: shows joined groups + "Create new group"
  ↓
Pick a group, optionally add caption (safety-checked)
  ↓
POST /api/v1/hub/groups/{id}/posts { source_artifact_type, source_id, caption? }
  Server attaches: author_user_id, author_child_id, author_agent_id,
                   agent_name_snapshot, agent_avatar_id_snapshot,
                   agent_title_snapshot, safety_score
  ↓
Post appears in group feed under buddy byline
```

Client request body NEVER contains the snapshot fields — server-attached only.

#### 3.12.4 Reading the Feed

`GET /api/v1/hub/groups/{id}/posts` returns paginated posts ordered by recency. Each post returns:

```ts
interface HubPost {
  post_id: string
  group_id: string
  source_artifact_type: 'art_story' | 'interactive_story'
  source_id: string
  caption: string | null
  byline: {
    agent_id: string
    agent_name: string
    agent_avatar_id: string
    agent_title: string
  }
  reaction_counts: { heart: number; star: number; wow: number }
  viewer_reactions: ('heart' | 'star' | 'wow')[]
  created_at: string
}
```

**The COPPA invariant**: this response shape contains no `user_id`, `username`, `email`, `display_name`, or `avatar_url`. Locked by JSON-schema contract test.

#### 3.12.5 Reactions

Three preset reactions: ❤️ (heart), 🌟 (star), 🤩 (wow). One row per `(post, user, reaction_type)`. Toggling off deletes the row. Counts visible; no global leaderboards (intentional — see §3.6 design philosophy on no-leaderboards).

No free-text comments in v1. The lower bar for moderation is what makes the v1 surface shippable.

#### 3.12.6 Moderation

- Post insert calls `check_content_safety` on caption (if any). Source artifacts have already passed safety at generation time.
- Buddy name + title were already safety-checked at agent creation/edit.
- Admin endpoint (piggybacks on `admin_artifacts`) can soft-delete a post (`removed_at`, `removed_reason`) — the post stops appearing in feeds but the row stays for audit.
- v2: report-then-auto-hide threshold, full moderation queue UI.

#### 3.12.7 Privacy Architecture

The buddy snapshot is the privacy mechanism. Three rules:

1. **Never join `users` for hub reads.** Repository and route code reads from snapshot fields only.
2. **Snapshot at write time.** The server pulls the current buddy state and writes it onto the post row. Subsequent buddy edits never propagate.
3. **Test the invariant.** A JSON-schema contract test asserts that no hub response contains any `users` table column.

This means a hub post can be served entirely without ever loading the user record — the user table can be considered "internal-only" for hub-read purposes.

#### Acceptance Criteria
- [ ] `POST /api/v1/hub/groups/{id}/posts` returns 412 with code `AGENT_REQUIRED` when `onboarded_at IS NULL`
- [ ] Posts written by the server include all four snapshot fields (`author_agent_id` + name + avatar + title) — never null
- [ ] Editing a buddy after publishing leaves prior post snapshots unchanged
- [ ] `GET /api/v1/hub/groups/{id}/posts` response contains no `user_id`, `username`, `email`, `display_name`, `avatar_url` fields (contract test)
- [ ] Public groups: `POST /groups/{id}/join` succeeds for any authenticated, onboarded user
- [ ] Private groups: `POST /groups/{id}/join?invite=<token>` succeeds only when token matches the row's `invite_token`
- [ ] Caption text passes `check_content_safety` ≥ 0.85 before insert; failures return 400 with the rejection reason
- [ ] Reactions are idempotent — second `POST /posts/{id}/reactions` with the same type toggles off
- [ ] Soft-deleted posts (`removed_at IS NOT NULL`) do not appear in `GET /posts`

#### Out of Scope (Phase 2)
- Free-text comments
- Cross-group global feed
- Followable buddies / friend graph
- Direct messages
- Notification system
- Trending / ranking algorithms (recency-only in v1)
- Image upload as buddy avatar
- Report-then-auto-hide moderation flow (v2)

---

## 3.13 Agent SDK Modernization [Phase 2 — Reliability]

Goal: replace the Claude Agent SDK subprocess-based execution with direct Anthropic API calls so all three agents work reliably in production (Railway) without OOM kills.

### 3.13.1 Problem
The `claude_agent_sdk` package spawns a separate process (the Claude CLI binary) for each agent call. This doubles memory usage on Railway's container, causing exit code -9 (OOM kill) on every generation request in production.

### 3.13.2 Solution
Switch all agents from `ClaudeSDKClient` to direct `anthropic.AsyncAnthropic()` API calls with manual tool orchestration. The `image_to_story_agent` already has a working direct-API fallback (`_direct_stream_image_to_story`); the pattern needs to be applied to `interactive_story_agent` and `kids_daily_agent`.

### 3.13.3 Stories
1. **Image-to-Story**: Make direct API the primary path, remove SDK subprocess dependency
2. **Interactive Story**: Port to direct API with multi-turn tool loop
3. **Kids Daily**: Port to direct API with dialogue generation
4. **Shared Base Module**: Extract common agent boilerplate (import guards, mock fallback, tool orchestration loop, response parsing)
5. **Safety Enforcement**: Ensure programmatic safety check runs post-generation even without SDK hooks

### 3.13.4 Acceptance Criteria
- [ ] All three agents generate content successfully on Railway (no exit code -9)
- [ ] Streaming SSE events work identically to current behavior
- [ ] Safety check runs on every generated output
- [ ] Mock fallback continues to work for tests
- [ ] No `claude_agent_sdk` subprocess spawned in production
- [ ] Existing API tests pass without modification

#### Out of Scope
- SDK hooks (PreToolUse) — deferred until SDK stabilizes post-1.0
- Session management via SDK — handled by our own session_repository
- Removing `claude_agent_sdk` from requirements.txt (keep for future re-evaluation)

---

## 3.14 Phase 3 Productization — Video, Parent Dashboard, and Achievements [Phase 3]

Phase 3 turns the existing foundations for video, growth metrics, and rewards into coherent product surfaces. The epic is tracked in #531, with delivery split across story video (#534), dynamic picture-book fallback (#533), parent creativity dashboard (#532), achievement infrastructure (#536), child-safe achievement surfaces (#537), and pitch/roadmap alignment (#522 / PR #554).

**Delivery status**: Phase 3 product surfaces are implemented through the child work above. Remaining positioning changes should keep shipped capabilities, in-progress polish, and future A2A/autonomous work clearly separated.

### 3.14.1 Story Video and Dynamic Picture Book

**User value**: Children can transform a completed story into a short animated picture-book moment they can rewatch, share safely, or keep in My Library.

**Implemented surface**:
- `backend/src/mcp_servers/video_generator_server.py` provides `generate_painting_video`, `check_video_status`, and video/audio combination tooling.
- `backend/src/api/routes/video.py` exposes authenticated video generation and status endpoints.
- Artifact models already include `video` and `final_video` roles.

**Shipped behavior**:
- Eligible completed stories expose video generation from child-facing story surfaces.
- Video job states cover queued, generating, completed, failed, and retryable flows without losing the original story.
- Completed video artifacts are displayed alongside story/audio artifacts with ownership checks.
- A lower-cost dynamic picture-book fallback uses existing images, audio, and CSS/JS animation when provider video is unavailable or too expensive.
- Motion-sensitive users can rely on reduced-motion and non-animated reading fallbacks.

**Out of scope**:
- Open-ended video editing.
- Public video remixing.
- Long-form video generation.

### 3.14.2 Parent Creativity Dashboard

**User value**: Parents can understand a child's creative habits without turning the app into surveillance or ranking.

**Implemented surface**:
- `GET /api/v1/library/stats-rich` provides richer Library metrics.
- `GrowthTimeline` already visualizes creation frequency.
- Parent role, parent email, consent status, and parent consent are represented in user models and onboarding.

**Shipped behavior**:
- Parent-facing dashboard entrypoints summarize creation frequency, content mix, favorite themes, and recent safe creations.
- Dashboard insights stay descriptive, not competitive: no leaderboards, no productivity scores, no pressure streaks.
- Visibility is scoped to parent role or age-appropriate child-facing growth views.
- Empty states guide families toward healthy creative prompts rather than more screen time.

**Out of scope**:
- Behavioral scoring.
- School-style grading.
- Cross-child comparisons.

### 3.14.3 Achievement Badges and Healthy Rewards

**User value**: Children receive gentle encouragement for breadth, completion, and creativity without addictive streak pressure.

**Implemented surface**:
- `StarPiggyBank`, `MysteryBagOverlay`, Daily Inspiration rewards, and streaming celebration effects already exist.
- Library and artifact metadata provide enough signal for first-pass achievement rules.

**Shipped behavior**:
- The badge catalog rewards healthy creative actions such as first story, first interactive ending, first Kids Daily listen, first shared post, first video, and trying multiple themes.
- Rewards are age-aware: visual-first for ages 3-5, simple progress for ages 6-8, optional reflective goals for ages 9-12.
- Achievements reward completed creative acts rather than daily-use pressure or infinite streaks.
- Persistent badges are backed by a server-owned achievement source of truth.

**Out of scope**:
- Competitive rankings.
- Paid reward boosts.
- Infinite streak mechanics.

### 3.14.4 Phase 3 Positioning and Pitch Alignment

**User value**: Internal roadmap, PRD, and external pitch materials describe the shipped product accurately and keep future claims clearly marked.

**In scope**:
- Align pitch deck and speaker scripts with the actual implementation of My Agent, video, parent dashboard, and gamification.
- Distinguish "foundation shipped" from "productized experience shipped."
- Update stale milestone counts and codebase module counts.
- Treat A2A, runtime dynamic specialist registration, and autonomous buddy initiatives as future-facing unless implemented.
- Track final pitch-deck source alignment in #522 / PR #554.

### Phase 3 Acceptance Criteria

- [x] Story video generation is reachable from at least one child-facing completed-story surface.
- [x] Video job status is visible and handles provider failure without losing the original story.
- [x] Completed videos appear in Library or story detail surfaces with ownership checks.
- [x] Dynamic picture-book fallback works when full video generation is unavailable.
- [x] Parent dashboard exposes descriptive growth metrics without PII leakage or cross-child ranking.
- [x] Achievement badges are backed by server-side state and reward healthy creative completion.
- [x] Age adaptation is applied across video, dashboard, and achievements.
- [x] Pitch and PRD language accurately distinguish shipped, in-progress, and future Phase 3 capabilities.

### Tracked Delivery

1. **#531 Epic: Phase 3 productization — video, parent dashboard, and achievements** (`type:epic`, `domain:video`, `phase:3`)
2. **#534 Productize story video generation from completed stories** (`type:story`, `domain:video`, `P1`) — closed
3. **#533 Add dynamic picture-book fallback for video-unavailable states** (`type:story`, `domain:video`, `P1`) — closed
4. **#532 Create parent creativity dashboard entrypoint** (`type:story`, `domain:library`, `P1`) — closed
5. **#536 Add server-owned achievement badge model** (`type:story`, `domain:gamification`, `P1`) — closed
6. **#537 Render child-safe achievement surfaces** (`type:story`, `domain:gamification`, `P2`) — closed
7. **#522 Align pitch deck and Phase 3 docs with shipped implementation** (`type:chore`, `domain:my-agent`, `P1`) — PR #554

---

## 3.15 Tablet & Mobile Capture Modalities [Phase 2 — Reach]

Goal: make the kid-facing flows usable on tablets and phones by replacing laptop-only input affordances (file picker, keyboard) with touch-native camera and voice input — without weakening content safety or parental consent.

### 3.15.1 Problem
The product is positioned for ages 3-12, but the lowest cohort cannot read or type, and tablet/phone users cannot take photos directly. `ImageUploader` (drag-drop only, no `capture` attribute), `InteractiveStoryPage` theme input (50-char free text), and `AgentChatPanel` textarea (buddy chat) are the worst offenders today. Today's UI assumes a laptop with a mouse + keyboard.

### 3.15.2 Solution
Two parallel tracks:
- **Camera capture**: tabbed picker ("Take Photo" | "Upload File") in `ImageUploader` defaulting to "Take Photo" on `(pointer: coarse) and (max-width: 1024px)` devices; new `CameraCapture` component using `getUserMedia` + `<canvas>` snapshot; `capture="environment"` fallback on a hidden input for the quick-win path. Captured JPEG flows through the existing `/api/v1/image-to-story` multipart contract with no backend change.
- **Voice input**: new `backend/src/services/stt_service.py` wrapping OpenAI Whisper (mirrors `tts_service.py` shape), new `POST /api/v1/audio/transcriptions` endpoint, reusable `VoiceInputButton` attached to the `InteractiveStoryPage` theme input and `AgentChatPanel` textarea. Web Speech API is progressive enhancement only — iPad Safari (most likely target device) does not support it, so server-side Whisper is canonical.

**Cross-cutting**: extend `child_profiles` with `camera_consent` and `microphone_consent` booleans, route first-use through the existing `ParentApprovalPage` flow. In-page `PermissionPrompt` component shows a child-friendly explainer before the browser prompt fires.

### 3.15.3 Stories
1. **Quick-win** — `capture="environment"` fallback + "Take Photo" affordance on touch devices (1-day ship, zero new dependencies)
2. **CameraCapture component** — live preview, capture, retake, front/back toggle, permission state machine
3. **ImageUploader tabbed picker** — default-to-camera on touch devices via `(pointer: coarse) and (max-width: 1024px)`
4. **STT backend** — `STTService` + `POST /api/v1/audio/transcriptions` + contract + API tests
5. **VoiceInputButton + useVoiceInput** — reusable mic button with waveform animation; state machine (idle → recording → processing → done | error)
6. **Voice on InteractiveStoryPage** — wire `VoiceInputButton` next to the Story Theme input
7. **Voice on AgentChatPanel** — wire `VoiceInputButton` next to the buddy chat textarea
8. **Parental consent** — `camera_consent` + `microphone_consent` on `child_profiles`, parent-only PIN gate via `ParentApprovalPage`
9. **PermissionPrompt component** — in-page child-friendly permission explainer before browser prompt

### 3.15.4 Acceptance Criteria
- [ ] "Take Photo" defaults on `(pointer: coarse) and (max-width: 1024px)`; "Upload File" defaults elsewhere
- [ ] Captured photos are JPEG, upright-normalized, ≤10MB, flow through existing `/api/v1/image-to-story` with no backend change
- [ ] `POST /api/v1/audio/transcriptions` accepts ≤2MB and ≤30s audio, returns `{text, language, duration_ms, safety_passed}`
- [ ] Transcribed text passes `check_content_safety` (threshold 0.85) BEFORE insertion into any input
- [ ] First-time camera/mic use requires `camera_consent` / `microphone_consent = true` (parent-set via `ParentApprovalPage`)
- [ ] Audio bytes are NOT persisted server-side; only the moderated transcript is stored
- [ ] Camera-denied state shows file-upload fallback; mic-denied state focuses the textarea
- [ ] Recording auto-stops at 30s; reduced-motion users get static states (no waveform animation)
- [ ] Voice recognition achieves ≥90% accuracy on a 20-clip kids-voice test set; transcripts return ≤3s after speech ends

#### Out of Scope
- Local on-device STT (Whisper.cpp) and Web Speech as the primary path — Web Speech only as progressive enhancement
- Real-time camera filters, AR overlays, or background blur — capture only
- Multilingual STT beyond OpenAI Whisper's automatic language detection
- Native iOS/Android apps — this is a web-only effort targeting tablet/phone browsers

---

## 3.16 Talk to Buddy — Realtime Voice [Phase 2 — Reach]

Two-way spoken conversation between the child and their My Agent buddy on `/my-agent`. Voice is a new I/O surface on top of the existing My Agent proxy (§3.11.7) — the proxy, memory wiring (§3.5), safety pipeline (§3.4), `launch_flow` handoffs, and Content Hub byline (§3.12) are all unchanged. Text-chat replies stay text-only in v1; voice is a separate surface, not a TTS overlay on text chat.

### 3.16.1 Problem
The buddy promise is companionship. Ages 3-5 cannot read the buddy's text replies, and ages 6-12 find typing slow on tablets. The existing one-shot `VoiceInputButton` (§3.15) lets a child speak a single prompt, but the buddy still answers in silence. That breaks the "creative buddy" pitch for the core pre-reader cohort and creates an unnatural rhythm for tablet users.

### 3.16.2 Solution
**Voice is the primary interaction mode on `/my-agent`; texting is the secondary mode and bypasses STT entirely** — typed input continues to flow through `POST /me/agent/chat` SSE with no transcription on the text path. When a child taps "Start Talking," a full-duplex realtime voice session opens. The child speaks; the buddy listens, thinks, and speaks back. Transcripts of every turn land in the same `agent_chat_messages` rows as text mode, with `input_modality` and `output_modality` tags so memory, search, and Content Hub byline see no difference.

**Provider strategy (v2 — voice-first cutover)**: end-to-end realtime via **OpenAI Realtime API** (`gpt-realtime-mini` default, `gpt-realtime-2` escalation per parent flag) as the primary path. Claude remains the brain for content + specialist work via **realtime tool calls** — the realtime model speaks naturally, calls tools (`launch_flow`, `delegate_to_specialist`, `recall_memory`, `end_call`), and Claude-orchestrated specialists do the heavy lifting (story generation, kids-daily, etc.). The provider abstraction in `realtime_voice_service.py` is unchanged: `REALTIME_VOICE_PROVIDER=hybrid` reverts to the cascaded Whisper+Claude+ElevenLabs path within one process restart.

**STT and TTS as discrete services remain in content-generation pipelines only** (image-to-story narration, kids-daily TTS, optional caption export). They are no longer in the interactive voice loop. The voice loop is end-to-end speech-to-speech.

**Why this changed (v1 was: hybrid as primary)**: production UX testing of the hybrid path showed cascaded p50 latency (~1.5–2.5s/turn) breaks the "the buddy is alive" promise for pre-readers, and Whisper-1 is one-shot (not streaming) so the latency floor is structural. OpenAI Realtime GA (June 2026) does true speech-to-speech at ~300–600ms median with native function calling, which lets Claude keep ownership of specialist orchestration through tool calls. The provider abstraction shipped in Phase A was built for exactly this kind of swap. Hybrid stays as fallback because (a) it's already shipped and tested, (b) it kicks in automatically when OpenAI credentials are missing, (c) it's the operator's escape hatch if the new path misbehaves under real load.

### 3.16.3 Consent & Privacy
Voice mode requires **two stacked consents** on `child_profiles`:
1. `microphone_consent` (existing, §3.15) — gates the mic itself
2. `voice_conversation_consent` (new) — gates the two-way spoken channel separately

Both are parent-PIN-gated via `ParentApprovalPage`. The consent screen explicitly lists the data flow (mic → STT → server → Claude → TTS → speaker) and the audio-not-stored invariant. Parents can revoke from the Parent Dashboard; in-flight sessions close within 2s. Past voice transcripts persist as text in chat history; raw audio bytes never reach disk.

### 3.16.4 Backend Pipeline
- `POST /api/v1/me/agent/voice/session` — issues an ephemeral WS token bound to `(user_id, child_id, agent_id)`, single-use, 60s TTL.
- `WS /api/v1/me/agent/voice/stream` — full-duplex broker. Per finalized child utterance: `check_content_safety` (threshold 0.85, fail-closed) → forward to `stream_my_agent_chat` → safety-review-specialist on the reply → stream Claude's text to TTS → stream audio frames back. `launch_flow` events arrive as control frames and trigger the same handoff as text-mode SSE.
- New columns: `agent_chat_messages.input_modality`, `agent_chat_messages.output_modality` (both `text|voice`); `child_profiles.voice_conversation_consent BOOL`.
- New table: `voice_sessions(user_id, child_id, agent_id, started_at, ended_at, duration_seconds, ended_reason)`.
- Quota: voice minutes count against the existing daily quota (§3.9.1) at age-adapted rates (see 3.16.6).

### 3.16.5 Frontend Entry & Layout
- **Entry surface (v2 — supersedes the FAB pattern from PR #633):** a prominent "Start Talking" pill in the **`AgentChatPanel` header**, gated by `shouldShowEntryButton` (capability + both consents + active child + not currently text-streaming + not already in voice mode).
- **In-place layout (replaces the full-screen overlay):** tapping the header pill swaps the composer textarea/send region for an **inline voice bubble** — the `TalkToBuddyPanel` mounted with `variant="inline"`. The message list above stays scrollable and visible; voice transcripts merge into the same list via `useAgentChatStore.appendVoiceCaption`. Tapping **End** unmounts the bubble and re-mounts the composer with focus restored to the textarea.
- **Why this beats the overlay+FAB pattern**: a single conversation surface, no modality jump, kid never sees two input affordances at once, scroll history stays anchored.
- **Why the entry stays inside `AgentChatPanel` (not global `PageContainer` chrome)**: only meaningful on `/my-agent` with a buddy + consents; cross-page header would re-litigate the "Ask"/"Talk" header-pill decision from commit `e31c2aa0`. The same rule applies — the entry surface lives where the action lives.
- **Setup path unchanged**: when `talkEntryReady === false`, the header pill is hidden. The empty-state onboarding banner from PR #633 (when consents are missing) remains the parent-setup affordance.
- **Components**: `frontend/src/pages/MyAgentPage/TalkToBuddyPanel.tsx` gains a `variant?: "overlay" | "inline"` prop (overlay = current full-screen behavior, inline = composer-slot layout). `frontend/src/hooks/useVoiceConversation.ts` is unchanged — the voice pipeline (state machine, WS, MediaRecorder, AudioContext) is reused as-is.
- `ParentConsentGate` `kind="voice_conversation"` variant from #619 stays the consent surface; the header pill simply hides until both consents land.

### 3.16.6 Age Adaptation

| Concern | 3-5 | 6-8 | 9-12 |
|---|---|---|---|
| Entry surface (header pill) | Giant emoji + "Talk!" | "Talk to {buddy_name}" | Mic icon + "Voice" |
| Default mode | Continuous VAD | Continuous VAD + PTT toggle | Push-to-talk default |
| Greeting | One short line | Two-sentence with prompt | One line + suggestion list |
| TTS voice picker | Parent-locked | 3 curated voices | 8 curated voices |
| Barge-in / interrupt | Disabled (toddlers talk over) | 500ms hold-off | 200ms hold-off |
| Max session | 10 min | 15 min | 20 min |
| Idle auto-end | 30s silence | 45s silence | 60s silence |
| Captions | Off; auto-show on rejection | On, small font | On, full scrollback |
| Safety threshold | 0.90 (raised) | 0.85 | 0.85 |
| Launch-flow speech | Full narration | One-sentence handoff | Brief tone + toast |
| Quota cost | 4 min = 1 unit | 3 min = 1 unit | 2 min = 1 unit |

### 3.16.7 Out of Scope (v1)
- Buddy voice cloning from a parent/child sample (→ Phase 3 via existing `voice_service.py`)
- Voice replies on the **text** chat panel — text stays text-only
- Multi-locale STT/TTS beyond Whisper auto-detect
- Voice-driven creation **inside** `/image-to-story` and `/interactive-story` (voice still launches them via `launch_flow`; pages remain text/keyboard)
- Group voice chat / multi-child sessions
- Offline / on-device STT or TTS
- Cross-device voice-session handoff
- Voice emotion or sentiment classification
- Voice-age classifier as an enforced gate
- Recording/downloading voice sessions for parents — transcripts only

### 3.16.8 Launch Prerequisites (added in v2 cutover)

Before any production traffic flows over the OpenAI Realtime path:

1. **ZDR enrollment** — Zero Data Retention must be enabled on the OpenAI org. Required by OpenAI's "Under-18 API Guidance" for any data of children under 13 (our 3-5 cohort). Operator action; not self-serve. Documented in `docs/guides/voice-launch-prerequisites.md`.
2. **Fallback validated** — `REALTIME_VOICE_PROVIDER=hybrid` smoke-tested in production env. Smoke flips the env var, waits one restart cycle, verifies the cascaded path still serves a voice session end-to-end.
3. **Cost ceiling configured** — monthly spending cap on the OpenAI org sized to expected voice quota: 10/15/20 min/day × user count × $0.05–$0.10/min (mini cached). `gpt-realtime-2` escalation is parent-flag-gated; cost telemetry alerts when cumulative org spend crosses 80% of cap.
4. **First-audio telemetry live** — Phase D telemetry hook reports p50/p95 to the Parent Dashboard + ops dashboard. Alert at p95 > 2500ms; provider auto-failover to hybrid considered at sustained p95 > 4000ms over 5 min.
5. **Safety pre-TTS gate verified** — contract test `test_voice_safety_pre_tts_contract` green; per-utterance + per-reply safety checks both fail-closed before audio streams to the client.
6. **Tool definitions versioned** — `launch_flow` tool schema pinned with `version` field; backward-incompatible changes ship as new tool name, not edited schema. The realtime session prompt includes the tool version so we can detect drift in production.

**ZDR contingency**: if ZDR is denied or delayed, the under-13 cohort cannot route through OpenAI Realtime. Fallback options (in order):
  (a) gate OpenAI Realtime to ages 9-12 only and continue serving hybrid to 3-8 (clean per-age split, mixed UX),
  (b) switch entirely to **ElevenLabs Conversational AI with Claude Sonnet 4-6 as the custom LLM** (validated in feasibility spike E7 — preserves Anthropic data terms but ElevenLabs hosts orchestration),
  (c) stay on hybrid and accept the latency floor for v2.
Decision belongs to the operator + legal, not engineering.

> **GitHub Epic**: tracked under the epic created by `/spec-to-backlog talk-to-buddy-realtime-voice` | **Phase**: 2 | **Milestone**: Phase 2 — Interactive + Memory + News

---

## 8. Risks & Limitations

### Product Risks
- **Content Quality**: AI-generated content may not be engaging enough
  - Mitigation: Continuously optimize Agent prompts, A/B testing

- **Safety Vulnerabilities**: AI may generate inappropriate content
  - Mitigation: Multi-layer safety review, manual spot checks

- **Privacy Concerns**: Parents worry about children's data security
  - Mitigation: COPPA compliance, transparent privacy policy

- **API Cost Overrun**: Real users heavily using AI APIs causing expenses to exceed budget
  - Mitigation: Per-user daily quota limit (§3.9.1) + Anthropic/OpenAI console monthly spending caps (external hard limit)

### Technical Limitations
- **Generation Speed**: AI generation takes 5-10 seconds
  - Mitigation: Optimize models, use streaming output

- **Cost**: TTS and AI call costs are high
  - Mitigation: Per-user quota limit (3/day); cache frequently used content; batch processing

---

## 9. Competitive Analysis

### Existing Products

| Product | Strengths | Weaknesses |
|---------|-----------|-----------|
| Story.com | AI story generation | No personalization, no memory |
| Storybird | Images with text | Not AI-powered, requires manual creation |
| Epic! | Digital book library | Passive reading, no creation |

### Our Advantages
- ✅ Personalized creation based on children's drawings
- ✅ Memory system enables story continuity
- ✅ Interactive multi-branch stories
- ✅ Strict content safety review
- ✅ Educational goal integration

---

## Appendix

### A. Related Documents
- [DOMAIN.md](./DOMAIN.md) - Domain background and core concepts
- [ARCHITECTURE.md](../architecture/ARCHITECTURE.md) - Technical architecture design
- [DEVELOPMENT_WORKFLOW.md](../guides/DEVELOPMENT_WORKFLOW.md) - Development workflow
- [README.md](../../README.md) - Project overview and quick start

### B. Reference Standards
- COPPA (Children's Online Privacy Protection Act)
- Common Core State Standards (age-based reading standards)
- ESRB Rating System (entertainment software rating)
