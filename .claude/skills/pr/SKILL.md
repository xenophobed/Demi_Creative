---
name: pr
description: Create a pull request with a well-structured description from current branch changes.
allowed-tools: Bash(git:*), Bash(gh:*)
argument-hint: [optional PR title]
disable-model-invocation: true
---

# Pull Request Skill

## Context

- Branch: !`git branch --show-current`
- Commits not in main: !`git log main..HEAD --oneline`
- Diff summary: !`git diff main..HEAD --stat`

## Conventions (auto-loaded)

!`cat .claude/rules/github-conventions.md`

## Process

1. Push the current branch: `git push -u origin HEAD`
2. Analyze all commits and changes since diverging from main
3. Identify the linked issue(s) from commit messages or branch name (e.g. `fix/46-...` → issue #46)
4. Look up the issue to find its milestone and parent epic
5. Create a PR with:
   - **Title**: `$ARGUMENTS` if provided, otherwise generate from changes
   - **Body**:
     ```
     ## Summary
     <What this PR does and why — reference the feature/fix in context of the product>

     ## Changes
     - <Change 1>
     - <Change 2>

     ## Testing
     <How this was tested — include test commands run>

     ## Agent / MCP Impact
     <If agent behaviour or MCP tools changed, describe the impact>

     ## Related Issues
     Fixes #N
     **Parent Epic**: #<epic number>
     ```
6. Assign the same milestone as the linked issue
7. Use `gh pr create` with the generated content
8. Output the PR URL

## Notes

- Do NOT push to main/master directly
- If CI tests exist, wait for them to pass before merging
- PR title and commit messages should follow conventional commit format
