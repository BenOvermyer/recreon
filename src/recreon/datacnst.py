"""Game balance constants and tables.

Port of DATACNST.PAS. Every value here is transcribed verbatim from the
original; none of it is derived or tuned. Changing a number here changes game
balance, so treat this file as data, not code.

Pascal arrays indexed by an enum become dicts keyed by the same enum, built
through :func:`_table`, which fails at import time if a row's length does not
match its key set. That check is the safety net for a bulk transcription.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import TypeVar

from .datastrc import DefenseRecord
from .types import (
    ATTACK_TYPES,
    CARGO_TYPES,
    CONSTR_TYPES,
    DEFNS_TYPES,
    RESOURCE_TYPES,
    SHIP_TYPES,
    STARBASE_TYPES,
    STARGATE_TYPES,
    Directions,
    FleetTypes,
    IndusTypes,
    ObjectTypes,
    ShellPos,
    TechLevel,
    TechnologyTypes,
    WorldClass,
    WorldTypes,
    tech_range,
)

K = TypeVar("K")
V = TypeVar("V")

T = TechnologyTypes
TL = TechLevel
WC = WorldClass
WT = WorldTypes
IT = IndusTypes


def _table(keys: Iterable[K], values: Sequence[V]) -> dict[K, V]:
    keys = tuple(keys)
    if len(keys) != len(values):
        raise ValueError(f"table has {len(values)} values for {len(keys)} keys")
    return dict(zip(keys, values, strict=True))


# --- Constants used in calculations ------------------------------------------

# TIP constants. The coefficient and exponent control the effect population has
# on the TIP; raising either increases it.
K1 = 1.76
K2 = 10
K3 = 0.75

# Absolute Production constants.
K4 = 0.0
K5 = 2.0  # DO NOT change
K6 = 11000.0

#: Safety margin applied to industrial distribution.
SAFETY_ADJ = 1.05

# Ambrosia.
AMBROSIA_ADJ = 1.45  # industry increase from ambrosia addiction
DRUGS_PER_BILLION = 11.5  # kilotons of ambrosia per billion people
CHANCE_TO_ADDICT = 25  # % chance per year to become addicted
ADDICT_DEATH_COEFF = 0.12  # tens of millions of deaths per ton lacking
ADDICT_EFF_COEFF = 0.9  # points of efficiency lost per death
ADDICT_REV_I_COEFF = 0.55  # points of revolution index per death

#: Megatons of supplies needed per billion people.
SUPPLIES_PER_BILLION = 25

# Chance per year of obtaining new technology.
TECH_INC_CAP = 12  # % for capital
TECH_INC_UNV = 15  # % per university world
TECH_INC_RNS = 5  # % per ruins world
TECH_INC_UNV_RNS = 17  # % for a university on a ruins world

TECH_LVL_INC = 16  # % chance a world has of increasing tech


# --- Names -------------------------------------------------------------------

TechnologyName: dict[T, str] = _table(
    TechnologyTypes,
    (
        "",
        "LAM",
        "defense satellite",
        "GDM",
        "ion cannon",
        "fighter",
        "hunter-killer",
        "jumpship",
        "jumptransport",
        "penetrator",
        "starship",
        "transport",
        "troop",
        "ninja",
        "ambrosia",
        "chemical",
        "metal",
        "supply",
        "trillum",
        "SRM",
        "command base",
        "fortress",
        "industrial complex",
        "outpost",
        "gate",
        "link",
        "disrupter",
        "terraforming",
    ),
)

TypeName: dict[WT, str] = _table(
    WorldTypes,
    (
        "agricultural world",
        "ambrosia world",
        "base planet",
        "base planet",
        "capital",
        "chemical planet",
        "independent world",
        "jumpship base",
        "jumpship base",
        "metal mine",
        "ninja world",
        "outpost",
        "raw material mine",
        "raw material mine",
        "starship base",
        "starship base",
        "transport base",
        "transport base",
        "university world",
        "terraforming",
        "trillum mine",
    ),
)

ThingNames: dict[T, str] = _table(
    RESOURCE_TYPES,
    (
        "",
        "LAMs",
        "defense satellites",
        "GDMs",
        "ion canons",
        "fighter squadrons",
        "hunter-killers",
        "jumpships",
        "jumptransports",
        "penetrators",
        "starships",
        "transports",
        "legions",
        "ninja legions",
        "kilotons of ambrosia",
        "megatons of chemicals",
        "megatons of metals",
        "megatons of supplies",
        "kilotons of trillum",
    ),
)

IndusNames: dict[IT, str] = _table(
    IndusTypes,
    (
        "bio-tech labs",
        "chemical plants",
        "metal mines",
        "ship yards",
        "jumpship yards",
        "starship yards",
        "transport yards",
        "food factories",
        "trillum mines",
    ),
)

ObjName: dict[ObjectTypes, str] = _table(
    ObjectTypes,
    (
        "",
        "construction",
        "star system",
        "starbase",
        "stargate",
        "black hole",
        "pulsar",
        "worm hole",
        "fleet",
        "(destroyed)",
        "unknown",
        "artifact",
    ),
)

TechN: dict[TL, str] = _table(
    TechLevel,
    (
        "pre-tech",
        "primitive",
        "pre-atomic",
        "atomic",
        "pre-warp",
        "warp",
        "jump",
        "bio-tech",
        "starship",
        "pre-gate",
        "gate",
    ),
)


# --- Map glyphs --------------------------------------------------------------
#
# Single-character map symbols. The starbase and stargate tables hold raw
# CP437 byte values in the original (high-bit and control-range positions that
# the DOS font renders as shapes and arrows); decoding them for display is the
# UI layer's job.

TypeStr: dict[WT, str] = _table(WorldTypes, tuple("aAbBCcijJmNorRsStTUXz"))
ClassStr: dict[WC, str] = _table(WorldClass, tuple("Aa0BjklmDEFGhIJO1P2UXV"))
TechStr: dict[TL, str] = _table(
    TechLevel,
    ("pt", " p", "pa", " a", "pw", " w", " j", " b", " s", "pg", " g"),
)
SYLetN: dict[IT, str] = _table(IndusTypes, tuple("---AJST--"))

#: CP437 code points: 0xFE, 0xF0, 0xE3, 'o'.
BaseTypeData: dict[T, int] = _table(STARBASE_TYPES, (0xFE, 0xF0, 0xE3, 0x6F))

#: CP437 code points: 0x12, 0x18, '@'.
GateTypeData: dict[T, int] = _table(STARGATE_TYPES, (0x12, 0x18, 0x40))


# --- Terraforming ------------------------------------------------------------

#: Classes a world of a given class can terraform into. The original is
#: ``ARRAY [WorldClass, 1..10]`` and is rolled against with a 1-based index, so
#: index 0 of each row is left unused.
TerraformPotentialClasses: dict[WC, tuple[WC | None, ...]] = _table(
    WorldClass,
    (
        # 1        2        3        4        5        6        7        8        9        10
        (None, WC.OcnCls, WC.ClsM, WC.ClsJ, WC.AmbCls, WC.AmbCls, WC.AmbCls, WC.AmbCls, WC.AmbCls, WC.AmbCls, WC.AmbCls),  # AmbCls
        (None, WC.DrtCls, WC.ArdCls, WC.ArdCls, WC.ArdCls, WC.ArdCls, WC.ArdCls, WC.ArdCls, WC.ArdCls, WC.ArdCls, WC.ArdCls),  # ArdCls
        (None, WC.ArtCls, WC.ArtCls, WC.ArtCls, WC.ArtCls, WC.ArtCls, WC.ArtCls, WC.ArtCls, WC.ArtCls, WC.ArtCls, WC.ArtCls),  # ArtCls
        (None, WC.VlcCls, WC.BarCls, WC.BarCls, WC.BarCls, WC.BarCls, WC.BarCls, WC.BarCls, WC.BarCls, WC.BarCls, WC.BarCls),  # BarCls
        (None, WC.ClsJ, WC.ClsK, WC.ClsL, WC.ClsM, WC.EthCls, WC.PsnCls, WC.OcnCls, WC.ClsJ, WC.ClsJ, WC.ClsJ),  # ClsJ
        (None, WC.ClsJ, WC.ClsK, WC.ClsL, WC.ClsM, WC.EthCls, WC.PsnCls, WC.UndCls, WC.ClsK, WC.ClsK, WC.ClsK),  # ClsK
        (None, WC.ClsJ, WC.ClsK, WC.ClsL, WC.ClsM, WC.EthCls, WC.DrtCls, WC.UndCls, WC.ClsL, WC.ClsL, WC.ClsL),  # ClsL
        (None, WC.ClsJ, WC.ClsK, WC.ClsL, WC.ClsM, WC.EthCls, WC.DrtCls, WC.OcnCls, WC.ClsM, WC.ClsM, WC.ClsM),  # ClsM
        (None, WC.ClsL, WC.ArdCls, WC.ClsM, WC.DrtCls, WC.DrtCls, WC.DrtCls, WC.DrtCls, WC.DrtCls, WC.DrtCls, WC.DrtCls),  # DrtCls
        (None, WC.FstCls, WC.EthCls, WC.ClsJ, WC.ClsK, WC.ClsL, WC.ClsM, WC.EthCls, WC.EthCls, WC.EthCls, WC.EthCls),  # EthCls
        (None, WC.EthCls, WC.JngCls, WC.FstCls, WC.FstCls, WC.FstCls, WC.FstCls, WC.FstCls, WC.FstCls, WC.FstCls, WC.FstCls),  # FstCls
        (None, WC.PsnCls, WC.GsGCls, WC.GsGCls, WC.GsGCls, WC.GsGCls, WC.GsGCls, WC.GsGCls, WC.GsGCls, WC.GsGCls, WC.GsGCls),  # GsGCls
        (None, WC.HLfCls, WC.FstCls, WC.EthCls, WC.HLfCls, WC.HLfCls, WC.HLfCls, WC.HLfCls, WC.HLfCls, WC.HLfCls, WC.HLfCls),  # HLfCls
        (None, WC.OcnCls, WC.IceCls, WC.IceCls, WC.IceCls, WC.IceCls, WC.IceCls, WC.IceCls, WC.IceCls, WC.IceCls, WC.IceCls),  # IceCls
        (None, WC.ParCls, WC.FstCls, WC.JngCls, WC.JngCls, WC.JngCls, WC.JngCls, WC.JngCls, WC.JngCls, WC.JngCls, WC.JngCls),  # JngCls
        (None, WC.IceCls, WC.AmbCls, WC.OcnCls, WC.OcnCls, WC.OcnCls, WC.OcnCls, WC.OcnCls, WC.OcnCls, WC.OcnCls, WC.OcnCls),  # OcnCls
        (None, WC.ParCls, WC.JngCls, WC.ParCls, WC.ParCls, WC.ParCls, WC.ParCls, WC.ParCls, WC.ParCls, WC.ParCls, WC.ParCls),  # ParCls
        (None, WC.GsGCls, WC.ClsJ, WC.ClsK, WC.PsnCls, WC.PsnCls, WC.PsnCls, WC.PsnCls, WC.PsnCls, WC.PsnCls, WC.PsnCls),  # PsnCls
        (None, WC.EthCls, WC.RnsCls, WC.RnsCls, WC.RnsCls, WC.RnsCls, WC.RnsCls, WC.RnsCls, WC.RnsCls, WC.RnsCls, WC.RnsCls),  # RnsCls
        (None, WC.VlcCls, WC.ClsK, WC.ClsL, WC.UndCls, WC.UndCls, WC.UndCls, WC.UndCls, WC.UndCls, WC.UndCls, WC.UndCls),  # UndCls
        (None, WC.TerCls, WC.TerCls, WC.TerCls, WC.TerCls, WC.TerCls, WC.TerCls, WC.TerCls, WC.TerCls, WC.TerCls, WC.TerCls),  # TerCls
        (None, WC.UndCls, WC.BarCls, WC.VlcCls, WC.VlcCls, WC.VlcCls, WC.VlcCls, WC.VlcCls, WC.VlcCls, WC.VlcCls, WC.VlcCls),  # VlcCls
    ),
)


# --- Combat ------------------------------------------------------------------

#: Military power of individual ships and defenses, 0..100.
MPower: dict[T, int] = _table(
    tech_range(T.LAM, T.trn),
    # LAM  def  GDM  ion  fgt  hkr  jmp  jtn  pen  ssp  trn
    (100, 100, 10, 50, 1, 20, 12, 1, 25, 100, 0),
)

#: Destructive power of attacker vs defender. 100 points destroys one unit,
#: 200 destroys two, and so on. Valid entries should never be 0.
CombatTable: dict[T, dict[T, int]] = _table(
    ATTACK_TYPES,
    tuple(
        _table(ATTACK_TYPES, row)
        for row in (
            # NUL LAM  def  GDM  ion   fgt   hkr  jmp  jtn  pen  ssp  trn  men  nnj
            (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),  # NUL
            (0, 200, 100, 200, 150, 250, 60, 75, 100, 50, 15, 200, 0, 0),  # LAM
            (0, 0, 0, 0, 0, 25, 90, 100, 100, 50, 6, 250, 0, 0),  # def
            (0, 0, 0, 0, 0, 250, 100, 100, 100, 50, 25, 50, 0, 0),  # GDM
            (0, 0, 0, 0, 0, 50, 65, 75, 75, 15, 2, 100, 0, 0),  # ion
            (0, 5, 5, 1, 25, 25, 15, 8, 20, 12, 1, 25, 5, 4),  # fgt
            (0, 12, 40, 38, 20, 50, 50, 75, 50, 50, 4, 75, 0, 0),  # hkr
            (0, 8, 15, 25, 10, 150, 25, 38, 50, 25, 1, 150, 0, 0),  # jmp
            (0, 0, 1, 0, 0, 25, 1, 1, 5, 0, 0, 10, 0, 0),  # jtn
            (0, 15, 35, 50, 35, 50, 65, 105, 125, 50, 5, 250, 0, 0),  # pen
            (0, 45, 90, 200, 50, 1000, 250, 300, 500, 100, 15, 500, 0, 0),  # ssp
            (0, 0, 0, 0, 0, 12, 0, 0, 1, 0, 0, 5, 0, 0),  # trn
            (0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0, 7, 2),  # men
            (0, 0, 0, 0, 0, 8, 0, 0, 0, 0, 0, 0, 20, 10),  # nnj
        )
    ),
)

#: Average effectiveness of weapons per ship type. Should never be 0.
WeapEff: dict[T, int] = _table(
    ATTACK_TYPES,
    # NUL  LAM  def  GDM  ion  fgt  hkr  jmp  jtn  pen  ssp  trn  men  nnj
    (0, 100, 150, 100, 30, 30, 100, 100, 10, 150, 100, 10, 100, 100),
)

#: Average value of a given ship.
ShipValue: dict[T, int] = _table(
    ATTACK_TYPES,
    # NUL LAM def GDM ion fgt hkr jmp jtn  pen  ssp trn men  nnj
    (0, 0, 0, 0, 0, 5, 50, 50, 30, 100, 200, 30, 50, 100),
)

#: How well a given ship can protect others.
ProtecOffered: dict[T, int] = _table(
    SHIP_TYPES,
    # fgt hkr jmp jtn pen  ssp trn
    (5, 10, 10, 1, 50, 100, 0),
)

#: Relative strength needed to protect each ship type. Should never be 0.
ProtecNeeded: dict[T, int] = _table(
    SHIP_TYPES,
    # fgt hkr jmp jtn  pen  ssp  trn
    (5, 30, 20, 50, 200, 500, 150),
)


# --- Population, tech and industry -------------------------------------------

#: Average population at 50% efficiency, by tech level.
BasePop: dict[TL, int] = _table(
    TechLevel,
    # pt   p   pa    a   pw    w     j     b     s    pg     g
    (3, 10, 100, 250, 500, 700, 1100, 1700, 2000, 2500, 3000),
)

#: TIP adjustment by technology.
TechAdj: dict[TL, int] = _table(
    TechLevel,
    # pt  p  pa   a  pw   w   j   b   s  pg    g
    (25, 40, 49, 57, 66, 80, 85, 90, 94, 97, 100),
)

#: Production adjustment by technology.
TechAdj2: dict[TL, int] = _table(
    TechLevel,
    # pt  p  pa   a  pw   w   j   b   s  pg    g
    (12, 24, 36, 47, 58, 67, 76, 84, 90, 95, 100),
)

#: Minimum supply industry for self-sufficient worlds, by tech level.
MinSupInd: dict[TL, int] = _table(
    TechLevel,
    # pt  p  pa   a  pw   w   j   b   s  pg   g
    (95, 90, 80, 70, 50, 40, 34, 30, 28, 26, 23),
)

#: Minimum tech level required to have a given industry.
MinTechLevel: dict[IT, TL] = _table(
    IndusTypes,
    (
        TL.BioTchLvl,  # BioInd
        TL.PreAtmLvl,  # CheInd
        TL.PrimitLvl,  # MinInd
        TL.PreWrpLvl,  # SYGInd
        TL.JmpTchLvl,  # SYJInd
        TL.StrTchLvl,  # SYSInd
        TL.WrpTchLvl,  # SYTInd
        TL.PreTchLvl,  # SupInd
        TL.AtomicLvl,  # TriInd
    ),
)

#: Minimum tech level required to designate a world to a given type.
MinTechForType: dict[WT, TL] = _table(
    WorldTypes,
    (
        TL.PreTchLvl,  # AgrTyp
        TL.BioTchLvl,  # AmbTyp
        TL.PreWrpLvl,  # BseTyp
        TL.GteTchLvl,  # BseSTyp
        TL.JmpTchLvl,  # CapTyp
        TL.PreAtmLvl,  # CheTyp
        TL.PreTchLvl,  # IndTyp
        TL.JmpTchLvl,  # JmpTyp
        TL.GteTchLvl,  # JmpSTyp
        TL.PrimitLvl,  # MinTyp
        TL.StrTchLvl,  # NnjTyp
        TL.GteTchLvl,  # OutTyp
        TL.PrimitLvl,  # RawTyp
        TL.GteTchLvl,  # RawSTyp
        TL.BioTchLvl,  # StrTyp
        TL.GteTchLvl,  # StrSTyp
        TL.PreWrpLvl,  # TrnTyp
        TL.GteTchLvl,  # TrnSTyp
        TL.JmpTchLvl,  # RsrTyp
        TL.WrpTchLvl,  # TerTyp
        TL.AtomicLvl,  # TriTyp
    ),
)

#: Minimum tech level required to have a population on a given planet class.
MinTechForClass: dict[WC, TL] = _table(
    WorldClass,
    (
        TL.PreTchLvl,  # AmbCls
        TL.PrimitLvl,  # ArdCls
        TL.JmpTchLvl,  # ArtCls
        TL.PreWrpLvl,  # BarCls
        TL.PreTchLvl,  # ClsJ
        TL.PreTchLvl,  # ClsK
        TL.PreTchLvl,  # ClsL
        TL.PreTchLvl,  # ClsM
        TL.PrimitLvl,  # DrtCls
        TL.PreTchLvl,  # EthCls
        TL.PreTchLvl,  # FstCls
        TL.PreWrpLvl,  # GsGCls
        TL.PreAtmLvl,  # HLfCls
        TL.PreAtmLvl,  # IceCls
        TL.PreTchLvl,  # JngCls
        TL.PreWrpLvl,  # OcnCls
        TL.PreTchLvl,  # ParCls
        TL.AtomicLvl,  # PsnCls
        TL.PreTchLvl,  # RnsCls
        TL.PrimitLvl,  # UndCls
        TL.WrpTchLvl,  # TerCls
        TL.PreAtmLvl,  # VlcCls
    ),
)

#: Average trillum reserves for a given class.
TriResByClass: dict[WC, int] = _table(
    WorldClass,
    (
        200,  # AmbCls
        350,  # ArdCls
        50,  # ArtCls
        1200,  # BarCls
        700,  # ClsJ
        800,  # ClsK
        900,  # ClsL
        800,  # ClsM
        1500,  # DrtCls
        800,  # EthCls
        500,  # FstCls
        450,  # GsGCls
        500,  # HLfCls
        900,  # IceCls
        600,  # JngCls
        300,  # OcnCls
        600,  # ParCls
        350,  # PsnCls
        200,  # RnsCls
        900,  # UndCls
        800,  # TerCls
        1100,  # VlcCls
    ),
)

#: Percent of industry that is effective, by world class.
ClassIndAdj: dict[WC, dict[IT, int]] = _table(
    WorldClass,
    tuple(
        _table(IndusTypes, row)
        for row in (
            # Bio  Che  Min  SYG  SYJ  SYS  SYT  Sup  Tri
            (100, 100, 75, 100, 100, 100, 100, 100, 75),  # AmbCls
            (100, 80, 100, 100, 100, 100, 100, 85, 100),  # ArdCls
            (100, 40, 40, 250, 200, 300, 300, 40, 40),  # ArtCls
            (100, 60, 175, 100, 100, 100, 100, 40, 175),  # BarCls
            (100, 120, 120, 100, 100, 100, 100, 100, 90),  # ClsJ
            (100, 90, 120, 100, 100, 100, 100, 100, 100),  # ClsK
            (100, 100, 100, 100, 100, 100, 100, 90, 120),  # ClsL
            (100, 100, 100, 100, 100, 100, 100, 120, 90),  # ClsM
            (100, 60, 80, 100, 100, 100, 100, 60, 190),  # DrtCls
            (100, 100, 100, 100, 100, 100, 100, 100, 100),  # EthCls
            (100, 120, 100, 100, 100, 100, 100, 145, 100),  # FstCls
            (100, 150, 50, 150, 125, 175, 150, 40, 60),  # GsGCls
            (100, 100, 100, 100, 100, 100, 100, 100, 100),  # HLfCls
            (100, 90, 80, 100, 100, 100, 100, 60, 80),  # IceCls
            (100, 130, 100, 100, 100, 100, 100, 125, 100),  # JngCls
            (100, 135, 40, 100, 100, 100, 100, 130, 40),  # OcnCls
            (120, 150, 125, 100, 100, 100, 100, 200, 150),  # ParCls
            (100, 200, 80, 100, 100, 100, 100, 40, 80),  # PsnCls
            (100, 100, 100, 100, 100, 100, 100, 100, 100),  # RnsCls
            (100, 100, 150, 100, 100, 100, 100, 70, 125),  # UndCls
            (1, 1, 1, 1, 1, 1, 1, 10, 1),  # TerCls
            (100, 125, 175, 100, 100, 100, 100, 75, 150),  # VlcCls
        )
    ),
)

#: Percent of population in the military at military index 50, by tech level,
#: in hundredths of a percent.
MilitPer: dict[TL, int] = _table(
    TechLevel,
    # pt   p   pa   a  pw   w   j   b   s  pg   g
    (1, 80, 100, 90, 80, 75, 60, 50, 30, 15, 10),
)

#: Percent of population in the military by world type, in hundredths of a percent.
OptMilitary: dict[WT, int] = _table(
    WorldTypes,
    # a    A    b    B    C   c   i    j    J   m    N  o
    (5, 100, 200, 200, 200, 10, 80, 100, 100, 20, 150, 0,
     # r   R    s    S   t   T  U   X   z
     20, 20, 150, 150, 80, 80, 1, 10, 30),
)


def _tech_dev() -> dict[TL, frozenset[T]]:
    """Technology available at each tech level.

    Pascal writes these as set literals containing subranges, e.g.
    ``[GDM,men,che..tri]``; the ranges are expanded here.
    """
    r = tech_range
    return {
        TL.PreTchLvl: frozenset({T.sup}),
        TL.PrimitLvl: frozenset({T.men, T.met, T.sup}),
        TL.PreAtmLvl: frozenset({T.men, *r(T.che, T.sup)}),
        TL.AtomicLvl: frozenset({T.GDM, T.men, *r(T.che, T.tri)}),
        TL.PreWrpLvl: frozenset({T.GDM, T.fgt, T.men, *r(T.che, T.tri)}),
        TL.WrpTchLvl: frozenset({T.GDM, T.fgt, T.trn, T.men, *r(T.che, T.tri)}),
        TL.JmpTchLvl: frozenset(
            {T.GDM, T.ion, T.fgt, T.trn, T.jmp, T.jtn, T.men, *r(T.che, T.tri)}
        ),
        TL.BioTchLvl: frozenset(
            {
                *r(T.def_, T.ion),
                *r(T.fgt, T.pen),
                T.trn,
                T.men,
                *r(T.amb, T.tri),
                T.out,
            }
        ),
        TL.StrTchLvl: frozenset(
            {*r(T.LAM, T.trn), *r(T.men, T.tri), T.SRM, T.cmm, T.cmp, T.out}
        ),
        TL.PreGteLvl: frozenset({*r(T.LAM, T.tri), *r(T.SRM, T.out), T.lnk, T.dis}),
        TL.GteTchLvl: frozenset(r(T.LAM, T.ter)),
    }


#: Technology development by technological level.
TechDev: dict[TL, frozenset[T]] = _tech_dev()


def init_defense_record() -> DefenseRecord:
    """Default distribution of defenses by ship type and orbit.

    The Pascal constant specifies ``ShellDefDist`` only, leaving
    ``StarbaseDefDist`` zero-filled.
    """
    shell_rows = (
        # fgt hkr jmp jtn pen ssp trn
        (5, 50, 10, 0, 15, 0, 0),  # deep space
        (10, 10, 20, 0, 30, 50, 0),  # high orbit
        (10, 10, 30, 0, 30, 30, 0),  # orbit
        (55, 30, 40, 0, 25, 20, 0),  # sub-orbit
        (20, 0, 0, 100, 0, 0, 100),  # ground
    )
    record = DefenseRecord()
    record.ShellDefDist = _table(
        ShellPos, tuple(_table(SHIP_TYPES, row) for row in shell_rows)
    )
    return record


# --- Cargo and fuel ----------------------------------------------------------

#: Units of cargo that fit in one transport, by cargo type.
CargoSpace: dict[T, int] = _table(
    CARGO_TYPES,
    # men nnj  amb che met sup  tri
    (5, 5, 100, 3, 3, 2, 100),
)

#: Cargo capacity of ships relative to a transport = 1.
TrnAdj: dict[T, float] = _table(
    SHIP_TYPES,
    # fgt hkr jmp  jtn pen ssp trn
    (0, 0, 0, 0.2, 0, 0, 1),
)

JUMP_CARGO_RATIO = 5

#: Units of fuel to move one unit one sector, by thing type, in thousandths.
FuelCons: dict[T, int] = _table(
    tech_range(T.fgt, T.tri),
    # fgt   hkr  jmp  jtn  pen   ssp  trn  men  nnj  amb  che  met  sup  tri
    (10, 1086, 659, 894, 943, 1427, 994, 10, 10, 15, 10, 10, 15, 20),
)

#: Maximum fuel each ship can hold, in hundredths.
FuelCap: dict[T, int] = _table(
    SHIP_TYPES,
    # fgt  hkr  jmp   jtn   pen   ssp   trn
    (3, 851, 329, 1341, 1886, 2854, 1988),
)

#: Fleet movement rate in sectors per year, by fleet type.
FltMovementRate: dict[FleetTypes, int] = _table(FleetTypes, (1, 10, 10, 2, 2))

FUEL_PER_TON = 265
TRI_TO_LAUNCH = 0
#: A standing fleet burns ``FuelCons / SFUEL_CONS``.
SFUEL_CONS = 10


# --- Production --------------------------------------------------------------

#: Relative amounts of each thing that each industry makes.
ThgAdj: dict[IT, dict[T, int]] = _table(
    IndusTypes,
    tuple(
        _table(tech_range(T.fgt, T.tri), row)
        for row in (
            # fgt hkr jmp jtn pen ssp trn  men nnj  amb  che  met  sup tri
            (0, 0, 0, 0, 0, 0, 0, 0, 10, 175, 0, 0, 0, 0),  # Bio
            (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 175, 0, 0, 0),  # Che
            (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 350, 0, 0),  # Min
            (27, 5, 9, 5, 4, 2, 10, 0, 0, 0, 0, 0, 0, 0),  # SYG
            (0, 25, 50, 30, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),  # SYJ
            (0, 0, 0, 0, 40, 15, 0, 0, 0, 0, 0, 0, 0, 0),  # SYS
            (75, 0, 0, 0, 0, 0, 45, 0, 0, 0, 0, 0, 0, 0),  # SYT
            (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 320, 0),  # Sup
            (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 75),  # Tri
        )
    ),
)

#: Raw material needed to make 100 units of a given thing.
RawM: dict[T, dict[T, int]] = _table(
    RESOURCE_TYPES,
    tuple(
        _table(CARGO_TYPES, row)
        for row in (
            # men nnj amb  che  met sup tri
            (0, 0, 0, 0, 0, 0, 0),  # none
            (0, 0, 0, 25, 20, 0, 5),  # LAM
            (0, 0, 0, 30, 140, 0, 20),  # def
            (0, 0, 0, 10, 20, 0, 2),  # GDM
            (0, 0, 0, 25, 150, 0, 10),  # ion
            (0, 0, 0, 5, 30, 0, 2),  # fgt
            (0, 0, 0, 100, 110, 0, 18),  # hkr
            (0, 0, 0, 65, 70, 0, 12),  # jmp
            (0, 0, 0, 100, 110, 0, 16),  # jtn
            (0, 0, 0, 95, 275, 0, 20),  # pen
            (0, 0, 0, 175, 520, 0, 30),  # ssp
            (0, 0, 0, 90, 600, 0, 10),  # trn
            (0, 0, 0, 0, 0, 0, 0),  # men
            (0, 0, 100, 50, 0, 0, 0),  # nnj
            (0, 0, 0, 110, 0, 0, 0),  # amb
            (0, 0, 0, 0, 0, 0, 0),  # che
            (0, 0, 0, 0, 0, 0, 0),  # met
            (0, 0, 0, 0, 0, 0, 0),  # sup
            (0, 0, 0, 0, 0, 0, 0),  # tri
        )
    ),
)

#: Units of metal needed to build 100 points of industrial development.
NewIndRawN: dict[IT, int] = _table(
    IndusTypes,
    # Bio  Che  Min   SYG   SYJ   SYS   SYT  Sup  Tri
    (100, 500, 100, 1900, 1200, 1500, 1000, 0, 300),
)

#: How to distribute a world's industry.
#:
#: Industries split into Production Industries (Bio, SYG, SYJ, SYS, SYT) and
#: Raw Material Industries (Che, Min, Tri). Sup is special and is calculated
#: first from population and this value -- it is a multiple of the world's own
#: need, so AgrTyp's 10.0 means ten times what it consumes.
#:
#: If every PI value is 0 (as for AgrTyp) the RI values are percentages of the
#: industry left over after Sup. If any PI value is non-zero it is the maximum
#: setting for that industry, and the rest are fitted around it to balance the
#: world.
TypeData: dict[WT, dict[IT, float]] = _table(
    WorldTypes,
    tuple(
        _table(IndusTypes, row)
        for row in (
            # Bio  Che  Min  SYG  SYJ  SYS  SYT   Sup  Tri
            (0, 40, 40, 0, 0, 0, 0, 10.0, 20),  # AgrTyp
            (100, 1.2, 5.0, 0, 0, 0, 0, 1.1, 5.0),  # AmbTyp
            (0, 1.2, 1.7, 100, 0, 0, 0, 1.1, 1.7),  # BseTyp
            (0, 0.5, 0.5, 100, 0, 0, 0, 0.5, 0.5),  # BseSTyp
            (0, 2.0, 2.5, 100, 0, 0, 0, 1.5, 2.0),  # CapTyp
            (0, 80, 10, 0, 0, 0, 0, 1.1, 10),  # CheTyp
            (0, 2.0, 2.5, 100, 0, 0, 0, 1.5, 2.0),  # IndTyp
            (0, 1.2, 1.7, 0, 100, 0, 0, 1.1, 1.7),  # JmpTyp
            (0, 0.5, 0.5, 0, 100, 0, 0, 0.5, 0.5),  # JmpSTyp
            (0, 10, 80, 0, 0, 0, 0, 1.1, 10),  # MinTyp
            (100, 1.2, 5.0, 0, 0, 0, 0, 1.1, 5.0),  # NnjTyp
            (0, 0, 0, 0, 0, 0, 0, 0, 0),  # OutTyp
            (0, 40, 40, 0, 0, 0, 0, 1.1, 20),  # RawTyp
            (0, 40, 40, 0, 0, 0, 0, 0.5, 20),  # RawSTyp
            (0, 1.2, 1.3, 0, 0, 100, 0, 1.1, 1.2),  # StrTyp
            (0, 0.5, 0.5, 0, 0, 100, 0, 0.5, 0.5),  # StrSTyp
            (0, 1.2, 1.7, 0, 0, 0, 100, 1.1, 1.2),  # TrnTyp
            (0, 0.5, 0.5, 0, 0, 0, 100, 0.5, 0.5),  # TrnSTyp
            (0, 10, 10, 0, 0, 0, 0, 1.1, 5),  # RsrTyp
            (0, 10, 10, 0, 0, 0, 0, 1.1, 5),  # TerTyp
            (0, 10, 10, 0, 0, 0, 0, 1.1, 80),  # TriTyp
        )
    ),
)

PrincipalIndustry: dict[WT, IT] = _table(
    WorldTypes,
    (
        IT.SupInd,  # AgrTyp
        IT.BioInd,  # AmbTyp
        IT.SYGInd,  # BseTyp
        IT.SYGInd,  # BseSTyp
        IT.SYGInd,  # CapTyp
        IT.CheInd,  # CheTyp
        IT.SYGInd,  # IndTyp
        IT.SYJInd,  # JmpTyp
        IT.SYJInd,  # JmpSTyp
        IT.MinInd,  # MinTyp
        IT.BioInd,  # NnjTyp
        IT.SYGInd,  # OutTyp
        IT.MinInd,  # RawTyp
        IT.MinInd,  # RawSTyp
        IT.SYSInd,  # StrTyp
        IT.SYSInd,  # StrSTyp
        IT.SYTInd,  # TrnTyp
        IT.SYTInd,  # TrnSTyp
        IT.MinInd,  # RsrTyp
        IT.MinInd,  # TerTyp
        IT.TriInd,  # TriTyp
    ),
)


# --- ISSP --------------------------------------------------------------------

DEFAULT_ISSP = 0x5555

MAX_ISSP = 10
NORMAL_ISSP = 5  # 100%

#: How much over or under its need an industry produces. Indexed 0..MAX_ISSP.
#: DESIGN.PAS's ChangeISSP and GetISSPLine depend on these values.
ISSP: tuple[float, ...] = (0.01, 0.10, 0.25, 0.50, 0.75, 1.00, 1.50, 2.00, 3.00, 4.00, 5.00)


# --- Construction ------------------------------------------------------------

#: Years to complete each construction type.
YearsToBuild: dict[T, int] = _table(
    CONSTR_TYPES,
    # SRM cmm frt cmp out gte lnk dis
    (2, 6, 12, 10, 3, 15, 5, 8),
)

#: Material needed per year, per construction type.
ConsCargoNeeded: dict[T, dict[T, int]] = _table(
    CONSTR_TYPES,
    tuple(
        _table(CARGO_TYPES, row)
        for row in (
            # men nnj amb   che   met sup   tri
            (0, 0, 0, 110, 500, 0, 80),  # SRM
            (0, 0, 0, 460, 2300, 0, 180),  # cmm
            (0, 0, 0, 840, 2870, 0, 250),  # frt
            (0, 0, 0, 590, 2600, 0, 150),  # cmp
            (0, 0, 0, 350, 1120, 0, 150),  # out
            (0, 0, 0, 2530, 3920, 0, 1450),  # gte
            (0, 0, 0, 1560, 2550, 0, 290),  # lnk
            (0, 0, 0, 1110, 1180, 0, 1120),  # dis
        )
    ),
)

#: Optimum defenses for 100 men, 20 billion population, and 50% efficiency.
DefAdj: dict[T, int] = _table(DEFNS_TYPES, (145, 76, 215, 83))
DefBuildRate: dict[T, int] = _table(DEFNS_TYPES, (220, 50, 250, 95))


# --- Directions --------------------------------------------------------------

DirX: dict[Directions, int] = _table(Directions, (0, 0, 1, 1, 1, 0, -1, -1, -1))
DirY: dict[Directions, int] = _table(Directions, (0, -1, -1, 0, 1, 1, 1, 0, -1))
