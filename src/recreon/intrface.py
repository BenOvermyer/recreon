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
    CargoSpace,
    ClassIndAdj,
    FltMovementRate,
    PrincipalIndustry,
    TechAdj2,
    ThgAdj,
    TypeData,
    YearsToBuild,
)
from .galaxy import Location, XYCoord
from .misc import fleet_cargo_space, total_prod
from .primintr import (
    get_base_type,
    get_class,
    get_efficiency,
    get_gate_type,
    get_issp,
    get_object,
    get_population,
    get_special,
    get_status,
    get_tech,
    get_type,
    get_warp_link_freq,
)
from .types import (
    MAX_NO_OF_CONSTR_SITES,
    MAX_NO_OF_FLEETS,
    MAX_NO_OF_STARBASES,
    MAX_NO_OF_STARGATES,
    SHIP_TYPES,
    Empire,
    IndusTypes,
    IDNumber,
    ObjectTypes,
    SpecialConditions,
    TechnologyTypes,
    WorldTypes,
    empty_quadrant,
    indus_range,
    ship_array,
)
from .utils.pascal import pascal_round

#: Pascal's ``SYGInd TO SYTInd`` -- the four shipyard industries.
SHIPYARD_INDUSTRIES = indus_range(IndusTypes.SYGInd, IndusTypes.SYTInd)

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


def probe_scout(game: GameEnvironment, emp: Empire, xy: XYCoord) -> None:
    """Reveal the sectors around ``xy`` to ``emp``, at risk of losing the probe.

    Like :func:`scout` but with two differences that matter. It sweeps
    ``NoDir`` first, so the probe's own sector is revealed as well as the eight
    around it. And a garrisoned world can shoot it down: the chance is
    ``ISqrt(Cargo[men])`` percent, so a world holding 2500 troops destroys a
    probe half the time. An independent world never fires -- only an owned one.

    A destroyed probe stops the whole sweep, so everything the pass had not yet
    reached stays hidden. A dark nebula ends it the same way.
    """
    from .datacnst import DirX, DirY
    from .misc import same_xy
    from .news import NewsTypes, add_news
    from .primintr import (
        get_cargo,
        get_nebula,
        get_object,
        get_status,
        known,
        scout_object,
        scouted,
    )
    from .types import Directions, NebulaTypes
    from .utils.int_utils import isqrt, rnd

    if same_xy(xy, XYCoord(0, 0)):
        return

    for direction in Directions:
        x = xy.x + DirX[direction]
        y = xy.y + DirY[direction]
        if not game.Galaxy.in_galaxy(x, y):
            continue

        temp = XYCoord(x, y)
        obj = get_object(game, temp)
        other_emp = get_status(game, obj)

        if not scouted(game, emp, obj) and obj.ObjTyp != ObjectTypes.Void:
            loc = Location(XY=XYCoord(0, 0), ID=obj)
            chance_to_destroy = isqrt(get_cargo(game, obj)[TechnologyTypes.men])
            if other_emp != Empire.Indep and rnd(1, 100) < chance_to_destroy:
                add_news(game, emp, NewsTypes.PDest, loc, 0, 0, 0)
                add_news(game, other_emp, NewsTypes.PCap, loc, int(emp), 0, 0)
                return

            if not known(game, emp, obj) and other_emp != emp:
                add_news(game, emp, NewsTypes.POk, loc, 0, 0, 0)

            scout_object(game, emp, obj)

        if get_nebula(game, temp) == NebulaTypes.DarkNebula:
            return


def update_probes(game: GameEnvironment, emp: Empire) -> None:
    """Land every probe in transit and free it for relaunch.

    Probes are not really in flight -- one launched last turn arrives here at
    the start of the next, reveals what it found and is immediately ``PReady``
    again. Without this an empire launches its whole stock once and is blind
    from then on, since :func:`~recreon.primintr.get_probe` only ever returns a
    ``PReady`` one.
    """
    from .types import NO_OF_PROBES_PER_EMPIRE, ProbeStatus

    for i in range(1, NO_OF_PROBES_PER_EMPIRE + 1):
        probe = game.Universe.EmpireData[emp].Probe[i]
        if probe.Status == ProbeStatus.PInTrans:
            probe_scout(game, emp, probe.Dest)
            probe.Status = ProbeStatus.PReady


