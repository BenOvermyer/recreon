# Translation Notes: Pascal to Python

This document covers the key patterns and gotchas when translating the Anacreon Pascal source code to Python.

---

## Data Structures

### Records → Dataclasses

**Pascal:**
```pascal
PlanetRecord = RECORD
   XY: XYCoord;
   Emp: Empire;
   Cls: WorldClass;
   Pop: Population;
   Ships: ShipArray;
END;
```

**Python:**
```python
@dataclass
class PlanetRecord:
    XY: XYCoord
    Emp: Empire
    Cls: WorldClass
    Pop: int
    Ships: dict[ShipTypes, int]
```

**Notes:**
- Use `@dataclass` decorator for clean syntax
- Add type hints for all fields
- Default values use `field(default_factory=...)` for mutable types
- No need for `WITH ... DO` - just access attributes directly

### Arrays → Lists

**Pascal:**
```pascal
TYPE
   ShipArray = ARRAY [fgt..trn] OF Word;
   PlanetArray = ARRAY [1..200] OF PlanetRecord;
```

**Python:**
```python
# Option 1: Use dict for named indices
ShipArray = dict[ShipTypes, int]

# Option 2: Use list with 0-index unused
PlanetArray = list[Optional[PlanetRecord]]  # [0..200], index 0 unused
```

**Notes:**
- Pascal arrays can have any index range; Python lists are always 0-indexed
- **Strategy**: Keep 1-based indexing to match Pascal (index 0 unused)
- For enum-indexed arrays (like ShipArray), use `dict[EnumType, value_type]`
- Initialize lists with `None` for empty slots: `[None] * 201`

### Sets → set or IntFlag

**Pascal:**
```pascal
TYPE
   SetOfEmpires = SET OF Empire;
   SetOfSpecialConditions = SET OF SpecialCondition;
```

**Python:**
```python
# Option 1: Python set
SetOfEmpires = set[Empire]

# Option 2: IntFlag for bit operations
from enum import IntFlag

class SpecialConditions(IntFlag):
    AmbrosiaAddiction = 1 << 0
    Holocaust = 1 << 1
    Plague = 1 << 2
    SelfSufficient = 1 << 3
    Virgin = 1 << 4
```

**Notes:**
- Python `set` is more idiomatic for most cases
- Use `IntFlag` only if you need bit operations (AND, OR, XOR)
- Pascal `IN` operator → Python `in` operator

### Pointers → Direct References

**Pascal:**
```pascal
TYPE
   FleetRecordPtr = ^FleetRecord;
   
VAR
   Fleet: ARRAY [1..240] OF FleetRecordPtr;

BEGIN
   New(Fleet[1]);
   Fleet[1]^.Ships[fgt] := 100;
END;
```

**Python:**
```python
from typing import Optional

Fleet = list[Optional[FleetRecord]]

# Initialize
fleet = [None] * 241  # 0 unused

# Create new fleet
fleet[1] = FleetRecord()
fleet[1].Ships[ShipTypes.fgt] = 100
```

**Notes:**
- Python objects are already references
- No need for `New()` or `Dispose()`
- Use `Optional[T]` for nullable references
- Garbage collector handles cleanup

---

## Control Flow

### CASE Statement → match/case

**Pascal:**
```pascal
CASE ObjType OF
   Pln: HandlePlanet;
   Base: HandleBase;
   Flt: HandleFleet;
   ELSE HandleVoid;
END;
```

**Python (3.10+):**
```python
match obj_type:
    case ObjectTypes.Pln:
        handle_planet()
    case ObjectTypes.Base:
        handle_base()
    case ObjectTypes.Flt:
        handle_fleet()
    case _:
        handle_void()
```

**Notes:**
- Python 3.10+ has structural pattern matching
- Use `_` for default case (like `ELSE`)
- Can match on enum values, types, and complex patterns

### FOR Loop → for loop

**Pascal:**
```pascal
FOR i := 1 TO 200 DO
   UpdatePlanet(i);
```

**Python:**
```python
for i in range(1, 201):  # 201 is exclusive
    update_planet(i)
```

**Notes:**
- Python `range(start, end)` is exclusive of `end`
- Pascal `TO` is inclusive
- Adjust: `FOR i := 1 TO N` → `range(1, N+1)`

### WHILE Loop → while loop

**Pascal:**
```pascal
WHILE (Fleet.Status = InTrans) AND (Fuel > 0) DO
   MoveFleet;
```

**Python:**
```python
while fleet.Status == FleetStatus.InTrans and fleet.Fuel > 0:
    move_fleet()
```

**Notes:**
- Syntax is nearly identical
- Python uses `and`/`or` instead of `AND`/`OR`
- Python uses `==` for comparison (not `=`)

---

## Global Variables → GameEnvironment Class

**Pascal:**
```pascal
VAR
   Year: Word;
   Player: Empire;
   Universe: ^UniverseRecord;

PROCEDURE UpdateTurn;
BEGIN
   Year := Year + 1;
   UpdateUniverse(Universe);
END;
```

