# Implementation Plan

## Overview

This document outlines the phased implementation approach for Re:creon. Each phase builds on the previous one, with clear milestones and deliverables.

---

## Phase 1: Project Setup & Core Data Structures

**Duration**: Weeks 1-2

### 1.1 Initialize Python project with uv

```bash
uv init recreon
cd recreon
uv add textual rich pytest
```

### 1.2 Create project structure

Set up the directory structure as defined in [ARCHITECTURE.md](ARCHITECTURE.md).

### 1.3 Implement core types (types.py)

**Source files**: TYPES.PAS, NPETYPES.PAS, CDETYPES.PAS

**Key types to implement:**

```python
from enum import Enum, IntEnum
from dataclasses import dataclass

class Empire(IntEnum):
    Empire1 = 1
    Empire2 = 2
    # ... through Empire8
    Indep = 9

class ObjectTypes(Enum):
    Void = 0
    Con = 1      # Construction site
    Pln = 2      # Planet
    Base = 3     # Starbase
    Gate = 4     # Stargate/link/disrupter
    BlkHl = 5    # Black hole
    Plsr = 6     # Pulsar
    WrmHl = 7    # Worm hole
    Flt = 8      # Fleet
    Wndr = 9     # Wanderer
    ArtOBJ = 10  # Artifact

class WorldClass(Enum):
    Ambrosia = 0
    Arid = 1
    Artificial = 2
    Barren = 3
    ClassJ = 4
    ClassK = 5
    ClassL = 6
    ClassM = 7
    Desert = 8
    Earthlike = 9
    Forest = 10
    GasGiant = 11
    HostileLife = 12
    Ice = 13
    Jungle = 14
    Ocean = 15
    Paradise = 16
    Poisonous = 17
    Ruins = 18
    Underground = 19
    Terraforming = 20
    Volcanic = 21

class WorldTypes(Enum):
    Agricultural = 0
    Ambrosia = 1
    Base = 2
    Capital = 3
    Chemical = 4
    Independent = 5
    Jumpship = 6
    MetalMine = 7
    Ninja = 8
    Outpost = 9
    RawMaterial = 10
    ResearchUniversity = 11
    Starship = 12
    Transport = 13
    Terraforming = 14
    Trillum = 15
    # ... additional types

class TechLevel(IntEnum):
    PreTech = 0
    Primitive = 1
    PreAtomic = 2
    Atomic = 3
    PreWarp = 4
    Warp = 5
    Jump = 6
    BioTech = 7
    Starship = 8
    PreGate = 9
    Gate = 10

class ShipTypes(Enum):
    fgt = 0  # Fighter
    hkr = 1  # Hunter-killer
    jmp = 2  # Jumpship
    jtn = 3  # Jump-transport
    pen = 4  # Penetrator
    ssp = 5  # Starship
    trn = 6  # Transport

class DefenseTypes(Enum):
    LAM = 0  # Local Area Missile
    defns = 1  # Defense satellite
    GDM = 2  # Global Defense Missile
    ion = 3  # Ion cannon

class CargoTypes(Enum):
    men = 0  # Legions (troops)
    nnj = 1  # Ninja legions
    amb = 2  # Ambrosia
    che = 3  # Chemicals
    met = 4  # Metals
    sup = 5  # Supplies
    tri = 6  # Trillum

class FleetStatus(Enum):
    Ready = 0
    InTrans = 1
    Inactive = 2
    Lost = 3

@dataclass
class XYCoord:
    x: int
    y: int

@dataclass
class IDNumber:
    obj_type: ObjectTypes
    index: int
```

### 1.4 Implement data structures (datastrc.py)

**Source files**: DATASTRC.PAS

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class PlanetRecord:
    XY: XYCoord
    Emp: Empire
    ScoutedBy: set[Empire]
    KnownBy: set[Empire]
    Cls: WorldClass
    Typ: WorldTypes
    Tech: TechLevel
    Eff: int  # 0-100
    RevIndex: int  # 0-100
    Pop: int  # 0-9999
    Ships: dict[ShipTypes, int]
    Defns: dict[DefenseTypes, int]
    Cargo: dict[CargoTypes, int]
    Indus: dict[str, int]  # 9 industry types
    Special: set[str]  # Special conditions
    TriReserve: int
    TerraformTarget: Optional[WorldClass]

