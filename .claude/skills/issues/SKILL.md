---
name: issues
description: List and summarize current GitHub issues. Use when you want to see open issues, plan work, or check project status.
allowed-tools: Bash(gh:*)
argument-hint: [optional filter: "mvp", "bugs", "P1", domain name, or epic number]
---

# Issues Skill

## Current Open Issues

!`gh issue list --state open --limit 50 --json number,title,labels,milestone --jq '.[] | "#\(.number) [\(.milestone.title // "none")] \(.title) — \([.labels[].name] | join(", "))"'`

## Epics Overview

!`gh issue list --state open --label type:epic --json number,title,milestone --jq '.[] | "#\(.number) \(.title) [\(.milestone.title // "none")]"'`

## Milestone Progress

!`gh api repos/:owner/:repo/milestones --jq '.[] | "\(.title): \(.closed_issues)/\(.open_issues + .closed_issues) done"'`

## Task

Summarize the issues above in a clear, prioritized view. Group by epic/milestone.

If `$ARGUMENTS` is provided, filter the view:
- A domain name (e.g. "image-to-story") → show only that domain
- "bugs" → show only `type:bug` issues
- "mvp" → show only `phase:mvp` issues
- "P0" or "P1" → show only that priority
- An epic number (e.g. "40") → show only children of that epic
- No argument → show the full board grouped by milestone, then by epic

For each issue, show: `#number | title | priority | layer`

End with a **suggested next action** — what's the highest-impact thing to work on right now.