**Python:**
```python
class GameEnvironment:
    def __init__(self):
        self.Year: int = 4021
        self.Player: Empire = Empire.Empire1
        self.Universe: UniverseRecord = UniverseRecord()
    
    def update_turn(self):
        self.Year += 1
        self.update_universe()
    
    def update_universe(self):
        # Update all entities
        pass
```

**Notes:**
- Encapsulate all global state in a class
- Pass `game` instance to functions that need it
- Makes testing easier (can create multiple game instances)
- Alternative: Use `contextvars` for implicit passing

---

## Index Adjustments

### 1-Based → 1-Based (Keep Same)

**Strategy**: Maintain 1-based indexing to match Pascal source.

**Pascal:**
```pascal
Planet: ARRAY [1..200] OF PlanetRecord;
```

**Python:**
```python
Planet: list[Optional[PlanetRecord]] = [None] * 201  # Index 0 unused
```

**Notes:**
- Allocate `N+1` elements for 1-based indexing
- Index 0 is always `None` or unused
- Makes direct comparison with Pascal source easier
- Slight memory overhead (negligible for this game)

### Alternative: 0-Based (Adjust Indices)

If you prefer Pythonic 0-based indexing:

```python
Planet: list[PlanetRecord] = []

# When accessing Pascal code:
# Pascal: Planet[i] where i in [1..200]
# Python: Planet[i-1] where i in [1..200]

# When displaying to user:
# Python: Planet[i] where i in [0..199]
# Display: i+1
```

**Recommendation**: Use 1-based indexing for this project to minimize translation errors.

---

## Memory Management

### Heap Allocation → Automatic GC

**Pascal:**
```pascal
TYPE
   FleetRecordPtr = ^FleetRecord;

VAR
   FleetPtr: FleetRecordPtr;

BEGIN
   New(FleetPtr);
   FleetPtr^.Ships[fgt] := 100;
   { ... use fleet ... }
   Dispose(FleetPtr);
END;
```

**Python:**
```python
fleet = FleetRecord()
fleet.Ships[ShipTypes.fgt] = 100
# ... use fleet ...
# No need to dispose - garbage collector handles it
```

**Notes:**
- Python automatically manages memory
- No `New()` or `Dispose()` needed
- Objects are destroyed when no references remain
- Use `del` only if you need to explicitly remove a reference

### Dynamic Arrays → Lists

**Pascal:**
```pascal
TYPE
   DynamicArray = ARRAY [1..1] OF PlanetRecord;
   DynamicArrayPtr = ^DynamicArray;

VAR
   Planets: DynamicArrayPtr;
   NoOfPlanets: Word;

BEGIN
   GetMem(Planets, SizeOf(PlanetRecord) * 200);
   NoOfPlanets := 0;
   
   { Add planet }
   Inc(NoOfPlanets);
   Planets^[NoOfPlanets] := NewPlanet;
END;
```

**Python:**
```python
Planets: list[PlanetRecord] = []
NoOfPlanets: int = 0

# Add planet
planets.append(new_planet)
NoOfPlanets = len(planets)
```

**Notes:**
- Python lists are dynamic arrays
- Use `append()`, `insert()`, `pop()` for dynamic sizing
- No need for manual memory allocation

---

## Overlay System → Lazy Imports

**Pascal:**
```pascal
{$O PlayTurn}
UNIT PlayTurn;
```

**Python:**
```python
# Option 1: Lazy import
def player_takes_turn():
    from .playturn import play_turn
    play_turn()

# Option 2: importlib for dynamic loading
import importlib

def load_module(module_name):
    return importlib.import_module(f"recreon.{module_name}")
```

**Notes:**
- Pascal overlays loaded code on demand to save memory
- Python doesn't need this (much more memory available)
- Use lazy imports only if startup time is an issue
- For this project, regular imports are fine

---

## String Handling

### Pascal Strings → Python str

**Pascal:**
```pascal
VAR
   Name: STRING[30];
   
BEGIN
   Name := 'Earth';
   Length := Length(Name);
   Copy := Copy(Name, 1, 3);
END;
```

**Python:**
```python
name: str = "Earth"
length: int = len(name)
copy: str = name[0:3]  # "Ea"
```

**Notes:**
- Python strings are immutable
- No length limit (Pascal had `STRING[n]`)
- Slicing: `s[start:end]` (end exclusive)
- Use f-strings for formatting: `f"Year {year}"`

### String Concatenation

**Pascal:**
```pascal
FullName := FirstName + ' ' + LastName;
```

**Python:**
```python
full_name = f"{first_name} {last_name}"
# or
full_name = first_name + " " + last_name
```

---

## File I/O

### Pascal File I/O → Python File I/O

**Pascal:**
```pascal
VAR
   f: FILE OF UniverseRecord;
   
BEGIN
   Assign(f, 'savegame.dat');
   Rewrite(f);
   Write(f, Universe^);
   Close(f);
END;
```

