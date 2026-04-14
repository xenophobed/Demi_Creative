# Application Prompts

**Source**: `backend/src/prompts/`

## What This Is

**Explorer**: Prompts are instruction sheets for the AI. Just like a recipe tells a chef what to cook and how, a prompt tells Claude what to write, what rules to follow, and how to adapt the output for different ages.

**Maker**: Application prompts are markdown files consumed by agents at runtime. They define the AI's persona, task description, output format, and age-adaptation rules. These are separate from Claude Code developer skills (`.claude/skills/`) — prompts run inside the app; skills run inside the development tool.

## Prompt Files

| File | Used By | Purpose |
|------|---------|---------|
| `story-generation.md` | `image_to_story_agent.py` | How to write a story from a drawing analysis |
| `interactive-story.md` | `interactive_story_agent.py` | How to write branching story segments with choices |
| `morning-show.md` | `kids_daily_agent.py` | How to write a dialogue script between Mimi and Duo |
| `age-adapter.md` | All agents | Age adaptation rules: vocabulary, complexity, themes per age group |

## How Prompts Are Used

```python
# Agent loads prompt file at import time
_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "morning-show.md"

# Agent reads and injects it into the system prompt
prompt_template = _PROMPT_PATH.read_text()
system_prompt = prompt_template.format(
    age_group=age_group,
    topic=topic,
    headlines=headline_text,
)
```

## Key Concepts

**System Prompt vs User Prompt**: The system prompt (from these files) defines the AI's role and rules — it stays constant across generations. The user prompt changes per request (specific drawing, chosen topic, etc.). Think of it as: system prompt = job description; user prompt = today's task.

**Age Adapter**: The `age-adapter.md` prompt defines rules like:
- 3-5: Use words a kindergartner knows, max 2 sentences, warm tone
- 6-8: Elementary vocabulary, simple cause-and-effect, curious tone
- 9-12: Richer vocabulary, complex plots, respect their intelligence

**Prompt Engineering**: The art of writing instructions that consistently produce good AI output. Small changes in wording can dramatically change results. These prompts were refined through testing with real children's content.

## Important Distinction

| Layer | Location | Purpose | Runs Where |
|-------|----------|---------|------------|
| **Application prompts** | `backend/src/prompts/` | Guide AI content generation | Inside the running app |
| **Claude Code skills** | `.claude/skills/` | Guide the developer AI (Claude Code) | In your development terminal |

These are completely separate systems. Editing a skill won't change how stories are generated, and editing a prompt won't change how Claude Code helps you write code.

## Thinking Question

The morning show prompt tells Claude to write dialogue between "Mimi" and "Duo." What if you wanted to let children create their own show characters with custom names and personalities? How would you modify the prompt to accept dynamic character definitions while still maintaining safety and age-appropriateness?
