---
name: refactor
description: Refactor code to improve quality without changing behaviour. Use for cleanup, extracting duplicated prompt logic, simplifying agent orchestration, improving type annotations, or reducing tech debt.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash
argument-hint: [file/area to refactor and optional goal, e.g. "backend/src/agents/ extract shared prompt builder"]
---

# Refactoring Skill

Refactor: $ARGUMENTS

## Process

1. **Assess current state**:
   - Read the target code and understand its behaviour
   - Identify the specific smells or issues to address
   - Check test coverage — refactoring without tests is risky
   - Run existing tests to establish baseline: `cd backend && python -m pytest tests/ -v`

2. **Ensure test coverage**:
   - If tests are insufficient, write them FIRST before refactoring
   - Tests are your safety net — especially important for agent functions

3. **Plan changes**:
   - List specific refactoring steps
   - Keep each step small and verifiable
   - Common patterns in this project:
     - **Extract prompt builder**: duplicated f-string prompts in agent functions
       → extract to helper functions or `backend/src/prompts/` files
     - **Extract age config**: `AGE_CONFIG` dict duplicated across agents
       → move to shared `backend/src/utils/age_config.py`
     - **Simplify streaming**: duplicated SSE event yield patterns
       → extract `yield_status`, `yield_tool_use`, `yield_error` helpers
     - **Rename for clarity**: `child_id` vs `user_id` inconsistency
     - **Type annotations**: add `Optional[str]` where `None` is returned
     - **Break up large agents**: `interactive_story_agent.py` is 1100+ lines
       → extract `_build_prompt`, `_parse_result`, `_handle_audio` etc.

4. **Execute incrementally**:
   - Make one refactoring at a time
   - Run tests after each change: `cd backend && python -m pytest tests/ -v`
   - Commit at safe points

5. **Verify**:
   - All existing tests pass
   - Behaviour is unchanged (same API responses, same streaming events)
   - Code is measurably improved (fewer lines of duplication, clearer names, etc.)

## Project-Specific Notes

- The two agent files (`image_to_story_agent.py` and `interactive_story_agent.py`) contain
  significant duplication — the streaming event yielding pattern and TTS audio path extraction
  are repeated verbatim. These are prime candidates for extraction.
- Application prompts live in `backend/src/prompts/` — if inline f-string prompts are getting
  complex, consider moving the static parts there and loading them at runtime.
- Keep `async def` / `await` correctness when extracting helpers from async generators.
