# Kids Daily Agent

**Source**: `backend/src/agents/kids_daily_agent.py`

## What This File Does

**Explorer**: This is the news reporter for kids. It finds real news from around the world, rewrites it in fun, easy-to-understand language, and turns it into a podcast-style show with two characters — Mimi (the curious kid) and Duo (the fun expert) — who chat about the news together.

**Maker**: This agent implements a news-to-kids content pipeline: fetch real headlines via Tavily API → rewrite as an age-adapted dialogue script between two characters → generate TTS audio for each dialogue line → assemble into a podcast episode. Supports on-demand generation (user clicks "Listen Now") and scheduled generation (daily cron).

## How It Works

### The Pipeline

```
1. Fetch Headlines
   └─ Tavily API → 3-5 real news articles for the selected topic (space, animals, etc.)

2. Build Dialogue Script
   └─ Claude rewrites news into a conversation between:
       - Mimi (curious_kid) — asks questions, reacts with wonder
       - Duo (fun_expert) — explains, adds fun facts
       - Guest expert — topic-specific character (Professor Owl, Captain Comet)
   └─ Adapted to age group:
       3-5: max 2 sentences/turn, 70 words, warm tone
       6-8: max 3 sentences/turn, 110 words, curious tone
       9-12: max 4 sentences/turn, 150 words, conversational tone

3. Safety Check
   └─ Full dialogue text checked via safety MCP tool

4. TTS Audio Generation
   └─ Each dialogue line gets a voice:
       - Mimi → Nova (soft female)
       - Duo → Shimmer (lively female)
       - Guest → varies by character
   └─ Audio files stitched into episode MP3

5. Save Episode
   └─ Episode data + audio URLs stored in database
   └─ Available via /api/v1/news/daily/{episode_id}
```

### Character System

The show uses recurring characters with distinct personalities:

| Character | Role | Voice | Personality |
|-----------|------|-------|-------------|
| Mimi | `curious_kid` | Nova | Asks questions, shows excitement, represents the child |
| Duo | `fun_expert` | Shimmer | Explains concepts, shares fun facts, keeps it engaging |
| Guest | `guest` | Varies | Topic expert — changes per episode |

Character names come from `ROLE_DISPLAY_NAMES` and can be enriched by the memory system's `character_repository` for recurring guest appearances.

### On-Demand vs Scheduled

- **On-demand**: Child clicks "Listen Now" on a topic → backend generates episode immediately → streams progress → redirects to player
- **Scheduled**: `kids_daily_scheduler.py` runs on a cron schedule → pre-generates episodes for all subscribed topics → ready when child opens the app

## Key Concepts

**Dialogue Script**: A structured conversation format where each line has a speaker role and text. The `DialogueScript` Pydantic model validates the format, ensuring every line has a valid role and appropriate length for the age group.

**Age Rules**: Each age group has different limits on sentence count, word count, and tone. A 4-year-old gets "Wow, did you know some fish can fly? They have special fins like wings!" while a 11-year-old gets a more detailed scientific explanation.

**Character Continuity (#140)**: The `character_repo` tracks which guest characters have appeared before. If "Professor Owl" appeared in a space episode last week, the agent can reference that: "Remember when Professor Owl told us about Saturn's rings?"

**Content Curation**: Raw news headlines go through multiple transformation steps: fetch → filter (kid-safe topics only) → rewrite (age-adapted language) → safety check. Each step reduces the chance of inappropriate content reaching children.

## Connections

- **Upstream**: `api/routes/kids_daily.py` for on-demand; `services/kids_daily_scheduler.py` for scheduled
- **MCP tools used**: web-search (Tavily), safety-check, tts-generation
- **Services**: `news_headline_fetcher.py` provides headline data; `tts_service.py` generates audio
- **Prompts**: `prompts/morning-show.md` contains the dialogue generation prompt template
- **Database**: Episodes stored via subscription/story repositories; character data via `character_repository.py`
- **Frontend**: `MorningShowPage` plays episodes; `MorningShowSubscriptionsPage` manages topic subscriptions

## Thinking Question

The dialogue script has Mimi asking questions and Duo answering. But what if the AI generates a script where Duo gives wrong information (e.g., "The Sun is a planet")? The safety check catches harmful content, but not factual errors. How would you add fact-checking to the pipeline? Consider: a separate fact-check MCP tool, using the original source articles as ground truth, or flagging uncertain claims for human review.
