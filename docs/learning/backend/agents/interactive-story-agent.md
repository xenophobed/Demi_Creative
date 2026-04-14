# Interactive Story Agent

**Source**: `backend/src/agents/interactive_story_agent.py`

## What This File Does

**Explorer**: This is the choose-your-own-adventure storyteller. It creates a story with choices — "Do you go left into the cave, or right toward the river?" — and writes the next part based on what the child picks. Every story is different because every child makes different choices.

**Maker**: This agent manages multi-turn branching narratives using a state machine. It generates an opening segment with choices, then produces subsequent segments based on the child's selections. It tracks segment count, enforces story length modes (short/medium/unlimited), maintains narrative coherence via continuity anchors, and ensures satisfying endings that reference the opening hook.

## How It Works

### State Machine

```
┌──────────┐   start    ┌──────────┐  choose   ┌──────────┐
│  SETUP   │ ────────▶  │ OPENING  │ ────────▶ │ PLAYING  │ ◀─┐
│ (age,    │            │ (seg 0)  │           │ (seg 1+) │ ──┘ (loop: choose → next segment)
│ interests│            │ + 2-3    │           │ + 2-3    │
│ theme)   │            │ choices  │           │ choices  │
└──────────┘            └──────────┘           └────┬─────┘
                                                    │ is_final_segment?
                                                    ▼
                                              ┌──────────┐
                                              │  ENDING  │
                                              │ (final   │
                                              │ segment) │
                                              └──────────┘
```

### Story Length Modes (#331)

| Mode | Segments | Behavior |
|------|----------|----------|
| `short` | 5 | Auto-ends after 5 choices with fast-paced conclusion |
| `medium` | 10 | Auto-ends after 10 choices with developed plot |
| `unlimited` | No limit | Child presses "End My Story" to trigger graceful ending |

The `is_final_segment` logic:
```python
if force_ending:           # /end endpoint called
    is_final_segment = True
elif mode == "unlimited":  # Never auto-end
    is_final_segment = False
else:                      # short/medium — count-based
    is_final_segment = segment_count >= total_segments - 1
```

### Ending Coherence

When generating the final segment, the prompt requires:
1. **Opening callback** — Must explicitly reference the story's opening hook
2. **Continuity anchors** — Must quote at least 2 phrases from prior segments verbatim
3. **No new quests** — Focus on resolution, not new conflicts
4. **Educational summary** — Themes, concepts, and moral of the story

`_ensure_ending_coherence()` validates these requirements and rewrites weak endings.

### Age Configuration

```python
AGE_CONFIG = {
    "3-5": { "total_segments": 3, "word_count": "50-100", "complexity": "very simple" },
    "6-8": { "total_segments": 4, "word_count": "100-200", "complexity": "simple" },
    "9-12": { "total_segments": 5, "word_count": "150-300", "complexity": "moderate" },
}
```

Note: `total_segments` from AGE_CONFIG is the base value, overridden by `STORY_LENGTH_SEGMENTS` when a length mode is selected.

## Key Concepts

**Branching Narrative**: A story structure where the reader makes choices that change what happens next. Each choice creates a "branch." With 3 choices per segment and 5 segments, there are theoretically 3^5 = 243 possible story paths.

**Continuity Anchors**: Key phrases, character names, and plot points from earlier segments that the ending must reference. This prevents the AI from writing a generic ending that doesn't connect to the specific adventure the child experienced.

**Soft Cap**: In unlimited mode, the story doesn't have a hard segment limit, but it has age-based soft caps (15/30/50 segments). At the soft cap, the prompt gently encourages wrapping up, but the child can keep going. This prevents runaway API costs while respecting the child's autonomy.

**Force Ending**: When the child clicks "End My Story" in unlimited mode, the `/end/stream` endpoint sets `force_ending=True` in the session data. The agent sees this flag and generates a final segment regardless of segment count.

## Connections

- **Upstream**: `api/routes/interactive_story.py` — start, choose, end, resume endpoints
- **MCP tools used**: safety-check, tts-generation (optional), vector-search (for character memory)
- **Database**: `session_repository.py` stores session state, segments, choice history
- **Store**: Frontend `useInteractiveStoryStore.ts` mirrors session state for UI rendering
- **Prompts**: No separate file — `_build_opening_prompt()` and `_build_next_segment_prompt()` construct prompts inline

## Thinking Question

Each segment needs context from all previous segments to maintain coherence. But after 20+ segments in unlimited mode, the full context might exceed the AI's context window. The issue mentions "rolling context summarization after 15 segments." How would you implement this? Think about: what to summarize vs keep verbatim, how to preserve important details (character names, plot twists), and the trade-off between context compression and story quality.
