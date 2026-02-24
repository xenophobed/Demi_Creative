# Development Workflow — Complete Guide

Everything you need to know about the software engineering process for this project, using Claude Code skills.

---

## Before You Start: How This Project Is Organized

### Three layers of configuration

```
.claude/rules/                ← ALWAYS-LOADED CONVENTIONS
    github-conventions.md     ← Label taxonomy, epics, branch naming, PR rules
                                 (you never need to invoke this — it's always active)

.claude/skills/               ← DEVELOPER TOOLS (slash commands you type)
    # ── Product skills ──
    product-audit/            ← /product-audit (find gaps between PRD and code)
    feature-spec/             ← /feature-spec  (design a new feature before coding)
    prd/                      ← /prd           (update the PRD document)
    # ── Planning skills ──
    issues/                   ← /issues        (see what needs doing)
    create-issue/             ← /create-issue  (track new work)
    # ── Design skills ──
    investigate/              ← /investigate   (understand code before changing it)
    plan/                     ← /plan          (design before coding)
    # ── Build skills ──
    fix-issue/                ← /fix-issue     (pick up and complete an issue)
    codegen/                  ← /codegen       (write new code)
    test/                     ← /test          (add tests)
    debug/                    ← /debug         (fix broken things)
    refactor/                 ← /refactor      (improve existing code)
    docs/                     ← /docs          (write documentation)
    # ── Ship skills ──
    review/                   ← /review        (check code quality)
    commit/                   ← /commit        (save your work to git)
    pr/                       ← /pr            (submit your work for review)
    dev/                      ← /dev           (start/stop dev servers)
    release/                  ← /release       (cut a versioned release)

backend/src/prompts/          ← APPLICATION PROMPTS (not for you — for the AI agents)
    story-generation.md       ← Instructions the app's story agent reads at runtime
    interactive-story.md      ← Instructions the interactive story agent reads
    age-adapter.md            ← Age adaptation rules
```

### How to invoke a skill

Type `/` followed by the skill name in Claude Code:

```
/issues
/investigate how does the safety check work
/fix-issue 46
```

Some skills trigger automatically when Claude recognizes your intent. Skills with side effects (git, GitHub) only run when you explicitly type them.

---

## Phase 0: SETUP — First Time Getting Started

If you just cloned the repo and need to get everything running:

### 1. Prerequisites

Ask Claude directly:
```
check if I have python 3.11+, node 18+, npm, and gh CLI installed
```

If anything is missing, Claude will tell you how to install it.

### 2. Install dependencies

```
install the backend and frontend dependencies for me
```

Claude will set up the Python virtual environment, install pip packages, and run `npm install` in the frontend.

### 3. Environment variables

```
help me set up the .env file for this project
```

You'll need two API keys:
- `ANTHROPIC_API_KEY` — for Claude Agent SDK + Vision
- `OPENAI_API_KEY` — for TTS audio

Claude will guide you through creating the `.env` file safely.

### 4. Start the servers

```
/dev start
```

### 5. Verify everything works

```
/dev status
```

### 6. Orient yourself

```
/issues                    ← see what needs doing
/investigate <any topic>   ← explore the codebase
```

Read these docs:
- `docs/product/PRD.md` — what we're building
- `docs/guides/DEVELOPMENT_WORKFLOW.md` — this file (how to work)
- `CLAUDE.md` — project rules and conventions

---

## The Complete Software Engineering Lifecycle

Every piece of work follows this cycle. The sections below cover each phase.

```
  DISCOVER        DEFINE         PLAN           DESIGN         BUILD          VERIFY         SHIP           MAINTAIN
  ────────        ──────         ────           ──────         ─────          ──────         ────           ────────
  /product-audit  /feature-spec  /issues        /investigate   /dev           /test          /commit        /debug
                  /prd           /create-issue  /plan          /codegen       /review        /pr            /fix-issue
                                                               /debug                        /release       /refactor
                                                               /refactor
                                                               /docs
```

The first two phases (DISCOVER, DEFINE) are **product** work. The rest are **engineering**.

---

