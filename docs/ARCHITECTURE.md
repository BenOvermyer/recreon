# Architecture

## Module Structure

```
src/recreon/
├── main.py              # Entry point - game loop (ANACREON.PAS)
├── types.py             # All enums and type definitions (TYPES.PAS)
├── datastrc.py          # Universe, Planet, Fleet, Empire records (DATASTRC.PAS)
├── datacnst.py          # Game balance constants, combat tables (DATACNST.PAS)
├── galaxy.py            # Sector grid, coordinates (GALAXY.PAS)
├── environ.py           # Global game state (ENVIRON.PAS)
├── primintr.py          # Low-level entity property access (PRIMINTR.PAS)
├── intrface.py          # High-level operations (INTRFACE.PAS)
├── misc.py              # Utility functions (MISC.PAS)
├── update.py            # Universe update logic (UPDATE.PAS)
├── fleet.py             # Fleet movement and management (FLEET.PAS)
├── attack.py            # Combat mechanics (ATTACK.PAS)
├── attnpe.py            # Automatic battle driver (ATTNPE.PAS)
├── battle.py            # Simplified combat, unused in v2.0 (BATTLE.PAS)
├── design.py            # World designation, ISSP (DESIGN.PAS)
├── resource.py          # Cargo, production (RESOURCE.PAS)
├── constr.py            # Construction commands, UI only (CONSTR.PAS)
├── sbase.py             # Starbase movement, self-destruct (SBASE.PAS)
├── orders.py            # Fleet order scripting (ORDERS.PAS)
├── npe/                 # AI system (NPE*.PAS)
│   ├── __init__.py
│   ├── types.py         # AI type definitions (NPETYPES.PAS)
│   ├── core.py          # Shared AI primitives (NPEINTR.PAS)
│   ├── dispatch.py      # AI dispatcher (NPE.PAS)
│   ├── common.py        # Shared persona behaviour (NPE00.PAS)
│   ├── pirate.py        # Pirate AI (NPE01.PAS)
│   ├── kingdom.py       # Kingdom AI (NPE02.PAS)
│   ├── guardian.py      # Guardian AI (NPE03.PAS)
│   └── berserker.py     # Berserker AI (NPE04.PAS)
├── ui/                  # Textual UI layer
│   ├── __init__.py
│   ├── app.py           # Main Textual application
│   ├── map_view.py      # Galaxy map (MAPWIND.PAS)
│   ├── menus.py         # Menu system (MENU.PAS, PULLDOWN.PAS)
│   ├── status.py        # Status windows (STAWIND.PAS, FLTWIND.PAS, EMPWIND.PAS)
│   ├── command.py       # Command input (DISPLAY.PAS)
│   └── widgets/         # Custom Textual widgets
├── utils/               # Utility modules
│   ├── __init__.py
│   ├── strg.py          # String utilities (STRG.PAS)
│   ├── int_utils.py     # Integer utilities (INT.PAS)
│   └── sort.py          # Sorting algorithms (SORT.PAS, QSORT.PAS)
└── data/                # Game data files
    ├── names.txt        # Empire/world names
    └── scenarios/       # Scenario files
```

## Core Data Layer

### types.py
All type definitions, enums, and constants from TYPES.PAS, NPETYPES.PAS, CDETYPES.PAS.

**Key types:**
- `Empire` - Empire1..Empire8, Indep
- `ObjectTypes` - Void, Pln, Base, Flt, Gate, BlkHl, Plsr, WrmHl, Con, Wndr, ArtOBJ
- `WorldClass` - 22 planet classes (Ambrosia, Arid, Artificial, Barren, etc.)
- `WorldTypes` - 21 designations (Agricultural, Capital, Chemical, etc.)
- `TechLevel` - 11 levels (PreTech through Gate)
- `ShipTypes` - fgt, hkr, jmp, jtn, pen, ssp, trn
- `DefenseTypes` - LAM, def, GDM, ion
- `CargoTypes` - men, nnj, amb, che, met, sup, tri
- `FleetStatus` - Ready, InTrans, Inactive, Lost
- `XYCoord` - (x, y) coordinate pair
- `IDNumber` - (obj_type, index) object identifier

