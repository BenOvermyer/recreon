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
├── constr.py            # Construction commands (CONSTR.PAS)
├── sbase.py             # Starbase movement, self-destruct (SBASE.PAS)
├── orders.py            # Fleet order scripting (ORDERS.PAS)
├── mess.py              # Diplomatic messages (MESS.PAS)
├── prolog.py            # Game lifecycle, prologue commands (PROLOG.PAS)
├── msccomm.py           # Defense settings, self-destruct (MSCCOMM.PAS)
├── fltcomm.py           # Fleet commands (FLTCOMM.PAS)
├── clscomm.py           # World close-up, production forecast (CLSCOMM.PAS)
├── playturn.py          # Command set and the seven menus (PLAYTURN.PAS)
├── attcomm.py           # Target selection, auto-attack, the battle loop (ATTCOMM.PAS)
├── designcom.py         # World and empire commands (DESIGN.PAS)
├── loadsave.py          # Save/load a game (LOADSAVE.PAS)
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
│   ├── map_view.py      # Galaxy map buffer, 3 columns/sector (MAPWIND.PAS)
│   ├── newgame.py       # Scenario picker, intro, naming (NEWGAME.PAS front end)
│   ├── prologue.py      # The menu before and between games (PROLOG.PAS)
│   ├── construction.py  # Construction status, warp links (CONSTR.PAS)
│   ├── defenses.py      # Shell distribution grid, self-destruct (MSCCOMM.PAS)
│   ├── fleet.py         # Fleet list, distribution grid, orders (FLTCOMM.PAS)
│   ├── closeup.py       # Close-up and production screens (CLSCOMM.PAS)
│   ├── menu.py          # The in-game menu bar and its dispatch (PLAYTURN.PAS)
│   ├── attack.py        # The attack screens, auto and interactive (ATTCOMM.PAS)
│   ├── worlds.py        # Designate, terraform, ISSP, liberate, messages, LAMs
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
counterpart, where the player picks targets round by round; `attcomm` drives
the same ATTACK.PAS primitives a round at a time instead of looping here.

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
Construction commands from CONSTR.PAS — a Phase 8 file, not a Phase 6 one.

Despite the unit name, CONSTR.PAS holds *only* interactive command handlers.
Construction's mechanics live elsewhere and were done in Phase 6:

- `intrface.construction()`, `destroy_construction()`, `next_constr_slot()` — create and tear down a site
- `update.update_construction()` — annual progress, material draw and completion, driven from `update_universe`
- `update.construct_starbase()` / `construct_stargate()` — what a finished site becomes

**Functions:** `available_constr_types()` (gated on the empire's technology
*set*, not its level, so a scenario can grant one type on its own),
`sector_is_free()`, `construct_command()`, `abort_construction_command()`,
`constr_status_rows()`, `warp_link_freq_list()`, `set_warp_link_frequency()`,
`warp_link_advice()`. `ConsName` is the display table; `noun()` is STRG.PAS's
article-picker, which counts Y as a vowel.

Two details worth knowing. **A name pinned to the sector follows the site** —
the label moves off the bare coordinate onto the site's ID, because a finished
site becomes a base or a gate and can then move. And **the status table's
shortfall column is the mechanic made legible**: a site consumes material per
year and only the owner's fleets parked on it can supply it, so the column is
"how much more must be sitting there when the year turns".

The warp-link command is filed here because a warp link is a construction type,
but it applies to any stargate the player knows of, including other empires' —
matching your frequency to theirs is how you get to use their gate.

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

### mess.py
Diplomatic messages from MESS.PAS. The store, the delivery rules and the
save/load sections; the compose and inbox windows stay with the rest of the UI.

`MessageList` is a list on `GameEnvironment`, newest first, and a message body
(`TextStructure` in TEXTSTRC.PAS, a linked list of lines) is a `list[str]`.