def in_range_of_starbase(game: GameEnvironment, emp: Empire, obj_xy: XYCoord) -> bool:
    """Whether any of ``emp``'s scanning starbases covers ``obj_xy``.

    Industrial complexes do not scan -- only command bases, fortresses,
    outposts and the rest. The radius is under 6, so 5 sectors.
    """
    from .misc import distance
    from .primintr import get_base_type, get_coord

    for i in range(1, MAX_NO_OF_STARBASES + 1):
        if i not in game.GlobalSets.SetOfStarbasesOf[emp]:
            continue
        base_id = IDNumber(ObjectTypes.Base, i)
        if distance(get_coord(game, base_id), obj_xy) < 6:
            if get_base_type(game, base_id) != TechnologyTypes.cmp:
                return True
    return False


def in_range_of_planet(
    game: GameEnvironment, emp: Empire, f_typ, obj_xy: XYCoord
) -> bool:
    """Whether one of ``emp``'s worlds can *detect* a fleet at ``obj_xy``.

    Weaker than scouting: it tells the empire something is there without
    revealing what. Hunter-killers and penetrators are built to slip this, and
    any nebula at all defeats it.
    """
    from .misc import distance
    from .primintr import get_coord, get_nebula
    from .types import FleetTypes, NebulaTypes

    if f_typ in (FleetTypes.HKFleet, FleetTypes.Penetrator):
        return False
    if get_nebula(game, obj_xy) != NebulaTypes.NoNeb:
        return False

    for i in range(1, game.NoOfPlanets + 1):
        if i not in game.GlobalSets.SetOfPlanetsOf[emp]:
            continue
        base_id = IDNumber(ObjectTypes.Pln, i)
        if distance(get_coord(game, base_id), obj_xy) <= 5:
            return True
    return False


def determine_if_scouted(game: GameEnvironment, emp: Empire, obj: IDNumber) -> None:
    """Decide whether ``emp`` can see ``obj`` in detail this turn.

    Two quite different paths, keyed on whether the empire knows the object
    exists at all:

    - **Known already**: it is scouted if the empire owns it, or it is within 5
      sectors of the capital, or a scanning starbase covers it. So an empire
      sees its own space and its border in detail and nothing else.
    - **Not known**: only a starbase scan can reveal it, and only on a coin
      flip -- ``Rnd(1,2)=1``. This is the one path by which an empire discovers
      something it had no idea was there, and it files an ``OutProbe``
      headline when it does.

    The coin flip means a newly-built starbase takes a few years to map its
    surroundings rather than revealing everything at once.
    """
    from .misc import distance
    from .news import NewsTypes, add_news
    from .primintr import get_capital, get_coord, get_status, known, scout_object, scouted
    from .utils.int_utils import rnd

    obj_xy = get_coord(game, obj)

    if known(game, emp, obj):
        if scouted(game, emp, obj):
            return
        cap_xy = get_coord(game, get_capital(game, emp))
        if get_status(game, obj) == emp:
            scout_object(game, emp, obj)
        elif distance(cap_xy, obj_xy) < 6:
            scout_object(game, emp, obj)
        elif in_range_of_starbase(game, emp, obj_xy):
            scout_object(game, emp, obj)
    elif rnd(1, 2) == 1 and in_range_of_starbase(game, emp, obj_xy):
        add_news(game, emp, NewsTypes.OutProbe, Location(XY=XYCoord(0, 0), ID=obj), 0, 0, 0)
        scout_object(game, emp, obj)


