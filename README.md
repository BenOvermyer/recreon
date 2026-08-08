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

The picker scans `src/recreon/data/scenarios/` by default, which ships `frontier.scn` — that is also the scenario `--no-ui` uses when none is given.

The 13 scenarios the original shipped are in `original/scenarios/`, and you can play them:

```bash
uv run recreon --scenario-dir original/scenarios
uv run recreon --scenario original/scenarios/INTRO.SCN
```

Three of them do not load cleanly, and that is faithful to the DOS build rather than a bug here. `AWAKEN.SCN` asks for more worlds than the game can hold and `PRINCES.SCN` has a malformed starbase block, so neither will ever load; `GAUNTLET.SCN` packs its worlds so tightly that placement fails on an unlucky roll, so it loads roughly nine times in ten — try again if it refuses.

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