**Functions:** `new_message()`, `delete_all_messages()`,
`delete_read_messages()`, `get_messages()`, `set_message_read()`,
`send_message()`, `intercept_message()`, `load_message_data()`,
`save_message_data()`.

Interception is the mechanic worth knowing: every empire that is *not* a
recipient rolls once per world at `150 / distance²` percent, measured from the
recipient's capital, and a hit files a garbled copy in the eavesdropper's inbox
plus a `MessI` headline. Worlds near a capital are how a third party reads
someone else's diplomacy. Four original bugs live in this unit — #47, #48, #49
and #50 — of which #50 is the one that changes play.

### designcom.py
DESIGN.PAS's command half; the mechanics are `design.py`. Seven commands:
designate, terraform, ISSP, liberate, trade technology, send and read
messages, launch LAMs.

**Functions:** `designation_options()` / `designation_warnings()` /
`designate_command()`, `terraform_options()` / `terraform_command()`,
`issp_settings()` / `set_issp_settings()`, `independence_recipients()` /
`grant_independence_command()`, `tradeable_technologies()` /
`technology_recipients()` / `sell_technology()`, `message_recipients()` /
`send_message_command()` / `inbox()` / `read_message()`, `lam_targets()` /
`launch_lam()`. `ClassN` is the full world-class names, a table local to
`TerraformCommand` and distinct from `ClassStr`'s single letters.

Four things worth knowing:

- **The warnings are advice.** All five of `DesignateCommand`'s proceed on
  yes, and only the first matching one fires (`ELSE IF`).
- **"Trade technology" is a gift** -- nothing is asked in return, and the offer
  does not check whether the recipient already has it.
- **You cannot gift a world to an absent empire** -- only to independence, or
  to an empire with a scouted fleet in the world's own sector.
- **LAMs target on `Known`, not `Scouted`** -- a fleet you know is there but
  cannot see the composition of is still a legitimate target, within five
  sectors of the launching base.

### attcomm.py
All of ATTCOMM.PAS. The automatic fight is `attnpe.npe_attack`, which despite
its name consults no AI persona and so resolves a player's attack too; the
interactive one is driven here.

**Functions:** `attack_targets()` (`GetTarget`), `auto_attack_command()`,
`attack_command()`, `raze_command()` (`TakeOverConOrGate`), `result_message()`,
`casualty_report()`.

**Classes:** `GroupSplitter` (`GetGroups`), `BattleSession` (`Engage` +
`CleanUp`), `MoveOption`, `CaptureQuestion`, `BattleReport`.

**A fleet in orbit screens the world beneath it** -- `GetTarget` offers the
object under the fleet only after finding no enemy fleets, so a world cannot be
attacked while an enemy fleet shares its sector.

**The interactive half is a state machine, not a loop.** `AttackCommand`'s
`REPEAT Menu(Comm) ... UNTIL EndBattle` blocks on the keyboard and Textual
cannot, so `BattleSession` exposes each menu entry as a method and the UI asks
what is legal, applies a decision, and reads `end_battle` to know when to stop.
`GroupSplitter` is `GetGroups`; `WarpIn`, `WarpOut`, `GroupsDestroyedSFX` and
`DrawScreen` are video-memory writes with no counterpart, and what they said
survives as `BattleSession.report`.

**Nothing happens unless the player makes it happen.** `Engage` has no
`AllAdvance` and no target prioritisation -- those belong to ATTNPE. Groups
start in deep space with `Trg = NoRes`, so an untouched battle trades no fire
at all. Closing and aiming are the decisions the screen exists for.

Four original bugs live here: #65 (the auto-attack builds its casualty report by
reading the fleet record *after* the fight, without checking the fleet
survived), #69 and #70 (uninitialised `Result` and `Capture`), and #71 (the
auto-attack reports a construction site or stargate destroyed without
destroying it).

