---
name: create-issue
description: Create a well-structured GitHub issue following project conventions. Use when filing new bugs, feature requests, or tasks.
allowed-tools: Bash(gh:*), Read, Grep, Glob
argument-hint: [issue title or description]
disable-model-invocation: true
---

# Create Issue Skill

Create issue: $ARGUMENTS

## Conventions (auto-loaded)

!`cat .claude/rules/github-conventions.md`

## Process

1. **Analyze the request**: Determine the type (`type:bug`, `type:story`, `type:chore`, `type:spike`)

2. **Research context**:
   - Search codebase for relevant files and current behaviour
   - Check for existing related issues: `gh issue list --search "$ARGUMENTS"`
   - Identify the parent epic from the Epic Registry above
   - Identify affected layers and product domain

3. **Determine all labels**: Apply one from each required category (type, layer, domain, priority, phase) per the conventions above

4. **Determine milestone**: Derive from the phase label

5. **Draft the issue body** using the appropriate template:

### For Bugs (`type:bug`):
```
## Description
<What's happening vs what should happen>

**Parent Epic**: #<epic number>
**Source**: <how discovered — user report, test failure, code review, etc.>

## Affected Files
- `path/to/file.py:line` — <why relevant>

## Steps to Reproduce
1. ...

## Expected Behavior
<What should happen>

## Actual Behavior
<What actually happens>

## Impact
<How this affects the product / users>
```

### For Stories (`type:story`):
```
## Description
<What this delivers and why — reference PRD section if applicable>

**Parent Epic**: #<epic number>
**PRD Reference**: §<section> (if applicable)

## Scope
- [ ] Task 1
- [ ] Task 2

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Affected Areas
- `path/to/relevant/code`
```

### For Chores (`type:chore`):
```
## Description
<What needs cleaning up and why>

## Affected Files
- `path/to/file`

## Definition of Done
- [ ] ...
```

6. **Create the issue** with all labels and milestone:
   ```bash
   gh issue create \
     --title "<title per naming convention>" \
     --label "type:...,domain:...,layer:...,P...:...,phase:..." \
     --milestone "<milestone name>" \
     --body "..."
   ```

7. **Report**: Show the created issue URL and summarize labels/milestone assigned.
