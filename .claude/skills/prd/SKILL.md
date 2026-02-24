---
name: prd
description: Update the Product Requirements Document. Add new feature sections, update existing features, mark progress, retire deprecated features, or reorganize sections. Use after a feature spec is approved or when product decisions change.
allowed-tools: Read, Edit, Grep, Glob, Bash(gh issue list:*), Bash(git diff:*)
argument-hint: [action, e.g. "add My Library feature", "update §3.1 status to complete", "retire news-to-kids", "sync progress"]
---

# PRD Update Skill

Update the PRD: $ARGUMENTS

## Current PRD Structure
!`grep -n "^## \|^### \|^#### " docs/product/PRD.md`

## Current Domain Model
!`grep -n "^## \|^### " docs/product/DOMAIN.md`

## Epic Status
!`gh issue list --label type:epic --state all --json number,title,state --jq '.[] | "#\(.number) [\(.state)] \(.title)"' 2>/dev/null || echo "none"`

## Milestone Progress
!`gh api repos/:owner/:repo/milestones --jq '.[] | "\(.title): \(.closed_issues)/\(.open_issues + .closed_issues) done"' 2>/dev/null || echo "none"`

## Process

Based on `$ARGUMENTS`, determine the action:

### Adding a new feature section

1. Read the full PRD: `docs/product/PRD.md`
2. Read the domain model: `docs/product/DOMAIN.md`
3. Identify the correct location in the PRD (which section number)
4. Check if a `/feature-spec` output was provided — if so, use it as source
5. Write the new section matching the PRD's existing format:
   - Section heading with number
   - Description paragraph
   - User journey (numbered steps)
   - Acceptance criteria (checkbox list)
   - Out-of-scope notes
6. Update the table of contents if one exists
7. Update cross-references in other docs if needed (ARCHITECTURE.md, DOMAIN.md)
8. Show the diff of what changed

### Updating an existing feature

1. Read the full PRD
2. Find the section to update
3. Make the requested change (description, criteria, status, scope)
4. Preserve all existing content that isn't being changed
5. Show the diff

### Marking feature progress

1. Read the full PRD
2. Cross-reference with GitHub milestone and epic status
3. Add or update status indicators:
   - `[Not Started]` — no stories completed
   - `[In Progress]` — some stories completed
   - `[Complete]` — all stories closed, epic closed
   - `[Deferred]` — moved to later phase
4. Show the diff

### Syncing PRD with reality (`sync progress`)

1. Read the full PRD
2. Fetch all epic and story status from GitHub
3. Update every feature section's status
4. Flag any features that exist in code but not in PRD
5. Flag any PRD features with no GitHub tracking
6. Show a summary table and the diff

### Retiring/deferring a feature

1. Read the full PRD
2. Find the section
3. Mark it as `[Deferred to Phase N]` or `[Retired]` with a reason
4. Do NOT delete the section — keep it for historical reference
5. Update the phase/milestone references
6. Show the diff

## Rules

- NEVER delete PRD content without explicit confirmation — mark as deferred/retired instead
- ALWAYS show the diff before finalizing (use `git diff` after editing)
- ALWAYS maintain the existing PRD format and numbering scheme
- If adding a feature would renumber existing sections, add it as a subsection instead
- Update DOMAIN.md if the feature introduces new domain concepts (age rules, safety categories)
- Update ARCHITECTURE.md cross-references if the feature adds new system components
- After updating, remind the user to `/commit` the changes

## Output Format

```
## PRD Update: <what changed>

### Action
<add / update / mark progress / sync / retire>

### Changes Made
- <file>: <what changed>

### Diff
<show the actual git diff>

### Cross-Reference Updates Needed
- [ ] <other doc that may need updating>

### Next Steps
- [ ] `/commit` to save changes
- [ ] `/create-issue` if new stories need filing
- [ ] Update GitHub epic/milestone if scope changed
```
