---
name: plan
description: Design an implementation plan before coding. Use when a task touches multiple files, involves architectural decisions, or is bigger than a one-file fix. Creates a step-by-step plan with file changes, interfaces, risks, and test strategy.
allowed-tools: Read, Grep, Glob, Bash(git log:*), Bash(gh issue view:*)
argument-hint: [issue number or feature description]
context: fork
agent: Plan
---

# Plan Skill

Create an implementation plan for: $ARGUMENTS

## Conventions (auto-loaded)

!`cat .claude/rules/github-conventions.md`

## Process

1. **Understand the goal**:
   - If an issue number is given, read it: `gh issue view $ARGUMENTS --json title,body,labels,comments`
   - If a description is given, clarify scope and acceptance criteria
   - Identify the parent epic and PRD section if applicable

2. **Map the current state**:
   - Find all files that will be affected
   - Read each file to understand current interfaces and data flow
   - Identify dependencies between components
   - Check existing tests for the affected area

3. **Design the approach**:
   - List every file that needs to change and what changes
   - Define new interfaces, models, or schemas before implementation
   - Identify the order of changes (what depends on what)
   - Flag anything that could break existing functionality
   - Consider backward compatibility

4. **Define the test strategy**:
   - What contract tests are needed (MCP tool schemas)
   - What API tests are needed (route behavior)
   - What integration tests are needed (end-to-end flows)
   - What edge cases matter most

5. **Identify risks**:
   - What could go wrong
   - What areas need `/investigate` first
   - What migrations or data changes are needed
   - Performance or safety implications

## Output Format

```
## Plan: <title>

### Goal
<1-2 sentences: what we're building and why>

### Files to Change
1. `path/to/file.py` — <what changes and why>
2. `path/to/file.py` — <what changes and why>
(in dependency order — change this file first, then that one)

### New Interfaces / Models
<Any new classes, schemas, API contracts to define>

### Step-by-Step Implementation
1. <first step — smallest safe change>
2. <second step>
3. ...
(each step should be independently testable)

### Test Strategy
- Contract: <what to test>
- API: <what to test>
- Integration: <what to test>

### Risks
- <risk 1 and mitigation>
- <risk 2 and mitigation>

### Estimated Scope
- Files changed: N
- New files: N
- Complexity: Small / Medium / Large
```

## When NOT to use this skill

- One-file bug fixes → just use `/fix-issue` or `/debug`
- Pure refactoring with no interface changes → just use `/refactor`
- Adding tests only → just use `/test`
