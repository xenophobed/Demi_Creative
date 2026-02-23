---
name: review
description: Review code changes for bugs, security, performance, and style. Use for PR review or reviewing staged changes. Especially important for agent prompt changes and content safety logic.
allowed-tools: Read, Grep, Glob, Bash(git diff:*), Bash(git log:*), Bash(gh:*)
argument-hint: [PR number, branch name, or empty for staged changes]
context: fork
---

# Code Review Skill

Review: $ARGUMENTS

## Context Gathering

If a PR number is given:
```bash
gh pr diff $ARGUMENTS
gh pr view $ARGUMENTS --json title,body,comments
```

If a branch name is given:
```bash
git diff main...$ARGUMENTS
```

If empty, review staged changes:
```bash
git diff --staged
```

## Review Process

1. **Understand intent**: What is this change trying to accomplish?

2. **Review for correctness**:
   - Logic errors or edge cases
   - `None`/`undefined` handling (especially in agent result parsing)
   - Off-by-one errors
   - Race conditions or concurrency issues (async/await correctness)
   - Error handling completeness (are exceptions caught and yielded as error events?)
   - MCP tool name correctness (`mcp__server-name__tool_name` format)
   - `ClaudeAgentOptions` — are `allowed_tools` and `mcp_servers` consistent?

3. **Review for security** (see @SECURITY_CHECKLIST.md):
   - Input validation (Pydantic models)
   - File path traversal (image upload paths)
   - Authentication/authorization gaps
   - Exposed secrets or credentials in code/prompts

4. **Review for child safety** (critical for this project):
   - Any new content generation bypasses `check_content_safety` MCP tool?
   - Age adaptation rules correctly applied?
   - No inappropriate content can leak through prompts or agent outputs?
   - Application prompts in `backend/src/prompts/` reviewed for safety regressions?

5. **Review for performance**:
   - Unnecessary blocking calls in async functions
   - Missing `await` on coroutines
   - Unbounded operations (e.g., no `max_turns` limit on agent calls)
   - Large payloads passed through unnecessarily

6. **Review for maintainability**:
   - Code clarity and naming
   - Test coverage for new/changed code (contract tests for MCP tools?)
   - Documentation for public APIs
   - Consistent with existing patterns (repository pattern, streaming generator pattern)

## Output Format

Organize feedback by severity:
- **Must Fix**: Bugs, security issues, child safety risks, data loss risks
- **Should Fix**: Performance issues, missing edge cases, missing tests
- **Suggestion**: Style, readability, nice-to-haves
- **Looks Good**: What was done well

Be specific: reference exact files/lines and suggest concrete fixes.
