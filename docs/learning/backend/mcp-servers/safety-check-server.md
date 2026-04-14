# Safety Check MCP Server

**Source**: `backend/src/mcp_servers/safety_check_server.py`

## What This File Does

**Explorer**: This is the safety guard. Before any story, news episode, or creative content reaches a child, this helper reads it and makes sure nothing scary, mean, or inappropriate is included — like a teacher who reviews every story before sharing it with the class.

**Maker**: This MCP server wraps the Anthropic API to perform content classification against a rule set. It returns a 0.0-1.0 safety score and structured feedback. All content must score >= 0.85 before delivery — this is a non-negotiable product rule enforced at the route level.

## How It Works

1. **Agent calls `check_content_safety`** with the generated text, content type (story/news/interactive), and target age
2. **The server builds a prompt** containing `SAFETY_RULES` — a comprehensive rubric covering:
   - Negative content (violence, horror, inappropriate language, adult topics)
   - Positive values (gender equality, cultural diversity, moral education, inclusivity, environmental awareness)
3. **Claude evaluates the content** against these rules and returns a JSON response with:
   - `safety_score` (0.0-1.0)
   - `is_safe` (boolean — true if score >= 0.85)
   - `issues` (list of specific problems found)
   - `suggestions` (how to fix identified issues)
4. **If content fails** (score < 0.85), the agent can call `suggest_content_improvements` to get a rewritten version that passes

## Key Concepts

**Safety Score**: A number from 0.0 to 1.0 measuring how appropriate content is for children.
- 0.0-0.3: Clearly inappropriate (violence, adult content)
- 0.3-0.7: Has problems that need fixing
- 0.7-0.85: Mostly okay but could be better
- 0.85-1.0: Safe for children

**Content Safety Rules**: A structured rubric (`SAFETY_RULES` constant) that defines what's not allowed and what's encouraged. This isn't just about blocking bad content — it actively promotes positive values like inclusivity and environmental awareness.

**Threshold**: The 0.85 cutoff is a product decision. Lower = more permissive (risk of inappropriate content). Higher = more restrictive (risk of bland, over-sanitized content). 0.85 balances safety with creative freedom.

## Connections

- **Upstream**: Called by all three agents (`image_to_story_agent.py`, `interactive_story_agent.py`, `kids_daily_agent.py`) during generation
- **Downstream**: Uses `anthropic.Anthropic` client to call the Claude API for evaluation
- **Config**: Model selection via `utils/model_config.py` → `get_safety_model()`
- **Routes**: `interactive_story.py` and `image_to_story.py` check `safety_score` before saving/returning content

## Thinking Question

What happens if the safety check model itself generates an incorrect score — say, it rates violent content as 0.95 (safe)? How would you design a second layer of protection? Think about: redundancy, rule-based fallbacks, human review queues, and the trade-off between latency and safety.