## Phase 1: DISCOVER — Find What's Missing or Wrong

### "I think something in the app doesn't match what we planned"

```
/product-audit My Stories page
/product-audit the upload flow
/product-audit navigation and page naming
```

This runs in an isolated subagent. It:
1. Reads the PRD and domain model to understand what the product *should* be
2. Examines the actual code (frontend pages, backend routes, data models)
3. Compares the two and finds gaps: naming mismatches, missing features, wrong scope
4. Cross-checks against existing GitHub issues to avoid duplicates
5. Returns a structured list of gaps with suggested issues to file

### "I want a full audit of the entire product"

```
/product-audit full audit
```

This systematically checks each PRD section (§3.1–§3.5) against the implementation.

### When to use `/product-audit`

| Situation | Use it? |
|-----------|---------|
| Something feels wrong in the UI | yes |
| You're about to start a new milestone | yes (audit everything first) |
| You just finished an epic and want to verify completeness | yes |
| You're fixing a specific bug | no — use `/fix-issue` |

---

## Phase 2: DEFINE — Design New Features

### "I have an idea for a new feature"

```
/feature-spec my library page that shows all artifact types not just stories
/feature-spec parent dashboard to see what kids created
/feature-spec drawing upload with AI suggestions
```

This runs in an isolated subagent. It:
1. Reads the PRD and domain model to understand the product context
2. Checks what already exists in the code
3. Designs the feature at the **product level** (not engineering):
   - User stories ("As a child, I can...")
   - Acceptance criteria (testable conditions)
   - Age adaptation rules (how 3-5 vs 6-8 vs 9-12 experience differs)
   - Content safety requirements
   - Edge cases (empty state, errors, first use)
4. Drafts a PRD section ready to paste
5. Proposes an epic and stories for GitHub

**After reviewing the spec:**
```
/prd add <feature name>       ← add the approved section to the PRD
/create-issue <epic>          ← create the GitHub epic
/create-issue <story 1>       ← create each story
```

### "I need to update the PRD"

```
/prd add My Library feature
/prd update §3.1 to include multi-image upload
/prd sync progress
/prd retire news-to-kids to phase 3
```

What each action does:
- **add**: Writes a new feature section matching the PRD format
- **update**: Modifies an existing section
- **sync progress**: Cross-references all GitHub epics/stories and updates status markers
- **retire/defer**: Marks a feature as deferred (never deletes — preserves history)

Always shows you a diff before finalizing. Reminds you to `/commit` after.

### "I ran a product audit — now what?"

The audit gives you a list of gaps. Here's how to process them:

1. **Review the gaps** — not everything needs immediate action. Prioritize by impact.
2. **For the main finding** (e.g. "My Stories → My Library"):
   ```
   /feature-spec <the core redesign idea>    ← design it properly
   /prd add <feature>                        ← update the PRD
   /create-issue <epic>                      ← create GitHub epic
   /create-issue <story 1>                   ← create individual stories
   /create-issue <story 2>
   ```
3. **For small, obvious gaps** (e.g. wrong label, missing badge): skip the feature spec and file issues directly:
   ```
   /create-issue <description>
   ```
4. **For things already tracked**: the audit tells you — skip them.
5. **For Phase 2+ items**: file them with the right phase label so they go to the backlog, not your current sprint.

### The product workflow end-to-end

```
/product-audit <area or "full audit">  ← find gaps
/feature-spec <new feature>            ← design the big ones
  (review and refine the spec)
/prd add <feature>                     ← update the PRD
/create-issue <epic>                   ← create GitHub tracking
/create-issue <story 1>               ← create stories
/create-issue <story 2>
```

Then hand off to engineering (Phase 3+).

---

## Phase 3: PLAN — Decide What to Work On

### "I just sat down. What should I work on?"

```
/issues
```

This shows all open issues grouped by milestone and epic, with priorities. It ends with a suggested next action.

You can filter:
```
/issues mvp          ← only MVP milestone
/issues bugs         ← only bugs
/issues P1           ← only high-priority items
/issues 40           ← only issues under epic #40
```

### "I found a bug / I have a feature idea"