@dataclass
class FleetRecord:
    XY: XYCoord
    Emp: Empire
    Ships: dict[ShipTypes, int]
    Cargo: dict[CargoTypes, int]
    Dest: XYCoord
    Status: FleetStatus
    FuelHigh: int
    Fuel: int
    NextOrder: int
    OrderData: list[int]
    NPEDataIndex: int

@dataclass
class StarbaseRecord:
    # Similar to PlanetRecord but mobile
    pass

@dataclass
class StargateRecord:
    XY: XYCoord
    GateType: str  # gte, lnk, dis
    WLF: dict[Empire, int]  # Warp Link Frequencies

@dataclass
class ConstrRecord:
    XY: XYCoord
    ConstrType: str
    TimeToCompletion: int
    Emp: Empire

@dataclass
class EmpireRecord:
    IsAPlayer: bool
    EmpireName: str
    Capital: IDNumber
    TechnologyLevel: TechLevel
    Technology: set[str]
    DefenseSettings: dict
    Probe: list[XYCoord]
    TotalRevIndex: int
    RevFactor: int
    Founding: int
    Modifiers: set[str]
    TimeLeft: int

@dataclass
class UniverseRecord:
    Planet: list[Optional[PlanetRecord]]  # [0..200], 0 unused
    Starbase: list[Optional[StarbaseRecord]]  # [0..100]
    Fleet: list[Optional[FleetRecord]]  # [0..240]
    Stargate: list[Optional[StargateRecord]]  # [0..50]
    Constr: list[Optional[ConstrRecord]]  # [0..50]
    EmpireData: dict[Empire, EmpireRecord]
```

### 1.5 Implement game constants (datacnst.py)

**Source files**: DATACNST.PAS

Extract all game balance constants:
- Combat tables (14x14 matrices)
- Production tables (ThgAdj, RawM)
- Tech advancement data (TechDev)
- Planet class adjustments (ClassIndAdj)
- Construction costs and times
- Fuel consumption rates
- Cargo space values

**Milestone 1**: Core data structures compile and can be instantiated.

---

## Phase 2: Galaxy & Basic Game Loop

**Duration**: Weeks 3-4

### 2.1 Galaxy generation (galaxy.py)

**Source files**: GALAXY.PAS

```python
@dataclass
class SectorRecord:
    Obj: IDNumber
    Flts: set[Empire]  # Which empires have fleets here
    MineScout: set[Empire]
    Special: int  # Low 4 bits = nebula, high 4 bits = mine owner

class Galaxy:
    def __init__(self, width=100, height=100):
        self.width = width
        self.height = height
        self.sectors = [[None for _ in range(height)] for _ in range(width)]
    
    def initialize_sector(self, x, y):
        self.sectors[x][y] = SectorRecord(...)
    
    def get_sector(self, x, y) -> SectorRecord:
        return self.sectors[x][y]
```

### 2.2 Global state (environ.py)

**Source files**: ENVIRON.PAS

```python
class GameEnvironment:
    def __init__(self):
        self.Year: int = 4021
        self.Player: Empire = Empire.Empire1
        self.Universe: UniverseRecord = UniverseRecord()
        self.Galaxy: Galaxy = Galaxy()
        self.ExitProgram: bool = False
        self.ExitGame: bool = False
    
    def initialize_new_game(self):
        # Initialize universe, galaxy, empires
        pass
    
    def player_takes_turn(self):
        # Player command loop
        pass
    
    def update_turn(self):
        # Update universe
        pass
    
    def advance_to_next_empire(self):
        # Move to next empire
        pass
```

### 2.3 Basic interface layer

**Source files**: PRIMINTR.PAS, INTRFACE.PAS, MISC.PAS

Implement property getters/setters and utility functions:
- `get_planet_property(planet_id, property_name)`
- `set_planet_property(planet_id, property_name, value)`
- `distance(xy1, xy2)` - Calculate distance between coordinates
- `fuel_capacity(fleet)` - Calculate fleet fuel capacity
- `military_power(ships)` - Calculate military strength

### 2.4 Minimal game loop (main.py)

**Source files**: ANACREON.PAS (simplified)

```python
def main():
    game = GameEnvironment()
    game.initialize_new_game()
    
    while not game.ExitProgram:
        if game.player_is_active():
            game.player_takes_turn()
        game.update_turn()
        game.advance_to_next_empire()
```

### 2.5 Basic Textual UI skeleton

**Source files**: DISPLAY.PAS, MAPWIND.PAS (simplified)

```python
from textual.app import App
from textual.widgets import Header, Footer, Static

