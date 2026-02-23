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

## Process

1. Push the current branch: `git push -u origin HEAD`
2. Analyze all commits and changes since diverging from main
3. Create a PR with:
   - **Title**: `$ARGUMENTS` if provided, otherwise generate from changes
   - **Body**:
     ```
     ## Summary
     <What this PR does and why — reference the feature/fix in context of Kids Creative Workshop>

     ## Changes
     - <Change 1>
     - <Change 2>

     ## Testing
     <How this was tested — include test commands run>
     ```bash
     cd backend && python -m pytest tests/ -v
     ```

     ## Agent / MCP Impact
     <If agent behaviour or MCP tools changed, describe the impact>

     ## Related Issues
     <Fixes #N or Related to #N>
     ```
4. Use `gh pr create` with the generated content
5. Output the PR URL

## Notes

- Do NOT push to main/master directly
- If CI tests exist, wait for them to pass before merging
- Tag relevant reviewers if known