def scout_fleets(game: GameEnvironment, player_emp: Empire) -> None:
    """Recompute which fleets ``player_emp`` can see, and how well.

    Three tiers, and the difference between them is the whole of fleet fog of
    war:

    - **Own fleets** are always both scouted and known.
    - **Scouted** (you see what it is made of): the fleet is adjacent to one of
      your worlds or fleets -- but *only if it is not a hunter-killer group*,
      which is what lets HK raiders sit next to a world unseen -- or it is
      inside a starbase's scan.
    - **Known only** (you see something is there): `in_range_of_planet` picks
      it up at 5 sectors, unless it is an HK or penetrator fleet or sitting in
      a nebula.

    Both flags are cleared for this empire first, so a fleet that has moved out
    of range this turn is genuinely forgotten rather than remembered forever.

    A fleet spotted next to your territory files a ``FltDet`` headline. The
    location it reports is the *observer*: the world that saw it, or -- when
    the spotter was a fleet rather than a world -- the highest-numbered of your
    fleets in that sector, found by counting down from ``MaxNoOfFleets``.
    """
    from .datacnst import DirX, DirY
    from .news import NewsTypes, add_news
    from .primintr import get_fleets, get_status, type_of_fleet
    from .types import Directions, FleetTypes

    for i in range(1, MAX_NO_OF_FLEETS + 1):
        if i not in game.GlobalSets.SetOfActiveFleets:
            continue

        fleet = game.Universe.Fleet[i]
        flt_id = IDNumber(ObjectTypes.Flt, i)
        f_typ = type_of_fleet(game, flt_id)

        fleet.ScoutedBy.discard(player_emp)
        fleet.KnownBy.discard(player_emp)

        if fleet.Emp == player_emp:
            fleet.ScoutedBy.add(player_emp)
            fleet.KnownBy.add(player_emp)
            continue

        spotted = False
        if f_typ != FleetTypes.HKFleet:
            for direction in Directions:
                x = fleet.XY.x + DirX[direction]
                y = fleet.XY.y + DirY[direction]
                if not game.Galaxy.in_galaxy(x, y):
                    continue

                sector = game.Galaxy.sector(XYCoord(x, y))
                if get_status(game, sector.Obj) != player_emp and (
                    player_emp not in sector.Flts
                ):
                    continue

                fleet.ScoutedBy.add(player_emp)
                fleet.KnownBy.add(player_emp)

                loc_id = sector.Obj
                if get_status(game, sector.Obj) != player_emp:
                    # Spotted by a fleet, not a world: report the highest-
                    # numbered friendly fleet in that sector.
                    mine = get_fleets(game, XYCoord(x, y)) & (
                        game.GlobalSets.SetOfFleetsOf[player_emp]
                    )
                    j = MAX_NO_OF_FLEETS
                    while j > 0 and j not in mine:
                        j -= 1
                    loc_id = IDNumber(ObjectTypes.Flt, j)

                add_news(
                    game,
                    player_emp,
                    NewsTypes.FltDet,
                    Location(XY=XYCoord(0, 0), ID=loc_id),
                    int(fleet.Emp),
                    0,
                    0,
                )
                spotted = True
                break

        if spotted:
            continue

        if in_range_of_starbase(game, player_emp, fleet.XY):
            fleet.ScoutedBy.add(player_emp)
            fleet.KnownBy.add(player_emp)
            continue

        if in_range_of_planet(game, player_emp, f_typ, fleet.XY):
            fleet.KnownBy.add(player_emp)


