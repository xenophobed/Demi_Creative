---
name: product-audit
description: Compare what the PRD says vs what's actually built. Finds naming mismatches, missing features, incomplete implementations, and product-level gaps. Use when you notice something doesn't match the product vision or want a systematic audit of an area.
allowed-tools: Read, Grep, Glob, Bash(git log:*), Bash(gh issue view:*), Bash(gh issue list:*)
argument-hint: [area or observation, e.g. "My Stories page", "upload flow", "navigation", "full audit"]
context: fork
agent: Plan
---

# Product Audit Skill

Audit the implementation against product spec for: $ARGUMENTS

## Product Spec (auto-loaded)

### PRD Summary
!`head -100 docs/product/PRD.md`

### Domain Model
!`head -80 docs/product/DOMAIN.md`

### Architecture
!`head -60 docs/architecture/ARCHITECTURE.md`

## Conventions
!`cat .claude/rules/github-conventions.md`

## Already-Filed Issues
!`gh issue list --state open --limit 50 --json number,title,labels --jq '.[] | "#\(.number) \(.title) — \([.labels[].name] | join(", "))"'`

## Process

1. **Understand the audit scope**:
   - If a specific area is given (e.g. "My Stories page"), focus on that area
   - If "full audit" is given, systematically check each PRD section
   - If an observation is given (e.g. "My Stories should be My Library"), investigate that specific gap

2. **Load the product spec**:
   - Read the full PRD: `docs/product/PRD.md`
   - Read the domain model: `docs/product/DOMAIN.md`
   - Identify what the spec says should exist for the audited area

3. **Examine the implementation**:
   - Find all relevant frontend components, pages, and routes
   - Find all relevant backend routes, agents, and services
   - Check actual naming, copy text, labels, navigation, and data models
   - Compare against what the PRD defines

4. **Identify gaps** — look for these categories:
   - **Naming mismatches**: UI labels/copy that don't match PRD terminology (e.g. "My Stories" vs "My Library")
   - **Missing features**: PRD features not implemented at all
   - **Incomplete features**: Partially built features missing key behaviors
   - **Wrong scope**: Features that are too narrow for the product vision (e.g. only stories when the PRD says stories + news + interactive)
   - **UX gaps**: Missing navigation, empty states, error handling, loading states
   - **Data model drift**: Backend models that don't match the domain model
   - **Safety gaps**: Missing content safety checks required by PRD

5. **Cross-check with existing issues**:
   - Compare findings against already-filed GitHub issues
   - Skip anything that's already tracked
   - Note if an existing issue needs updating to match findings

## Output Format

```
## Product Audit: <area>

### Spec Says
<What the PRD/domain model defines for this area>

### Implementation Has
<What actually exists in the code>

### Gaps Found

#### 1. <Gap title>
- **Type**: Naming mismatch | Missing feature | Incomplete | Wrong scope | UX gap | Data model drift | Safety gap
- **Spec**: <what the PRD says>
- **Actual**: <what the code does>
- **Impact**: High | Medium | Low
- **Suggested fix**: <brief description>
- **Already tracked?**: #N or No

#### 2. <next gap>
...

### Suggested Issues to File
For each untracked gap, provide a ready-to-file issue:
- **Title**: <conventional title>
- **Labels**: <from taxonomy>
- **Epic**: <parent epic #>
- **Body**: <1-2 sentence description>
```

## Notes

- This skill only identifies gaps — it does not create issues automatically
- After reviewing the audit, use `/create-issue` to file issues for gaps you want to fix
- For a full audit, work through PRD sections systematically: §3.1 Image-to-Story, §3.2 Interactive Story, §3.3 News, §3.4 Memory, §3.5 TTS
- Focus on MVP milestone gaps first (Phase 1), then Phase 2+
