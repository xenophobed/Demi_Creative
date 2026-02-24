---
name: feature-spec
description: Design a new product feature before engineering begins. Produces user stories, acceptance criteria, age-adaptation rules, safety requirements, and a draft PRD section. Use when you have a feature idea and need to think it through from the product perspective.
allowed-tools: Read, Grep, Glob, Bash(gh issue list:*), Bash(gh issue view:*)
argument-hint: [feature idea, e.g. "my library page that shows all artifact types" or "parent dashboard"]
context: fork
agent: Plan
---

# Feature Spec Skill

Design product feature: $ARGUMENTS

## Product Context (auto-loaded)

### Current PRD Sections
!`grep -n "^## \|^### " docs/product/PRD.md | head -40`

### Domain Rules
!`head -80 docs/product/DOMAIN.md`

### Existing Epics
!`gh issue list --state open --label type:epic --json number,title,labels --jq '.[] | "#\(.number) \(.title)"' 2>/dev/null || echo "none"`

### Open Issues (for overlap check)
!`gh issue list --state open --limit 50 --json number,title --jq '.[] | "#\(.number) \(.title)"' 2>/dev/null || echo "none"`

## Conventions
!`cat .claude/rules/github-conventions.md`

## Process

1. **Understand the feature idea**:
   - What is the user trying to achieve? (user goal)
   - What user problem does this solve?
   - Which age groups does it affect (3-5, 6-8, 9-12)?
   - Which PRD section does it belong to (§3.1-§3.5), or is it a new section?

2. **Check for overlap**:
   - Read the full PRD: `docs/product/PRD.md`
   - Read domain rules: `docs/product/DOMAIN.md`
   - Search existing GitHub issues for overlap
   - Does this feature already exist partially? Is it planned?

3. **Examine what exists in the code**:
   - What's already built that relates to this feature?
   - What backend routes, agents, frontend pages would be affected?
   - What infrastructure is already in place?

4. **Design the feature** (product level, NOT engineering):
   - User stories: "As a [child/parent], I can [action], so that [benefit]"
   - Acceptance criteria: testable conditions that define "done"
   - Age adaptation: how the feature behaves differently per age group
   - Content safety: what safety checks are needed
   - Edge cases: empty states, error states, first-time use

5. **Draft the PRD section**:
   - Write a draft section matching the PRD's existing format
   - Include: description, user journey, acceptance criteria, out-of-scope

6. **Propose the epic and stories**:
   - Which phase does this belong to (MVP, Phase 2, Phase 3)?
   - What epic should contain it (existing or new)?
   - Break down into stories (each independently deliverable)
   - Estimate priority for each story

## Output Format

```
## Feature Spec: <feature name>

### Problem
<What user problem does this solve? 1-2 sentences>

### Target Users
<Which users and age groups>

### PRD Alignment
<Which PRD section this extends or new section needed>
<Phase: MVP / Phase 2 / Phase 3>

### User Stories
1. As a [role], I can [action], so that [benefit]
2. ...

### Acceptance Criteria
- [ ] <testable condition>
- [ ] <testable condition>
- [ ] ...

### Age Adaptation
| Age Group | Behavior |
|-----------|----------|
| 3-5 | ... |
| 6-8 | ... |
| 9-12 | ... |

### Content Safety Requirements
- <what needs safety checking>

### Edge Cases
- Empty state: <what to show when no data>
- Error state: <what to show when something fails>
- First use: <onboarding behavior>

### What Already Exists
- <existing code/features that relate>

### Draft PRD Section
<Ready-to-paste PRD section in the existing doc format>

### Proposed Epic & Stories

**Epic**: <new epic title> OR **Existing Epic**: #N
**Phase**: MVP / Phase 2 / Phase 3

| # | Story | Priority | Layer |
|---|-------|----------|-------|
| 1 | <story title> | P1/P2/P3 | backend/frontend/both |
| 2 | <story title> | P1/P2/P3 | backend/frontend/both |

### Out of Scope
- <what this feature intentionally does NOT include>
```

## After This Skill

1. Review the spec — does it match your vision?
2. Use `/prd <feature name>` to add the approved section to the PRD
3. Use `/create-issue` to file the epic and individual stories
4. Then proceed to `/plan` → `/fix-issue` for engineering
