# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Re:creon is a Python recreation of **Anacreon: Reconstruction 4021** (v2.0, Jan 2004), a turn-based 4X space strategy game originally written in Turbo Pascal. The complete original Pascal source (~39k lines, 85 units) lives in `original/` and is the **authoritative specification** — the Python port is intended to be behavior-faithful, not a reimagining.

**Turbo Pascal 5.0 or later, not 4.0** as this file long claimed. `ANACREON.PAS` uses `{$O}` overlay directives and `ANACREON.OVR` carries a `TPOV` signature; the overlay manager did not exist before TP 5.0. This is not pedantry — it dates the build into the range where Borland's `Random` uses the `$08088405` LCG that `utils/pascal.py` reproduces.

**Current state: Phases 1–6 complete except the combat UI (§5.3, ATTCOMM.PAS); Phase 7 (AI) complete; Phase 8 under way.** Ported: `types.py` (TYPES.PAS), `datastrc.py` (DATASTRC.PAS), `datacnst.py` (DATACNST.PAS), `cdetypes.py` (CDETYPES.PAS), `npe/types.py` (NPETYPES.PAS), `galaxy.py` (GALAXY.PAS), `environ.py` (ENVIRON.PAS + `InitializeUniverse` from LOADSAVE.PAS), `misc.py` (MISC.PAS), `primintr.py` and `intrface.py` (PRIMINTR/INTRFACE.PAS — the subsets used so far, now including the whole name subsystem), `news.py` (NEWS.PAS), `update.py` (UPDATE.PAS world update), `design.py` (DESIGN.PAS designation + INTRFACE's `DesignateWorld`/`TerraformWorld`), `resource.py` (RESOURCE.PAS), `newgame.py` (NEWGAME.PAS), `orders.py` (ORDERS.PAS), `fleet.py` (FLEET.PAS), `attack.py` (ATTACK.PAS), `attnpe.py` (ATTNPE.PAS), `battle.py` (BATTLE.PAS), `sbase.py` (SBASE.PAS), `mess.py` (MESS.PAS), `loadsave.py` (LOADSAVE.PAS), `npe/` (NPE.PAS, NPEINTR.PAS, NPE00.PAS, NPE01–NPE04.PAS), `utils/` (INT.PAS, REAL1.PAS, DFA.PAS), the turn loop in `main.py`, and `ui/`.

Phase 8 so far: the scouting sweep, the map buffer, `GetNewsLine`, save/load (§8.4) with the message subsystem it depends on, the scenario front end (§8.5), the prologue menu (PROLOG.PAS), all four world/fleet command units (CONSTR, MSCCOMM, FLTCOMM, CLSCOMM), and the in-game menu bar. **FLTCOMM also closed Phase 4's §4.3.** What remains is **ATTCOMM (§5.3, the interactive combat UI)** — the last unported unit of consequence — plus the handful of commands listed in `ui/menu.py`'s `PENDING` that have no screen yet.

**The seven menus are PLAYTURN.PAS, not MENU.PAS.** MENU.PAS is the scrolling-list *widget* and PULLDOWN.PAS the menu-bar widget; Textual's `ListView` replaces both, so neither is ported. `InitializeMainMenu` (PLAYTURN.PAS:1262) is where the menus are actually defined, and `playturn.py` transcribes them — titles, order and accelerator letters, which are not always the first letter ("caNcel orders" is N, "auTo attack" is T).

**PLAYTURN.PAS is only half ported.** The command enum and the menus are done; the **typed-command parser** (`GetCommand`, so a player can type `LAUNCH` or `DES`) and the **parameter table** (`ParameterTypes` + `SetOfErrors` per command, validated by `GetParameters`) are not. Each ported screen collects its own parameters instead, which is why they work without it — but that table is the original's single statement of what every command requires, and is worth transcribing when the last commands land.

**The production screen is a projection, and it lies.** `CLSCOMM.PAS`'s `GetProdInfo` re-derives UPDATE.PAS's production formula rather than calling it, and the two copies have drifted (#62): the forecast ignores an exhausted trillum reserve, omits the floor-at-1 on raw materials, and clamps cargo with `IntLmt` (±32767) where production uses `ThgLmt` (0..9999). All three make it optimistic. Reproduced exactly — it is what a player saw — so **do not "correct" `clscomm.production_forecast` against `update.py`**.

**Command screens are bound directly to keys until MENU.PAS lands**: `f` fleets, `b` construction, `w` warp links, `d` defenses, `x` self-destruct, `z` close-up, `i` production, `g` the prologue menu. The close-up and production screens act on whatever the map cursor is over, which is how the original reaches them too.

**A fleet must be scouted to appear in its own empire's menus.** `GetGround` filters on `Scouted(Player, Flt2)` with no exemption for your own fleets. In practice yours always are — `set_up_turn` runs `scout_fleets` before the player acts — but a fleet created outside a turn (a test helper, say) is invisible to the transfer, abort and refuel menus until something scouts it.

**MSCCOMM.PAS is mostly dead code.** It declares five commands, but `HolocaustCommand`, `ArtifactCommand` and `TransactionCommand` all sit inside the `(* … *)` block spanning lines 533–655 and are unreachable in v2.0. That block is why `attack.holocaust_world` has no caller and why `cdetypes.py` has none either. The live half is `DefenseCommand` and `SelfDestructCommand`, and it is ported.

**The defense grid is the one screen that shapes every future battle.** `msccomm.normalize_defenses` forces each ship type's five shells to total 100, and **sub-orbit is the fallback all three of its steps use**: ground percentages for ships that cannot land move there, a shortfall goes there, and the remainder lost to `Trunc` when scaling a surplus goes there too. So an even 100/100/100 comes out 33/33/33 with the spare 1 in sub-orbit, not spread. Typing a percentage outside 0..100 stores **0**, not the nearest bound.

**The game is playable end to end from the UI.** `recreon` opens on the prologue (`ui/prologue.py`), which is where ANACREON.PAS starts: new game, load, save, quit, and the settings that live outside a game. "New game" pushes the scenario picker (`ui/newgame.py`) — choose a scenario, page the introduction, pick a player count, name the empires. `--scenario` skips straight to the map. Turns autosave after each one, as ANACREON.PAS does.

**PROLOG.PAS's two flags are `PrologueState`, not `GameEnvironment` state.** `GameLoaded` gates almost every command ("You must Load a game first"); `GameModified` is what makes quitting or loading stop to ask. They are unit-level typed constants in the original — globals scoped to exactly the prologue — so they stay scoped that way here.

**The AI runs.** `update_turn` calls `npe.dispatch.implement_npe` for every non-player empire, at the point ANACREON.PAS:240-251 does. All four personas are ported: pirate (NPE01), kingdom (NPE02, both variants), guardian (NPE03), berserker (NPE04), over the NPEINTR primitives and the NPE00 shared layer. `newgame` calls `initialize_npe` where the original does, so a persona's character is rolled from the generator at scenario load.

**Fog of war is three-valued, and recomputed from scratch every turn.** `main.set_up_turn` (ANACREON.PAS `SetUpTurn`) runs for humans and NPEs alike: `clear_scout_set` drops everything the empire *observed*, then `scout_fleets` and `scout_objects` rebuild it from where its worlds and fleets actually are, and `update_probes` lands whatever was in flight. `KnownBy` persists across the clear; `ScoutedBy` does not — so an empire that pulls back genuinely loses sight of what it was watching.

The three levels are **unknown** (no idea it exists), **known** (something is there) and **scouted** (you can see what it is made of). The map keys on **`KnownBy`**; `ScoutedBy` gates the detail panels, not the glyph. An HK fleet next to your world is neither — that exemption is what makes hunter-killer raids work. The only way to discover something you had no idea existed is a starbase scan, and that is a coin flip per object per turn, so a new base maps its surroundings over several years.

Ten original bugs are now filed against the AI (#23–#30, #33–#35, #37–#40). Four matter most before anyone tunes balance: **#40** (a softened target is judged by its casualty list, so the AI commits to assaults it should decline), **#34** (a world with no ships can never be reinforced), **#23** and **#28**. **#35** is a hang rather than a wrong number and is the strongest candidate for an early exception to the port-stays-faithful rule.

**News is stored as (headline, location, three parms) and rendered late.** `news.py` files items; `intrface.get_news_line` turns one into prose at display time, substituting `*` for the location and `@` for the empire in `Parm1`. So a headline's parameters are only meaningful against its template — `Parm1` is an empire ordinal for most combat headlines but a *material* for `IndLack` and a death toll (in hundreds of millions) for `Starv`. Check the template before assuming what a parm means.

**Save files are JSON and are not the original's format.** LOADSAVE.PAS writes records with `BlockWrite` straight out of memory, which only works because a Turbo Pascal record has a fixed layout. Nothing in Python does, and `original/` ships no `.SAV` or `.BAK` to be compatible with, so `loadsave.py` defines its own format with its own signature and its own version line starting at 1. **A save from the DOS build cannot be loaded, and the original's version shims — `SFVersion > 13` for `TerraformTarget`, `> 14` for a stargate's `WLF`, `< 12` for the old NPE `FleetData` — are unportable rather than unported**, since each reinterprets a byte layout that has no counterpart. Don't "add" them.

What *is* ported is the structure: sections in the original's order, the per-empire sets rebuilt from the records rather than saved (so a save cannot disagree with itself about who owns what), `NoOfPlanets` recounted on load, `LoadFleets`' repair of a fleet saved at Limbo, and both version warnings. The bar the format is held to is `tests/test_loadsave.py`: re-saving a loaded game is byte-identical, and a loaded game plays on through sixty further turns to the same state as one that never left memory.

The codec is `utils/serial.py`, which walks *annotations* rather than values so an `IntEnum` comes back as that enum and a `set[Empire]` as a set of `Empire` — a save that round-tripped `Empire.Empire3` as a bare `2` would look right in a diff and fail at the first enum-keyed `dict` lookup. It refuses ambiguous unions instead of inventing a discriminator; the one such field, `NPEDataRecord.Data`, is dispatched on the `Typ` beside it exactly as NPE.PAS's `LoadNPE` does.

**`DoNotSaveGame` clears the modified flag; it does not touch autosave.** PROLOG.PAS:392 is the whole body — `GameModified := False` — and ANACREON.PAS:411 calls it when the last player has been destroyed, so the prologue does not offer to save a finished game on the way out. The autosave is separate and keys on `AutoSave`; it is skipped on that path only because `AutoBackup` sits in the other branch of the `IF`. `main.play` gets the behaviour right and this file previously got the reason wrong — it claimed the procedure was declared nowhere, which was the grep problem below.

**CONSTR.PAS is all UI, and is now ported.** Despite the name it holds only interactive command handlers — `ConstructCommand`, `AbortConstructionCommand`, `ConstrStatusCommand`, `WarpLinkFrequencyCommand`. Construction's mechanics live in `intrface.py` (`construction`, `destroy_construction`, `next_constr_slot`) and `update.py` (`update_construction`). `constr.py` is therefore a Phase 8 file, not a Phase 6 one, and `tests/test_constr.py` tests the *mechanics* while `tests/test_constr_commands.py` tests the commands.

**`my_lord` draws from the generator.** `MyLord` picks how the staff address the ruler with `Rnd(1,4)` for an empress and `Rnd(1,6)` for an emperor — so the one piece of pure presentation in the game moves the LCG, and the command handlers call it constantly. Ported with the draws intact, but it means the port's stream can only match the original's if the UI makes the same calls in the same order, which it cannot. One more reason a DOS-era galaxy is not reproducible here.

A scenario file loads into a populated galaxy — worlds, empires with capitals, nebulae, minefields — and worlds run a full economy: production, industry growth, population, famine, ambrosia addiction, tech drift, revolution and rebellion. Fleets deploy, carry cargo, burn fuel, move through gates, fortresses, minefields, disrupters and nebulae, and run compiled standing orders. Combat resolves end to end through `attnpe.npe_attack`: groups fight across five shells, worlds and empires fall, and conquest, morale and news all settle. Command bases and fortresses crawl toward their destinations under `sbase.move_player_starbases`. Non-player empires take their turns: they read the news, escalate policy, launch raiders and battle fleets, garrison and expand. What remains of Phases 4–7 is all UI: the fleet TUI (§4.3), the combat TUI (§5.3, ATTCOMM.PAS) and the construction commands (CONSTR.PAS). Phase 8 (the menus, save/load and the scenario front end) is next.

**Combat's entry point is `attnpe.npe_attack`, not anything in `attack.py`.** ATTACK.PAS holds only the mechanics — one round at one shell, plus the routines that apply an outcome. ATTNPE.PAS is the loop: retreat check, targeting, `group_engage` over all five shells, repeat. Despite the name it consults no AI persona, so it resolves a player's attack too; ATTCOMM.PAS is the interactive variant where the player picks targets each round, and is unported.

**Two ATTACK.PAS routines are unreachable in v2.0.** `HolocaustWorld` and `HolocaustEffectiveness` are called only from `HolocaustCommand` in MSCCOMM.PAS, which sits inside the `(* … *)` block spanning lines 533–655 — dead code, like the CDE subsystem. They are ported anyway (they are part of the unit's interface) and carry two original bugs kept deliberately: `EnemyRev` is applied uninitialised on the surrender path, and `RevertTechnology` is handed `Deaths` where an `Index` (0..100) is expected, so any sizeable world always reverts to pre-tech. `WorldSurrenders` leans on `Random(1)` always being 0, which makes every world in the PreWrp..StrTch band capitulate.

**`SetOfPlanetsOf` and its siblings are maintained by `set_status`, and this file used to claim otherwise.** The earlier note here said the original rebuilt the per-empire sets only at load and at `CreatePlanet`, never on `SetStatus`, and that `conquer_empire` therefore read a stale set. That was wrong: PRIMINTR.PAS:724-750 moves the index out of the old owner's set and into the new one on every `SetStatus`, for planets, starbases *and* construction sites alike. The port had simply dropped that half of the procedure — a transcription slip, not a faithful reproduction.

It mattered more than it looks. Worlds are created independent and assigned owners afterwards, so **every empire read as owning nothing from the moment a scenario finished loading**. Nothing noticed until the AI was wired up, because almost the only code that sweeps `SetOfPlanetsOf` is the AI; with it fixed, `INTRO.SCN` goes from a static galaxy to one where an NPE grows from 1 world to 25 over 200 turns. If a sweep over an empire's holdings ever comes back empty when it should not, check this first.

**Pascal's `DIV` truncates toward zero; Python's `//` floors.** They agree on non-negative operands, which covers most `DIV` in the original, but not all — `battle.calc_attack_round` jitters a dividend negative. Use `utils.pascal.pascal_div` wherever the dividend can go below zero.

**Fleets do not all move at the same moment in the turn rotation.** `update_all_fleets(player, next_player)` moves warp fleets and anything sitting on a gate for the *incoming* empire, and jump/HK fleets for the *outgoing* one, so a jump ordered this turn lands this turn. It is called from `main.update_turn`, not from `update_universe` — fleet movement is per-turn, world updates are per-year. `sbase.move_player_starbases` rides alongside it on the same incoming empire.

**Bases path differently from fleets, and can end up outside the galaxy.** A base cannot enter an occupied sector at all, so `sbase.get_new_base_pos` sidesteps when the direct step is blocked — and the sidestep is the one move in the game that travels *across* a bearing rather than along it, so unlike every fleet step it can leave the playable grid. The original bounds-checks it nowhere; a base hugging an edge really can be pushed into row or column 0. Ported faithfully (#20), so do not assume `get_coord` on a starbase satisfies `in_galaxy`.

**Galaxies come from scenario files.** `newgame.py` (NEWGAME.PAS) is a **scenario-file interpreter, not a procedural generator** — there is no code path that builds a galaxy without a `.scn`.

**The front end is something loading calls into, not a wrapper around it.** The original asks for the player count and the empire names *between* the header and the first directive, in the same forward pass over the open file, so a front end that ran first would have to parse twice. `ScenarioFrontEnd` is that hook; `load_scenario` calls `introduction`, `no_of_players` and `empire_identity` at the points `ScenarioIntroduction` and `InputEmpireName` run. The Textual screens cannot answer from inside a blocking parse, so they read the header and intro up front via `read_scenario_intro` and hand the answers back — **safe only because neither the header nor the introduction draws from the generator**; `run` is what seeds it. Don't move a draw earlier than `run`.

**`RndEmpireName` is the original's 59 names, and the draw rejects rather than filters.** `GetRandomEmpireName` rolls `Rnd(1, 59)` and re-rolls when the name is taken. Drawing once from a pre-filtered list would call `Rnd` with a smaller bound *and* make exactly one call, so both the value and the number of draws diverge the moment two empires collide — and every draw after it in the scenario shifts. The table's order and its count of 59 are therefore both load-bearing. Both this and the table itself were wrong until the grep problem was found: 16 invented names stood in `newgame.py` under a comment saying the real table "is not in the source".

**`CreatePlayerEmpire` makes no random draw; `CreateNPEmpire` does.** A player's sex comes from `InputEmpireName`, so the original calls `Rnd(0,1)` only for NPEs. The port used to roll for both, consuming an LCG step the original never consumes.

**The original `*.SCN` files are in `original/scenarios/`** — 13 of them, all declaring format version 10. This reverses the earlier premise that they were permanently unavailable, and they are now the authority on the format: where a real scenario disagrees with what the parser seemed to want, the file wins. `data/scenarios/frontier.scn` is still authored content rather than a port (it declares version 16 and reproduces no galaxy the original shipped), and is still the default the game boots.

**11 of the 13 load. The other two are defective as shipped**, and would have failed in the DOS build too:

- `AWAKEN.SCN` asks for 212 worlds (36 explicit plus 176 random) against `MaxNoOfPlanets = 200`. The original has no bounds check here and would have written past the planet array; the port reports `Too many worlds created` instead.
- `PRINCES.SCN` has a stray `0 ; (reserved)` token in its one `CreateStarbase` block. Every other scenario's starbase block has six fields after the coordinate; this one has seven, so the block runs long and its trailing cargo amount is read as the next directive.

Neither is a parser bug — don't "fix" the parser to accept them, and don't edit the shipped files.

**A third, `GAUNTLET.SCN`, loads about 92% of the time and genuinely fails the rest.** It packs 172 worlds into small zones, and `GetRandomXY` gives up after 101 tries rather than looping — so an unlucky roll reports `No room for random world in zone`. This is faithful; the DOS build failed on the same rolls. Because every shipped scenario carries `Seed 0`, **a test cannot pin its way out of this**: `ScenarioLoader.run` calls `randomize()` itself and discards any seed set beforehand. `test_shipped_scenarios_load` retries three times for that reason; don't "simplify" it back to a single attempt, and treat a red GAUNTLET as a roll rather than a regression.

**Galaxy generation runs on Turbo Pascal's own RNG** (`utils/pascal.py`), not Python's: seed update `s = s*134775813 + 1 mod 2^32`, and `Random(N)` is the top 32 bits of `s * N`, *not* `s mod N`. Every draw in the game funnels through `int_utils.rnd`, so this governs combat and the economy as well as generation. Verified against the published Borland Pascal 7 sequence in `tests/test_pascal.py`.

Note what this does *not* buy: **all 13 shipped scenarios carry `Seed 0`**, meaning `Randomize`. The galaxies players saw in 2004 were rolled fresh on every new game and never existed twice, so there is nothing there to reproduce. What the LCG gives is that our own seeded scenarios draw the sequence the original would have drawn, and that quirks call sites depend on — `Random(1)` is always 0, which `ATTACK.PAS` relies on — behave correctly.

`cdetypes.py` has no caller because the artifact and transaction directives are commented out of the scenario dispatch in v2.0, making that whole subsystem unreachable dead code in the original.

**Loading is one forward pass, and the introduction is part of it.** Between the header and the first directive, `read_introduction` discards every token until `BEGINTEXT` and then reads lines until `ENDTEXT` (`NEWPAGE` splits pages, both matched as substrings of a line rather than as tokens). Scenarios rely on the discard: `Nebula.SCN` keeps a column ruler there. A scenario without a `BEGINTEXT` block fails to load.

The scenario header keeps its version at **fixed columns 10–11** of line 1, and the parser rejects anything else rather than parsing loosely: Python's `int()` strips whitespace where Pascal's `Val` errors, so a header off by one column would otherwise read as some low version, silently enable the old-format shims, and desync every directive after it.

`place_world` lives in `tests/conftest.py`, not in the package — unit tests want one world with known attributes; nothing in `src/` fabricates worlds.

Modules for later phases are not stubbed out — an absent file means unported. `docs/ARCHITECTURE.md` is the map of what each one will be.

## Original bugs get filed, not just commented

**Every defect found in the original Pascal gets a Worktree issue on `ben.overmyer/recreon`, labelled `original-bug`** — in addition to being documented at the call site and reproduced faithfully. File it when you find it, not in a batch at the end.

The port stays faithful; the issue records the problem for the post-port improvement phase, when the goal shifts from reproducing the game to improving it. An issue should say what the original does, why it is wrong, what the port does now, and what fixing it would change about gameplay. Where a defect might be deliberate balance rather than a mistake — the fortress catapult in #16 is the type case — say so and leave the judgement open rather than asserting it is a bug.

Forty are catalogued so far (#7–#10, #12–#18, #20–#21, #23–#30, #33–#35, #37–#40, #46–#50, #54–#55, #59–#60, #62). #54 and #55 came out of PROLOG.PAS; #59 and #60 out of FLTCOMM.PAS — editing a fleet's orders can leave its resume point past the end of the list (a crash in the port, so clamped), and mine sweeping costs 100 starships as a compiled order but nothing as an interactive command. #62 is the production screen's forecast disagreeing with what a world actually produces. #46–#50 came out of LOADSAVE.PAS and MESS.PAS: a `LoadGame` that never cleans up the universe it is replacing, and four in the message subsystem. #11 was withdrawn — it described a porting slip in `set_status`, not an original defect. Read them before "fixing" anything that looks broken in a ported module: it is probably already known and deliberate.

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

9. **Turbo Pascal builtins that differ from Python's go through `utils/pascal.py`.** `Round` is the live trap: Pascal breaks ties away from zero, Python's `round` is banker's rounding, so `Round(2.5)` is 3 and `round(2.5)` is 2. Call `pascal_round` for every `Round` in the original, `trunc` for every `Trunc`, `pascal_val` for every `Val` whose failure is meant to be caught (Python's `int` accepts surrounding whitespace, `_` separators and a unicode minus; Pascal's `Val` errors on all three), and `pascal_random` / `pascal_random_real` / `set_rand_seed` for `Random` and `RandSeed`. **Never call Python's `random` module** — a draw that bypasses the ported LCG desynchronises every draw after it. Tests that need determinism call `set_rand_seed`, not `random.seed`.

10. **Where an integer's *width* changes the answer, model the wrap.** Python ints are unbounded; Pascal's are not, and the build has range checking off, so `Word` and `Index` (0..100, stored as a byte) wrap silently. Most arithmetic never gets near a boundary and needs nothing. But when a value can underflow past zero or overflow its type, the wrapped result is the behaviour players saw, and a Python int gives a *different* bug rather than no bug — a negative troop load instead of a full one (#29), a clamped aggression score instead of a stuck one (#27). Both cases go through small local helpers (`npe/core.py`'s `_word`, `_index_dec`) with the reasoning at the call site. Check the Pascal `VAR` block for the declared type before assuming a subtraction is safe.

11. **Every DATACNST table is verified against the Pascal, automatically.** `tests/test_datacnst_source.py` parses `original/DATACNST.PAS` and compares all 30 numeric tables and 12 string/char tables against `datacnst.py`. They all match. Add a table there when you add one here — it is the only automatic check on a bulk transcription that a reviewer cannot eyeball.

    This file long claimed the opposite: that `CargoSpace`, `ObjName` and `MPower` were "declared in no file in the tree" and were "the one place where 'transcribed exactly' is a claim the repo cannot back up". **That was wrong.** All three are in DATACNST.PAS — `ObjName` at :162, `MPower` at :198, `CargoSpace` at :415 — and all three transcribe correctly. See the grep warning under "Working with the Pascal source" for why they looked absent.

> The code sketches in `docs/IMPLEMENTATION_PLAN.md` §1.3–1.4 are approximations written before the port and disagree with the Pascal in several places (empire numbering, `ObjectTypes` order, enum member names). Where they conflict with `original/`, the Pascal wins.

## Coordinates

Sector coordinates are effectively 1-based: the grid is allocated `0..size` inclusive, but `in_galaxy` requires `x > 0 and y > 0`, so row and column 0 exist without being playable. `Limbo` is (0, 0) — where objects sit when they are nowhere. `Galaxy.sector()` raises on out-of-range input rather than following the Pascal, because Python's negative indexing would silently wrap to the opposite edge of the galaxy.

Distance is **Chebyshev**, not Euclidean or Manhattan (`misc.distance`) — diagonal movement costs the same as orthogonal. Fleet movement follows from that: `fleet.get_new_pos` steps both axes at once.

Player-facing coordinates are **relative to the active player's capital**, which reads as `0,0`. The two axes do not convert the same way: `absolute_x` adds the capital's X, but `absolute_y` *subtracts* from the capital's Y, because +Y is north for the player while grid row 1 is at the top. `relative_x`/`relative_y` invert the same pair. Getting this symmetric silently mirrors every typed destination about the capital.

## Pascal subranges in loops

`FOR X := A TO B` iterates **ordinals**, so a loop that reads like a semantic grouping may sweep in members between the endpoints. `FOR IndI := CheInd TO TriInd` looks like the three raw-material industries but is ordinals 1..8 — it also covers the four shipyards and `SupInd`. That one matters: `SupInd` producing supplies inside `produce_raw_material` is the only thing that feeds a world, and narrowing the loop starves the entire galaxy while every unit test still passes.

Use `types.indus_range` / `types.tech_range` rather than writing members out by hand, and check the endpoints' ordinals before assuming what a range contains.

## Working with the Pascal source

**Ten files in `original/` contain high-bit bytes and `grep` treats them as binary.** They are ATTCOMM.PAS, DATACNST.PAS, EIO.PAS, MAPWIND.PAS, MENU.PAS, PLAYTURN.PAS, PROLOG.PAS, PULLDOWN.PAS, TMA.PAS and WND.PAS — UI code carrying CP437 box-drawing glyphs, plus DATACNST.PAS for `BaseTypeData`/`GateTypeData`.

`grep -I` skips them **silently**, and `grep -r` prints `Binary file … matches` instead of the line. So a plain search over `original/` will tell you an identifier appears nowhere when it is sitting in one of these files. **Always pass `-a`** (`grep -rna 'Ident' original/`), and be suspicious of any conclusion of the form "declared nowhere" that predates this note.

This has already produced two false claims in this file, both now corrected: that three DATACNST tables had no source (they do, and they transcribe correctly), and that `DoNotSaveGame` was declared nowhere (it is PROLOG.PAS:39/392). If you find another claim of that shape, re-check it with `-a` before building on it.

Highest-value reference files in `original/`:

- `TYPES.PAS`, `NPETYPES.PAS`, `CDETYPES.PAS` — every enum and ordinal type
- `DATASTRC.PAS` — the record definitions (Planet, Fleet, Starbase, Stargate, Constr, Empire, Universe)
- `DATACNST.PAS` — balance tables that must be transcribed exactly: 14×14 `CombatTable`, `ThgAdj`, `RawM`, `ClassIndAdj`, `FuelCons`, `CargoSpace`. **`CombatTechAdj` is not among them** despite this file long claiming otherwise — it, `CombatClassAdj`, `CombatBaseAdj`, `CombatPower`, `GDMLaunch` and `GDMKill` are all declared inside ATTACK.PAS, and live in `attack.py`.
- `UPDATE.PAS` — the annual universe tick; planet update is a fixed 13-step sequence whose order matters
- `ATTACK.PAS` — combat across 5 orbital shells (DpSpc → HiOrb → Orbit → SbOrb → Grnd), resolved outermost first
- `PRIMINTR.PAS` (~1700 lines) — low-level entity accessors; nearly everything else calls into it
- `original/changelog.txt` — describes v2.0 behavior changes (disrupters, SRM sweep orders, terraforming) that are live in this source and must be ported, not treated as legacy

`FASTSCR.ASM`/`.OBJ` are x86 direct-video-memory routines and `ANACREON.OVR` is a compiled overlay — neither has a Python equivalent; Textual replaces them.

Numeric constants and balance tables should be transcribed, never re-derived or "improved" — deviation there silently changes game balance, and `docs/IMPLEMENTATION_PLAN.md` Phase 9 exists to validate outputs against the Pascal originals.