class RecreonApp(App):
    CSS_PATH = "ui/style.css"
    
    def compose(self):
        yield Header()
        yield Static("Galaxy Map", id="map")
        yield Footer()
    
    def on_key(self, event):
        if event.key == "q":
            self.exit()

if __name__ == "__main__":
    app = RecreonApp()
    app.run()
```

**Milestone 2**: Can start game, see empty galaxy map, advance turns.

---

## Phase 3: Planet Management & Economy

**Duration**: Weeks 5-6

### 3.1 Universe update logic (update.py)

**Source files**: UPDATE.PAS

Implement `update_universe()` with full planet update sequence:

```python
def update_universe(game: GameEnvironment):
    game.Year += 1
    
    # Update all planets
    for planet_id in range(1, 201):
        if game.Universe.Planet[planet_id]:
            update_planet(game, planet_id)
    
    # Update all starbases
    for base_id in range(1, 101):
        if game.Universe.Starbase[base_id]:
            update_starbase(game, base_id)
    
    # Update construction sites
    for constr_id in range(1, 51):
        if game.Universe.Constr[constr_id]:
            update_construction(game, constr_id)
    
    # Update empires
    for empire in Empire:
        if empire != Empire.Indep:
            update_empire(game, empire)

def update_planet(game: GameEnvironment, planet_id: int):
    planet = game.Universe.Planet[planet_id]
    
    # 1. Update terraforming
    update_terraforming(planet)
    
    # 2. Calculate Industrial Production
    tip = calculate_industrial_production(planet)
    
    # 3. Produce raw materials
    produce_raw_materials(planet, tip)
    
    # 4. Update industry distribution
    distribute_industry(planet, tip)
    
    # 5. Produce ships and cargo
    produce_ships_and_cargo(planet)
    
    # 6. Update efficiency
    update_efficiency(planet)
    
    # 7. Update tech level
    update_tech_level(game, planet)
    
    # 8. Update population
    update_population(planet)
    
    # 9. Consume food
    consume_food(planet)
    
    # 10. Handle ambrosia
    handle_ambrosia(planet)
    
    # 11. Update military recruitment
    update_military(planet)
    
    # 12. Auto-build defenses
    auto_build_defenses(planet)
    
    # 13. Update revolution
    update_revolution(planet)
    
    # 14. Handle hostile life
    handle_hostile_life(game, planet)
```

### 3.2 World designation (design.py)

**Source files**: DESIGN.PAS

```python
def designate_world(game: GameEnvironment, planet_id: int, world_type: WorldTypes):
    planet = game.Universe.Planet[planet_id]
    planet.Typ = world_type
    # Update industrial distribution based on type

def set_issp(game: GameEnvironment, planet_id: int, percentage: int):
    # Set industrial self-sufficiency percentage
    pass
```

### 3.3 Resource calculations (resource.py)

**Source files**: RESOURCE.PAS

```python
def calculate_cargo_space(fleet: FleetRecord) -> int:
    # Calculate total cargo capacity
    pass

def subtract_casualties(fleet: FleetRecord, losses: dict):
    # Remove ships/cargo after combat
    pass
```

### 3.4 Enhanced UI

- World status window showing planet details
- Empire status window showing tech, worlds, military
- World selection on map
- Designation menu
- ISSP adjustment dialog

**Milestone 3**: Planets produce resources, population grows, tech advances. Can designate worlds.

---

## Phase 4: Fleet Management

**Duration**: Weeks 7-8

### 4.1 Fleet operations (fleet.py)

**Source files**: FLEET.PAS

```python
def deploy_fleet(game: GameEnvironment, planet_id: int, ships: dict, cargo: dict) -> int:
    # Create new fleet from world
    fleet_id = find_empty_fleet_slot(game)
    fleet = FleetRecord(...)
    game.Universe.Fleet[fleet_id] = fleet
    return fleet_id

def abort_fleet(game: GameEnvironment, fleet_id: int):
    # Transfer fleet to ground
    pass

def change_fleet_composition(game: GameEnvironment, fleet_id: int, transfers: dict):
    # Load/unload ships and cargo
    pass

def refuel_fleet(game: GameEnvironment, fleet_id: int):
    # Convert trillum to fuel
    pass