```
/create-issue the progress bar is stuck at 0% during interactive stories
/create-issue add support for uploading multiple drawings at once
```

This will:
1. Search the codebase for relevant files
2. Check if a similar issue already exists
3. Create a properly labeled issue with the right milestone, priority, domain, and parent epic
4. Return the issue URL

### "I have a bunch of issues to file (from an audit or brainstorm)"

File them one at a time with `/create-issue`. Each invocation creates one issue with proper labels:

```
/create-issue Epic: My Library — Unified Content Library
/create-issue Expand My Stories page into My Library with multi-content-type tabs
/create-issue Display meaningful titles on story cards instead of truncated UUIDs
/create-issue Add content type badges to library cards
```

**Tips for batch filing:**
- Create the **epic first**, so child stories can reference it
- Claude remembers the epic number from the previous command — it will link them automatically
- File P1 items first, P3 items last — you can always stop partway
- If you have a `/product-audit` result open, just say `/create-issue based on the product audit result` and Claude will extract the issues from it

### "I want to understand the big picture before planning"

Read these docs:
- `docs/product/PRD.md` — what features we're building and why
- `docs/product/DOMAIN.md` — age groups, safety rules, educational goals
- `docs/architecture/ARCHITECTURE.md` — how the system is designed

---

## Phase 4: DESIGN — Think Before You Code

This phase is the difference between "coding yourself into a corner" and "getting it right the first time." Skip it for tiny fixes. Use it for anything that touches more than one or two files.

### "I need to understand how the code works first"

```
/investigate how does the image-to-story agent call MCP tools
/investigate the streaming SSE event flow from backend to frontend
/investigate how session state is managed in the interactive story
```

This runs in an isolated subagent so it doesn't clutter your conversation. It returns:
- Summary of how the code works
- Key files and their roles
- Architecture diagram
- Data flow
- Risks and recommendations

### "I need to plan my approach before writing code"

```
/plan 46
/plan add character growth tracking to the memory system
```

This runs in an isolated subagent and returns:
- **Files to change** — listed in dependency order (change this first, then that)
- **New interfaces / models** — what new schemas or contracts to define
- **Step-by-step implementation** — each step independently testable
- **Test strategy** — what contract, API, and integration tests to write
- **Risks** — what could break, what to watch out for
- **Scope estimate** — how many files, how complex

### When to use `/plan` vs just starting

| Situation | Skip `/plan` | Use `/plan` |
|-----------|-------------|------------|
| 1-file bug fix | yes | |
| Change a single function | yes | |
| New API route + model + tests | | yes |
| Touches backend AND frontend | | yes |
| New MCP tool server | | yes |
| Database schema change | | yes |
| You're unsure where to start | | yes |

---

## Phase 5: BUILD — Do the Work

There are several scenarios. Pick the one that matches what you're doing.

---

### Scenario A: Fix an existing GitHub issue

**This is the most common workflow.** One command does everything.

```
/fix-issue 46
```

This will:
1. Read the issue from GitHub (title, body, labels, comments)
2. Investigate the relevant code
3. Create a branch (`fix/46-word-count-chars` or `feat/46-...`)
4. Write a failing test first (TDD)
5. Implement the fix
6. Run all tests to verify
7. Commit with the issue reference
8. Open a PR with `Fixes #46` in the body

**You don't need to do anything else.** Just review the PR it creates.

---

### Scenario B: Build a new feature from scratch

When the work is bigger and you want to control each step:

**Step 1 — Understand the area**
```
/investigate how does the memory system store character vectors
```

**Step 2 — Plan the approach**
```
/plan add character growth tracking to memory system
```

Review the plan. If it looks right, proceed. If not, discuss with Claude what to change.

**Step 3 — Create an issue to track the work**
```
/create-issue add character growth tracking to memory system
```

**Step 4 — Write tests first (TDD)**
```
/test backend/src/mcp_servers/vector_search_server.py
```

This reads the code, studies existing test patterns, and writes:
- Happy path tests
- Edge case tests (empty input, boundary values)
- Error case tests (SDK unavailable, network failure)