### datastrc.py
All entity records from DATASTRC.PAS.

**Key records:**
- `PlanetRecord` - Location, ownership, class, type, tech, efficiency, population, ships, cargo, industry, special conditions, trillum reserves
- `FleetRecord` - Location, ships, cargo, destination, status, fuel, orders
- `StarbaseRecord` - Like planets but mobile, with type (cmm, frt, cmp, out)
- `StargateRecord` - Gate type (gte, lnk, dis), warp link frequencies per empire
- `ConstrRecord` - Construction type, location, time to completion, material requirements
- `EmpireRecord` - Capital, tech level, technology set, defense settings, probes, revolution index
- `UniverseRecord` - Container for all planets, starbases, fleets, stargates, construction sites, empire data

### datacnst.py
Game balance constants from DATACNST.PAS.

**Key constants:**
- `CombatTable` - 14x14 damage matrix
- `CombatTechAdj` - 11x11 tech advantage matrix
- `ThgAdj` - Industry production outputs
- `RawM` - Raw material requirements
- `ClassIndAdj` - Planet class industry effectiveness multipliers
- `FuelCons` - Fuel consumption per ship type per sector
- `CargoSpace` - Transport capacity per cargo type
- Construction costs and times for all structure types
- Tech advancement data (TechDev)

### galaxy.py
Galaxy grid from GALAXY.PAS.

**Key types:**
- `SectorRecord` - Object in sector, fleet scouting, mine scouting, special (nebula/mine owner)
- `Galaxy` - 2D grid of sectors (max 100x100)
- Coordinate validation and distance utilities

### environ.py
Global game state from ENVIRON.PAS.

**GameEnvironment class:**
- `Year` - Current game year
- `Player` - Active player empire
- `Universe` - UniverseRecord instance
- `Galaxy` - Galaxy instance
- Configuration settings
- Save/load state management

## Interface Layer

### primintr.py
Low-level property getters/setters (~1700 lines in Pascal).

**Functions:**
- Get/set properties for all entity types
- Scout/knowledge tracking
- Property validation

### intrface.py
High-level operations from INTRFACE.PAS.

**Functions:**
- Scout objects
- Designate worlds
- Balance fleets
- Gate passage logic
- Fleet composition changes

### misc.py
Utility functions from MISC.PAS.

**Functions:**
- Distance calculations
- Fuel capacity calculations
- Military power calculations
- Cargo space calculations

## Game Logic Layer

### update.py
Universe update logic from UPDATE.PAS.

**Key functions:**
- `update_universe()` - Main annual update
- `update_planet()` - Full planet update (production, industry, population, efficiency, tech, revolution)
- `update_starbase()` - Starbase annual update
- `update_construction()` - Construction site progress
- `update_empire()` - Empire tech research, revolution tracking

**Planet update sequence:**
1. Update terraforming progress
2. Calculate Industrial Production (TIP)
3. Produce raw materials (chemicals, metals, trillum, supplies)
4. Update industry distribution
5. Produce ships and cargo
6. Update efficiency
7. Update tech level
8. Update population (growth, starvation)
9. Handle ambrosia effects
10. Update military recruitment
11. Auto-build defenses
12. Update revolution
13. Handle hostile life events

### fleet.py
Fleet management from FLEET.PAS.

**Key functions:**
- `deploy_fleet()` - Create new fleet from world
- `abort_fleet()` - Transfer fleet to ground (must be followed by `destroy_fleet()`)
- `change_composition_of_fleet()` - Load/unload ships and cargo, moving fuel to match
- `refuel_fleet()` - Convert trillum to fuel
- `update_fleet()` - One year of movement, then orders on arrival
- `update_all_fleets()` - Which fleets move at this point in the turn rotation
- `execute_fleet_orders()` - Run order scripts
- `in_range_of_disrupter()` / `in_range_of_my_disrupter()` - Disrupter interaction
- `mine_field_damage()` - SRM mine losses

