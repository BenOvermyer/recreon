---
description: Run the pytest suite (optionally filtered by pattern)
agent: build
---
Run the test suite with `uv run pytest`$1.

If a pattern argument was supplied (passed as `$1`), use it as a `-k` filter:
`uv run pytest -k "$1"`.

Report any failures with their tracebacks and suggest minimal fixes that respect the project's faithfulness conventions (see AGENTS.md). Do **not** edit anything under `original/`.