Test locations in this project:
- `backend/tests/contracts/` — MCP tool input/output schema tests
- `backend/tests/api/` — FastAPI route tests
- `backend/tests/integration/` — end-to-end flow tests

**Step 5 — Generate the implementation**
```
/codegen add character_growth field to vector embeddings and update search
```

This reads similar existing code first, matches the project's patterns, generates the implementation, and runs the tests.

**Step 6 — Review your own changes**
```
/review
```

Gives feedback organized by severity: Must Fix, Should Fix, Suggestion, Looks Good. Checks for child content safety issues.

**Step 7 — Commit and open a PR**
```
/commit
/pr
```

---

### Scenario C: Fix a bug you just discovered (not yet tracked)

**Option 1 — Quick fix** (small, obvious bug):
```
/debug the word_count is counting characters instead of words
```

Then commit:
```
/commit
```

**Option 2 — Track it first** (if you want a paper trail):
```
/create-issue word_count counts characters instead of words in image_to_story route
/fix-issue <the number it gives you>
```

---

### Scenario D: Something is broken and you don't know why

```
/debug TypeError: 'NoneType' object is not subscriptable in image_to_story_agent.py
/debug the safety check is returning 0.0 for all content
/debug tests are hanging and never finishing
/debug frontend not receiving SSE events from the streaming endpoint
```

What happens:
1. Searches the codebase for the error pattern
2. Forms 2-3 hypotheses about the root cause
3. Checks recent git changes
4. Narrows down to the exact line and condition
5. Applies a minimal fix
6. Runs tests to verify
7. Adds a regression test

Project-specific things it knows to check:
- `claude_agent_sdk` not installed → mock mode silently activated
- MCP tool name mismatch (`mcp__server-name__tool_name` format)
- Missing `await` on async calls
- Blocking calls inside `async` functions

---

### Scenario E: Improve existing code (refactoring)

```
/refactor backend/src/agents/ extract duplicated TTS audio path extraction into a helper
/refactor backend/src/agents/ move AGE_CONFIG to a shared utility module
/refactor frontend/src/store/useInteractiveStoryStore.ts simplify the choice handling
```

What happens:
1. Reads the target code
2. Runs all existing tests first (safety net)
3. Makes one small change at a time
4. Runs tests after each change
5. Reports what improved

**Important**: Never refactor without tests. If there are no tests, run `/test` first.

---

### Scenario F: Add test coverage

```
/test backend/src/mcp_servers/safety_check_server.py
/test backend/src/agents/image_to_story_agent.py
/test frontend/src/hooks/useStoryGeneration.ts
```

What happens:
1. Reads the code to understand its behavior
2. Studies existing tests to match the style
3. Writes tests for: happy path, edge cases, error cases
4. Runs them and verifies they pass
5. Checks that they fail when the code is broken

---

### Scenario G: Write documentation

```
/docs backend/src/mcp_servers/safety_check_server.py
/docs the image-to-story agent workflow
/docs backend/src/api/routes/interactive_story.py
```

What happens:
1. Reads the code
2. Checks `docs/` for existing docs to avoid duplication
3. Writes appropriate docs (docstrings, API docs, or feature docs)

---

### Scenario H: Switch to a hotfix mid-feature

You're working on a feature branch but need to fix something urgent on main.

**Step 1 — Save your current work**
```
save my current changes so I can switch branches
```
Claude will stash your uncommitted changes.

**Step 2 — Fix the urgent issue**
```
switch to main and pull latest
/fix-issue <urgent issue number>
```
This creates a new branch from main, fixes the issue, and opens a PR.

**Step 3 — Go back to your feature**
```
switch back to my feature branch and restore my saved changes
```
Claude will checkout your branch and pop the stash.

If the hotfix touched the same files, ask:
```
rebase my feature branch on top of the latest main first, then restore my changes
```

---

### Scenario I: Add or update a dependency

Just tell Claude what you need:
```
add the python package "httpx" to the backend
add "framer-motion" to the frontend
remove "old-package" from the backend
```

