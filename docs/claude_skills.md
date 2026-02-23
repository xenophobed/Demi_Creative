# Building Custom Claude Code Commands for the Software Engineering Lifecycle

A comprehensive guide based on the latest official Claude Code documentation (2025).

---

## Architecture Overview

Claude Code provides **two mechanisms** to extend its capabilities:

| Mechanism | Best For | Location | Invocation |
|-----------|----------|----------|------------|
| **Slash Commands** | Quick, single-file prompts you invoke explicitly | `.claude/commands/` or `~/.claude/commands/` | `/command-name` (manual) |
| **Skills** | Complex workflows with multiple files, scripts, templates | `.claude/skills/` or `~/.claude/skills/` | `/skill-name` (manual) or automatic (Claude decides) |

**Key insight**: Custom slash commands have been **merged into Skills**. A file at `.claude/commands/review.md` and a skill at `.claude/skills/review/SKILL.md` both create `/review`. Your existing `.claude/commands/` files still work, but Skills add optional features: supporting files, invocation control, and auto-discovery.

### Scope

| Scope | Commands Path | Skills Path | Shared via git? |
|-------|--------------|-------------|-----------------|
| **Project** (team) | `.claude/commands/` | `.claude/skills/` | Yes |
| **Personal** (all projects) | `~/.claude/commands/` | `~/.claude/skills/` | No |

---

## SKILL.md Anatomy

Every skill needs a `SKILL.md` with two parts:

```markdown
---
# YAML Frontmatter (between --- markers)
name: skill-name              # becomes /skill-name
description: When to use it   # helps Claude auto-discover
allowed-tools: Bash(git:*), Read, Write  # tools granted without per-use approval
model: claude-opus-4-6        # optional: override model
argument-hint: [arg1] [arg2]  # shown during autocomplete
disable-model-invocation: true # only you can invoke (not Claude)
user-invocable: false          # only Claude can invoke (not you)
context: fork                  # run in subagent (isolated context)
---

# Markdown Instructions
Step-by-step instructions Claude follows when the skill is invoked.
```

### Frontmatter Reference

| Field | Purpose | Default |
|-------|---------|---------|
| `name` | Becomes the `/slash-command` | Folder name |
| `description` | Helps Claude decide when to auto-load | First line of prompt |
| `allowed-tools` | Tools granted without per-use approval | Inherits from conversation |
| `model` | Override model for this skill | Inherits from conversation |
| `argument-hint` | Shown in autocomplete | None |
| `disable-model-invocation` | Prevent Claude from auto-invoking | `false` |
| `user-invocable` | Allow user to invoke directly | `true` |
| `context` | `fork` = run in subagent, `inline` = run in main context | `inline` |

### Arguments

- `$ARGUMENTS` — captures all arguments as one string
- `$1`, `$2`, `$3` — positional arguments (like shell scripts)

### Special Syntax in Skill Content

- `!`backtick command backtick — execute bash before skill runs, output included in context
- `@path/to/file` — include file contents in the prompt

---

## SDLC Command Suite — Complete Implementation

Below is a full set of skills covering the software engineering lifecycle. Create these under your project's `.claude/skills/` directory.

---

### 1. `/investigate` — Code Investigation & Exploration

```
.claude/skills/investigate/
├── SKILL.md
└── CHECKLIST.md
```

**SKILL.md:**
```markdown
---
name: investigate
description: Investigate a codebase area, feature, or bug. Use when exploring unfamiliar code, understanding how something works, or tracing data flow.
allowed-tools: Read, Grep, Glob, Bash(find:*), Bash(git log:*), Bash(git blame:*)
argument-hint: [topic or area to investigate]
context: fork
---

# Investigation Skill

Investigate: $ARGUMENTS

## Process

1. **Scope the investigation**: Identify what exactly needs to be understood
2. **Find entry points**: Use Grep/Glob to locate relevant files, functions, and classes
3. **Trace the flow**: Follow the code path from entry to exit
   - Data flow: where data comes from, how it's transformed, where it goes
   - Control flow: what triggers this code, what decisions are made
   - Dependencies: what external services/libraries are involved
4. **Check history**: Use `git log` and `git blame` on key files to understand evolution
5. **Identify risks**: Note any code smells, tech debt, or potential issues
6. **Document findings**: Produce a clear summary

## Output Format

Produce a structured report:
- **Summary**: 2-3 sentence overview
- **Key Files**: List of relevant files with their roles
- **Architecture**: How components connect (ASCII diagram if helpful)
- **Data Flow**: How data moves through the system
- **Risks & Concerns**: Anything noteworthy
- **Recommendations**: Suggested next steps

Refer to @CHECKLIST.md for investigation checklist items.
```

