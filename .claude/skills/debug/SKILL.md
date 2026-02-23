---
name: debug
description: Debug an error, unexpected behavior, or failing test. Use when something is broken and needs diagnosis and a fix — including FastAPI route errors, Claude Agent SDK failures, MCP tool errors, test failures, or frontend issues.
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
argument-hint: [error message, symptom, or failing test]
---

# Debugging Skill

Debug: $ARGUMENTS

## Process

1. **Reproduce**: Understand the exact error or symptom
   - If an error message is provided, search the codebase for it
   - If a test is failing, run it to see the exact failure:
     ```bash
     cd backend && python -m pytest tests/ -k "<test_name>" -v
     ```

2. **Hypothesize**: Form 2-3 hypotheses about root cause
   - Check recent changes: `git log --oneline -20` and `git diff`
   - Look for common patterns: null refs, type mismatches, race conditions, config issues
   - For agent errors: check `ClaudeAgentOptions`, `allowed_tools`, MCP server registration
   - For API errors: check Pydantic model validation, route dependencies

3. **Narrow down**: Use binary search approach
   - Add strategic logging or use existing logs
   - Check input/output at each boundary (API → Agent → MCP Tool → Service)
   - Isolate: is it in our code, Claude Agent SDK, an MCP server, or the environment?

4. **Root cause**: Identify the exact line(s) and condition causing the issue

5. **Fix**: Apply minimal, targeted fix
   - Fix the root cause, not just the symptom
   - Preserve existing behavior for non-broken paths
   - Follow project patterns (async/await, Pydantic models, repository pattern)

6. **Verify**:
   - Run the failing test/repro case to confirm the fix
   - Run related tests to check for regressions:
     ```bash
     cd backend && python -m pytest tests/ -v
     ```
   - Consider edge cases the fix might affect

7. **Prevent**:
   - Add a test that would have caught this
   - If appropriate, add validation or error handling

## Common Failure Points in This Project

| Layer | Common Issues |
|-------|--------------|
| FastAPI routes | Missing deps, Pydantic validation errors, missing `await` |
| Claude Agent SDK | `claude_agent_sdk` not installed → fallback mock used; check `ClaudeSDKClient is None` guard |
| MCP servers | Tool name mismatch (`mcp__server-name__tool_name` format), server not in `mcp_servers` dict |
| Database | Missing schema migration, repository method not found |
| TTS | OpenAI API key missing, audio path not returned correctly |
| Vector search | Qdrant not running, embedding dimension mismatch |
| Frontend | API URL mismatch, SSE event type not handled in store |

## Output

- Root cause explanation
- The fix applied
- Verification results
- Prevention measures added
