---
name: discover
description: "Pipeline: investigate -> plan -> feature-spec. Explore an idea end-to-end before coding."
allowed-tools: Read, Grep, Glob, Bash(git log:*), Bash(gh issue list:*), Bash(gh issue view:*), Bash(gh pr list:*)
argument-hint: [idea or area to explore, e.g. "story recommendation" or "interactive story save flow"]
context: fork
agent: Plan
---

# Discovery Pipeline Skill

Explore: $ARGUMENTS

> **Pipeline skill** - composes `/investigate` -> `/plan` -> `/feature-spec` into a discovery flow.
> **Read-only by default** - no code edits, no branch creation, no issue creation.

## Process

### Step 1: Investigate Current State (from /investigate)

1. Parse the topic from `$ARGUMENTS`
2. Trace current implementation across backend, frontend, and docs
3. Find related issues/PRs to avoid duplicate work:
   ```bash
   gh issue list --state all --search "$ARGUMENTS"
   gh pr list --state all --search "$ARGUMENTS"
   ```
4. Check recent changes in related paths:
   ```bash
   git log --oneline --since="3 months ago" -- <relevant paths>
   ```
5. Summarize what exists, what is missing, and what is risky

**Checkpoint**: Show investigation summary and confirm discovery scope.

### Step 2: Build an Implementation Plan (from /plan)

1. List files likely to change and expected responsibilities
2. Define required interfaces/schemas and dependency order
3. Identify testing strategy and safety implications
4. Estimate complexity (Small/Medium/Large)
5. Propose 1 recommended path and 1 fallback path

**Checkpoint**: Present plan options and confirm the recommended plan.

### Step 3: Convert Plan into Product Spec (from /feature-spec)

1. Turn the chosen plan into user stories + acceptance criteria
2. Add age adaptation and content safety requirements
3. Add edge cases and failure handling expectations
4. Propose epic/story breakdown with priorities
5. Map each story to an execution path (`/fix-issue`, `/codegen`, `/test`)

## Output Format

```
## Discovery: <topic>

### Investigation Summary
- Existing behavior: <what currently exists>
- Gaps: <what is missing>
- Risks: <key risk list>
- Related work: <issues/PRs>

### Recommended Plan
- Complexity: Small / Medium / Large
- Files likely to change: <list>
- Key interfaces/contracts: <list>
- Test strategy: <list>

### Feature Spec Draft
- User stories: <list>
- Acceptance criteria: <list>
- Age + safety requirements: <list>

### Suggested Next Commands
1. `/spec-to-backlog <feature>` to create product artifacts and issues
2. `/fix-issue <N>` for the first story after planning
```

## Guardrails

- Keep this workflow read-only unless the user explicitly asks to start implementation
- Do not create issues automatically in this skill
- Flag unknowns early instead of guessing requirements