Claude will install it, update the lock/requirements files, and you just commit:
```
/commit
```

---

### Scenario J: Run specific tests

Just ask Claude:
```
run all the tests
run only the contract tests
run only the safety check tests
run the tests for image_to_story_agent
run the frontend tests
```

Claude knows the test directory structure and will run the right command. If a test fails:
```
/debug <paste the test failure output>
```

---

### Scenario K: Database schema changed

This project uses SQLite with a repository pattern. There's no migration framework (like Alembic) yet.

**If you changed a Pydantic model or added a table:**

1. Understand the current schema:
   ```
   /investigate how does the database schema get created
   ```

2. Tell Claude what you need:
   ```
   add a "title" column to the stories table and update the repository
   ```

3. If you don't need to keep existing data (dev environment):
   ```
   delete the dev database and restart the servers so it gets recreated
   /dev restart
   ```

4. If you need to keep data, ask for a migration:
   ```
   /codegen write a SQLite migration script that adds column title to the stories table
   ```

5. Add tests for the new schema:
   ```
   /test backend/src/services/database/
   ```

---

## Phase 6: VERIFY — Make Sure It Works

### Before you commit

Run `/review` to check your own changes:

```
/review                ← review staged changes
/review main           ← review your branch vs main
```

Feedback categories:
- **Must Fix**: bugs, security issues, data loss risks, child safety violations
- **Should Fix**: performance issues, missing edge cases, missing tests
- **Suggestion**: style, readability improvements
- **Looks Good**: things done well

### Before you merge a PR

```
/review 42             ← review GitHub PR #42
```

### Project-specific safety checks (from `SECURITY_CHECKLIST.md`)

Every review automatically checks:
- Does any new content generation bypass `check_content_safety`?
- Are `child_id` queries properly scoped (no cross-user data leakage)?
- Are file upload paths sanitized (no path traversal)?
- Are API keys in env vars, never in code?

### "CI failed on my PR — what do I do?"

Just ask Claude:
```
CI failed on PR #50, help me fix it
```

Claude will:
1. Check what failed on the PR
2. Read the error log
3. Diagnose the root cause
4. Fix it locally

If you already see the error, you can go straight to:
```
/debug <paste the CI error message>
/commit
push my changes
```
The PR updates automatically when you push.

**Common CI failures:**

| Failure | What to say |
|---------|------------|
| Test failure | `/debug <paste the test error>` |
| Lint/format error | `fix the lint errors in my code` |
| Missing dependency | `I forgot to update requirements.txt, fix it` |
| Type error (frontend) | `fix the TypeScript type errors` |

---

## Phase 7: SHIP — Save, Submit, and Release

### Commit your changes

```
/commit
```

This will:
1. Show what changed (`git status` + `git diff`)
2. Generate a conventional commit message automatically:
   ```
   feat(agent): add character growth tracking to memory system

   - Add growth_level field to character embeddings
   - Update vector search to include growth context
   - Add contract tests for growth tracking
   ```
3. Create the commit

Commit types used:
- `feat` — new feature
- `fix` — bug fix
- `refactor` — code improvement, no behavior change
- `test` — adding/improving tests
- `docs` — documentation
- `chore` — build, config, tooling

Scopes: `agent`, `mcp`, `api`, `prompts`, `db`, `frontend`, `skills`

### Open a pull request

```
/pr
/pr Add character growth tracking to memory system
```

This will:
1. Push your branch to GitHub
2. Read all commits since you branched from main
3. Look up the linked issue to find its milestone and parent epic
4. Generate a structured PR with Summary, Changes, Testing, Related Issues
5. Create the PR and return the URL

### Cut a release

When you've merged several PRs and want to mark a version:

```
/release v0.1.0
```

This will:
1. Gather all merged PRs and commits since the last tag
2. Generate a changelog grouped by type (features, fixes, improvements)
3. Create a git tag
4. Create a GitHub release with the changelog

---

## Phase 8: MAINTAIN — After Your PR Is Submitted

This is what happens after `/pr`. Most beginners don't know these steps exist.

### "My PR has review comments — how do I address them?"

```
show me the comments on PR #42
```

