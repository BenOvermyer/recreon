# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Re:creon is a Python recreation of **Anacreon: Reconstruction 4021** (v2.0, Jan 2004), a turn-based 4X space strategy game originally written in Turbo Pascal 4.0. The complete original Pascal source (~39k lines, 85 units) lives in `original/` and is the **authoritative specification** — the Python port is intended to be behavior-faithful, not a reimagining.

**Current state: Phase 1 complete** — the type and data layer only. Ported: `types.py` (TYPES.PAS), `datastrc.py` (DATASTRC.PAS), `datacnst.py` (DATACNST.PAS), `cdetypes.py` (CDETYPES.PAS), `npe/types.py` (NPETYPES.PAS), and the type declarations from `galaxy.py` (GALAXY.PAS — its sector runtime is Phase 2). There is no game loop, galaxy generation, AI, or UI yet. Phase 2 in `docs/IMPLEMENTATION_PLAN.md` is next.

Modules for later phases are not stubbed out — an absent file means unported. `docs/ARCHITECTURE.md` is the map of what each one will be.

## Commands

```bash
uv sync                                     # install deps
uv run pytest                               # full suite
uv run pytest tests/test_datacnst.py -q     # one file
uv run pytest -k combat_table               # one test by name
uv run recreon                              # entry point (src/recreon/main.py)
```

Python 3.12, Textual for the TUI, pytest for tests. No linter or type checker is configured yet.

## Documentation map

Read these before writing code; they carry the full design and are more specific than this file:

- `docs/ARCHITECTURE.md` — target module layout under `src/recreon/`, with the Pascal unit each Python module ports, plus dependency graph and per-module function lists.
- `docs/IMPLEMENTATION_PLAN.md` — 9 phases with milestones and code sketches. Phases are ordered by dependency: data structures → galaxy/game loop → economy → fleets → combat → construction → AI → UI → validation.
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

> The code sketches in `docs/IMPLEMENTATION_PLAN.md` §1.3–1.4 are approximations written before the port and disagree with the Pascal in several places (empire numbering, `ObjectTypes` order, enum member names). Where they conflict with `original/`, the Pascal wins.

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