**Python:**
```python
import pickle

# Save
with open('savegame.pkl', 'wb') as f:
    pickle.dump(game.universe, f)

# Load
with open('savegame.pkl', 'rb') as f:
    universe = pickle.load(f)
```

**Notes:**
- Use `pickle` for binary serialization
- Use `json` for human-readable format
- Always use `with` statement for file handling
- Consider compression for large save files

---

## Type Conversion

### Ordinal Types → Enum/IntEnum

**Pascal:**
```pascal
TYPE
   Empire = (Empire1, Empire2, ..., Empire8, Indep);
   TechLevel = 0..10;
```

**Python:**
```python
from enum import Enum, IntEnum

class Empire(IntEnum):
    Empire1 = 1
    Empire2 = 2
    # ...
    Indep = 9

class TechLevel(IntEnum):
    PreTech = 0
    Primitive = 1
    # ...
    Gate = 10
```

**Notes:**
- Use `IntEnum` when you need numeric values
- Use `Enum` for pure symbolic constants
- Can iterate over enums: `for empire in Empire:`
- Access by value: `Empire(1)` → `Empire.Empire1`

---

## Common Gotchas

### 1. Array Bounds

**Pascal:**
```pascal
FOR i := 1 TO 200 DO  { 1 to 200 inclusive }
```

**Python:**
```python
for i in range(1, 201):  # 1 to 200 inclusive (201 exclusive)
```

### 2. Boolean Operators

**Pascal:**
```pascal
IF (a > 0) AND (b < 10) THEN ...
```

**Python:**
```python
if a > 0 and b < 10:
    ...
```

### 3. Assignment vs Comparison

**Pascal:**
```pascal
x := 5;      { Assignment }
IF x = 5 THEN ...  { Comparison }
```

**Python:**
```python
x = 5        # Assignment
if x == 5:   # Comparison
    ...
```

### 4. Integer Division

**Pascal:**
```pascal
x := 10 DIV 3;  { Integer division: 3 }
y := 10 / 3;    { Real division: 3.333... }
```

**Python:**
```python
x = 10 // 3  # Integer division: 3
y = 10 / 3   # Float division: 3.333...
```

### 5. Case Sensitivity

**Pascal:** Case-insensitive (`BEGIN` = `begin`)
**Python:** Case-sensitive (`True` ≠ `true`)

### 6. Semicolons

**Pascal:** Required at end of statements
**Python:** Not used (newlines separate statements)

---

## Testing Strategy

### Unit Tests

```python
import pytest
from recreon.types import Empire, ShipTypes
from recreon.datastrc import FleetRecord

def test_fleet_creation():
    fleet = FleetRecord()
    fleet.Ships[ShipTypes.fgt] = 100
    assert fleet.Ships[ShipTypes.fgt] == 100

def test_empire_enum():
    assert Empire.Empire1 == 1
    assert Empire.Indep == 9
```

### Validation Against Pascal

For critical calculations (combat, production):

1. Extract test cases from Pascal source
2. Implement in Python
3. Compare outputs
4. Iterate until matches

```python
def test_combat_matches_pascal():
    # Test case from Pascal source
    attacker = create_test_fleet(ships={ShipTypes.ssp: 10})
    defender = create_test_world(ships={ShipTypes.fgt: 1000})
    
    result = resolve_battle(attacker, defender)
    
    # Expected values from Pascal
    assert result.attacker_losses[ShipTypes.ssp] == 2
    assert result.defender_losses[ShipTypes.fgt] == 800
```

---

## Performance Considerations

### When to Optimize

1. **Don't optimize prematurely** - Get it working first
2. **Profile before optimizing** - Use `cProfile` to find bottlenecks
3. **Focus on hot loops** - Update functions, combat resolution

### Optimization Techniques

```python
# Use numpy for large arrays
import numpy as np

# Instead of list of lists
galaxy = [[0] * 100 for _ in range(100)]

# Use numpy array
galaxy = np.zeros((100, 100), dtype=int)

# Use dataclass slots for memory efficiency
@dataclass(slots=True)
class PlanetRecord:
    XY: XYCoord
    Emp: Empire
    # ...
```

---

## Summary

Key translation patterns:

| Pascal | Python |
|--------|--------|
| `RECORD` | `@dataclass` |
| `ARRAY [1..N]` | `list[T]` (1-based, index 0 unused) |
| `SET OF T` | `set[T]` or `IntFlag` |
| `^Pointer` | Direct object reference |
| `CASE ... OF` | `match ... case` |
| `FOR i := 1 TO N` | `for i in range(1, N+1)` |
| `New(p)` | `obj = Class()` |
| `Dispose(p)` | Automatic GC |
| Global variables | `GameEnvironment` class |
| Overlay units | Regular imports |

**Golden Rule**: When in doubt, match the Pascal source exactly. Optimize for correctness first, Pythonic style second.