def scout_objects(game: GameEnvironment, emp: Empire) -> None:
    """Sweep the space around everything ``emp`` owns, then rescan for the rest.

    Two halves. First :func:`scout` runs from every world and every fleet the
    empire holds, revealing the ring of sectors around each. Then every world,
    starbase and stargate in the galaxy is put through
    :func:`determine_if_scouted`, which is what picks up objects at a distance
    via capital and starbase scans.

    Note the second half sweeps **every** world, not only known ones -- that is
    how an empire first learns a world exists.
    """
    from .primintr import get_coord

    for i in range(1, game.NoOfPlanets + 1):
        if i in game.GlobalSets.SetOfPlanetsOf[emp]:
            scout(game, emp, get_coord(game, IDNumber(ObjectTypes.Pln, i)))

    active_empire_fleets = (
        game.GlobalSets.SetOfFleetsOf[emp] & game.GlobalSets.SetOfActiveFleets
    )
    for i in range(1, MAX_NO_OF_FLEETS + 1):
        if i in active_empire_fleets:
            scout(game, emp, get_coord(game, IDNumber(ObjectTypes.Flt, i)))

    for i in range(1, game.NoOfPlanets + 1):
        determine_if_scouted(game, emp, IDNumber(ObjectTypes.Pln, i))

    for i in range(1, MAX_NO_OF_STARBASES + 1):
        if i in game.GlobalSets.SetOfActiveStarbases:
            determine_if_scouted(game, emp, IDNumber(ObjectTypes.Base, i))

    for i in range(1, MAX_NO_OF_STARGATES + 1):
        if i in game.GlobalSets.SetOfActiveGates:
            determine_if_scouted(game, emp, IDNumber(ObjectTypes.Gate, i))


def probes_return(game: GameEnvironment, emp: Empire) -> None:
    """Free any probe sitting at its destination for relaunch.

    Nothing in v2.0 sets ``PAtDest`` -- :func:`update_probes` takes a probe
    straight from ``PInTrans`` back to ``PReady`` -- so this never has anything
    to do. Ported as part of the unit's interface.
    """
    from .types import NO_OF_PROBES_PER_EMPIRE, ProbeStatus

    for i in range(1, NO_OF_PROBES_PER_EMPIRE + 1):
        probe = game.Universe.EmpireData[emp].Probe[i]
        if probe.Status == ProbeStatus.PAtDest:
            probe.Status = ProbeStatus.PReady


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


def destroy_stargate(game: GameEnvironment, gte_id: IDNumber) -> None:
    """Remove a stargate, emptying the sector it stood in.

    The gate record itself is left as it was; only the sector pointer and the
    active set are cleared, so the slot is free for reuse.
    """
    gate = game.Universe.Stargate[gte_id.Index]
    game.Galaxy.sector(gate.XY).Obj = empty_quadrant()
    game.GlobalSets.SetOfActiveGates.discard(gte_id.Index)


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


# --- Construction ------------------------------------------------------------


def next_constr_slot(game: GameEnvironment) -> int:
    """Highest free construction-site index, or 0 when all are taken.

    Counts down from the top like the starbase and stargate allocators, so
    slot assignment matches when comparing runs side by side.
    """
    slot = MAX_NO_OF_CONSTR_SITES
    while slot > 0 and slot in game.GlobalSets.SetOfActiveConstructionSites:
        slot -= 1
    return slot


def construction(
    game: GameEnvironment,
    empr: Empire,
    cons_type: TechnologyTypes,
    loc: XYCoord,
) -> IDNumber:
    """Break ground on a construction site. Returns its ID, or EmptyQuadrant.

    The site occupies its sector immediately -- it is a real object that can
    be scouted, named and attacked from the moment it exists, long before it
    finishes. Only the builder knows about it to begin with.

    Silently does nothing when every slot is in use, as the original does.
    """
    i = next_constr_slot(game)
    if i == 0:
        return empty_quadrant()

    con_id = IDNumber(ObjectTypes.Con, i)
    site = game.Universe.Constr[i]
    site.XY = loc
    site.Emp = empr
    site.CTyp = cons_type
    site.ScoutedBy = {empr}
    site.KnownBy = {empr}
    site.TimeToCompletion = YearsToBuild[cons_type]

    game.GlobalSets.SetOfActiveConstructionSites.add(i)
    game.GlobalSets.SetOfConstructionSitesOf[empr].add(i)
    game.Galaxy.sector(loc).Obj = con_id
    return con_id


