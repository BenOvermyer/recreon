# Re:creon

This is a recreation of the old 4X space strategy game Anacreon: Reconstruction 4021, using its Pascal open source as reference.

Re:creon is written in Python.

## Requirements

- Python 3.12 or later
- [uv](https://docs.astral.sh/uv/) for dependency management
- A terminal that can show at least 80x24 (the UI is [Textual](https://textual.textualize.io/); a truecolor terminal looks best)

## Starting the game

```bash
uv sync          # install dependencies (first time only)
uv run recreon   # launch the game
```

This opens on the prologue menu, which is where the original starts: new game, load a saved game, save, quit, and the settings that live outside a game. Choose **New game** to pick a scenario, page through its introduction, choose how many empires are played by humans, and name them.

### Command-line options

```bash
uv run recreon --scenario path/to/GAME.SCN   # skip the picker and start this scenario
uv run recreon --scenario-dir DIR            # scan DIR for *.SCN in the picker
uv run recreon --name "Terran Concordat"     # name your empire (default: Player)
uv run recreon --save-dir DIR                # where saves are written and read (default: .)
uv run recreon --no-ui                       # advance one turn headlessly and print the result
uv run recreon --version
```

`--scenario` starts a game immediately and drops you on the map with the given empire name, bypassing the prologue and the scenario picker.

### Scenarios

Fourteen scenarios ship with the game, in `src/recreon/data/scenarios/`, and the picker lists them all:

| Scenario | Difficulty | Players | Length |
| --- | --- | --- | --- |
| First Light: 4021 | Beginner | 1-3 | 50+ years |
| Corsairs of Meridian | Beginner | 1-2 | 50+ years |
| The Outer Reach | Beginner | 1-4 | 50+ years |
| Two Crowns | Intermediate | 1-2 | 5-10 years |
| The Four Heirs | Intermediate | 2-4 | 20-30 years |
| Triad | Intermediate | 2-3 | 50+ years |
| Vhalsecc | Intermediate | 1-4 | 100+ years |
| The Reckoning | Intermediate | 2-4 | 100+ years |
| The Long Sleep | Intermediate | 2-4 | 100+ years |
| The Thousand Suns | Intermediate | 3-8 | 100+ years |
| The Boundary Stones | Advanced | 2-4 | 100+ years |
| The Kalgan Frontier | Advanced | 1-4 | 50-200 years |
| The Long Run | Advanced | 1 | 100+ years |
| The Veil | Expert | 1-4 | 100+ years |

**First Light: 4021** is the one to start with, and **The Kalgan Frontier** is the default `--no-ui` uses.

Thirteen of these are the scenarios the original shipped, imported under new titles; the galaxies are byte-identical to the originals, and only the titles were changed. `src/recreon/data/scenarios/README.md` maps each one back to the file it came from, and documents the two that needed repairing to load at all. `The Kalgan Frontier` is new content rather than a port.

The unmodified originals are still in `original/scenarios/` under their own names, and can be played directly — two of them will not load, faithfully:

```bash
uv run recreon --scenario-dir original/scenarios
uv run recreon --scenario original/scenarios/INTRO.SCN
```

One caveat on the bundled set: **The Long Run** and **The Long Sleep** pack their worlds tightly enough that placement legitimately fails on a small fraction of new games, reporting `No room for random world in zone`. The DOS build failed on the same rolls. Start a new game and it will place.

## Playing

The game autosaves after each turn, as the original does.

The map screen's keys:

| Key | Does |
| --- | --- |
| arrows / `hjkl` | move the map cursor |
| `n` | end your turn |
| `z` | close-up of whatever the cursor is over |
| `i` | production forecast for that world |
| `f` | fleets |
| `b` | construction |
| `w` | warp links |
| `d` | defenses |
| `m` or `F2` | command menu |
| `g` | prologue menu (save, load, quit) |
| `q` | quit |

The function keys open the original's status windows: `F1` help, `F3`/`F4` world and military status, `F5`/`F6` fleets, `F7` news, `F8` empires, `F9` names, `F10` map.

## Development

```bash
uv run pytest                    # full test suite
uv run pytest tests/test_fleet.py -q
uvx ruff check src/ tests/       # lint
```

`CLAUDE.md` covers the porting conventions and the known original bugs that are reproduced deliberately; `docs/` carries the architecture and the implementation plan.