**CHECKLIST.md:**
```markdown
# Investigation Checklist

- [ ] Entry points identified
- [ ] All relevant files located
- [ ] Data flow traced end-to-end
- [ ] Error handling paths checked
- [ ] External dependencies cataloged
- [ ] Configuration/env vars documented
- [ ] Tests coverage assessed
- [ ] Recent changes reviewed (git log)
- [ ] Related issues/PRs checked
```

---

### 2. `/debug` — Debugging

```
.claude/skills/debug/
└── SKILL.md
```

**SKILL.md:**
```markdown
---
name: debug
description: Debug an error, unexpected behavior, or failing test. Use when something is broken and needs diagnosis and fix.
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
argument-hint: [error message, symptom, or failing test]
---

# Debugging Skill

Debug: $ARGUMENTS

## Process

1. **Reproduce**: Understand the exact error or symptom
   - If an error message is provided, search the codebase for it
   - If a test is failing, run it to see the exact failure
   
2. **Hypothesize**: Form 2-3 hypotheses about root cause
   - Check recent changes: `git log --oneline -20` and `git diff`
   - Look for common patterns: null refs, type mismatches, race conditions, config issues

3. **Narrow down**: Use binary search approach
   - Add strategic logging or use existing logs
   - Check input/output at each boundary
   - Isolate: is it in our code, a dependency, or the environment?

4. **Root cause**: Identify the exact line(s) and condition causing the issue

5. **Fix**: Apply minimal, targeted fix
   - Fix the root cause, not just the symptom
   - Preserve existing behavior for non-broken paths

6. **Verify**: 
   - Run the failing test/repro case to confirm the fix
   - Run related tests to check for regressions
   - Consider edge cases the fix might affect

7. **Prevent**: 
   - Add a test that would have caught this
   - If appropriate, add validation or error handling

## Output
- Root cause explanation
- The fix applied
- Verification results
- Prevention measures added
```

---

### 3. `/codegen` — Code Generation

```
.claude/skills/codegen/
├── SKILL.md
└── templates/
    └── component.md
```

**SKILL.md:**
```markdown
---
name: codegen
description: Generate new code — components, modules, functions, APIs, services. Use for any code creation task.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash
argument-hint: [what to generate, e.g. "REST API for user management"]
---

# Code Generation Skill

Generate: $ARGUMENTS

## Process

1. **Understand requirements**: Parse what needs to be built
2. **Study existing patterns**: 
   - Find similar code in the project and match the style
   - Check for shared utilities, base classes, or conventions
   - Review CLAUDE.md for project-specific conventions
3. **Plan the structure**: 
   - List files to create/modify
   - Define interfaces/types first
   - Plan the dependency graph
4. **Generate code**:
   - Follow project naming conventions
   - Include proper error handling
   - Add appropriate types/interfaces
   - Write doc comments for public APIs
5. **Add tests**: 
   - Unit tests for core logic
   - Edge case coverage
   - Match the project's test patterns
6. **Verify**:
   - Run linter/formatter
   - Run the new tests
   - Run related existing tests
   - Type check if applicable

## Principles
- Match existing code style exactly
- Prefer composition over inheritance
- Handle errors explicitly
- Keep functions focused and small
- Add types/interfaces before implementation
```

---

### 4. `/create-issue` — Issue Creation

```
.claude/skills/create-issue/
└── SKILL.md
```

**SKILL.md:**
```markdown
---
name: create-issue
description: Create a well-structured GitHub/GitLab issue from a description or bug report. Use when filing new issues.
allowed-tools: Bash(gh:*), Read, Grep, Glob
argument-hint: [issue title or description]
disable-model-invocation: true
---

# Create Issue Skill

Create issue: $ARGUMENTS

## Process

1. **Analyze the request**: Determine if this is a bug, feature, task, or improvement
2. **Research context**:
   - Search codebase for relevant files and current behavior
   - Check for existing related issues: `gh issue list --search "$ARGUMENTS"`
   - Identify affected components
3. **Draft the issue**:

### For Bugs:
```
Title: [Bug] <concise description>