**Fleet movement sequence** (`update_fleet`, skipped entirely when the fleet is
already at its destination):
1. Decide the mode: usable stargate under the fleet, or fortress (teleport if
   the destination is within 5 sectors, else a catapult boost)
2. Consume one year's fuel, refuelling from carried trillum; go inactive if
   there is none
3. Teleport to the destination, unless a dense nebula sits on it
4. Otherwise step up to `FltMovementRate` sectors, checking each step for
   SRM mines and hostile disrupters (jump and HK fleets only), friendly
   disrupters (warp fleets, which then run at jump speed), and dense nebulae
5. Execute orders if the fleet arrived

**Turn scheduling.** Fleets do not all move at the same moment. Warp fleets and
anything sitting on a gate move for the *incoming* empire; jump and HK fleets
move for the *outgoing* one, so a jump ordered this turn lands this turn.

### attack.py
Combat mechanics from ATTACK.PAS. Everything here resolves *one* round at
*one* shell, or applies an outcome; the loop around it lives in `attnpe.py`.

**Key functions:**
- `default_distribution()` - Split a fleet into groups, one per ship type
- `get_enemy()` - Flatten the defender into per-shell counts
- `calculate_combat_data()` - Tech, terrain and base modifiers for the fight
- `get_target_array()` - Two-pass targeting priority; spends LAMs and GDMs
- `ships_destroyed()` - Combat table lookup with the defender adjustment
- `battle()` - One simultaneous exchange at one shell
- `advance_groups()` - Movement, and the transport-to-troops swap on landing
- `enemy_surrenders()` - Separate tests for fleet and world defenders
- `restore_combatant()` / `resolve_attack()` - Write losses back; conquest,
  morale and news
- `conquer_world()` / `conquer_empire()` - Change of ownership, and breakup
- `lam_attack()`, `holocaust_world()` - Standalone strikes

**Combat shells (outer to inner):**
1. Deep Space (DpSpc)
2. High Orbit (HiOrb)
3. Orbit
4. Sub-Orbit (SbOrb)
5. Ground (Grnd)

### attnpe.py
The battle driver from ATTNPE.PAS: retreat check, targeting, then one round at
every shell, repeated until somebody wins. Written for NPEs but consults no AI
persona, so it resolves any attack headlessly. ATTCOMM.PAS is the interactive
counterpart, where the player picks targets round by round (Phase 5.3, not yet
ported).

**Functions:**
- `npe_attack()` - Fight a fleet against a target to a conclusion
- `group_engage()` - One full round: every shell, then movement

### battle.py
Simplified combat from BATTLE.PAS: both sides reduced to a power number,
one round settled in a step. **Nothing in v2.0 calls it** - a second, coarser
combat model that was written but never wired up. Ported for completeness; its
`MilitaryPower` table disagrees with both `datacnst.MPower` and
`attack.CombatPower`, and nothing reconciles the three.

**Functions:**
- `calc_military_power()` - Total worth of a force
- `calc_attack_round()` - Casualties in one round

### design.py
World designation from DESIGN.PAS.

**Functions:**
- `designate_world()` - Set world type
- `set_issp()` - Set industrial self-sufficiency percentage
- ISSP import/export logic
- LAM launch
- Technology trading
- Message handling

### resource.py
Resource calculations from RESOURCE.PAS.

**Functions:**
- `calculate_cargo_space()` - Total fleet cargo capacity
- `subtract_casualties()` - Remove ships/cargo after combat
- Resource trading logic

### constr.py
Construction commands from CONSTR.PAS. **Unported — a Phase 8 file, not a Phase 6 one.**

Despite the unit name, CONSTR.PAS holds *only* interactive command handlers:
`ConstructCommand`, `AbortConstructionCommand`, `ConstrStatusCommand`,
`WarpLinkFrequencyCommand`. Construction's mechanics are done and live elsewhere:

- `intrface.construction()`, `destroy_construction()`, `next_constr_slot()` - create and tear down a site
- `update.update_construction()` - annual progress, material draw and completion, driven from `update_universe`
- `update.construct_starbase()` / `construct_stargate()` - what a finished site becomes

So this module is the four menus and nothing else, and it arrives with the rest
of the UI in Phase 8.

### sbase.py
Starbase movement and self-destruct from SBASE.PAS.

**Functions:**
- `self_destruct_object()` - Scuttle a starbase or stargate, destroying every fleet in its sector
- `xy2dir()` - Bearing from one coordinate to another
- `get_new_base_pos()` - One step toward a destination, with the two-deep sidestep lookahead
- `move_base()` - Reseat a base in a new sector
- `move_player_starbases()` - Advance an empire's command bases and fortresses one sector

Command bases and fortresses are the only towable installations. They burn a
flat 100 tons of trillum a year regardless of distance and cannot enter an
occupied sector at all, which is why base pathing needs a sidestep that fleet
pathing does not. Called from `main.update_turn` for the *incoming* empire,
alongside `update_all_fleets`.

**Construction types:**
- SRM field (2 years)
- Command base (6 years)
- Fortress (12 years)
- Industrial complex (10 years)
- Outpost (3 years)
- Stargate (15 years)
- Warp link (5 years)
- Disrupter (8 years)

### orders.py
Fleet order scripting from ORDERS.PAS.

**Order types:**
- `DEST` - Set destination
- `TRAN` - Transfer cargo (positive = pick up, negative = drop off)
- `SRMS` - SRM mine sweep (requires 100+ starships)
- `REPE` - Repeat from start of orders
- `WAIT` - Pause execution

Only the first four characters of a verb are significant, so `DEST` and
`DESTination` are the same order.

**Functions:**
- `parse_line()` - Convert one line of text to a `CommandRecord`
- `compile_orders()` - Compile order text into an `OrderStructure`
- `decompile_orders()` - Render compiled orders back to editable text
- `get_fleet_code()` / `set_fleet_code()` - The fleet's stored order list
- `fleet_next_statement()` / `set_fleet_next_statement()` - Where it resumes

`AbortCOM` exists as an enum member with no parser or executor: the `ABOR`
branch is commented out of `ParseLine` in v2.0, so no compiled order carries
it. Execution lives in `fleet.execute_fleet_orders()`.

## AI Layer (npe/)

### npe/types.py
AI type definitions from NPETYPES.PAS.

**AI types:**
- PirateNPE - Raids trade routes
- Kingdom1NPE - Passive but easy to provoke
- Kingdom2NPE - Aggressive
- BerserkerNPE - Aggressive expansion
- GuardianNPE - Defensive

**Personality traits:**
- Defensive (0-100)
- Offensive (0-100)
- Techno (0-100)
- Provoke (0-100)
- Imperialist (0-100)
- Honorable (0-100)

**Fleet missions:**
- Return, HK attack, Wait for transports, Attack transports, Attack world, Berserker attack, Stack at base, Guard, Conquer independent, Jump attack, Refuel, Slow attack, Raid transports, Supply world

**Diplomatic policy (State Department):**
- Neutral → Defend → Harass → Preempt → Conflict → War

### npe/core.py
Shared AI primitives from NPEINTR.PAS. One module per Pascal unit, so the
NPE.PAS dispatcher and NPE00.PAS land separately (see below) rather than being
folded in here.

**Fleet-data bookkeeping:**
- `next_fleet_data_slot()`, `already_targetted()`, `enforce_npe_data_links()`

**Composition and assessment:**
- `get_fleet_composition()` - Build a fleet to a requested power and ground strength
- `get_potential_res()` - A world's holdings plus everything inbound to it
- `minimum_defense()`, `average_military_power()`

**Regions:**
- `create_region_array()` - Base worlds and capital, the AI's frame of reference
- `get_regional_capital()` - Nearest of those to an object