def destroy_construction(game: GameEnvironment, con_id: IDNumber) -> None:
    """Cancel a construction site, emptying the sector it occupied."""
    site = game.Universe.Constr[con_id.Index]
    old_emp = site.Emp
    game.Galaxy.sector(site.XY).Obj = empty_quadrant()
    game.GlobalSets.SetOfActiveConstructionSites.discard(con_id.Index)
    game.GlobalSets.SetOfConstructionSitesOf[old_emp].discard(con_id.Index)


# --- Fleet helpers -----------------------------------------------------------

#: Order in which BalanceFleet jettisons cargo: cheapest first, ambrosia last.
#: 1-based in the original; index 0 is unused here for the same reason.
CARGO_PRIORITY: tuple[TechnologyTypes | None, ...] = (
    None,
    TechnologyTypes.che,
    TechnologyTypes.sup,
    TechnologyTypes.met,
    TechnologyTypes.men,
    TechnologyTypes.nnj,
    TechnologyTypes.tri,
    TechnologyTypes.amb,
)


def balance_fleet(ships: dict[TechnologyTypes, int], cargo: dict[TechnologyTypes, int]) -> None:
    """Jettison cargo in place until the fleet fits in its own transports.

    Works down CARGO_PRIORITY dumping whole cargo types, then partly refills
    the last one to exactly fill the space that freed up. A fleet whose
    transports were destroyed loses cargo this way rather than becoming
    illegal.
    """
    to_remove = 1
    thing = CARGO_PRIORITY[to_remove]
    space_left = fleet_cargo_space(ships, cargo)

    while space_left < 0:
        cargo[thing] = 0
        new_space_left = fleet_cargo_space(ships, cargo)
        if new_space_left < 0:
            space_left = new_space_left
            to_remove += 1
            thing = CARGO_PRIORITY[to_remove]
        else:
            cargo[thing] = new_space_left * CargoSpace[thing]
            space_left = 0


def passing_through_fortress(game: GameEnvironment, flt_xy: XYCoord) -> bool:
    """Whether a fortress starbase sits on the fleet's current sector."""
    base_obj = get_object(game, flt_xy)
    return (
        base_obj.ObjTyp == ObjectTypes.Base
        and get_base_type(game, base_obj) == TechnologyTypes.frt
    )


def passing_through_gate(
    game: GameEnvironment, flt_id: IDNumber, flt_xy: XYCoord, dest_xy: XYCoord
) -> bool:
    """Whether the fleet can jump from ``flt_xy`` to ``dest_xy`` via a gate.

    A plain gate (``gte``) sends a fleet anywhere. A link (``lnk``) only
    connects to another gate or link at the far end -- and, per the original,
    only when the destination gate's frequency does *not* match, which is what
    distinguishes a link's own network from a gate the fleet could simply use.

    Fortresses are handled separately by the caller.
    """
    gate_obj = get_object(game, flt_xy)
    if gate_obj.ObjTyp != ObjectTypes.Gate:
        return False
    if get_warp_link_freq(game, get_status(game, flt_id), gate_obj) != get_warp_link_freq(
        game, get_status(game, gate_obj), gate_obj
    ):
        return False

    gate_type = get_gate_type(game, gate_obj)
    if gate_type == TechnologyTypes.gte:
        return True
    if gate_type == TechnologyTypes.lnk:
        dest_obj = get_object(game, dest_xy)
        return (
            dest_obj.ObjTyp == ObjectTypes.Gate
            and get_gate_type(game, dest_obj)
            in (TechnologyTypes.lnk, TechnologyTypes.gte)
            and get_warp_link_freq(game, get_status(game, flt_id), dest_obj)
            != get_warp_link_freq(game, get_status(game, dest_obj), dest_obj)
        )
    return False


# --- Travel estimates --------------------------------------------------------