def update_fleet(game: GameEnvironment, fleet_id: int):
    fleet = game.Universe.Fleet[fleet_id]
    
    # 1. Calculate path toward destination
    path = calculate_path(fleet.XY, fleet.Dest)
    
    # 2. Check for stargates
    if stargate_at(fleet.XY):
        teleport_through_gate(game, fleet)
        return
    
    # 3. Move one sector
    next_sector = path[0]
    
    # 4. Consume fuel
    fuel_needed = calculate_fuel_consumption(fleet)
    if fleet.Fuel < fuel_needed:
        # Auto-consume trillum or become inactive
        pass
    
    fleet.Fuel -= fuel_needed
    fleet.XY = next_sector
    
    # 5. Handle SRM mine damage (jump/HK fleets)
    if is_jump_fleet(fleet):
        check_srm_mine_damage(game, fleet)
    
    # 6. Check for disrupters
    check_disrupter_effects(game, fleet)
    
    # 7. On arrival, execute orders
    if fleet.XY == fleet.Dest:
        execute_fleet_orders(game, fleet_id)

def execute_fleet_orders(game: GameEnvironment, fleet_id: int):
    fleet = game.Universe.Fleet[fleet_id]
    
    while fleet.NextOrder > 0:
        order = fleet.OrderData[fleet.NextOrder]
        
        if order == DEST:
            fleet.Dest = order.parameters
            fleet.NextOrder += 1
        elif order == TRAN:
            transfer_cargo(game, fleet_id, order.parameters)
            fleet.NextOrder += 1
        elif order == SRMS:
            sweep_srm_mines(game, fleet_id)
            fleet.NextOrder += 1
        elif order == REPE:
            fleet.NextOrder = 1
        elif order == WAIT:
            break
```

### 4.2 Orders system (orders.py)

**Source files**: ORDERS.PAS

```python
@dataclass
class Order:
    command: str  # DEST, TRAN, SRMS, REPE, WAIT
    parameters: dict

def parse_orders(text: str) -> list[Order]:
    # Convert text to order list
    pass

def compile_orders(fleet: FleetRecord, orders: list[Order]):
    # Store orders in fleet
    pass
```

### 4.3 Fleet UI

- Fleet status window showing ships, cargo, fuel, orders
- Fleet deployment dialog
- Transfer dialog (ships/cargo between fleet and ground)
- Order editor
- Fleet selection and destination setting

**Milestone 4**: Can deploy fleets, set destinations, transfer cargo, fleets move on map.

---

## Phase 5: Combat System

**Duration**: Weeks 9-10

### 5.1 Combat resolution (attack.py)

**Source files**: ATTACK.PAS

```python
def resolve_battle(game: GameEnvironment, attacker_fleet_id: int, defender_world_id: int):
    attacker = game.Universe.Fleet[attacker_fleet_id]
    defender = game.Universe.Planet[defender_world_id]
    
    # Split attacker into groups by ship type
    groups = split_into_groups(attacker)
    
    # Combat through 5 orbital shells
    for shell in [DpSpc, HiOrb, Orbit, SbOrb, Grnd]:
        for group in groups:
            # Calculate targeting priority
            targets = calculate_targeting_priority(group, defender, shell)
            
            # Resolve combat
            for target in targets:
                losses = ships_destroyed(group, target, game)
                apply_losses(target, losses)
            
            # Check if group can advance
            if can_advance(group, shell):
                group.shell = next_shell(shell)
    
    # Ground assault
    if attacker_has_troops(attacker):
        ground_assault(game, attacker, defender)
    
    # Check for surrender
    if should_surrender(defender):
        conquer_world(game, attacker, defender)
    
    # Clean up destroyed units
    cleanup_battle(game)

def ships_destroyed(attacker, defender, game: GameEnvironment) -> int:
    # Combat table lookup with tech adjustment
    base_damage = CombatTable[attacker.type][defender.type]
    tech_adj = CombatTechAdj[attacker.tech][defender.tech]
    return base_damage * tech_adj
```

### 5.2 Simplified combat (battle.py)

**Source files**: BATTLE.PAS

```python
def calculate_battle_outcome(attacker, defender) -> str:
    # Quick resolution for AI and auto-attack
    attacker_power = calculate_military_power(attacker)
    defender_power = calculate_military_power(defender)
    
    if attacker_power > defender_power * 1.5:
        return "attacker_wins"
    elif defender_power > attacker_power * 1.5:
        return "defender_wins"
    else:
        return "mutual_destruction"