## Description
<What's happening vs what should happen>

## Steps to Reproduce
1. ...
2. ...

## Expected Behavior
<What should happen>

## Actual Behavior
<What actually happens>

## Affected Files
- `path/to/file.ts` — <why relevant>

## Possible Fix
<If you have an idea>
```

### For Features:
```
Title: [Feature] <concise description>

## Summary
<What and why>

## Motivation
<Problem this solves>

## Proposed Solution
<How to implement>

## Alternatives Considered
<Other approaches>

## Affected Areas
- <component/module>
```

4. **Create**: Use `gh issue create` with the drafted content
5. **Add labels**: Apply appropriate labels based on type and priority
6. **Report**: Show the created issue URL

## Labels Guide
- `bug` — something is broken
- `enhancement` — new feature
- `documentation` — docs needed
- `good first issue` — beginner friendly
- `priority:high` / `priority:low` — urgency
```

---

### 5. `/fix-issue` — Issue Resolution

```
.claude/skills/fix-issue/
└── SKILL.md
```

**SKILL.md:**
```markdown
---
name: fix-issue
description: Fix a GitHub issue end-to-end. Reads the issue, investigates, implements a fix, and prepares a PR.
allowed-tools: Bash, Read, Grep, Glob, Write, Edit
argument-hint: [issue number]
disable-model-invocation: true
---

# Fix Issue Skill

Fix issue #$ARGUMENTS

## Process

1. **Read the issue**: 
   ```
   gh issue view $1 --json title,body,labels,comments
   ```

2. **Understand the problem**:
   - Parse the issue description and any reproduction steps
   - Read all comments for additional context
   - Identify acceptance criteria

3. **Investigate**:
   - Locate the relevant code
   - Understand the current behavior
   - Identify root cause (for bugs) or implementation plan (for features)

4. **Create a branch**:
   ```
   git checkout -b fix/$1-<short-description>
   ```

5. **Implement the fix**:
   - Make minimal, focused changes
   - Follow existing code patterns
   - Add/update tests
   - Update documentation if needed

6. **Verify**:
   - Run the test suite
   - Manually verify the fix matches the issue description
   - Check for regressions

7. **Commit and prepare PR**:
   - Write a clear commit message referencing the issue
   - Push the branch
   - Create a PR with:
     - Reference to the issue (`Fixes #$1`)
     - Summary of changes
     - Testing done

## Output
- Summary of what was changed and why
- Link to the created PR
```

---

### 6. `/review` — Code Review

```
.claude/skills/review/
├── SKILL.md
└── SECURITY_CHECKLIST.md
```

**SKILL.md:**
```markdown
---
name: review
description: Review code changes for bugs, security, performance, and style. Use for PR review or reviewing staged changes.
allowed-tools: Read, Grep, Glob, Bash(git diff:*), Bash(git log:*)
argument-hint: [PR number, branch name, or empty for staged changes]
context: fork
---

# Code Review Skill

Review: $ARGUMENTS

## Context Gathering

If a PR number is given:
```
gh pr diff $1
gh pr view $1 --json title,body,comments
```

If a branch name is given:
```
git diff main...$1
```

If empty, review staged changes:
```
git diff --staged
```

## Review Process

1. **Understand intent**: What is this change trying to accomplish?

2. **Review for correctness**:
   - Logic errors or edge cases
   - Null/undefined handling
   - Off-by-one errors
   - Race conditions or concurrency issues
   - Error handling completeness

3. **Review for security** (see @SECURITY_CHECKLIST.md):
   - Input validation
   - SQL injection / XSS risks
   - Authentication/authorization gaps
   - Exposed secrets or credentials

4. **Review for performance**:
   - N+1 queries
   - Unnecessary allocations
   - Missing indices
   - Unbounded operations

5. **Review for maintainability**:
   - Code clarity and naming
   - Test coverage for new/changed code
   - Documentation for public APIs

## Output Format