**Target selection:**
- `get_best_target()`, `get_best_base()`, `get_best_planet_to_protect()`, `get_best_raider_target()`

**Deployment:**
- `deploy_battle_fleet()`, `deploy_cargo_fleet()`
- `deploy_jump_attack()`, `deploy_slow_attack()`, `deploy_hk_raiders()`
- `deploy_harass_fleet()` - empty in v2.0 (#25)

**Designation:**
- `get_new_designation()`, `redesignate_empire()`

**Missions** (arrival handlers, one per `MissionTypes`):
- `implement_conquer_msn()`, `implement_jump_attack_msn()`, `implement_raid_trn_msn()`,
  `implement_guard_msn()`, `implement_stack_msn()`, `implement_supply_msn()`,
  `implement_refuel_msn()`, `implement_return_msn()`
- `set_fleet_return()`, `set_raiding_fleet_new_target()`, `mid_course_correction()`
- `destroy_all_fleets_in_sector()`, `plunder_world()`

**Diplomacy:**
- `state_dept_report()` - Refresh strength, world counts and threat scores
- `state_department()` - Move policy up and down the escalation ladder

**Misc:**
- `set_empire_defenses()` - Roll one of four defense distributions

### intrface.py — scouting and probes
`scout()`, `probe_scout()` reveal the ring of sectors around a point (both
start at `NoDir`, so the point itself is included); `in_range_of_starbase()`
and `in_range_of_planet()` are the two scan tests; `determine_if_scouted()`
decides an object's fog level; `scout_fleets()` and `scout_objects()` are the
per-turn sweeps, driven from `main.set_up_turn`. `update_probes()` lands probes
in flight and frees them for relaunch; `probes_return()` is unreachable in v2.0.

### npe/dispatch.py
AI dispatcher from NPE.PAS — `initialize_npe()`, `implement_npe()`,
`cleanup_npe()`, dispatching on `NPEmpireTypes` to the persona modules. Also
`load_npe()`/`save_npe()`, which wait on save/load (§8.4).

### npe/common.py
Shared persona behaviour from NPE00.PAS. Where `core.py` holds the primitives,
this decides *when* to use them; a persona is largely a matter of which of these
it calls, in what order, and how often.

**Functions:**
- `review_news()` - React to the year's headlines: escalate policy against attackers, send tankers to stranded fleets, freight metal to worlds short of it
- `defend_empire()` - Sweep every world, compare defenses against what the persona wants, shuttle ships to and from the regional capital, engage enemy fleets found overhead
- `imperial_expansion()` - Roll against `Imperialist` and take one independent world; drifts the persona afterwards
- `war_cabinet()` - Per enemy empire, deploy raiders and battle fleets by policy, and probe their capital
- `cargo_supply_fleet()` - Move a specific cargo to a world, directly or by first sending empty transports to a world that has it
- `npe_conquest()` - Redesignate a world just taken
- `exploration_and_probing()` - Spend every remaining probe around the regional capitals

Persona is threaded through as an `NPECharacterRecord` and consulted at each
branch; `imperial_expansion` mutates it, so temperament drifts over a game.

Three original defects are reproduced here and filed: #33 (`AttackSeverity`
indexes `MPower` past its end on ground losses), #34 (`DefendEmpire` will not
reinforce a world that has no ships), #35 (`ExplorationAndProbing` hangs for an
empire with no regions).

### npe/pirate.py, kingdom.py, guardian.py, berserker.py
The four personas, from NPE01-NPE04.PAS. Each exposes
`initialize_*`, `implement_*` and `clean_up_*` for the dispatcher.

