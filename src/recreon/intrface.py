"""High-level operations on entities.

Port of INTRFACE.PAS -- the Phase 3 subset: world creation and the optimum
industrial distribution. Gate passage, fleet balancing and the status-line
formatters arrive with the phases that use them.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .datacnst import (
    DEFAULT_ISSP,
    ISSP,
    K4,
    K6,
    SAFETY_ADJ,
    SUPPLIES_PER_BILLION,
    AMBROSIA_ADJ,
    ClassIndAdj,
    PrincipalIndustry,
    TechAdj2,
    ThgAdj,
    TypeData,
)
from .galaxy import Location, XYCoord
from .misc import total_prod
from .primintr import (
    get_class,
    get_efficiency,
    get_issp,
    get_population,
    get_special,
    get_tech,
    get_type,
)
from .types import (
    Empire,
    IndusTypes,
    IDNumber,
    ObjectTypes,
    SpecialConditions,
    TechnologyTypes,
    WorldTypes,
)

if TYPE_CHECKING:
    from .environ import GameEnvironment

IT = IndusTypes

#: Cross-elasticity of each raw-material industry against each production
#: industry: how much Che/Min/Tri capacity one unit of the main industry
#: needs. Only the Che, Min and Tri rows are non-zero.
Gamma: dict[IT, dict[IT, float]] = {
    IT.BioInd: dict.fromkeys(IndusTypes, 0.0),
    IT.CheInd: {
        IT.BioInd: 1.12857,
        IT.CheInd: 0.0,
        IT.MinInd: 0.0,
        IT.SYGInd: 0.19143,
        IT.SYJInd: 0.50000,
        IT.SYSInd: 0.36714,
        IT.SYTInd: 0.25286,
        IT.SupInd: 0.0,
        IT.TriInd: 0.0,
    },
    IT.MinInd: {
        IT.BioInd: 0.10000,
        IT.CheInd: 0.0,
        IT.MinInd: 0.0,
        IT.SYGInd: 0.30514,
        IT.SYJInd: 0.27286,
        IT.SYSInd: 0.53714,
        IT.SYTInd: 0.83571,
        IT.SupInd: 0.0,
        IT.TriInd: 0.0,
    },
    IT.SYGInd: dict.fromkeys(IndusTypes, 0.0),
    IT.SYJInd: dict.fromkeys(IndusTypes, 0.0),
    IT.SYSInd: dict.fromkeys(IndusTypes, 0.0),
    IT.SYTInd: dict.fromkeys(IndusTypes, 0.0),
    IT.SupInd: dict.fromkeys(IndusTypes, 0.0),
    IT.TriInd: {
        IT.BioInd: 0.10000,
        IT.CheInd: 0.0,
        IT.MinInd: 0.0,
        IT.SYGInd: 0.07627,
        IT.SYJInd: 0.20400,
        IT.SYSInd: 0.16667,
        IT.SYTInd: 0.08000,
        IT.SupInd: 0.0,
        IT.TriInd: 0.0,
    },
}

#: World types with no production industry: the raw-material percentages are
#: shares of whatever industry the supply requirement leaves over.
_RAW_MATERIAL_TYPES = frozenset(
    {
        WorldTypes.AgrTyp,
        WorldTypes.CheTyp,
        WorldTypes.MinTyp,
        WorldTypes.RawTyp,
        WorldTypes.RawSTyp,
        # Pascal's `RsrTyp..TriTyp` subrange.
        WorldTypes.RsrTyp,
        WorldTypes.TerTyp,
        WorldTypes.TriTyp,
    }
)


def get_industrial_distribution(
    game: GameEnvironment, obj: IDNumber
) -> dict[IT, float]:
    """Optimum share of industry for each industry type, as percentages.

    Supply industry is sized first, from population and the world's supply
    ISSP. What remains is split either as fixed shares (raw-material worlds)
    or around the world's principal industry, with the raw-material
    industries sized to feed it via :data:`Gamma`.
    """
    tech = get_tech(game, obj)
    cls = get_class(game, obj)
    pop = get_population(game, obj)
    typ = get_type(game, obj)
    eff = get_efficiency(game, obj)
    amb_addict = SpecialConditions.AmbAddict in get_special(game, obj)

    ind_dist: dict[IT, float] = dict.fromkeys(IndusTypes, 0.0)

    alpha = (TechAdj2[tech] / 100) * (eff + 250) / K6
    tip = float(total_prod(pop, tech))
    if amb_addict:
        tip *= AMBROSIA_ADJ
    tip = min(tip, 999)

    # Beta[i] = TIP * ClassIndAdj[Cls, i] / 10000, floored at 1 so it can be
    # divided by safely.
    temp = tip / 10000
    beta = {}
    for ind in IndusTypes:
        beta[ind] = temp * ClassIndAdj[cls][ind]
        if beta[ind] == 0:
            beta[ind] = 1

    # Supply industry.
    i = (
        math.sqrt(
            (
                SAFETY_ADJ
                * ISSP[get_issp(game, obj, IT.SupInd)]
                * (SUPPLIES_PER_BILLION / 100)
                * pop
            )
            / ((ThgAdj[IT.SupInd][TechnologyTypes.sup] / 100) * alpha)
        )
        - K4
    ) / beta[IT.SupInd]
    if i > 95 or i < 0 or typ == WorldTypes.AgrTyp:
        i = 95
    ind_dist[IT.SupInd] = i

    if typ in _RAW_MATERIAL_TYPES:
        # No production industry: split the remainder by fixed shares.
        i = 100 - ind_dist[IT.SupInd]
        ind_dist[IT.CheInd] = i * (TypeData[typ][IT.CheInd] / 100)
        ind_dist[IT.MinInd] = i * (TypeData[typ][IT.MinInd] / 100)
        ind_dist[IT.TriInd] = i * (TypeData[typ][IT.TriInd] / 100)
        return ind_dist

    main_ind = PrincipalIndustry[typ]

    a = -K4 * (1 / beta[IT.CheInd] + 1 / beta[IT.MinInd] + 1 / beta[IT.TriInd])
    b = (
        math.sqrt(SAFETY_ADJ * ISSP[get_issp(game, obj, IT.CheInd)] * Gamma[IT.CheInd][main_ind])
        / beta[IT.CheInd]
        + math.sqrt(SAFETY_ADJ * ISSP[get_issp(game, obj, IT.MinInd)] * Gamma[IT.MinInd][main_ind])
        / beta[IT.MinInd]
        + math.sqrt(SAFETY_ADJ * ISSP[get_issp(game, obj, IT.TriInd)] * Gamma[IT.TriInd][main_ind])
        / beta[IT.TriInd]
    )

    i = (100 - (ind_dist[IT.SupInd] + a + (K4 * b))) / (1 + (beta[main_ind] * b))
    i = min(i, TypeData[typ][main_ind])
    ind_dist[main_ind] = i

    for raw in (IT.CheInd, IT.MinInd, IT.TriInd):
        i = (
            (ind_dist[main_ind] * beta[main_ind] + K4)
            * math.sqrt(SAFETY_ADJ * ISSP[get_issp(game, obj, raw)] * Gamma[raw][main_ind])
            - K4
        ) / beta[raw]
        if i < 0:
            i = 1
        ind_dist[raw] = i

    return ind_dist


def get_optimum_indus(game: GameEnvironment, obj: IDNumber) -> dict[IT, int]:
    """The industry array a world would settle at, given its distribution.

    Used when a world is created already developed, rather than growing into
    its industry year by year.
    """
    from .datacnst import ClassIndAdj as _cls_adj
    from .utils.pascal import pascal_round

    ind_dist = get_industrial_distribution(game, obj)
    cls = get_class(game, obj)
    tech = get_tech(game, obj)
    pop = get_population(game, obj)

    tip = total_prod(pop, tech)
    temp = tip / 10000

    indus: dict[IT, int] = {}
    for ind in IndusTypes:
        level = pascal_round(temp * ind_dist[ind] * _cls_adj[cls][ind])
        if ind_dist[ind] > 0 and level == 0:
            level = 1
        indus[ind] = min(level, 999)
    return indus


def scout(game: GameEnvironment, emp: Empire, xy: XYCoord) -> None:
    """Reveal the eight sectors around ``xy`` to ``emp``.

    A dark nebula blocks the sweep -- the original bails out of the whole
    loop on hitting one, so which sectors get revealed depends on scan order.
    Preserved as-is.
    """
    from .datacnst import DirX, DirY
    from .news import NewsTypes, add_news
    from .primintr import (
        get_nebula,
        get_object,
        get_status,
        known,
        scout_object,
        scouted,
    )
    from .types import Directions, NebulaTypes

    if xy == XYCoord(0, 0):
        return

    for direction in Directions:
        x = xy.x + DirX[direction]
        y = xy.y + DirY[direction]
        if not game.Galaxy.in_galaxy(x, y):
            continue

        temp = XYCoord(x, y)
        obj = get_object(game, temp)
        other_emp = get_status(game, obj)

        if obj.ObjTyp != ObjectTypes.Void and not scouted(game, emp, obj):
            if not known(game, emp, obj) and other_emp != emp:
                add_news(game, emp, NewsTypes.POk, Location(XY=XYCoord(0, 0), ID=obj))
            scout_object(game, emp, obj)

        if get_nebula(game, temp) == NebulaTypes.DarkNebula:
            return


def next_stargate_slot(game: GameEnvironment) -> int:
    """Highest free stargate index, or 0 when all are taken."""
    slot = len(game.Universe.Stargate) - 1
    while slot > 0 and slot in game.GlobalSets.SetOfActiveGates:
        slot -= 1
    return slot


def create_stargate(
    game: GameEnvironment,
    obj: IDNumber,
    new_emp: Empire,
    gate_type: TechnologyTypes,
    pos: XYCoord,
) -> None:
    game.Galaxy.sector(pos).Obj = obj

    gate = game.Universe.Stargate[obj.Index]
    gate.XY = pos
    gate.GTyp = gate_type
    gate.Emp = new_emp
    game.GlobalSets.SetOfActiveGates.add(obj.Index)


def create_planet(game: GameEnvironment, obj: IDNumber, new_xy: XYCoord) -> None:
    """Place a planet into the world and register it in its sector."""
    game.Galaxy.sector(new_xy).Obj = obj

    planet = game.Universe.Planet[obj.Index]
    planet.XY = new_xy
    planet.ImpExp = DEFAULT_ISSP
    game.GlobalSets.SetOfActivePlanets.add(obj.Index)
    game.GlobalSets.SetOfPlanetsOf[planet.Emp].add(obj.Index)


def next_starbase_slot(game: GameEnvironment) -> int:
    """Highest free starbase index, or 0 when all are taken.

    Counts down from the top, as the original does, so slot assignment
    matches when comparing runs side by side.
    """
    slot = len(game.Universe.Starbase) - 1
    while slot > 0 and slot in game.GlobalSets.SetOfActiveStarbases:
        slot -= 1
    return slot


def create_starbase(
    game: GameEnvironment,
    obj: IDNumber,
    new_emp,
    new_xy: XYCoord,
    new_typ: TechnologyTypes,
) -> None:
    game.Galaxy.sector(new_xy).Obj = obj

    base = game.Universe.Starbase[obj.Index]
    base.XY = new_xy
    base.STyp = new_typ
    base.Emp = new_emp
    game.GlobalSets.SetOfActiveStarbases.add(obj.Index)
    game.GlobalSets.SetOfStarbasesOf[new_emp].add(obj.Index)


__all__ = [
    "Gamma",
    "create_planet",
    "create_stargate",
    "next_stargate_slot",
    "scout",
    "create_starbase",
    "get_industrial_distribution",
    "get_optimum_indus",
    "next_starbase_slot",
    "ObjectTypes",
]
