---
description: Launch the recreon TUI or run headlessly
agent: build
---
Run the game with `uv run recreon`

If arguments are supplied via `$ARGUMENTS`, append them. Known flags:
- `--scenario <path.scn>` — pick a scenario file (default: `data/scenarios/frontier.scn`).
- `--name <X>` — set the player empire name.
- `--no-ui` — advance one turn headlessly.

Examples:
- `/run --scenario data/scenarios/frontier.scn --name Terrans`
- `/run --no-ui`

Report what happened (any exception with traceback). Do **not** edit anything under `original/`.