Then fix what they asked for:
```
/debug <the reviewer's concern>
/commit
push my changes
```

The PR updates automatically when you push.

### "My PR has merge conflicts"

This happens when someone else changed the same files while you were working.

```
my PR has merge conflicts, help me resolve them
```

Claude will fetch the latest main, rebase your branch, walk you through each conflict, and push the resolved branch.

### "My PR is approved — how do I merge?"

```
merge PR #50 with squash and delete the branch
```

Or just click "Squash and merge" on GitHub.

### "There's an urgent bug in production (hotfix)"

```
/create-issue <describe the urgent bug>
/fix-issue <number>
this is urgent, help me merge PR #N
```

The `/fix-issue` skill creates the branch from main, so your hotfix is isolated from any in-progress work.

### "I need to pick up someone else's unfinished work"

```
fetch and switch to the branch called feat/50-my-library
/investigate what was this branch trying to do
```

Then continue the work normally with `/codegen`, `/test`, `/commit`.

### "I want to throw away my current work and start over"

```
undo all my uncommitted changes
```

If you already committed but haven't pushed:
```
undo my last commit but keep the code changes
```

### "I want to save my work-in-progress without a proper commit"

```
stash my current changes so I can switch branches
```

Later, when you're back:
```
restore my stashed changes
```

---

## Common Scenarios Quick Reference

| I want to... | Do this |
|--------------|---------|
| **Product** | |
| Find product gaps or naming issues | `/product-audit <area>` |
| Design a new feature idea | `/feature-spec <idea>` |
| Update the PRD | `/prd <action>` |
| Check PRD progress against GitHub | `/prd sync progress` |
| Process audit results into issues | `/create-issue` for each gap |
| **Plan** | |
| See what needs doing | `/issues` |
| See only MVP bugs | `/issues bugs` |
| Track a new bug or idea | `/create-issue <description>` |
| File multiple issues from an audit | `/create-issue` one at a time (epic first) |
| Understand unfamiliar code | `/investigate <topic>` |
| Plan a multi-file feature | `/plan <issue number or description>` |
| **Build** | |
| Start dev servers | `/dev` or `/dev start` |
| Stop dev servers | `/dev stop` |
| Check if servers are running | `/dev status` |
| See server logs | `/dev logs` |
| Pick up and complete an issue | `/fix-issue <number>` |
| Build something new | `/investigate` → `/plan` → `/create-issue` → `/test` → `/codegen` → `/review` → `/commit` → `/pr` |
| Fix a bug I just found | `/debug <error>` → `/commit` |
| Something is broken, I'm stuck | `/debug <symptom or error message>` |
| Add tests to existing code | `/test <file path>` |
| Clean up messy code | `/test <file>` first, then `/refactor <file> <goal>` |
| Add or update a dependency | tell Claude: `add <package> to the backend/frontend` |
| Run specific tests | tell Claude: `run the contract tests` |
| Database schema changed | tell Claude: `add column X to table Y` |
| Switch to a hotfix mid-feature | tell Claude: `stash my changes` → `/fix-issue` → `restore my changes` |
| **Verify** | |
| Check my work before committing | `/review` |
| Review someone's PR | `/review <PR number>` |
| CI failed on my PR | tell Claude: `CI failed on PR #N, help me fix it` |
| **Ship** | |
| Save my changes | `/commit` |
| Submit my work | `/pr` |
| Cut a release | `/release v0.1.0` |
| Document a function or feature | `/docs <file or topic>` |
| **Maintain** | |
| Address PR review comments | `/debug <concern>` → `/commit` → `push my changes` |
| Resolve merge conflicts | tell Claude: `my PR has merge conflicts` |
| Merge an approved PR | tell Claude: `merge PR #N with squash` |
| Handle an urgent production bug | `/create-issue` → `/fix-issue` → merge immediately |
| Pick up someone else's work | tell Claude: `switch to branch X` → `/investigate` |
| Undo my changes | tell Claude: `undo my uncommitted changes` |
| Save work-in-progress | tell Claude: `stash my changes` |
| **Setup** | |
| First time getting started | See Phase 0 above |

