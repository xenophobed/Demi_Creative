---
name: release
description: Cut a release with a changelog generated from merged PRs and closed issues since the last tag. Use when you want to version and document what shipped.
allowed-tools: Bash(git:*), Bash(gh:*)
argument-hint: [version number, e.g. "v0.1.0"]
disable-model-invocation: true
---

# Release Skill

Create release: $ARGUMENTS

## Context (auto-loaded)

- Latest tag: !`git describe --tags --abbrev=0 2>/dev/null || echo "no tags yet"`
- Current branch: !`git branch --show-current`
- Commits since last tag: !`git log $(git describe --tags --abbrev=0 2>/dev/null || git rev-list --max-parents=0 HEAD)..HEAD --oneline 2>/dev/null || git log --oneline`
- Merged PRs since last tag: !`gh pr list --state merged --limit 30 --json number,title,labels,mergedAt --jq '.[] | "#\(.number) \(.title)"' 2>/dev/null || echo "none found"`

## Process

1. **Determine version**:
   - If `$ARGUMENTS` is provided, use it as the version (e.g. `v0.1.0`)
   - If not provided, suggest a version based on changes:
     - Breaking changes or major features → bump major
     - New features → bump minor
     - Bug fixes only → bump patch
   - Follow semver: `vMAJOR.MINOR.PATCH`

2. **Generate changelog**:
   - Group merged PRs and commits by type:
     - **Features** — `feat` commits or `type:story` PRs
     - **Bug Fixes** — `fix` commits or `type:bug` PRs
     - **Improvements** — `refactor`, `perf` commits
     - **Documentation** — `docs` commits
     - **Infrastructure** — `chore`, `ci` commits
   - Include PR numbers and issue references
   - Skip merge commits and trivial formatting changes

3. **Create the release**:
   ```bash
   # Tag the release
   git tag -a <version> -m "Release <version>"

   # Push the tag
   git push origin <version>

   # Create GitHub release with changelog
   gh release create <version> --title "<version>" --notes "<changelog>"
   ```

4. **Report**: Show the release URL and full changelog.

## Changelog Format

```markdown
## <version> — <date>

### Features
- <description> (#PR)

### Bug Fixes
- <description> (#PR)

### Improvements
- <description> (#PR)

### Documentation
- <description> (#PR)

### Infrastructure
- <description> (#PR)
```

## Notes

- Only create releases from the `main` branch
- All PRs should be merged before releasing
- If there are open P0/P1 bugs, warn before proceeding