**`pirate.py` (NPE01)** — commerce raiding. Patrols a 5x5 block of the galaxy
on `WaitForTrnMSN`, intercepts a convoy where it is *going* rather than where it
is, strips it and runs. Blocks that pay get more attractive, blocks that do not
get less: the `HuntingGround` grid is the only memory a pirate keeps between
years, and both updates wrap (#37). Separately raids rich, poorly defended
worlds and strips them via `plunder_world`. Never repairs a stranded fleet --
`NoFuel` means the fleet is destroyed.

**`kingdom.py` (NPE02)** — the reference persona, and the only one that uses the
whole stack. `implement_kingdom1_npe` is the clearest single statement of what
an AI turn is: fleets, news, state department, war cabinet, defense, expansion,
a seventh-year review, probing. Kingdom1 and Kingdom2 share every line and
differ only in the persona rolled at initialisation.

**`guardian.py` (NPE03)** — LAMs and nothing else. No fleets, no expansion, no
diplomacy, no persona. Fires on *any* fleet within 5 sectors that is not its
own, hardest target first, including neutrals and independents.

**`berserker.py` (NPE04)** — the only persona built around starbases. Command
bases and fortresses crawl the galaxy under `sbase.move_player_starbases`, each
running a `BaseMissionTypes` state machine, launching strikes at whatever they
park next to. One conquest in three ends in `_bsrk_destroy_world`: half the
population killed, industry gutted, technology thrown back to pre-atomic.

## UI Layer (ui/)

### ui/app.py
Main Textual application.

**Layout:**
- Title bar (year, empire name)
- Command input area
- Main display area (map, status windows, menus)
- Status bar

### ui/map_view.py
Galaxy map from MAPWIND.PAS.

**Features:**
- Scrollable 100x100 sector map
- Object rendering (planets, fleets, bases, gates, phenomena)
- Nebula display
- SRM mine field display
- Name labels
- Scouting/fog of war
- Cursor navigation

### ui/menus.py
Menu system from MENU.PAS, PULLDOWN.PAS.

**7 main menus:**
1. Info - About, DOS shell
2. Game - Pause, Print, Next Turn, Quit
3. Empire - Send/Read messages, Trade technology, Link frequencies
4. Worlds - Close-up, Designate, Production, ISSP, Name, Liberate, Self-destruct, Terraform
5. Fleet - Deploy, Destination, Transfer, Abort/join, Refuel, SRM sweep, Orders, Cancel, Probe
6. Build - Site status, New construction, Abort
7. Ministry of War - Attack, Auto-attack, Launch LAMs, Defenses

### ui/status.py
Status windows from STAWIND.PAS, FLTWIND.PAS, EMPWIND.PAS.

**Windows:**
- World status (planet details, production, military)
- Fleet status (ships, cargo, fuel, orders)
- Empire status (tech, worlds, military power)
- News window
- Help window

### ui/command.py
Command input from DISPLAY.PAS.

**Features:**
- Command parsing
- Error handling
- Parameter validation
- Command execution

## Utility Layer (utils/)

### utils/strg.py
String utilities from STRG.PAS.

### utils/int_utils.py
Integer utilities from INT.PAS.

### utils/sort.py
Sorting algorithms from SORT.PAS, QSORT.PAS, LSORT.PAS.

## Data Files

### data/names.txt
Empire and world names for random generation.

### data/scenarios/
Scenario files for pre-defined game setups.

## Module Dependencies

```
main.py
├── environ.py
│   ├── types.py
│   ├── datastrc.py
│   ├── galaxy.py
│   └── datacnst.py
├── update.py
│   ├── primintr.py
│   ├── intrface.py
│   ├── misc.py
│   └── datacnst.py
├── fleet.py
│   ├── primintr.py
│   ├── orders.py
│   └── datacnst.py
├── attack.py
│   ├── primintr.py
│   ├── battle.py
│   └── datacnst.py
├── design.py
│   ├── primintr.py
│   └── intrface.py
├── constr.py
│   ├── primintr.py
│   └── datacnst.py
├── sbase.py
│   ├── primintr.py
│   ├── fleet.py
│   └── news.py
├── npe/
│   ├── core.py
│   ├── dispatch.py
│   ├── common.py
│   ├── pirate.py
│   ├── kingdom.py
│   ├── guardian.py
│   └── berserker.py
└── ui/
    ├── app.py
    ├── map_view.py
    ├── menus.py
    ├── status.py
    └── command.py
```