Organize feedback by severity:
- 🔴 **Must Fix**: Bugs, security issues, data loss risks
- 🟡 **Should Fix**: Performance issues, missing edge cases
- 🟢 **Suggestion**: Style, readability, nice-to-haves
- ✅ **Looks Good**: What was done well

Be specific: reference exact lines and suggest concrete fixes.
```

---

### 7. `/test` — Test Generation

```
.claude/skills/test/
└── SKILL.md
```

**SKILL.md:**
```markdown
---
name: test
description: Generate or improve tests for specific code. Use when adding test coverage, writing tests for new code, or improving existing tests.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash
argument-hint: [file path or function to test]
---

# Test Generation Skill

Write tests for: $ARGUMENTS

## Process

1. **Analyze the target code**: Read the file/function to understand behavior
2. **Study existing test patterns**:
   - Find existing test files to match framework, style, and conventions
   - Note assertion patterns, setup/teardown approaches, mocking strategy
3. **Identify test cases**:
   - Happy path (normal operation)
   - Edge cases (empty inputs, boundary values, large inputs)
   - Error cases (invalid inputs, network failures, permission errors)
   - Integration points (how it interacts with dependencies)
4. **Write tests**:
   - Use the project's test framework and patterns
   - Group by behavior/scenario
   - Use descriptive test names
   - Keep each test focused on one behavior
   - Mock external dependencies appropriately
5. **Run and verify**:
   - Execute the new tests
   - Confirm they pass
   - Verify they fail when the code is broken (mutation check)
```

---

### 8. `/refactor` — Code Refactoring

```
.claude/skills/refactor/
└── SKILL.md
```

**SKILL.md:**
```markdown
---
name: refactor
description: Refactor code to improve quality without changing behavior. Use for cleanup, pattern improvements, or tech debt reduction.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash
argument-hint: [file/area to refactor and optional goal]
---

# Refactoring Skill

Refactor: $ARGUMENTS

## Process

1. **Assess current state**:
   - Read the target code and understand its behavior
   - Identify the specific smells or issues to address
   - Check test coverage — refactoring without tests is risky

2. **Ensure test coverage**:
   - If tests are insufficient, write them FIRST before refactoring
   - Tests are your safety net

3. **Plan changes**:
   - List specific refactoring steps
   - Keep each step small and verifiable
   - Common patterns:
     - Extract method/function
     - Rename for clarity
     - Remove duplication (DRY)
     - Simplify conditionals
     - Introduce proper abstractions
     - Break up large files/classes

4. **Execute incrementally**:
   - Make one refactoring at a time
   - Run tests after each change
   - Commit at safe points

5. **Verify**:
   - All existing tests pass
   - Behavior is unchanged
   - Code is measurably improved (smaller functions, less duplication, etc.)
```

---

### 9. `/commit` — Smart Commits

```
.claude/skills/commit/
└── SKILL.md
```

**SKILL.md:**
```markdown
---
name: commit
description: Create a well-structured git commit from current changes.
allowed-tools: Bash(git:*)
argument-hint: [optional commit message override]
disable-model-invocation: true
---

# Smart Commit Skill

## Context

- Current status: !`git status --short`
- Current diff: !`git diff --staged`
- Unstaged changes: !`git diff`
- Current branch: !`git branch --show-current`
- Recent commits for style reference: !`git log --oneline -5`

## Process

1. If nothing is staged, stage all changes: `git add -A`
2. Analyze the diff to understand what changed
3. Generate a commit message following conventional commits:
   ```
   type(scope): concise description
   
   - Detail of change 1
   - Detail of change 2
   ```
   Types: feat, fix, refactor, test, docs, chore, style, perf, ci
4. If $ARGUMENTS is provided, use it as the message instead
5. Create the commit
6. Show the result
```

---

### 10. `/pr` — Pull Request Creation

```
.claude/skills/pr/
└── SKILL.md
```

**SKILL.md:**
```markdown
---
name: pr
description: Create a pull request with a well-structured description.
allowed-tools: Bash(git:*), Bash(gh:*)
argument-hint: [optional PR title]
disable-model-invocation: true
---

# Pull Request Skill

## Context

- Branch: !`git branch --show-current`
- Commits not in main: !`git log main..HEAD --oneline`
- Diff summary: !`git diff main..HEAD --stat`

## Process

