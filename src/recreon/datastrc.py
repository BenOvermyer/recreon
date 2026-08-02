"""Universe data structures.

Port of DATASTRC.PAS.

Two things from the original are deliberately dropped:

* ``Reserved: ARRAY [1..n] OF Byte`` padding fields. They exist to hold the
  on-disk record size steady across versions; save/load (Phase 8) will handle
  layout explicitly rather than carrying dead fields around.
* ``GlobalSets: GlobalSetsRecord ABSOLUTE SetOfActiveFleets``, a Turbo Pascal
  aliasing trick that overlays one record on the loose globals so they can be
  written out in one block. Here there is just the one GlobalSets object.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .galaxy import Location, XYCoord
from .types import (
    MAX_NO_OF_CONSTR_SITES,
    MAX_NO_OF_FLEETS,
    MAX_NO_OF_PLANETS,
    MAX_NO_OF_STARBASES,
    MAX_NO_OF_STARGATES,
    NO_OF_PROBES_PER_EMPIRE,
    SHIP_TYPES,
    Empire,
    EmpireModifiers,
    FleetStatus,
    IDNumber,
    IndusTypes,
    ProbeStatus,
    ShellPos,
    SpecialConditions,
    TechLevel,
    TechnologyTypes,
    WorldClass,
    WorldTypes,
    cargo_array,
    defns_array,
    indus_array,
    ship_array,
)


@dataclass(slots=True)
class PlanetRecord:
    XY: XYCoord = field(default_factory=XYCoord)
    Emp: Empire = Empire.Indep
    #: Empires that have scouted it.
    ScoutedBy: set[Empire] = field(default_factory=set)
    #: Empires that know of it.
    KnownBy: set[Empire] = field(default_factory=set)

    Cls: WorldClass = WorldClass.BarCls
    Typ: WorldTypes = WorldTypes.OutTyp
    #: Packed import/export setting per RawMType (see DEFAULT_ISSP).
    ImpExp: int = 0
    Tech: TechLevel = TechLevel.PreTchLvl
    Eff: int = 0  # efficiency, 0-100%
    RevIndex: int = 0  # revolution index, 0-100
    Special: set[SpecialConditions] = field(default_factory=set)
    TerraformTarget: WorldClass = WorldClass.BarCls

    Pop: int = 0
    Ships: dict[TechnologyTypes, int] = field(default_factory=ship_array)
    Cargo: dict[TechnologyTypes, int] = field(default_factory=cargo_array)
    Defns: dict[TechnologyTypes, int] = field(default_factory=defns_array)
    Indus: dict[IndusTypes, int] = field(default_factory=indus_array)

    TriReserve: int = 0

    #: Link to the next object in the same sector.
    NextID: IDNumber = field(default_factory=IDNumber)


@dataclass(slots=True)
class StarbaseRecord:
    XY: XYCoord = field(default_factory=XYCoord)
    Emp: Empire = Empire.Indep
    ScoutedBy: set[Empire] = field(default_factory=set)
    KnownBy: set[Empire] = field(default_factory=set)

    #: Starbase kind: one of STARBASE_TYPES (cmm, frt, cmp, out).
    STyp: TechnologyTypes = TechnologyTypes.cmm
    Typ: WorldTypes = WorldTypes.BseTyp
    Tech: TechLevel = TechLevel.PreTchLvl
    Eff: int = 0
    RevIndex: int = 0
    Special: set[SpecialConditions] = field(default_factory=set)

    Pop: int = 0
    Ships: dict[TechnologyTypes, int] = field(default_factory=ship_array)
    Cargo: dict[TechnologyTypes, int] = field(default_factory=cargo_array)
    Defns: dict[TechnologyTypes, int] = field(default_factory=defns_array)
    Indus: dict[IndusTypes, int] = field(default_factory=indus_array)

    #: Years until the starbase moves.
    Move: int = 0
    Dest: XYCoord = field(default_factory=XYCoord)
    Status: FleetStatus = FleetStatus.FReady

    NextID: IDNumber = field(default_factory=IDNumber)


@dataclass(slots=True)
class FleetRecord:
    XY: XYCoord = field(default_factory=XYCoord)
    Emp: Empire = Empire.Indep
    ScoutedBy: set[Empire] = field(default_factory=set)

    Ships: dict[TechnologyTypes, int] = field(default_factory=ship_array)
    Cargo: dict[TechnologyTypes, int] = field(default_factory=cargo_array)

    Dest: XYCoord = field(default_factory=XYCoord)
    Status: FleetStatus = FleetStatus.FReady

    #: Fuel is carried as ``FuelHigh * MaxInt + Fuel`` in the original, because
    #: a 16-bit Integer could not hold the range. Both halves are kept so the
    #: arithmetic in FLEET.PAS ports directly; see :func:`fuel_of`.
    FuelHigh: int = 0
    Fuel: int = 0

    KnownBy: set[Empire] = field(default_factory=set)

    #: Index of the next order to execute, 1-based; 0 means "no orders".
    NextOrder: int = 0
    #: The compiled order list. Declared ``ARRAY [1..6] OF Byte`` in the
    #: original and type-punned to an ``OrderStructure`` (a length and a heap
    #: pointer) by ORDERS.PAS; here it just holds the commands.
    OrderData: list = field(default_factory=list)

    NPEDataIndex: int = 0

    NextID: IDNumber = field(default_factory=IDNumber)


#: Turbo Pascal's ``MaxInt`` for a 16-bit Integer, the multiplier in the
#: split-fuel representation above.
MAXINT16 = 32767


def fuel_of(fleet: FleetRecord) -> int:
    """Total fuel a fleet carries, recombining the split representation."""
    return fleet.FuelHigh * MAXINT16 + fleet.Fuel


def set_fuel(fleet: FleetRecord, total: int) -> None:
    """Store ``total`` back into the split representation."""
    fleet.FuelHigh, fleet.Fuel = divmod(total, MAXINT16)


@dataclass(slots=True)
class StargateRecord:
    XY: XYCoord = field(default_factory=XYCoord)
    Emp: Empire = Empire.Indep
    ScoutedBy: set[Empire] = field(default_factory=set)
    KnownBy: set[Empire] = field(default_factory=set)

    #: Gate kind: one of STARGATE_TYPES (gte, lnk, dis).
    GTyp: TechnologyTypes = TechnologyTypes.gte
    Dest: XYCoord = field(default_factory=XYCoord)
    #: Warp Link Frequency per empire, including Indep.
    WLF: dict[Empire, int] = field(default_factory=lambda: dict.fromkeys(Empire, 0))

    NextID: IDNumber = field(default_factory=IDNumber)


@dataclass(slots=True)
class ConstrRecord:
    XY: XYCoord = field(default_factory=XYCoord)
    Emp: Empire = Empire.Indep
    ScoutedBy: set[Empire] = field(default_factory=set)
    KnownBy: set[Empire] = field(default_factory=set)

    #: What is being built: one of CONSTR_TYPES.
    CTyp: TechnologyTypes = TechnologyTypes.SRM
    TimeToCompletion: int = 0

    NextID: IDNumber = field(default_factory=IDNumber)


@dataclass(slots=True)
class NameRecord:
    """Player-assigned name for a location. A linked list in the original.

    ``Coord`` is a full :class:`~recreon.galaxy.Location`, not a bare
    coordinate: a name can be pinned to an object that moves (a fleet) as
    readily as to a fixed point in space.
    """

    Name: str = ""
    Coord: Location = field(default_factory=Location)


def defense_distribution_array() -> dict[ShellPos, dict[TechnologyTypes, int]]:
    """Percent of each ship type to place in each orbital shell."""
    return {shell: dict.fromkeys(SHIP_TYPES, 0) for shell in ShellPos}


@dataclass(slots=True)
class DefenseRecord:
    ShellDefDist: dict[ShellPos, dict[TechnologyTypes, int]] = field(
        default_factory=defense_distribution_array
    )
    StarbaseDefDist: dict[ShellPos, dict[TechnologyTypes, int]] = field(
        default_factory=defense_distribution_array
    )


@dataclass(slots=True)
class ProbeRecord:
    Dest: XYCoord = field(default_factory=XYCoord)
    Status: ProbeStatus = ProbeStatus.PReady


@dataclass(slots=True)
class EmpireDataRecord:
    InUse: bool = False
    IsAPlayer: bool = False
    EmpireName: str = ""
    Pass: str = ""

    TimeLeft: int = 0
    Capital: IDNumber = field(default_factory=IDNumber)

    DefenseSettings: DefenseRecord = field(default_factory=DefenseRecord)

    Probe: list[ProbeRecord] = field(
        default_factory=lambda: [ProbeRecord() for _ in range(NO_OF_PROBES_PER_EMPIRE + 1)]
    )

    #: Pascal keeps a linked list plus a tail pointer; a list serves both.
    Names: list[NameRecord] = field(default_factory=list)

    #: Adjustment applied to every world's individual revolution index.
    TotalRevIndex: int = 0

    TechnologyLevel: TechLevel = TechLevel.PreTchLvl
    Technology: set[TechnologyTypes] = field(default_factory=set)

    IsAnEmpress: bool = False
    #: Permanent adjustment to TotalRevIndex.
    RevFactor: int = 0
    Founding: int = 0
    Modifiers: set[EmpireModifiers] = field(default_factory=set)


def _one_based(size: int, factory) -> list:
    """Pascal ``ARRAY [1..size]`` as a list of ``size + 1`` with index 0 unused."""
    return [None] + [factory() for _ in range(size)]


@dataclass(slots=True)
class GlobalSetsRecord:
    SetOfActiveFleets: set[int] = field(default_factory=set)
    SetOfFleetsOf: dict[Empire, set[int]] = field(
        default_factory=lambda: {e: set() for e in Empire}
    )
    SetOfActivePlanets: set[int] = field(default_factory=set)
    SetOfPlanetsOf: dict[Empire, set[int]] = field(
        default_factory=lambda: {e: set() for e in Empire}
    )
    SetOfActiveStarbases: set[int] = field(default_factory=set)
    SetOfStarbasesOf: dict[Empire, set[int]] = field(
        default_factory=lambda: {e: set() for e in Empire}
    )
    SetOfActiveGates: set[int] = field(default_factory=set)
    SetOfActiveConstructionSites: set[int] = field(default_factory=set)
    SetOfConstructionSitesOf: dict[Empire, set[int]] = field(
        default_factory=lambda: {e: set() for e in Empire}
    )


@dataclass(slots=True)
class UniverseRecord:
    """Everything in the game world.

    All entity lists are 1-based: index 0 is unused and holds ``None``, so
    index arithmetic ports from the Pascal without adjustment.

    ``Fleet`` is an array of pointers in the original and is the one list whose
    slots are genuinely nullable at runtime -- an absent fleet is ``None``.
    """

    Planet: list[PlanetRecord | None] = field(
        default_factory=lambda: _one_based(MAX_NO_OF_PLANETS, PlanetRecord)
    )
    Starbase: list[StarbaseRecord | None] = field(
        default_factory=lambda: _one_based(MAX_NO_OF_STARBASES, StarbaseRecord)
    )
    Fleet: list[FleetRecord | None] = field(
        default_factory=lambda: [None] * (MAX_NO_OF_FLEETS + 1)
    )
    Stargate: list[StargateRecord | None] = field(
        default_factory=lambda: _one_based(MAX_NO_OF_STARGATES, StargateRecord)
    )
    Constr: list[ConstrRecord | None] = field(
        default_factory=lambda: _one_based(MAX_NO_OF_CONSTR_SITES, ConstrRecord)
    )
    EmpireData: dict[Empire, EmpireDataRecord] = field(
        default_factory=lambda: {e: EmpireDataRecord() for e in Empire}
    )
