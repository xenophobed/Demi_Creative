# Claude Code Skills — How to Use Them in This Project

A hands-on guide for the Kids Creative Workshop developer workflow.

---

## The Two Layers (Most Important Concept)

Before using any commands, understand what lives where and why:

```
.claude/skills/              ← YOU ARE HERE (Claude Code developer tools)
    investigate/             ← /investigate  (explore code before working)
    debug/                   ← /debug        (fix broken things)
    codegen/                 ← /codegen      (generate new code)
    review/                  ← /review       (review before merging)
    test/                    ← /test         (add test coverage)
    refactor/                ← /refactor     (improve code quality)
    commit/                  ← /commit       (create git commits)
    pr/                      ← /pr           (open pull requests)
    create-issue/            ← /create-issue (file GitHub issues)
    fix-issue/               ← /fix-issue    (resolve GitHub issues)
    docs/                    ← /docs         (write documentation)

backend/src/prompts/         ← APPLICATION AGENT PROMPTS (NOT for you)
    story-generation.md      ← Read by the image-to-story agent at runtime
    interactive-story.md     ← Read by the interactive story agent at runtime
    age-adapter.md           ← Age adaptation rules for all agents
```

**Rule of thumb**:
- `.claude/skills/` = tools that help **you** write code faster
- `backend/src/prompts/` = instructions that tell the **AI agent** how to behave in the app

---

## How Skills Are Invoked

### Method 1: You type the slash command directly

Type `/` followed by the skill name anywhere in the Claude Code chat:

```
/investigate image-to-story agent flow
/debug TypeError in safety_check_server.py
/commit
```

### Method 2: Claude invokes it automatically

Skills without `disable-model-invocation: true` can be loaded by Claude when your message matches their description. For example, saying "How does the vector search work?" may automatically trigger `/investigate`.

### Method 3: With arguments

Most skills accept arguments after the name:

```
/investigate <what to investigate>
/debug <error message or symptom>
/test <file path>
/fix-issue <issue number>
```

---

## Each Skill — What It Does and How to Use It

---

### `/investigate` — Explore Before You Work

**When**: Before touching any unfamiliar area of the codebase.

**How it works**: Runs in an **isolated subagent** (`context: fork`) so it doesn't clutter your main conversation. It reads files, traces data flow, checks git history, and returns a structured report.

**Try it**:
```
/investigate how does the image-to-story agent call MCP tools
/investigate why does the safety check require a score of 0.85
/investigate the streaming SSE event flow from backend to frontend
/investigate how session state is managed in the interactive story
```

**What you get back**:
- Summary (2-3 sentences)
- Key Files with their roles
- Architecture diagram (ASCII)
- Data flow explanation
- Risks & recommendations

**Pro tip**: Always run this before `/codegen` or `/refactor` on a new area. It saves you from breaking things you didn't know existed.

---

### `/debug` — Fix Broken Things

**When**: Something throws an error, a test fails, or behavior is unexpected.

**How it works**: Inline — Claude can read files, run bash commands, and edit code in your main session.

**Try it**:
```
/debug TypeError: 'NoneType' object is not subscriptable in image_to_story_agent.py
/debug the safety check is returning 0.0 for all content
/debug cd backend && python -m pytest tests/api/test_image_to_story.py -v
/debug frontend not receiving SSE events from the streaming endpoint
```

**What happens**:
1. Claude searches for the error pattern in the codebase
2. Forms hypotheses (checks recent git changes too)
3. Narrows down to the root cause
4. Applies a minimal fix
5. Runs the test to verify
6. Adds a test to prevent regression

**Project-specific**: The skill knows to check for common failure points like:
- `claude_agent_sdk` not installed → mock mode silently activated
- MCP tool name mismatch (`mcp__server-name__tool_name` format)
- Missing `await` on async calls

---

### `/codegen` — Generate New Code

**When**: Creating a new MCP tool, agent function, API route, React component, or test.

**How it works**: Inline — studies existing patterns first, then generates matching code.

**Try it**:
```
/codegen a new MCP tool server for image resizing
/codegen a FastAPI route for /api/v1/news-to-kids with streaming support
/codegen a React component for displaying the safety score badge
/codegen contract tests for the vector_search_server.py
/codegen a Pydantic model for the news article input
```

**What happens**:
1. Reads similar existing files (e.g., reads `safety_check_server.py` before generating a new MCP server)
2. Matches your project's exact patterns (async/await, Pydantic v2, `@tool` decorator)
3. Generates the implementation
4. Adds tests alongside it
5. Runs the tests to verify

**Project conventions the skill enforces**:
- MCP tools: `mcp__server-name__tool_name` naming
- Agents: always guard with `if ClaudeSDKClient is None` for test fallback
- Safety: all story generation must call `check_content_safety`
- Age adaptation: use `AGE_CONFIG` lookup, not hardcoded values

