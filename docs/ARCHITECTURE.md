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
├── attack.py            # Combat resolution (ATTACK.PAS)
├── battle.py            # Simplified combat (BATTLE.PAS)
├── design.py            # World designation, ISSP (DESIGN.PAS)
├── resource.py          # Cargo, production (RESOURCE.PAS)
├── constr.py            # Construction sites (CONSTR.PAS)
├── orders.py            # Fleet order scripting (ORDERS.PAS)
├── npe/                 # AI system (NPE*.PAS)
│   ├── __init__.py
│   ├── types.py         # AI type definitions (NPETYPES.PAS)
│   ├── core.py          # AI dispatcher (NPE.PAS, NPEINTR.PAS, NPE00.PAS)
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
- `abort_fleet()` - Transfer fleet to ground
- `change_fleet_composition()` - Load/unload ships and cargo
- `refuel_fleet()` - Convert trillum to fuel
- `update_fleet()` - Movement, fuel consumption, pathfinding
- `execute_fleet_orders()` - Run order scripts
- Stargate teleportation
- SRM mine damage
- Disrupter interaction

**Fleet movement sequence:**
1. Calculate path toward destination
2. Check for stargates (instant teleport)
3. Check for fortress teleportation
4. Consume fuel
5. Handle jump/HK fleet SRM mine damage
6. Handle disrupter effects
7. Check for dense nebulae
8. Execute orders on arrival

### attack.py
Combat resolution from ATTACK.PAS.

**Key functions:**
- `resolve_battle()` - Full combat with 5 orbital shells
- Targeting priority calculation
- `ships_destroyed()` - Combat table lookup with tech adjustment
- GDM/LAM missile mechanics
- Ground assault logic
- Surrender algorithm
- Conquest handling

**Combat shells (outer to inner):**
1. Deep Space (DpSpc)
2. High Orbit (HiOrb)
3. Orbit
4. Sub-Orbit (SbOrb)
5. Ground (Grnd)

### battle.py
Simplified combat from BATTLE.PAS.

**Functions:**
- `calculate_battle_outcome()` - Quick resolution for AI and auto-attack

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
Construction system from CONSTR.PAS.

**Functions:**
- `start_construction()` - Create new construction site
- `update_construction()` - Annual progress update
- Material delivery from fleets
- Completion logic
- Warp link frequency management

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

**Functions:**
- `parse_orders()` - Convert text to order list
- `compile_orders()` - Store in fleet
- `execute_orders()` - Run order script

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
AI dispatcher from NPE.PAS, NPEINTR.PAS, NPE00.PAS.

**Functions:**
- `implement_npe()` - Main AI entry point
- Threat assessment
- World evaluation
- Fleet mission assignment
- State Department updates

### npe/pirate.py, kingdom.py, guardian.py, berserker.py
Specific AI implementations from NPE01-NPE04.PAS.

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
├── npe/
│   ├── core.py
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