### playturn.py
PLAYTURN.PAS's command layer -- the `Command` enum and `MENU_BAR`, the seven
pull-downs transcribed from `InitializeMainMenu` with the original's order and
accelerator letters.

Note the menus are **not** MENU.PAS: that is the scrolling-list widget, and
PULLDOWN.PAS is the bar widget. Textual's `ListView` replaces both, so neither
is ported.

Half the unit is still outstanding and deliberately so: the typed-command
parser (`GetCommand`) and the parameter table (`ParameterTypes` +
`SetOfErrors` per command). The ported screens collect their own parameters,
so nothing is blocked -- but the table is the original's one statement of what
every command requires.

`UNREACHABLE` names the three commands inside the `(* ARTIFACTS ... *)` block;
`NOT_PORTABLE` names the DOS-only ones.

### clscomm.py
The two read-only world screens from CLSCOMM.PAS.

**Functions:** `basic_info()` (`GetBasicInfo`), `available_tip()`,
`industry_info()` / `outpost_info()`, `production_forecast()`,
`defense_forecast()`, and the two commands `production_com()` and
`close_up()`.

**The production forecast is a projection, and it disagrees with reality**
(#62). `GetProdInfo` re-derives UPDATE.PAS's formula rather than calling it,
and misses three things: the trillum reserve gate (a mined-out world forecasts
output it cannot deliver), the floor-at-1 on raw materials, and `ThgLmt` --
it uses `IntLmt`, three times the ceiling. Reproduced exactly; don't correct it
against `update.py`.

Two smaller details. `basic_info` appends a coordinate to the name only when
the name has no comma in it -- the original's test for "is this already a
coordinate?" -- so a place called "Kandii, Second" goes un-annotated. And
`defense_forecast` sizes defences off the *manpower in cargo*, not the
population: an outpost wants a quarter of the optimum, a command base or
fortress four times it.

### fltcomm.py
The nine fleet commands from FLTCOMM.PAS, over the mechanics in `fleet.py`.

**Functions:** `ground_candidates()` (`GetGround`), `player_fleets()`,
`launch_fleet_command()`, `abort_warnings()` / `abort_fleet_command()`,
`change_destination_command()`, `transfer_fleet_command()`,
`max_trillum_to_use()` / `trillum_to_use()` / `refuel_fleet_command()`,
`launch_probe_command()`, `mine_sweeper_command()`, `fleet_order_source()` /
`fleet_orders_command()` / `fleet_cancel_orders_command()`, plus the
distribution grid's rules: `masked_amounts()`, `distribution_error()`,
`report_transfer_to_other_empire()`.

Three details worth knowing:

- **Abort's guards are warnings, not refusals.** Aborting onto another
  empire's world hands them the ships — the only way to give ships away — and
  aborting past 9999 of a ship type loses the excess. Both ask and proceed.
- **Another empire's holdings read `????`** in the distribution grid. You can
  move things across but not count what is there. Transferring *to* them files
  a `TrnsShp` headline plus a `Trns2` line per resource, so they see what
  arrived.
- **Only a fleet can be overloaded.** A world has unlimited room, so the grid
  checks the ground side only when it is another fleet — and only *your* fleet
  errors: overload someone else's and the original quietly calls
  `BalanceFleet` on it.

Two original bugs live here: #59 (a shortened order list leaves the resume
point past the end — undefined in Pascal, an `IndexError` here, so the port
clamps) and #60 (mine sweeping costs 100 starships as an order and nothing as
a command).

### msccomm.py
MSCCOMM.PAS's live half. The unit declares five commands but three --
`HolocaustCommand`, `ArtifactCommand`, `TransactionCommand` -- sit inside the
`(* ... *)` block at lines 533-655 and are unreachable in v2.0.

**Functions:** `normalize_defenses()`, `illegal_amounts()`, `clamp_percent()`,
`shell_total()`, `defense_settings_for_editing()`, `save_defense_settings()`;
`can_self_destruct()`, `self_destruct_warning()`, `self_destruct_command()`,
`destructible_objects()`.