---

### `/review` — Code Review Before Merging

**When**: Before merging any PR, or to review your own staged changes.

**How it works**: Runs in an **isolated subagent** (`context: fork`). Reads diffs and gives structured feedback by severity.

**Try it**:
```
/review                          ← reviews your staged git changes
/review main                     ← reviews your branch vs main
/review 42                       ← reviews GitHub PR #42
/review feature/interactive-news ← reviews a branch by name
```

**What you get back** (organized by severity):
- **Must Fix**: bugs, security issues, child safety risks
- **Should Fix**: performance, missing edge cases, missing tests
- **Suggestion**: style, readability
- **Looks Good**: things done well

**Project-specific checks** (from `SECURITY_CHECKLIST.md`):
- Does any new content generation bypass `check_content_safety`?
- Are `child_id` queries properly scoped (no cross-user data leakage)?
- Are file upload paths sanitized?
- Are API keys in env vars, never in code?

---

### `/test` — Add Test Coverage

**When**: A function has no tests, you're about to refactor something, or CI is failing.

**How it works**: Inline — reads the target file, studies existing test patterns, writes tests, runs them.

**Try it**:
```
/test backend/src/mcp_servers/safety_check_server.py
/test backend/src/agents/image_to_story_agent.py image_to_story function
/test the streaming event types in interactive_story_agent.py
/test backend/src/services/database/story_repository.py
```

**What happens**:
1. Reads the target code to understand its contract
2. Reads existing tests in `backend/tests/` to match the style
3. Identifies: happy path, edge cases (age 3 vs age 12), error cases (SDK unavailable)
4. Writes the tests
5. Runs them: `cd backend && python -m pytest tests/ -k "<new_test>" -v`
6. Verifies they fail when code is broken

**Test locations used**:
- `backend/tests/contracts/` → MCP tool input/output schema tests
- `backend/tests/api/` → FastAPI `TestClient` tests
- `backend/tests/integration/` → end-to-end flows

---

### `/refactor` — Improve Code Without Breaking It

**When**: Code is duplicated, overly complex, or hard to understand.

**How it works**: Inline — runs existing tests first as a safety net, then refactors incrementally.

**Try it**:
```
/refactor backend/src/agents/ extract duplicated TTS audio path extraction into a helper
/refactor backend/src/agents/interactive_story_agent.py reduce duplication in prompt building
/refactor backend/src/agents/ move AGE_CONFIG to a shared utility module
/refactor frontend/src/store/useInteractiveStoryStore.ts simplify the choice handling
```

**What happens**:
1. Reads the target code
2. Runs tests first: `cd backend && python -m pytest tests/ -v`
3. Identifies specific duplication/smells
4. Executes one change at a time
5. Re-runs tests after each change
6. Reports: original issue → fix applied → tests pass

**Project-specific refactoring opportunities** the skill knows about:
- The two agent files have ~200 lines of identical streaming event handling — prime for extraction
- `AGE_CONFIG` is duplicated across agents
- The f-string prompt builders could be extracted to load from `backend/src/prompts/`

---

### `/commit` — Smart Git Commits

**When**: You're ready to commit changes.

**How it works**: Inline with `disable-model-invocation: true` — Claude will ONLY run this when **you** type it, never automatically.

**Try it**:
```
/commit
/commit feat(agent): add streaming support to image-to-story
```

**What happens**:
1. Reads current `git status` and `git diff --staged`
2. Stages all changes if nothing is staged (`git add -A`)
3. Generates a conventional commit message:
   ```
   feat(agent): add streaming support to image-to-story agent

   - Add generate_story_stream() async generator
   - Yield tool_use, thinking, result, complete event types
   - Extract audio path from TTS tool result
   ```
4. Creates the commit
5. Shows `git log --oneline -1` to confirm

**Commit types used in this project**:
- `feat` — new feature
- `fix` — bug fix
- `refactor` — code improvement, no behavior change
- `test` — adding/improving tests
- `docs` — documentation
- `chore` — build, config, tooling

**Scopes**: `agent`, `mcp`, `api`, `prompts`, `db`, `frontend`, `skills`

---

### `/pr` — Open a Pull Request

**When**: Your feature/fix branch is ready to merge.

**How it works**: Inline with `disable-model-invocation: true`. Pushes your branch and creates a PR via `gh` CLI.

**Try it**:
```
/pr
/pr Add streaming support for image-to-story endpoint
```

**What happens**:
1. Pushes your branch: `git push -u origin HEAD`
2. Reads all commits since diverging from `main`
3. Generates a structured PR body with Summary, Changes, Testing, Agent/MCP Impact, Related Issues sections
4. Runs `gh pr create`
5. Returns the PR URL

**Prerequisite**: You need `gh` (GitHub CLI) authenticated: `gh auth login`

