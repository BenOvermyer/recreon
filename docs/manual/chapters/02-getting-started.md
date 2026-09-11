# Getting Started

> *The first order of government is the map. The second is the budget.
> The third, unfortunately, is also the budget.*
> -- First manual of the Reconstruction fleet

## Installing and running

Re:creon needs Python 3.12 or later and [uv](https://docs.astral.sh/uv/)
to manage dependencies. From a clone of the repository:

```bash
uv sync            # install dependencies (first time only)
uv run recreon     # launch the game
```

The game opens full-screen in your terminal -- a Textual interface that
replaces the original's DOS screens one for one. Any terminal of at
least 80x24 works; a truecolor terminal looks best.

Useful command-line options:

| Option | Effect |
| --- | --- |
| `--scenario FILE.SCN` | Skip the scenario picker and start this game |
| `--scenario-dir DIR` | Where the picker looks for scenarios |
| `--name NAME` | Name your empire instead of choosing interactively |
| `--save-dir DIR` | Where saved games are written and read |
| `--no-ui` | Advance exactly one turn headlessly and print the result |
| `--version` | Print the version and exit |

## The prologue

What you see first is the **prologue**: the menu that lives outside any
game. Its rows, in order:

- **Begin...** -- enter the game that is loaded, if any.
- **New game** -- pick a scenario, page through its introduction,
  choose how many empires are run by humans, and name them. Computer
  empires get their names from the original's 59-name table; you can
  accept a random name or type your own.
- **Load game** / **Save game** -- saved games are JSON files in the
  save directory. (The original's save format is a raw dump of
  in-memory records; nothing in it could survive the translation to
  Python, so the saves here are readable, versioned files instead. A
  DOS-era save game cannot be loaded.)
- **Quit** -- leaves the program, asking first if the game has
  changed since the last save.
- **Time limit** -- seconds of thinking time added to each player's
  turn per year, for anyone who wants a clock.
- **New player empire** / **Delete player empire** -- adjust how many
  empires humans run.
- **Auto backup** -- whether the game autosaves after every turn. It
  is ON by default, and the autosave is how the original worked too:
  a turn that has ended is a turn that is already saved.
- **Pause** -- whether a year's news can pause for reading.
- **Sequential play** -- ON rotates through empires in a fixed order
  (Empire 1 through 8, then the year turns). OFF is the play-by-mail
  mode: each human takes their turn from the prologue, hands the save
  file on, and the year only turns when the last human has moved.
  For a solo game against the computer, leave it ON.

## The main screen

Once a game starts you are looking at the **strategic map**: a square
grid of sectors, each a star system. Worlds, bases, gates, fleets and
phenomena are single-character glyphs on a grid -- exactly as the
original drew them, because the original fit the whole game into
80x25.

- The cursor is your point of attention. Move it with the arrow keys
  or `h` `j` `k` `l`.
- Coordinates read **relative to your capital**, which sits at `0,0`;
  +Y is north. Another empire's capital has its own `0,0` from its
  own point of view, never yours.
- The menu bar carries the seven command menus -- *Info, Game,
  Empire, Worlds, Fleet, Build, Ministry of War* -- documented in
  full in chapter 8. Press `m` or `F2` to reach it.
- Direct keys skip the menu for the most-used screens: `f` fleets,
  `b` construction, `w` warp links, `d` defenses, `x` self-destruct,
  `z` close-up of the cursor's object, `i` production report for it.
- The `F` keys raise the status windows: `F3`/`F4` world and military
  status, `F5`/`F6` fleets, `F7` news, `F8` empires, `F9` names and
  records, `F10` the map. `F1` is help.
- `n` ends your turn and runs the year.

## What you can see: the fog of war

Knowledge comes in three grades, and they matter everywhere:

1. **Unknown** -- you have no idea the object exists.
2. **Known** -- you know something is there; not what it is. The map
   shows known objects.
3. **Scouted** -- you can see its contents. Detail panels, the
   status tables, and targeting all require scouting, not merely
   knowing.

Each turn, what your empire *observed* is recomputed from scratch:
fleets scout their own sector and report, and every world scouts
what it can see around itself. An empire that withdraws its fleets
genuinely loses sight of what it was watching. Objects far from
anything you own stay unknown until a **starbase scan** turns up
one -- and a base's scan is a coin flip per object per year, so a
new base maps its neighborhood over several years. **Probes**
(*Fleet ▸ Probe*, up to ten per empire) fly ahead and carry word of
what they find.

## A first turn

When a scenario starts, do this:

1. Press `z` on your capital's sector and read the close-up: class,
   population, technology, defenses, what is under construction.
2. Press `i` for the production report and see what your worlds are
   making. Ships are not built at sites -- a world with shipyards
   turns raw materials into hulls every year on its own. Sites
   (`b`) build the eight big structures: SRM fields, bases,
   fortresses, complexes, outposts, gates, links and disrupters.
3. Press `f` to see your starting fleets; select one, and give it a
   destination with *Fleet ▸ Change destination*. Explore something
   near your borders, not far from home: standard fleets cross one
   sector per year, and fuel is finite.
4. Press `n`, and read next year's news with `F7`.

That loop -- inspect, order, advance, read -- is the whole game. The
following chapters go into what each part is actually deciding for
you.