1. Push the current branch: `git push -u origin HEAD`
2. Analyze all commits and changes since diverging from main
3. Create a PR with:
   - **Title**: $ARGUMENTS if provided, otherwise generate from changes
   - **Body**:
     ```
     ## Summary
     <What this PR does and why>
     
     ## Changes
     - <Change 1>
     - <Change 2>
     
     ## Testing
     <How this was tested>
     
     ## Related Issues
     <Fixes #N or Related to #N>
     ```
4. Use `gh pr create` with the generated content
5. Output the PR URL
```

---

### 11. `/docs` — Documentation Generation

```
.claude/skills/docs/
└── SKILL.md
```

**SKILL.md:**
```markdown
---
name: docs
description: Generate or update documentation for code, APIs, or features.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash
argument-hint: [file, module, or topic to document]
---

# Documentation Skill

Document: $ARGUMENTS

## Process

1. **Analyze the target**: Read the code to understand its purpose, inputs, outputs, and behavior
2. **Check existing docs**: Look for existing documentation to update rather than duplicate
3. **Generate documentation**:
   - For functions/methods: JSDoc/docstring with params, return types, examples, and edge cases
   - For modules: README with overview, installation, usage, and API reference
   - For APIs: Endpoint docs with request/response examples
   - For features: User-facing docs with examples and screenshots if applicable
4. **Add inline comments**: For complex logic that needs explanation
5. **Verify**: Ensure code examples in docs actually work
```

---

## Setup Script

Run this to scaffold the entire SDLC command suite:

```bash
#!/bin/bash
# setup-sdlc-skills.sh — Run from your project root

SKILLS_DIR=".claude/skills"

skills=(investigate debug codegen create-issue fix-issue review test refactor commit pr docs)

for skill in "${skills[@]}"; do
    mkdir -p "$SKILLS_DIR/$skill"
    echo "Created $SKILLS_DIR/$skill/"
done

echo ""
echo "Skill directories created. Add SKILL.md files to each."
echo "Run /help in Claude Code to see available commands."
```

---

## Tips & Best Practices

### 1. Use `context: fork` for read-only skills
Skills like `/investigate` and `/review` that don't modify code should run in a subagent (`context: fork`). This keeps your main conversation context clean.

### 2. Use `disable-model-invocation: true` for side-effect skills
Skills like `/commit`, `/pr`, `/deploy`, and `/create-issue` have side effects. Prevent Claude from auto-triggering them.

### 3. Keep SKILL.md under 500 lines
Move detailed checklists, templates, and reference material into separate files within the skill directory. Reference them with `@filename`.

### 4. Combine with CLAUDE.md
Your project's `CLAUDE.md` should reference skills:
```markdown
## Workflows
- Use /investigate before starting any unfamiliar work
- Use /review before merging any PR
- Use /commit for all commits (follows our conventional commit format)
```

### 5. Use hooks for automation
Pair skills with hooks for automatic quality checks:
```json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Write(*.py)",
      "hooks": [{ "type": "command", "command": "ruff check $file" }]
    }]
  }
}
```

### 6. Character budget
Skill descriptions consume context. If you have many skills, check with `/context` for warnings. Set `SLASH_COMMAND_TOOL_CHAR_BUDGET` env var to increase the limit if needed.

### 7. Share with your team
Put skills in `.claude/skills/` (project scope) and commit to git. The whole team gets the same commands.

---

## Quick Reference

| Command | SDLC Phase | Auto-invoke? | Context |
|---------|-----------|-------------|---------|
| `/investigate` | Discovery | Yes | fork |
| `/debug` | Maintenance | Yes | inline |
| `/codegen` | Implementation | Yes | inline |
| `/create-issue` | Planning | No | inline |
| `/fix-issue` | Maintenance | No | inline |
| `/review` | Quality | Yes | fork |
| `/test` | Quality | Yes | inline |
| `/refactor` | Improvement | Yes | inline |
| `/commit` | Delivery | No | inline |
| `/pr` | Delivery | No | inline |
| `/docs` | Documentation | Yes | inline |

---

*Based on official Claude Code documentation at [code.claude.com/docs](https://code.claude.com/docs/en/slash-commands) and [Skills docs](https://code.claude.com/docs/en/skills).*
