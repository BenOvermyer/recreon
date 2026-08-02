# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Re:creon is a Python recreation of **Anacreon: Reconstruction 4021** (v2.0, Jan 2004), a turn-based 4X space strategy game originally written in Turbo Pascal 4.0. The complete original Pascal source (~39k lines, 85 units) lives in `original/` and is the **authoritative specification** — the Python port is intended to be behavior-faithful, not a reimagining.

**Current state: Phases 1–4 complete, except the Phase 4 UI (§4.3).** Ported: `types.py` (TYPES.PAS), `datastrc.py` (DATASTRC.PAS), `datacnst.py` (DATACNST.PAS), `cdetypes.py` (CDETYPES.PAS), `npe/types.py` (NPETYPES.PAS), `galaxy.py` (GALAXY.PAS), `environ.py` (ENVIRON.PAS + `InitializeUniverse` from LOADSAVE.PAS), `misc.py` (MISC.PAS), `primintr.py` and `intrface.py` (PRIMINTR/INTRFACE.PAS — the subsets used so far, now including the whole name subsystem), `news.py` (NEWS.PAS), `update.py` (UPDATE.PAS world update), `design.py` (DESIGN.PAS designation + INTRFACE's `DesignateWorld`/`TerraformWorld`), `resource.py` (RESOURCE.PAS), `newgame.py` (NEWGAME.PAS), `orders.py` (ORDERS.PAS), `fleet.py` (FLEET.PAS), `utils/` (INT.PAS, REAL1.PAS, DFA.PAS), the turn loop in `main.py`, and `ui/`.

A scenario file loads into a populated galaxy — worlds, empires with capitals, nebulae, minefields — and worlds run a full economy: production, industry growth, population, famine, ambrosia addiction, tech drift, revolution and rebellion. Fleets deploy, carry cargo, burn fuel, move through gates, fortresses, minefields, disrupters and nebulae, and run compiled standing orders. Phase 5 (combat) is next; the fleet TUI (§4.3) and `MovePlayerStarbases` (which belongs with Phase 6 construction) are the two pieces of Phase 4 still outstanding.

**Fleets do not all move at the same moment in the turn rotation.** `update_all_fleets(player, next_player)` moves warp fleets and anything sitting on a gate for the *incoming* empire, and jump/HK fleets for the *outgoing* one, so a jump ordered this turn lands this turn. It is called from `main.update_turn`, not from `update_universe` — fleet movement is per-turn, world updates are per-year.

**Galaxies come from scenario files.** `newgame.py` (NEWGAME.PAS) is a **scenario-file interpreter, not a procedural generator** — there is no code path that builds a galaxy without a `.scn`. The original `*.SCN` files are permanently unavailable, so `data/scenarios/frontier.scn` is authored against the format recovered from the parser. It is new content, not a port, and reproduces no galaxy the original shipped.

Two settled decisions: galaxy **generation uses Python's `random`** (seeded from the scenario's `Seed`), so a seed is reproducible within this port but will not match the DOS build — that divergence is accepted, not a bug, and it is scoped to generation only; the balance formulas stay transcribed exactly. And `cdetypes.py` has no caller because the artifact and transaction directives are commented out of the scenario dispatch in v2.0, making that whole subsystem unreachable dead code in the original.

The scenario header keeps its version at **fixed columns 10–11** of line 1, and the parser rejects anything else rather than parsing loosely: Python's `int()` strips whitespace where Pascal's `Val` errors, so a header off by one column would otherwise read as some low version, silently enable the old-format shims, and desync every directive after it.

`place_world` lives in `tests/conftest.py`, not in the package — unit tests want one world with known attributes; nothing in `src/` fabricates worlds.

Modules for later phases are not stubbed out — an absent file means unported. `docs/ARCHITECTURE.md` is the map of what each one will be.

## Commands

```bash
uv sync                                     # install deps
uv run pytest                               # full suite
uv run pytest tests/test_datacnst.py -q     # one file
uv run pytest -k combat_table               # one test by name
uv run recreon                              # launch the TUI
uv run recreon --scenario path.scn --name X  # pick a scenario / empire name
uv run recreon --no-ui                      # advance one turn headlessly
```