The defense distribution is the empire's standing orders for spreading each
ship type across the five orbital shells, and combat reads them whenever a
world or base is attacked. `normalize_defenses` forces each row to total 100 in
three steps, all of which fall back to **sub-orbit**: ground percentages for
ships that cannot land move there, a shortfall goes there, and the remainder
`Trunc` loses when scaling a surplus goes there too.

Self-destruct covers starbases and stargates but **not an industrial complex**
-- `cmp` is excluded by name, since a complex sits on a world rather than
standing alone.

### prolog.py
The prologue from PROLOG.PAS: the game's lifecycle and the settings that live
outside a game.

**Functions:** `save_the_game()`, `continue_old_game()`, `quit_game()`,
`start_a_new_game()`, `needs_saving()`, `do_not_save_game()`,
`add_player_empire()`, `delete_player_empire()`, `change_time_limit()`, the
three toggles, and `choose_player_options()` with its two callers
(`players_to_move`, `deletable_empires`).

`PrologueState` holds `GameLoaded` and `GameModified` — unit-level typed
constants in the original, so scoped to the prologue here rather than added to
`GameEnvironment`.

`add_player_empire()` is the substantial one: it seats a latecomer on the first
independent world above bio-tech with over 2000 people, gives them the highest
technology level in the galaxy, and files a `NewPlEmp` headline with every
empire that already knew the world. Two original bugs live here — #54 (a manual
save destroys the autosave, because it uses the same file as scratch) and #55
(the technology union is discarded on each new high-water mark).

Not ported: the title-screen effects, DOS shell, print map, mono/colour, and
the ANACREON.CNF configuration file.

### loadsave.py
Saving and loading from LOADSAVE.PAS. `InitializeUniverse` is on
`GameEnvironment`; everything else in the unit is here.

**Functions:** `save_game()`, `load_game()`, `clean_up_universe()`,
`auto_backup()`, `backup_path()`, plus a section pair per entity type
(`save_planets`/`load_planets`, starbases, fleets, stargates, constr, empires).
The other sections live in the unit that owns their state, as the original does:
`environ.save_environment()`, `galaxy.Galaxy.save_sector()`,
`news.save_news_data()`, `mess.save_message_data()`,
`npe.dispatch.save_npe_data()`.

**The format is JSON, not the original's raw record dump.** Pascal writes
records with `BlockWrite` straight out of memory; nothing in Python has that
layout, and no `.SAV` or `.BAK` is shipped in `original/` to be compatible with.
So this is its own format with its own signature and its own version line, and
**a save from the DOS build cannot be loaded**. The version shims in the
original (`SFVersion > 13` for `TerraformTarget`, `> 14` for a stargate's `WLF`,
`< 12` for the old NPE `FleetData`) are unportable rather than unported — each
reinterprets a byte layout that has no counterpart here.

What *is* ported is the structure and the behaviour: sections in the original's
order, the per-empire sets rebuilt from the records rather than saved, the world
count recounted on load, the fleet-position repair in `LoadFleets`, and the two
version warnings.

`utils/serial.py` is the codec underneath — it walks annotations rather than
values, so an `IntEnum` comes back as that enum and a `set[Empire]` as a set of
`Empire`. It refuses ambiguous unions rather than inventing a discriminator; the
one such field, `NPEDataRecord.Data`, is dispatched on the `Typ` beside it,
exactly as `NPE.PAS`'s `LoadNPE` does.

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

### intrface.py — news rendering
`get_news_line()` turns a `NewsRecord` into the sentence the player reads.
Each headline has a template where `*` is the location and `@` the empire named
by `Parm1`; both are substituted last. `Parm2`/`Parm3` carry a resource, an
industry or a second empire depending on the headline. Nine declared headline
types have no arm in the original's CASE and are never filed by anything.

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
`load_npe_data()`/`save_npe_data()`, which are the same `CASE` again: the
persona record class is chosen from the empire's own `Typ`, `ELSE` arm and all.

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

