"""Global types and primitive structures.

Port of TYPES.PAS.

Pascal enums are ordinal and 0-based, so every enum here uses explicit values
matching ``Ord()`` in the original. Code elsewhere depends on those ordinals
(e.g. ``NoSRMField = Ord(Indep) * 16`` in GALAXY.PAS), so they are not
arbitrary and must not be renumbered.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

# --- Data structure constants ------------------------------------------------

MAX_NO_OF_SCENARIOS = 10
MAX_NO_OF_SAVED_GAMES = 20

MAX_NO_OF_PLANETS = 200
MAX_NO_OF_STARBASES = 100
NO_OF_FLEETS_PER_EMPIRE = 30
MAX_NO_OF_FLEETS = 240  # NO_OF_FLEETS_PER_EMPIRE * number of empires
MAX_NO_OF_STARGATES = 50
MAX_NO_OF_CONSTR_SITES = 50
MAX_NO_OF_WANDERERS = 20
MAX_NO_OF_MESSAGES = 10
MAX_NO_OF_NEWS_ITEMS = 200

NO_OF_PROBES_PER_EMPIRE = 10
NO_OF_NAMES_PER_EMPIRE = 100

MAX_NO_OF_NPE_OBJECTIVES = 25

MAX_NO_OF_PARAMETERS = 10  # number of words max in input line

MAX_RESOURCES = 9999

# Pascal subrange types. Python has no subranges; these bounds are kept as
# constants so clamping stays explicit at the assignment sites that need it.
MAX_INDEX = 100  # Index = 0..100
MAX_INDUS_INDEX = 999  # IndusIndex = 0..999
MAX_FREQ = 9999  # Freq = 0..9999


class Empire(IntEnum):
    Empire1 = 0
    Empire2 = 1
    Empire3 = 2
    Empire4 = 3
    Empire5 = 4
    Empire6 = 5
    Empire7 = 6
    Empire8 = 7
    Indep = 8


MAX_NO_OF_EMPIRES = Empire.Empire8

#: Playable empires, i.e. Pascal's ``Empire1..Empire8`` subrange used by ScoutSet.
PLAYER_EMPIRES = tuple(Empire)[:8]


class Directions(IntEnum):
    NoDir = 0
    No = 1
    Ne = 2
    Ea = 3
    Se = 4
    So = 5
    Sw = 6
    We = 7
    Nw = 8


class TechnologyTypes(IntEnum):
    """Every buildable/tradeable thing in the game, in Pascal declaration order.

    The original declares one enum and then carves subranges out of it
    (ShipTypes, CargoTypes, ConstrTypes, ...). Those subranges overlap and are
    indexed against each other -- CombatTable is indexed by AttackTypes, which
    spans defenses, ships and troops at once -- so splitting this into separate
    Python enums would break the tables. The subranges are exposed below as
    tuples instead.
    """

    NoRes = 0
    LAM = 1
    def_ = 2  # Pascal ``def``; renamed only because ``def`` is a keyword.
    GDM = 3
    ion = 4
    fgt = 5
    hkr = 6
    jmp = 7
    jtn = 8
    pen = 9
    ssp = 10
    trn = 11
    men = 12
    nnj = 13
    amb = 14
    che = 15
    met = 16
    sup = 17
    tri = 18
    SRM = 19
    cmm = 20
    frt = 21
    cmp = 22
    out = 23
    gte = 24
    lnk = 25
    dis = 26
    ter = 27


T = TechnologyTypes


def tech_range(first: T, last: T) -> tuple[T, ...]:
    """Expand a Pascal subrange ``first..last`` over TechnologyTypes."""
    return tuple(T(i) for i in range(int(first), int(last) + 1))


FIRST_RESOURCE = T.LAM
LAST_RESOURCE = T.tri

FIRST_WAR_MACHINE = T.LAM
LAST_WAR_MACHINE = T.trn

# Pascal subranges of TechnologyTypes.
RESOURCE_TYPES = tech_range(T.NoRes, T.tri)
SHIP_TYPES = tech_range(T.fgt, T.trn)
RAWM_TYPES = tech_range(T.che, T.tri)
CARGO_TYPES = tech_range(T.men, T.tri)
DEFNS_TYPES = tech_range(T.LAM, T.ion)
ATTACK_TYPES = tech_range(T.NoRes, T.nnj)

CONSTR_TYPES = tech_range(T.SRM, T.dis)
STARBASE_TYPES = tech_range(T.cmm, T.out)
STARGATE_TYPES = tech_range(T.gte, T.dis)

# Readability aliases: these name the *intent* at a use site. They are all the
# same enum, matching Pascal, where the subrange types are assignment
# compatible with each other.
ShipTypes = TechnologyTypes
CargoTypes = TechnologyTypes
RawMTypes = TechnologyTypes
DefnsTypes = TechnologyTypes
AttackTypes = TechnologyTypes
ResourceTypes = TechnologyTypes
ConstrTypes = TechnologyTypes
StarbaseTypes = TechnologyTypes
StargateTypes = TechnologyTypes


class TechLevel(IntEnum):
    PreTchLvl = 0
    PrimitLvl = 1
    PreAtmLvl = 2
    AtomicLvl = 3
    PreWrpLvl = 4
    WrpTchLvl = 5
    JmpTchLvl = 6
    BioTchLvl = 7
    StrTchLvl = 8
    PreGteLvl = 9
    GteTchLvl = 10


class WorldClass(IntEnum):
    AmbCls = 0
    ArdCls = 1
    ArtCls = 2
    BarCls = 3
    ClsJ = 4
    ClsK = 5
    ClsL = 6
    ClsM = 7
    DrtCls = 8
    EthCls = 9
    FstCls = 10
    GsGCls = 11
    HLfCls = 12
    IceCls = 13
    JngCls = 14
    OcnCls = 15
    ParCls = 16
    PsnCls = 17
    RnsCls = 18
    UndCls = 19
    TerCls = 20
    VlcCls = 21


class WorldTypes(IntEnum):
    AgrTyp = 0
    AmbTyp = 1
    BseTyp = 2
    BseSTyp = 3
    CapTyp = 4
    CheTyp = 5
    IndTyp = 6
    JmpTyp = 7
    JmpSTyp = 8
    MinTyp = 9
    NnjTyp = 10
    OutTyp = 11
    RawTyp = 12
    RawSTyp = 13
    StrTyp = 14
    StrSTyp = 15
    TrnTyp = 16
    TrnSTyp = 17
    RsrTyp = 18
    TerTyp = 19
    TriTyp = 20


class IndusTypes(IntEnum):
    BioInd = 0
    CheInd = 1
    MinInd = 2
    SYGInd = 3
    SYJInd = 4
    SYSInd = 5
    SYTInd = 6
    SupInd = 7
    TriInd = 8


class SpecialConditions(IntEnum):
    AmbAddict = 0
    Holocst = 1
    Plague = 2
    SelfSuff = 3
    Virgin = 4


class EmpireModifiers(IntEnum):
    CentralEMD = 0  # Empire lost if capital conquered.
    Reserved1EMD = 1
    Reserved2EMD = 2
    Reserved3EMD = 3
    Reserved4EMD = 4
    Reserved5EMD = 5
    Reserved6EMD = 6


class FleetTypes(IntEnum):
    Standard = 0
    JumpFleet = 1
    HKFleet = 2
    Penetrator = 3
    AdvWrpFleet = 4


class FleetStatus(IntEnum):
    FReady = 0
    FInTrans = 1
    FInactive = 2
    FLost = 3


class ProbeStatus(IntEnum):
    PReady = 0
    PInTrans = 1
    PAtDest = 2
    PLost = 3


class ObjectTypes(IntEnum):
    Void = 0
    Con = 1
    Pln = 2
    Base = 3
    Gate = 4
    BlkHl = 5
    Plsr = 6
    WrmHl = 7
    Flt = 8
    DestFlt = 9
    Wndr = 10
    ArtOBJ = 11


#: Pascal ``PhenomenaTypes = Void..WrmHl``.
PHENOMENA_TYPES = tuple(ObjectTypes)[: int(ObjectTypes.WrmHl) + 1]


class NebulaTypes(IntEnum):
    NoNeb = 0
    Nebula = 1
    DarkNebula = 2
    DenseNebula = 3


class ShellPos(IntEnum):
    """Orbital shells, outermost first. Combat resolves in this order."""

    DpSpc = 0
    HiOrb = 1
    Orbit = 2
    SbOrb = 3
    Grnd = 4


@dataclass(slots=True)
class IDNumber:
    """Reference to an object: its kind plus its 1-based index in that array."""

    ObjTyp: ObjectTypes = ObjectTypes.Void
    Index: int = 0


def empty_quadrant() -> IDNumber:
    """Pascal's ``EmptyQuadrant`` constant.

    A function rather than a module-level value: the Pascal original is a typed
    constant that callers copy, and a shared mutable dataclass instance would
    alias instead.
    """
    return IDNumber(ObjectTypes.Void, 0)


# --- Array helpers -----------------------------------------------------------
#
# Pascal arrays indexed by a subrange become dicts keyed by the same enum
# members, so table lookups read the same as the original.


def ship_array() -> dict[TechnologyTypes, int]:
    return dict.fromkeys(SHIP_TYPES, 0)


def cargo_array() -> dict[TechnologyTypes, int]:
    return dict.fromkeys(CARGO_TYPES, 0)


def defns_array() -> dict[TechnologyTypes, int]:
    return dict.fromkeys(DEFNS_TYPES, 0)


def resource_array() -> dict[TechnologyTypes, int]:
    return dict.fromkeys(tech_range(T.LAM, T.tri), 0)


def indus_array() -> dict[IndusTypes, int]:
    return dict.fromkeys(IndusTypes, 0)


def indus_r_array() -> dict[IndusTypes, float]:
    return dict.fromkeys(IndusTypes, 0.0)
