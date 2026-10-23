# Contributing

## How we work

GitHub Flow. Short-lived branches off `master`.

1. `git checkout -b feat/thing` (or `fix/`, `docs/`).
2. Rebase onto `master` before opening the PR. Don't merge `master` into your branch.
3. Open the PR. CI (Python + Meson) has to be green.
4. One approving review, then squash-merge.
5. Releases: tag `master` with `git tag -a vX.Y.Z`.

## Commits

Conventional commits. `feat:`, `fix:`, `ci:`, `docs:`, `refactor:`.

## Ground rules

- `master` stays releasable.
- No direct pushes except maintainer emergencies.
- Keep PRs small. Stale PRs get rebased or closed.
- In `cursor_converter.py`, don't drop `host_path()` or its test.