### ui/newgame.py
The scenario front end from NEWGAME.PAS — `GetScenarios`,
`ScenarioIntroduction`, `InputEmpireName`, `SuggestionsWindow`. `NewGameScreen`
walks four steps in the original's order: pick a scenario, page the
introduction, choose a player count (skipped when the scenario is fixed, as
`NoChoice` does), name each empire. `SuggestionsScreen` is the Esc-from-naming
name list.

What the steps *decide* is in `newgame.py`; this draws it. The screens read the
header and intro first via `read_scenario_intro` rather than answering from
inside the parse, which an event loop cannot do — safe because neither draws
from the generator.

### ui/prologue.py
The prologue menu, plus the three little windows it opens: `Attention`
(`AttentionWindow`, acknowledgement or yes/no), `TextPrompt` (`InputString`),
and `ChooseFrom` (`ChoosePlayer` and the save-file picker). `PrologueScreen`
dismisses with `"begin"` or `"quit"` — the two ways `Prologue`'s loop ends.

### ui/construction.py
`ConstructionScreen` (the status table, with construct and abort on it) and
`WarpLinkScreen`. Reached from the map with `b` and `w`; the original hangs
them off the Build and Empire pull-downs, which are MENU.PAS and still to come.
`_interpret_xy` is DISPLAY.PAS's `InterpretXY` for the one form it needs —
capital-relative coordinates, where the two axes convert differently.

### ui/defenses.py
`DefenseScreen` (the shell distribution grid: arrows move, digits edit, Esc
normalises then leaves) and `SelfDestructScreen`. Reached from the map with
`d` and `x`.

The grid's Esc behaviour follows the original's `UNTIL (Ch=EscKey) AND NOT
(Error)`: the first Esc on an illegal grid reports what is wrong, normalises,
and stays; only a second one saves and leaves.

### ui/worlds.py
`DesignateScreen`, `TerraformScreen`, `ISSPScreen`, `LiberateScreen`,
`TradeTechnologyScreen`, `SendMessageScreen`, `ReadMessagesScreen`,
`LaunchLAMScreen`. All but the three empire-wide ones act on the world under
the map cursor; LAMs need a starbase there.

### ui/attack.py
`AutoAttackScreen`: pick a fleet, pick a target, confirm, resolve, and read the
outcome with its casualty list. Reached from Ministry of War > auTo attack.

### ui/menu.py
The in-game menu bar, on `m` or F10, dispatching to every screen ported so
far -- PLAYTURN.PAS's `CASE Comm OF` for what exists. `PENDING` names the
commands with no screen yet and says what each is waiting on, so they stay
visible on the menu rather than being hidden.

One Textual detail worth keeping: the screen holds **one** `ListView` and
refills it, rather than remounting per menu. Removing a focused `ListView`
leaves focus on the removed widget, which made the bar open but its items
never run.

### ui/closeup.py
`CloseUpScreen` and `ProductionScreen`, both acting on whatever the map cursor
is over. Reached with `z` and `i`. The production screen carries the trillum
reserve figure beside the forecast, which is the only way a player can tell
the trillum line is overstated (#62).

### ui/fleet.py
`FleetScreen` (the fleet list with the nine commands on it),
`DistributionScreen` (`InputNewDistribution`, shared by launch and transfer)
and `OrdersScreen` (the order editor). Reached from the map with `f`.

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

### utils/serial.py
JSON codec for the record types, used by the save/load sections. Not a port of
anything — the original had no need for one, since `BlockWrite` could dump a
record straight out of memory. See `loadsave.py` above.

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
├── loadsave.py
│   ├── environ.py
│   ├── galaxy.py
│   ├── mess.py
│   ├── news.py
│   ├── npe/dispatch.py
│   └── utils/serial.py
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