```

### 5.3 Combat UI

- Battle report window showing combat details
- Attack command
- Auto-attack toggle
- LAM launch dialog
- Defense settings (orbital shell distribution)

**Milestone 5**: Fleets can attack worlds, combat resolves with proper mechanics, conquest works.

---

## Phase 6: Construction & Advanced Features

**Duration**: Weeks 11-12

### 6.1 Construction system (constr.py)

**Source files**: CONSTR.PAS

```python
def start_construction(game: GameEnvironment, site_type: str, location: XYCoord, empire: Empire):
    constr_id = find_empty_constr_slot(game)
    constr = ConstrRecord(
        XY=location,
        ConstrType=site_type,
        TimeToCompletion=get_construction_time(site_type),
        Emp=empire
    )
    game.Universe.Constr[constr_id] = constr
    return constr_id

def update_construction(game: GameEnvironment, constr_id: int):
    constr = game.Universe.Constr[constr_id]
    
    # Check for material delivery
    materials_delivered = check_material_delivery(game, constr)
    
    if materials_delivered >= required_materials(constr.ConstrType):
        constr.TimeToCompletion -= 1
        
        if constr.TimeToCompletion == 0:
            complete_construction(game, constr_id)

def complete_construction(game: GameEnvironment, constr_id: int):
    constr = game.Universe.Constr[constr_id]
    
    if constr.ConstrType == "SRM":
        create_srm_mine(game, constr.XY, constr.Emp)
    elif constr.ConstrType == "Gate":
        create_stargate(game, constr.XY)
    elif constr.ConstrType == "Base":
        create_starbase(game, constr.XY, constr.Emp)
    
    # Remove construction site
    game.Universe.Constr[constr_id] = None
```

### 6.2 Terraforming

```python
def start_terraforming(game: GameEnvironment, planet_id: int, target_class: WorldClass):
    planet = game.Universe.Planet[planet_id]
    planet.TerraformTarget = target_class
    planet.Cls = WorldClass.Terraforming

def update_terraforming(game: GameEnvironment, planet_id: int):
    planet = game.Universe.Planet[planet_id]
    
    if planet.TerraformTarget:
        # Check for success, failure, or continuation
        result = roll_terraforming_check(planet)
        
        if result == SUCCESS:
            planet.Cls = planet.TerraformTarget
            planet.TerraformTarget = None
        elif result == CATASTROPHIC_FAILURE:
            planet.Cls = random.choice([WorldClass.Barren, WorldClass.Volcanic, WorldClass.Ice])
            planet.Pop //= 2  # Population loss
            planet.TerraformTarget = None
```

### 6.3 Diplomacy

```python
def send_message(game: GameEnvironment, from_empire: Empire, to_empire: Empire, message: str):
    # Add message to empire's inbox
    pass

def trade_technology(game: GameEnvironment, empire1: Empire, empire2: Empire, tech: str):
    # Exchange technology
    pass

def link_frequencies(game: GameEnvironment, empire: Empire, gate_id: int, frequencies: dict):
    # Set warp link frequencies for gate
    pass
```

**Milestone 6**: Can build starbases, gates, SRM mines. Terraforming works. Diplomacy functional.

---

## Phase 7: AI System (NPE)

**Duration**: Weeks 13-16

### 7.1 AI core (npe/core.py)

**Source files**: NPE.PAS, NPEINTR.PAS, NPE00.PAS

```python
def implement_npe(game: GameEnvironment, empire: Empire):
    # Main AI entry point
    npe_type = get_npe_type(empire)
    
    if npe_type == "Pirate":
        implement_pirate_npe(game, empire)
    elif npe_type == "Kingdom":
        implement_kingdom_npe(game, empire)
    elif npe_type == "Guardian":
        implement_guardian_npe(game, empire)
    elif npe_type == "Berserker":
        implement_berserker_npe(game, empire)

def assess_threats(game: GameEnvironment, empire: Empire) -> dict:
    # Evaluate threats from other empires
    pass

def evaluate_worlds(game: GameEnvironment, empire: Empire) -> list:
    # Rank worlds by value and vulnerability
    pass

def assign_fleet_missions(game: GameEnvironment, empire: Empire):
    # Assign missions to all fleets
    for fleet_id in get_empire_fleets(game, empire):
        mission = decide_mission(game, fleet_id, empire)
        execute_mission(game, fleet_id, mission)