Python 3.12, Textual for the TUI, pytest (with `asyncio_mode = "auto"`, for Textual's `run_test()` pilot) for tests. No linter or type checker is configured yet.

## Documentation map

Read these before writing code; they carry the full design and are more specific than this file:

- `docs/ARCHITECTURE.md` — target module layout under `src/recreon/`, with the Pascal unit each Python module ports, plus dependency graph and per-module function lists.
- `docs/IMPLEMENTATION_PLAN.md` — 10 phases (1–9, plus 3.5) with milestones and code sketches. Phases are ordered by dependency: data structures → galaxy/game loop → economy → scenario generation → fleets → combat → construction → AI → UI → validation.
- `docs/TRANSLATION_NOTES.md` — Pascal→Python idiom table and gotchas (`DIV` → `//`, 1-based `FOR..TO` inclusive ranges, records → dataclasses, pointers → references, overlays → plain imports).
- `docs/INITIAL_DESIGN.md` — game mechanics summary and success criteria.

## Porting conventions

These are project-wide decisions already made; don't relitigate them per-file:

1. **One Python module per Pascal unit.** Module names mirror the `.PAS` filename (`UPDATE.PAS` → `update.py`, `NPE01.PAS` → `npe/pirate.py`). This keeps side-by-side diffing against the original viable, which is the main correctness tool available.
2. **1-based indexing is preserved.** Pascal `ARRAY [1..200]` becomes a list of 201 elements with index 0 unused/`None`. This is deliberate — it prevents off-by-one drift when translating index arithmetic verbatim.
3. **Pascal field names are kept** on ported records (`Emp`, `Cls`, `Typ`, `Eff`, `RevIndex`, `TriReserve`), while new Python-level functions use snake_case. Ported enum members also keep Pascal spelling (`fgt`, `hkr`, `ssp`, `amb`, `tri`).
4. **Global `VAR` state collapses into a `GameEnvironment` class** (`environ.py`) that is threaded through functions as a parameter, replacing the Pascal globals `Year`, `Player`, `Universe`, `Galaxy`.
5. **Pascal's overlay directives (`{$O ...}` in ANACREON.PAS) are ignored** — they were a DOS memory-management artifact. Use regular imports.
6. **Enums are `IntEnum` with explicit 0-based values** matching Pascal `Ord()`. Other code depends on the ordinals (`NoSRMField = Ord(Indep) * 16`), so members must never be renumbered or reordered.
7. **`TechnologyTypes` is one enum, not several.** The original declares a single enum and carves overlapping subranges out of it (`ShipTypes = fgt..trn`, `CargoTypes = men..tri`, ...), then indexes tables across those subranges — `CombatTable` spans defenses, ships and troops at once. Splitting it would break the tables. Subranges are exported from `types.py` as tuples (`SHIP_TYPES`, `CARGO_TYPES`, ...), with same-name aliases kept for readability at use sites.
8. **Pascal arrays indexed by an enum become dicts keyed by that enum**, built via `datacnst._table`, which raises at import time on a row/key-count mismatch. Use it for every new table — it is the only automatic check on a bulk transcription.

9. **Turbo Pascal builtins that differ from Python's go through `utils/pascal.py`.** `Round` is the live trap: Pascal breaks ties away from zero, Python's `round` is banker's rounding, so `Round(2.5)` is 3 and `round(2.5)` is 2. Call `pascal_round` for every `Round` in the original, `trunc` for every `Trunc`, and `pascal_val` for every `Val` whose failure is meant to be caught (Python's `int` accepts surrounding whitespace, `_` separators and a unicode minus; Pascal's `Val` errors on all three).

10. **Two DATACNST tables have no source in `original/`.** `CargoSpace` and `ObjName` are referenced by the Pascal but declared in no file in the tree. Their values in `datacnst.py` therefore cannot be checked against anything — treat them as the one place where "transcribed exactly" is a claim the repo cannot back up, and do not silently "correct" them either.

> The code sketches in `docs/IMPLEMENTATION_PLAN.md` §1.3–1.4 are approximations written before the port and disagree with the Pascal in several places (empire numbering, `ObjectTypes` order, enum member names). Where they conflict with `original/`, the Pascal wins.

## Coordinates

Sector coordinates are effectively 1-based: the grid is allocated `0..size` inclusive, but `in_galaxy` requires `x > 0 and y > 0`, so row and column 0 exist without being playable. `Limbo` is (0, 0) — where objects sit when they are nowhere. `Galaxy.sector()` raises on out-of-range input rather than following the Pascal, because Python's negative indexing would silently wrap to the opposite edge of the galaxy.

Distance is **Chebyshev**, not Euclidean or Manhattan (`misc.distance`) — diagonal movement costs the same as orthogonal. Fleet movement follows from that: `fleet.get_new_pos` steps both axes at once.

Player-facing coordinates are **relative to the active player's capital**, which reads as `0,0`. The two axes do not convert the same way: `absolute_x` adds the capital's X, but `absolute_y` *subtracts* from the capital's Y, because +Y is north for the player while grid row 1 is at the top. `relative_x`/`relative_y` invert the same pair. Getting this symmetric silently mirrors every typed destination about the capital.

## Pascal subranges in loops

`FOR X := A TO B` iterates **ordinals**, so a loop that reads like a semantic grouping may sweep in members between the endpoints. `FOR IndI := CheInd TO TriInd` looks like the three raw-material industries but is ordinals 1..8 — it also covers the four shipyards and `SupInd`. That one matters: `SupInd` producing supplies inside `produce_raw_material` is the only thing that feeds a world, and narrowing the loop starves the entire galaxy while every unit test still passes.

Use `types.indus_range` / `types.tech_range` rather than writing members out by hand, and check the endpoints' ordinals before assuming what a range contains.

## Working with the Pascal source

Highest-value reference files in `original/`:

- `TYPES.PAS`, `NPETYPES.PAS`, `CDETYPES.PAS` — every enum and ordinal type
- `DATASTRC.PAS` — the record definitions (Planet, Fleet, Starbase, Stargate, Constr, Empire, Universe)
- `DATACNST.PAS` — balance tables that must be transcribed exactly: 14×14 `CombatTable`, 11×11 `CombatTechAdj`, `ThgAdj`, `RawM`, `ClassIndAdj`, `FuelCons`, `CargoSpace`
- `UPDATE.PAS` — the annual universe tick; planet update is a fixed 13-step sequence whose order matters
- `ATTACK.PAS` — combat across 5 orbital shells (DpSpc → HiOrb → Orbit → SbOrb → Grnd), resolved outermost first
- `PRIMINTR.PAS` (~1700 lines) — low-level entity accessors; nearly everything else calls into it
- `original/changelog.txt` — describes v2.0 behavior changes (disrupters, SRM sweep orders, terraforming) that are live in this source and must be ported, not treated as legacy

`FASTSCR.ASM`/`.OBJ` are x86 direct-video-memory routines and `ANACREON.OVR` is a compiled overlay — neither has a Python equivalent; Textual replaces them.

Numeric constants and balance tables should be transcribed, never re-derived or "improved" — deviation there silently changes game balance, and `docs/IMPLEMENTATION_PLAN.md` Phase 9 exists to validate outputs against the Pascal originals.