def estimated_date_of_arrival(game: GameEnvironment, obj: IDNumber) -> int:
    """Years until ``obj`` reaches its destination.

    A fleet riding a gate always arrives next year whatever the distance. A
    fortress shortens the trip by the four sectors it catapults the fleet --
    ``passing_through_fortress`` is checked at the fleet's *current* position,
    so the boost only counts while the fleet is still standing on it.

    Bases move one sector a year, so their estimate is the raw Chebyshev
    distance. The original leaves the result uninitialised for any other
    object type; every caller passes a fleet or a base.
    """
    from .fleet import type_of_fleet

    if obj.ObjTyp == ObjectTypes.Flt:
        fleet = game.Universe.Fleet[obj.Index]
        if passing_through_gate(game, obj, fleet.XY, fleet.Dest):
            return 1

        dist = max(abs(fleet.XY.x - fleet.Dest.x), abs(fleet.XY.y - fleet.Dest.y))
        if passing_through_fortress(game, fleet.XY):
            dist = max(dist - 4, 1)

        quads_per_year = FltMovementRate[type_of_fleet(game, obj)]
        eda = dist // quads_per_year
        if dist % quads_per_year > 0:
            eda += 1
        return eda

    if obj.ObjTyp == ObjectTypes.Base:
        base = game.Universe.Starbase[obj.Index]
        return max(abs(base.XY.x - base.Dest.x), abs(base.XY.y - base.Dest.y))

    return 0


def estimated_range(game: GameEnvironment, obj: IDNumber) -> int:
    """How many years of travel ``obj`` has fuel for.

    ``fuel_consumption`` starts at 1 rather than 0, so this cannot divide by
    zero even for an empty fleet. A base burns a flat 100 tons a year, which
    is where its divisor comes from.
    """
    from .fleet import get_fleet_fuel
    from .misc import fuel_consumption
    from .primintr import get_cargo, get_ships
    from .utils.pascal import trunc

    ships = get_ships(game, obj)
    cargo = get_cargo(game, obj)

    if obj.ObjTyp == ObjectTypes.Flt:
        return trunc(get_fleet_fuel(game, obj) / fuel_consumption(ships, cargo))
    if obj.ObjTyp == ObjectTypes.Base:
        return cargo[TechnologyTypes.tri] // 100
    return 0


def get_nearest_worlds(
    game: GameEnvironment, xy: XYCoord, n: int, set_to_consider: set[int]
) -> list[IDNumber]:
    """The ``n`` worlds in ``set_to_consider`` closest to ``xy``.

    A bucket sort by distance rather than a comparison sort: every world is
    dropped into the bucket for its distance, then the buckets are read out in
    order until ``n`` have been taken. Worlds tie-break by index, because the
    original appends to each bucket's list rather than prepending.

    A world sitting exactly on ``xy`` lands in bucket 0 and so comes back
    first. Returns fewer than ``n`` when the set holds fewer -- and an empty
    list for an empty set, which is where the original hands its caller a nil
    pointer to dereference.
    """
    from .misc import distance
    from .primintr import get_coord

    size = game.Galaxy.size
    buckets: list[list[IDNumber]] = [[] for _ in range(size + 1)]

    for i in range(1, game.NoOfPlanets + 1):
        if i not in set_to_consider:
            continue
        pln_id = IDNumber(ObjectTypes.Pln, i)
        dist = distance(get_coord(game, pln_id), xy)
        if dist <= size:
            buckets[dist].append(pln_id)

    near: list[IDNumber] = []
    for bucket in buckets:
        for pln_id in bucket:
            if len(near) >= n:
                return near
            near.append(pln_id)

    return near


# --- Empire totals -----------------------------------------------------------