```

### 7.2 AI types

**npe/pirate.py** - Pirate AI (NPE01.PAS)
- Raids trade routes
- Has hunting grounds grid
- Avoids strong defenses

**npe/kingdom.py** - Kingdom AI (NPE02.PAS)
- Passive but easy to provoke
- Personality traits determine behavior
- Builds up forces before attacking

**npe/guardian.py** - Guardian AI (NPE03.PAS)
- Defensive empire
- Protects all worlds equally
- Responds to attacks

**npe/berserker.py** - Berserker AI (NPE04.PAS)
- Aggressive expansion
- Uses base fleet system
- Constant attacks

### 7.3 State Department

```python
class DiplomaticPolicy(Enum):
    Neutral = 0
    Defend = 1
    Harass = 2
    Preempt = 3
    Conflict = 4
    War = 5

def update_state_department(game: GameEnvironment, empire: Empire, other_empire: Empire):
    # Update diplomatic policy based on interactions
    pass
```

**Milestone 7**: AI empires take turns, make decisions, attack/defend, expand.

---

## Phase 8: Polish & Complete UI

**Duration**: Weeks 17-20

### 8.1 Complete map features

- Nebula display with different types
- SRM mine field display
- Name labels for worlds and locations
- Scouting/fog of war (only show what player has scouted)
- Multi-empire fleet tracking

### 8.2 Complete menu system

Implement all 7 menus with all commands:

1. **Info** - About, DOS shell
2. **Game** - Pause, Print, Next Turn, Quit
3. **Empire** - Send/Read messages, Trade technology, Link frequencies
4. **Worlds** - Close-up, Designate, Production, ISSP, Name, Liberate, Self-destruct, Terraform
5. **Fleet** - Deploy, Destination, Transfer, Abort/join, Refuel, SRM sweep, Orders, Cancel, Probe
6. **Build** - Site status, New construction, Abort
7. **Ministry of War** - Attack, Auto-attack, Launch LAMs, Defenses

### 8.3 Status windows

- News window showing recent events
- Help window with command reference
- Military status summary
- Production info for worlds

### 8.4 Save/Load system

**Source files**: LOADSAVE.PAS

```python
def save_game(game: GameEnvironment, slot: int):
    # Serialize game state to file
    import pickle
    with open(f"saves/save_{slot}.pkl", "wb") as f:
        pickle.dump(game, f)

def load_game(slot: int) -> GameEnvironment:
    # Load game state from file
    import pickle
    with open(f"saves/save_{slot}.pkl", "rb") as f:
        return pickle.load(f)

def auto_backup(game: GameEnvironment):
    # Automatic backup before each turn
    pass
```

### 8.5 Scenario support

**Source files**: SCENA.PAS, CODE.PAS, ARTIFACT.PAS

- Scenario file format parser
- Scenario scripting engine
- Pre-defined scenarios

**Milestone 8**: Full game experience matching original Anacreon.

---

## Phase 9: Testing & Validation

**Duration**: Weeks 21-24

### 9.1 Unit tests

```python
# tests/test_types.py
def test_empire_enum():
    assert Empire.Empire1 == 1
    assert Empire.Indep == 9

# tests/test_galaxy.py
def test_galaxy_initialization():
    galaxy = Galaxy(100, 100)
    assert galaxy.width == 100
    assert galaxy.height == 100

# tests/test_update.py
def test_planet_production():
    # Test that planet production matches Pascal calculations
    pass

# tests/test_combat.py
def test_combat_resolution():
    # Test combat outcomes against Pascal source
    pass
```

### 9.2 Integration tests

```python
def test_full_game_loop():
    game = GameEnvironment()
    game.initialize_new_game()
    
    for _ in range(10):  # 10 turns
        game.player_takes_turn()
        game.update_turn()
        game.advance_to_next_empire()
    
    assert game.Year == 4031

def test_save_load_round_trip():
    game = GameEnvironment()
    game.initialize_new_game()
    save_game(game, 1)
    loaded = load_game(1)
    assert loaded.Year == game.Year
```

### 9.3 Validation against original

- Compare combat outcomes with Pascal source
- Compare production values
- Compare tech advancement rates
- Play-test scenarios to ensure game balance matches

**Milestone 9**: All tests pass, game validated against original.

---

## Summary

This phased approach ensures:

1. **Incremental development** - Each phase builds on the previous
2. **Clear milestones** - Know when each phase is complete
3. **Early validation** - Can test core mechanics before building UI
4. **Risk mitigation** - Complex systems (combat, AI) tackled after foundation is solid
5. **Maintainability** - Code structure mirrors original for easy reference

Total estimated time: **24 weeks** for complete implementation.
