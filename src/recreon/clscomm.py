"""World close-up and production screens.

Port of CLSCOMM.PAS. Two read-only commands: the close-up, which is everything
you can see about a world or base, and the production screen, which projects
what it will make in the coming year.

**The production screen is a projection, not a report.** ``GetProdInfo``
re-derives the production formula rather than calling UPDATE.PAS, and the two
copies have drifted -- see :func:`production_forecast` and issue #62. The
numbers here are what a player saw, which is the point of a port; they are not
always what the world went on to make.

Drawing all of it is :mod:`recreon.ui.closeup`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .datacnst import (
    AMBROSIA_ADJ,
    DRUGS_PER_BILLION,
    ISSP,
    SUPPLIES_PER_BILLION,
    ClassIndAdj,
    DefAdj,
    DefBuildRate,
    K4,
    K6,
    RawM,
    TechAdj2,
    TechDev,
    ThgAdj,
)
from .environ import GameEnvironment
from .intrface import get_industrial_distribution
from .misc import thg_lmt, total_prod
from .primintr import (
    get_base_type,
    get_cargo,
    get_class,
    get_coord,
    get_coord_name,
    get_defns,
    get_efficiency,
    get_empire_technology,
    get_indus,
    get_issp,
    get_population,
    get_rev_index,
    get_ships,
    get_special,
    get_tech,
    get_type,
    object_name,
    trillum_reserves,
)
from .types import (
    CARGO_TYPES,
    DEFNS_TYPES,
    SHIP_TYPES,
    Empire,
    IDNumber,
    IndusTypes,
    ObjectTypes,
    SpecialConditions,
    TechLevel,
    TechnologyTypes,
    WorldClass,
    WorldTypes,
    cargo_array,
    defns_array,
    indus_array,
    indus_range,
    ship_array,
    tech_range,
)
from .utils.int_utils import greater_int, int_lmt
from .utils.pascal import pascal_round

T = TechnologyTypes
IT = IndusTypes

#: Highest TIP a world can reach. `IF ATIP>999 THEN ATIP:=999`.
MAX_ATIP = 999


# --- Basic information -------------------------------------------------------


@dataclass(slots=True)
class BasicInfo:
    """The header both screens share. Port of ``GetBasicInfo``."""

    name: str
    cls: WorldClass
    typ: WorldTypes
    tech: TechLevel
    pop: int
    eff: int
    rev: int
    amb_addict: bool


def basic_info(game: GameEnvironment, player: Empire, obj: IDNumber) -> BasicInfo:
    """Name, class, type, tech, population, efficiency and unrest.

    The name gets its coordinate appended **only when it does not already
    contain a comma** -- the original's test for "has this been given a real
    name, or is it just a coordinate?". A player-assigned name like "The
    Deeps" gains "(3,4)"; an unnamed world already reads "3,4" and is left
    alone. So a place named "Kandii, Second" would be mistaken for a
    coordinate and go un-annotated.
    """
    name = object_name(game, player, obj, long_format=True)
    if "," not in name:
        name = f"{name} ({get_coord_name(game, get_coord(game, obj))})"

    return BasicInfo(
        name=name,
        cls=get_class(game, obj),
        typ=get_type(game, obj),
        tech=get_tech(game, obj),
        pop=get_population(game, obj),
        eff=get_efficiency(game, obj),
        rev=get_rev_index(game, obj),
        amb_addict=SpecialConditions.AmbAddict in get_special(game, obj),
    )


def available_tip(game: GameEnvironment, obj: IDNumber, info: BasicInfo) -> int:
    """The world's TIP, adjusted and capped. ``ATIP`` in ``ProductionCom``.

    An ambrosia-addicted world's production is scaled by ``AmbrosiaAdj``
    before the cap, which is how addiction shows up as an industrial figure
    rather than only as unrest.
    """
    atip = total_prod(info.pop, info.tech)
    if info.amb_addict:
        atip = pascal_round(atip * AMBROSIA_ADJ)
    return min(atip, MAX_ATIP)


# --- Industry ----------------------------------------------------------------


@dataclass(slots=True)
class IndustryInfo:
    """The industry table: what is set, what is optimal, and why."""

    issp_index: dict[IT, float] = field(default_factory=dict)
    class_adj: dict[IT, int] = field(default_factory=dict)
    distribution: dict[IT, int] = field(default_factory=dict)
    optimum: dict[IT, int] = field(default_factory=indus_array)
    actual: dict[IT, int] = field(default_factory=indus_array)


def industry_info(
    game: GameEnvironment, obj: IDNumber, atip: int, cls: WorldClass
) -> IndustryInfo:
    """What each industry is set to and what it could be. ``GetIndusInfo``.

    The optimum is ``ATIP * distribution * class adjustment / 10000``, floored
    at 1 for any industry the player has asked for at all -- so a world never
    reads "you want this industry and it should be zero".
    """
    distribution = get_industrial_distribution(game, obj)
    actual = get_indus(game, obj)

    info = IndustryInfo(distribution=distribution, actual=actual)
    for ind in indus_range(IT.BioInd, IT.TriInd):
        info.issp_index[ind] = ISSP[get_issp(game, obj, ind)]
        info.class_adj[ind] = ClassIndAdj[cls][ind]
        optimum = pascal_round(
            atip * distribution[ind] * info.class_adj[ind] / 10000
        )
        if optimum == 0 and distribution[ind] != 0:
            optimum = 1
        info.optimum[ind] = optimum

    return info


def outpost_info() -> IndustryInfo:
    """The industry table for a base that is not an industrial complex.

    ``GetOutpostInfo`` zeroes everything and fills ``ISSPIndex`` with 5s --
    a ``FillChar`` of the byte 5 across an array of *reals*, so what the
    original actually displayed there was whatever a real made of the byte
    pattern ``05 05 05 05``, not the number five. Reproduced as a zeroed table
    with the index left at ISSP's neutral setting, since the garbage float has
    no meaning to carry across.
    """
    info = IndustryInfo()
    for ind in indus_range(IT.BioInd, IT.TriInd):
        info.issp_index[ind] = ISSP[5]
        info.class_adj[ind] = 0
        info.distribution[ind] = 0
    return info


# --- Production forecast -----------------------------------------------------


@dataclass(slots=True)
class ProductionForecast:
    """What the world is projected to make and consume next year."""

    ships: dict[T, int] = field(default_factory=ship_array)
    cargo: dict[T, int] = field(default_factory=cargo_array)
    consumed: dict[T, int] = field(default_factory=cargo_array)
    trillum_reserves: int = 0


def production_forecast(
    game: GameEnvironment,
    player: Empire,
    obj: IDNumber,
    info: BasicInfo,
    indus: dict[IT, int],
) -> ProductionForecast:
    """Project next year's output. Port of ``GetProdInfo``.

    **Original bug (#62): this does not agree with what the world will
    actually produce.** It re-derives UPDATE.PAS's formula rather than calling
    it, and the two copies have drifted in three ways, all of which make the
    forecast optimistic:

    * **Trillum ignores the reserves.** The real path routes trillum through
      ``produce_trillum``, which returns zero once ``TriReserve`` hits zero.
      A mined-out world forecasts its full output and delivers none.
    * **No floor at 1.** ``produce_raw_material`` wraps its result in
      ``greater_int(1, ...)``; this does not.
    * **``int_lmt`` where production uses ``thg_lmt``** for cargo -- ±32767
      against 0..9999, so the forecast can exceed what the world can hold.

    Reproduced exactly, because the screen is what a player saw. Do not
    "correct" it against ``update.py`` without reading the issue.
    """
    forecast = ProductionForecast(trillum_reserves=trillum_reserves(game, obj))

    ip = (TechAdj2[info.tech] / 100) * ((info.eff + 250) / 100) / K6

    _, technology = get_empire_technology(game, player)
    technology = technology & TechDev[info.tech]

    for ind in indus_range(IT.BioInd, IT.TriInd):
        if indus[ind] <= 0:
            continue
        prod_adj = ip * (indus[ind] + K4) ** 2

        for thing in tech_range(T.fgt, T.tri):
            if ThgAdj[ind][thing] == 0 or thing not in technology:
                continue

            if thing in SHIP_TYPES:
                forecast.ships[thing] = thg_lmt(prod_adj * ThgAdj[ind][thing])
                continue

            forecast.cargo[thing] = int_lmt(prod_adj * ThgAdj[ind][thing])

            # Ninja and ambrosia are gated on world type, and ambrosia on
            # class as well. The original's chained ELSE IF means a
            # non-ninja world skips the ambrosia tests entirely -- kept.
            if thing == T.nnj and info.typ != WorldTypes.NnjTyp:
                forecast.cargo[T.nnj] = 0
            elif thing == T.amb and info.typ != WorldTypes.AmbTyp:
                forecast.cargo[T.amb] = 0
            elif thing == T.amb and info.cls not in (
                WorldClass.AmbCls,
                WorldClass.ParCls,
            ):
                forecast.cargo[T.amb] = 0

    # Raw material the projected output would eat, at RawM per hundred units.
    for thing in SHIP_TYPES:
        for raw in tech_range(T.amb, T.tri):
            forecast.consumed[raw] += thg_lmt(
                forecast.ships[thing] * (RawM[thing][raw] / 100)
            )

    for thing in tech_range(T.amb, T.tri):
        for raw in tech_range(T.amb, T.tri):
            forecast.consumed[raw] += thg_lmt(
                forecast.cargo[thing] * (RawM[thing][raw] / 100)
            )

    forecast.consumed[T.sup] = thg_lmt((info.pop / 100) * SUPPLIES_PER_BILLION)

    if info.amb_addict:
        forecast.consumed[T.amb] += thg_lmt((info.pop / 100) * DRUGS_PER_BILLION)

    return forecast


# --- Defenses ----------------------------------------------------------------


@dataclass(slots=True)
class DefenseForecast:
    """Planetary defenses: what is there, what is optimal, what can be built."""

    available: dict[T, int] = field(default_factory=defns_array)
    optimum: dict[T, int] = field(default_factory=defns_array)
    buildable: dict[T, int] = field(default_factory=defns_array)


def defense_forecast(
    game: GameEnvironment,
    player: Empire,
    obj: IDNumber,
    info: BasicInfo,
    men: int,
) -> DefenseForecast:
    """How many defenses the world wants and can build. ``GetDefnsInfo``.

    Both figures come off the *manpower* in cargo, not the population: troops
    build and crew the defences. Efficiency scales the build rate around 50%,
    and on a world the population scales it again -- so a big, efficient,
    well-manned world builds far faster than the sum of its parts suggests.

    Bases adjust instead of scaling by population: an outpost wants a quarter
    of the optimum, a command base or fortress four times it and builds four
    times as fast.

    Two things are zeroed outright: an outpost builds no ``def``, and only a
    base or capital gets ``LAM``.
    """
    forecast = DefenseForecast(available=get_defns(game, obj))

    _, technology = get_empire_technology(game, player)
    technology = technology & TechDev[get_tech(game, obj)]

    build_rate = (men / 2000) * (1 + ((info.eff - 50) / 100))
    optimum = men / 100
    base_type = None

    if obj.ObjTyp == ObjectTypes.Pln:
        build_rate *= info.pop / 2000
    elif obj.ObjTyp == ObjectTypes.Base:
        base_type = get_base_type(game, obj)
        if base_type == T.out:
            optimum /= 4
        elif base_type in (T.cmm, T.frt):
            optimum *= 4
            build_rate *= 4

    for defence in DEFNS_TYPES:
        if defence not in technology:
            continue

        forecast.optimum[defence] = thg_lmt(optimum * DefAdj[defence])
        forecast.buildable[defence] = greater_int(
            thg_lmt(build_rate * DefBuildRate[defence]), 1
        )

        if obj.ObjTyp == ObjectTypes.Base and base_type == T.out and defence == T.def_:
            forecast.optimum[defence] = 0
            forecast.buildable[defence] = 0
        elif defence == T.LAM and info.typ not in (
            WorldTypes.BseTyp,
            WorldTypes.CapTyp,
        ):
            forecast.optimum[defence] = 0
            forecast.buildable[defence] = 0

    return forecast


# --- The two commands --------------------------------------------------------


@dataclass(slots=True)
class ProductionReport:
    """Everything ``ProductionCom`` puts on the screen."""

    info: BasicInfo
    atip: int
    industry: IndustryInfo
    forecast: ProductionForecast
    defenses: DefenseForecast
    ships: dict[T, int]
    cargo: dict[T, int]


def production_com(
    game: GameEnvironment, player: Empire, obj: IDNumber
) -> ProductionReport:
    """The production screen. Port of ``ProductionCom``.

    A base that is not an industrial complex gets the zeroed industry table --
    an outpost or fortress has no economy of its own to show.
    """
    info = basic_info(game, player, obj)
    atip = available_tip(game, obj, info)

    if obj.ObjTyp == ObjectTypes.Base and get_base_type(game, obj) != T.cmp:
        industry = outpost_info()
    else:
        industry = industry_info(game, obj, atip, info.cls)

    cargo = get_cargo(game, obj)

    return ProductionReport(
        info=info,
        atip=atip,
        industry=industry,
        forecast=production_forecast(game, player, obj, info, industry.actual),
        defenses=defense_forecast(game, player, obj, info, cargo[T.men]),
        ships=get_ships(game, obj),
        cargo=cargo,
    )


@dataclass(slots=True)
class CloseUpReport:
    """Everything ``CloseUpCom`` puts on the screen."""

    info: BasicInfo
    ships: dict[T, int]
    cargo: dict[T, int]
    defenses: dict[T, int]
    #: Fleets in the same sector, as (id, name, owner) -- scouted ones only.
    fleets: list[tuple[IDNumber, str, Empire]] = field(default_factory=list)


def close_up(game: GameEnvironment, player: Empire, obj: IDNumber) -> CloseUpReport:
    """The close-up screen. Port of ``CloseUpCom``.

    Lists the fleets sharing the sector alongside the world itself, which is
    how a player sees a siege forming.
    """
    from .primintr import get_fleets, get_status, scouted

    report = CloseUpReport(
        info=basic_info(game, player, obj),
        ships=get_ships(game, obj),
        cargo=get_cargo(game, obj),
        defenses=get_defns(game, obj),
    )

    for index in sorted(get_fleets(game, get_coord(game, obj))):
        flt = IDNumber(ObjectTypes.Flt, index)
        if not scouted(game, player, flt):
            continue
        report.fleets.append(
            (flt, object_name(game, player, flt), get_status(game, flt))
        )

    return report


__all__ = [
    "MAX_ATIP",
    "BasicInfo",
    "CloseUpReport",
    "DefenseForecast",
    "IndustryInfo",
    "ProductionForecast",
    "ProductionReport",
    "available_tip",
    "basic_info",
    "close_up",
    "defense_forecast",
    "industry_info",
    "outpost_info",
    "production_com",
    "production_forecast",
]