---

### `/create-issue` — File a GitHub Issue

**When**: You found a bug or want to track a feature before working on it.

**How it works**: Inline with `disable-model-invocation: true`.

**Try it**:
```
/create-issue safety check always returns 0.0 for non-English content
/create-issue add support for PDF drawing uploads
/create-issue interactive story session not persisting between page refreshes
```

**What happens**:
1. Searches the codebase to identify affected files
2. Checks for existing related issues: `gh issue list --search "..."`
3. Drafts a structured issue (bug template or feature template)
4. Creates it with `gh issue create`
5. Returns the issue URL

---

### `/fix-issue` — Resolve a GitHub Issue End-to-End

**When**: You have an issue number and want to implement the fix.

**How it works**: Inline with `disable-model-invocation: true`. Reads the issue, investigates, branches, fixes, tests, and prepares a PR.

**Try it**:
```
/fix-issue 42
/fix-issue 7
```

**What happens**:
1. Reads the issue: `gh issue view 42`
2. Investigates the affected code
3. Creates a branch: `git checkout -b fix/42-<description>`
4. Implements the fix (TDD: write failing test first)
5. Runs `cd backend && python -m pytest tests/ -v`
6. Commits with `fix: ... (#42)` reference
7. Opens a PR with `Fixes #42` in the body

---

### `/docs` — Write Documentation

**When**: A function, API route, MCP tool, or feature needs documentation.

**How it works**: Inline — reads the target code, checks existing docs, writes or updates documentation.

**Try it**:
```
/docs backend/src/mcp_servers/safety_check_server.py
/docs the image-to-story agent workflow
/docs backend/src/api/routes/interactive_story.py
/docs backend/src/prompts/age-adapter.md (explain the adaptation rules)
```

**What happens**:
1. Reads the code to understand behavior
2. Checks `docs/` for existing docs to avoid duplication
3. Writes appropriate docs:
   - Python functions → docstrings with params/returns/examples
   - MCP tools → tool name, schema, when to use
   - API routes → endpoint, request/response, example (in `backend/docs/`)
   - Components → TypeScript props, usage, state management

---

## Typical Development Session Walkthrough

Here's a complete example of how these skills chain together for a real task — adding a new "news summary length" feature:

```
Step 1: Understand the area first
  /investigate how does the news-to-kids agent work and what controls output length

Step 2: File an issue to track it
  /create-issue add configurable summary length parameter to news-to-kids API

Step 3: Write the tests first (TDD)
  /test backend/src/agents/news_to_kids_agent.py — add test for length parameter

Step 4: Generate the implementation
  /codegen add max_length parameter to news_to_kids_agent and its API route

Step 5: Review your own changes
  /review

Step 6: Commit
  /commit

Step 7: Open a PR
  /pr Add configurable summary length to news-to-kids feature
```

---

## Quick Reference Card

| Command | Manual only? | Runs isolated? | What to pass |
|---------|-------------|----------------|-------------|
| `/investigate` | No (auto too) | Yes (fork) | topic/question |
| `/debug` | No (auto too) | No (inline) | error/symptom |
| `/codegen` | No (auto too) | No (inline) | what to build |
| `/review` | No (auto too) | Yes (fork) | PR#, branch, or empty |
| `/test` | No (auto too) | No (inline) | file path or function |
| `/refactor` | No (auto too) | No (inline) | file/area + goal |
| `/docs` | No (auto too) | No (inline) | file or topic |
| `/commit` | **Yes only** | No (inline) | optional message |
| `/pr` | **Yes only** | No (inline) | optional title |
| `/create-issue` | **Yes only** | No (inline) | description |
| `/fix-issue` | **Yes only** | No (inline) | issue number |

**"Manual only"** = `disable-model-invocation: true` is set — Claude will never auto-trigger these because they have real side effects (git commits, GitHub PRs, etc.).

**"Runs isolated"** = `context: fork` — the skill runs in a fresh subagent with no conversation history. Results are summarized back to you. Good for read-only exploration that shouldn't pollute your main context.

---

## Troubleshooting

**Skill not triggering automatically?**
- Check its description in the SKILL.md — does it match what you're asking?
- Try invoking it directly with `/skill-name`
- Run `/investigate` to confirm the skill is detected

**"gh: command not found"?**
- Install GitHub CLI: `brew install gh` (macOS)
- Authenticate: `gh auth login`
- `/commit` and `/pr` still work without `gh`, but `/create-issue` and `/fix-issue` need it

**Skills feel slow?**
- `/investigate` and `/review` run in a fork (subagent) — they take a moment to spin up but keep your main context clean
- `/debug` and `/codegen` are inline — they're as fast as normal responses

**Want to see all available skills?**
- Type `/` in Claude Code — it shows all available slash commands with their descriptions
- Or ask: "What skills are available?"
