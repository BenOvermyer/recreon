---
description: File an original-bug issue on Worktree/Forgejo
agent: bug-filer
subtask: true
---
File an `original-bug` issue on the Worktree/Forgejo tracker (`ben.overmyer/recreon`) for the defect described below, using the `mcp__worktree__*` tools.

Defect: $ARGUMENTS

The issue body must follow CLAUDE.md §"Original bugs get filed":
1. What the original does (Pascal `file:line` in `original/`).
2. Why it is wrong.
3. What the port does now (Python `file:line` in `src/recreon/`, reproduced faithfully).
4. What fixing it would change about gameplay (flag balance-touching cases as open judgement, not asserted bugs).

First search existing `original-bug` issues to avoid duplicates (#7–#18 are catalogued). Create the issue prefixed `[original-bug]` and apply the `original-bug` label (creating it if missing). Do not use `github_*` — the GitHub repo isn't reachable with the current token.