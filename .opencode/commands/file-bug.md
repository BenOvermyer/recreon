---
description: File an original-bug issue on GitHub
agent: bug-filer
subtask: true
---
File an `original-bug` issue on the GitHub tracker (`BenOvermyer/recreon`) for the defect described below, using the `gh` CLI.

Defect: $ARGUMENTS

The issue body must follow AGENTS.md §"Original bugs get filed":
1. What the original does (Pascal `file:line` in `original/`).
2. Why it is wrong.
3. What the port does now (Python `file:line` in `src/recreon/`, reproduced faithfully).
4. What fixing it would change about gameplay (flag balance-touching cases as open judgement, not asserted bugs).

First search existing `original-bug` issues to avoid duplicates (`gh issue list --repo BenOvermyer/recreon --label original-bug --state all`). Create the issue prefixed `[original-bug]` and apply the `original-bug` label.