---

## Branch and Issue Naming Conventions

These are enforced automatically by the skills, but good to know:

### Branch names
```
feat/46-add-character-memory       ← for stories (new features)
fix/47-progress-bar-math           ← for bugs
chore/48-readme-qdrant-chromadb    ← for chores (cleanup, docs)
spike/50-evaluate-tts-providers    ← for research/investigation
```

### Issue titles
```
"Add character growth tracking"              ← story (verb phrase)
"Bug: progress bar stuck at 0%"              ← bug
"Chore: update README vector DB reference"   ← chore
"Spike: evaluate TTS provider alternatives"  ← research
"Epic: Memory System — Character Recall"     ← epic (groups stories)
```

### Commit messages
```
feat(agent): add character growth tracking
fix(api): correct word_count to count words not characters (#46)
refactor(mcp): extract shared TTS path helper
test(contracts): add safety check edge case coverage
docs: update development workflow guide
chore(skills): add /issues command
```

---

## Project Documentation Map

```
docs/
├── product/                          # WHAT we're building
│   ├── PRD.md                        # Features, user journeys, KPIs
│   └── DOMAIN.md                     # Age groups, safety rules, education goals
├── architecture/                     # HOW it's built
│   ├── ARCHITECTURE.md               # System design, MCP tools, agent SDK
│   ├── ARTIFACT_GRAPH_MODEL.md       # Artifact lifecycle, schema, lineage
│   └── decisions/                    # Completed feature implementation records
│       └── 001-artifact-graph-model.md
└── guides/                           # HOW to work on it
    └── DEVELOPMENT_WORKFLOW.md       # This file
```

---

## Quick Reference Card

| Command | What it does | Side effects? | Isolated? |
|---------|-------------|---------------|-----------|
| `/product-audit` | Find gaps between PRD and code | No | Yes (fork) |
| `/feature-spec` | Design a new product feature | No | Yes (fork) |
| `/prd` | Update the PRD document | Yes (edits files) | No |
| `/dev` | Start/stop/restart dev servers | Yes (processes) | No |
| `/issues` | Show open issues, priorities, epics | No | No |
| `/investigate` | Explore and explain code | No | Yes (fork) |
| `/plan` | Design implementation approach | No | Yes (fork) |
| `/create-issue` | File a GitHub issue | Yes (GitHub) | No |
| `/fix-issue` | Resolve an issue end-to-end | Yes (git + GitHub) | No |
| `/codegen` | Generate new code | Yes (writes files) | No |
| `/test` | Write tests | Yes (writes files) | No |
| `/debug` | Diagnose and fix errors | Yes (edits files) | No |
| `/refactor` | Improve code quality | Yes (edits files) | No |
| `/review` | Review code for issues | No | Yes (fork) |
| `/commit` | Create a git commit | Yes (git) | No |
| `/pr` | Open a pull request | Yes (git + GitHub) | No |
| `/release` | Tag and publish a release | Yes (git + GitHub) | No |
| `/docs` | Write documentation | Yes (writes files) | No |

**Side effects?** = creates commits, pushes code, or creates GitHub issues/PRs.
**Isolated?** = runs in a separate subagent so it doesn't affect your conversation context.

---

## Troubleshooting

**Skill not showing up when I type `/`?**
- Make sure you're in the project directory
- Try typing the full name: `/issues`

**`gh: command not found`?**
- Install: `brew install gh`
- Authenticate: `gh auth login`

**Tests are hanging?**
- `/debug tests are hanging and never finishing`

**I made a mess and want to start over on a file?**
- `git checkout -- path/to/file` to undo uncommitted changes
- Or ask Claude: "undo my changes to this file"

**I committed something wrong?**
- Don't panic. Ask Claude: "I need to undo my last commit"
- Claude will guide you through `git reset` safely

**I don't understand an error message?**
- Just paste it: `/debug <paste the error>`
- Claude will find the root cause and fix it

**I don't know which skill to use?**
- Just describe what you want in plain English. Claude will suggest the right skill or handle it directly.