def get_empire_status(
    game: GameEnvironment, emp: Empire
) -> tuple[int, int, int, dict[TechnologyTypes, int]]:
    """Vital statistics for an empire.

    Returns ``(planets, total_pop, ship_ind, total_ships)`` -- world count,
    population in tens of millions, shipyard industry in tenths, and every
    ship the empire owns wherever it is standing.

    Starbases count toward ``planets`` alongside worlds, so the "number of
    worlds" this reports is really "number of holdings". Only a ``cmp``
    industrial complex contributes shipyard industry; other base types are
    counted as holdings but build nothing.
    """
    planets = 0
    total_pop = 0
    ship_ind = 0.0
    total_ships = ship_array()

    universe = game.Universe

    for i in range(1, game.NoOfPlanets + 1):
        if i not in game.GlobalSets.SetOfPlanetsOf[emp]:
            continue
        planet = universe.Planet[i]
        planets += 1
        total_pop += planet.Pop
        ip = (TechAdj2[planet.Tech] / 100) * ((planet.Eff + 250) / 100) / K6
        for ind in SHIPYARD_INDUSTRIES:
            ship_ind += ip * (planet.Indus[ind] + K4) ** 2
        for shp in SHIP_TYPES:
            total_ships[shp] += planet.Ships[shp]

    for i in range(1, MAX_NO_OF_STARBASES + 1):
        if i not in game.GlobalSets.SetOfStarbasesOf[emp]:
            continue
        base = universe.Starbase[i]
        planets += 1
        total_pop += base.Pop
        for shp in SHIP_TYPES:
            total_ships[shp] += base.Ships[shp]
        if base.STyp == TechnologyTypes.cmp:
            ip = (TechAdj2[base.Tech] / 100) * ((base.Eff + 250) / 100) / K6
            for ind in SHIPYARD_INDUSTRIES:
                ship_ind += ip * (base.Indus[ind] + K4) ** 2

    active = game.GlobalSets.SetOfFleetsOf[emp] & game.GlobalSets.SetOfActiveFleets
    for i in sorted(active):
        fleet = universe.Fleet[i]
        for shp in SHIP_TYPES:
            total_ships[shp] += fleet.Ships[shp]

    return planets, total_pop, pascal_round(ship_ind), total_ships


def destroy_empire(game: GameEnvironment, emp: Empire) -> None:
    """Wipe an empire out: worlds go independent, fleets are aborted and lost.

    Starbases change hands but keep their contents. Fleets are unloaded onto
    whatever object shares their sector before being destroyed, so a fleet
    dying over a friendly world still hands its cargo over.

    ``CleanUpNPE`` is not called. The NPE subsystem is Phase 7, and while
    ``npe/core.py`` is now ported nothing drives it yet, so there is still
    nothing for it to release. This needs wiring once the personas own
    per-empire state -- ``conquer_empire`` reaches here whenever a non-player
    empire's capital falls with no successor world.
    """
    from .fleet import abort_fleet, destroy_fleet
    from .news import erase_news
    from .primintr import (
        delete_all_names,
        get_coord,
        initialize_issp,
        set_status,
        set_type,
    )

    for index in range(1, game.NoOfPlanets + 1):
        obj = IDNumber(ObjectTypes.Pln, index)
        if get_status(game, obj) == emp:
            set_status(game, obj, Empire.Indep)
            set_type(game, obj, WorldTypes.IndTyp)
            initialize_issp(game, obj)

    for index in sorted(game.GlobalSets.SetOfStarbasesOf[emp]):
        set_status(game, IDNumber(ObjectTypes.Base, index), Empire.Indep)

    fleets = game.GlobalSets.SetOfFleetsOf[emp] & game.GlobalSets.SetOfActiveFleets
    for index in sorted(fleets):
        flt_id = IDNumber(ObjectTypes.Flt, index)
        ground = get_object(game, get_coord(game, flt_id))
        if ground != empty_quadrant():
            abort_fleet(game, flt_id, ground, True)
        destroy_fleet(game, flt_id)

    erase_news(game, emp)
    delete_all_names(game, emp)

    game.Universe.EmpireData[emp].InUse = False


__all__ = [
    "CARGO_PRIORITY",
    "Gamma",
    "balance_fleet",
    "create_planet",
    "create_stargate",
    "construction",
    "destroy_construction",
    "destroy_empire",
    "destroy_stargate",
    "next_constr_slot",
    "next_stargate_slot",
    "passing_through_fortress",
    "passing_through_gate",
    "scout",
    "create_starbase",
    "get_industrial_distribution",
    "get_optimum_indus",
    "next_starbase_slot",
    "ObjectTypes",
]
