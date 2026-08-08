"""The berserker empire.

Port of NPE04.PAS. The berserker is the only persona built around *starbases*
rather than worlds: its command bases and fortresses crawl across the galaxy
under `sbase.move_player_starbases`, and each one carries its own little state
machine deciding where to go and what to hit. Fleets are launched from a base,
strike whatever it is parked next to, and come straight back to it.

The base state machine, in `BaseMissionTypes`:

``AttackBMS``
    Closing on a target. Once in range -- 5 sectors for a fortress, adjacent
    for a command base -- it launches the strike and waits.
``WaitForAttackBMS``
    Strike away. Counts up; at 3 it re-anchors itself, and past 10 it gives up
    and picks a new target.
``FindHomeBMS``
    Too weak to fight. Looks for a regional capital within 10 sectors to
    refuel at, and wanders if there is none.
``RefuelBMS``
    Heading to that capital; on arrival the capital fires an enormous supply
    fleet back at it.
``WanderAroundBMS``
    Nothing to do. Drifts to a random sector for up to 10 years, then retargets.
``DefendBMS``
    An empty handler. Nothing ever sets this mission, and if something did the
    base would sit inert forever.

What makes a berserker a berserker is `_bsrk_destroy_world`: one conquest in
three is followed by killing half the population, gutting the industry and
throwing the world back to a pre-atomic tech level. It does not keep what it
takes -- `plunder_world` strips it first -- so a berserker leaves ruins behind
rather than an empire.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..attack import AttackResultTypes
from ..fleet import abort_fleet, destroy_fleet, set_fleet_destination
from ..galaxy import Location, XYCoord, limbo
from ..misc import distance, military_power
from ..news import NewsTypes, add_news, get_news_list
from ..primintr import (
    get_base_type,
    get_capital,
    get_cargo,
    get_coord,
    get_defns,
    get_fleet_status,
    get_indus,
    get_population,
    get_ships,
    get_status,
    npe_data_index,
    put_indus,
    set_population,
    set_tech,
)
from ..types import (
    MAX_NO_OF_STARBASES,
    NO_OF_FLEETS_PER_EMPIRE,
    Empire,
    FleetStatus,
    IDNumber,
    IndusTypes,
    ObjectTypes,
    TechLevel,
    TechnologyTypes,
    defns_array,
    indus_range,
)
from ..utils.int_utils import greater_int, lesser_int, rnd
from ..utils.pascal import pascal_random_real, pascal_round
from .core import (
    MAX_NO_OF_REGIONS,
    create_region_array,
    deploy_battle_fleet,
    enforce_npe_data_links,
    fleet_entry,
    implement_jump_attack_msn,
    plunder_world,
    set_empire_defenses,
)
from .types import BaseMissionTypes, BerserkerDataRecord, MissionTypes

if TYPE_CHECKING:
    from ..environ import GameEnvironment

T = TechnologyTypes
BM = BaseMissionTypes

#: Below this much military power a base gives up attacking and goes to refuel.
MIN_BASE_POWER = 100_000

#: A base further than this from any regional capital wanders instead of
#: trying to get home.
MAX_DISTANCE_TO_HOME = 10

#: Stands in for the original's "no candidate yet" sentinel distance.
NO_CANDIDATE = 1000


def _get_nearest_bsrk_base(
    game: GameEnvironment, emp: Empire, flt_id: IDNumber
) -> IDNumber:
    """The mobile base nearest ``flt_id``, falling back to the capital.

    Only command bases and fortresses count -- those are the two types
    `sbase.move_player_starbases` will tow.

    **Unreachable in v2.0.** `GetNearestBSRKBase` is declared in NPE04.PAS and
    called from nowhere in the tree: a returning strike force uses the
    `HomeBaseID` recorded when it launched instead, which is what
    `_bsrk_course_correction` keeps it aimed at. Ported as part of the unit,
    like `battle.py` and `holocaust_world`.
    """
    flt_xy = get_coord(game, flt_id)
    best_distance = NO_CANDIDATE
    base_id = None

    for i in range(1, MAX_NO_OF_STARBASES + 1):
        if i not in game.GlobalSets.SetOfStarbasesOf[emp]:
            continue
        test_id = IDNumber(ObjectTypes.Base, i)
        if get_base_type(game, test_id) not in (T.cmm, T.frt):
            continue
        dist = distance(flt_xy, get_coord(game, test_id))
        if dist < best_distance:
            best_distance = dist
            base_id = test_id

    if best_distance == NO_CANDIDATE:
        return get_capital(game, emp)
    return base_id


def _new_bsrk_base_target(
    game: GameEnvironment, emp: Empire, base_id: IDNumber, base_data: list
) -> None:
    """Pick what this base goes after next, or send it home if it is too weak.

    A world qualifies as a target if it is worth looting -- more than 2000 of
    metal and chemicals together, or more than 1000 trillum -- and if the
    base's power, jittered upward by up to 100%, beats its defense.

    A base with more than 4000 LAMs ignores the target's planetary defenses
    entirely when judging that, on the reasoning that it can flatten them
    before landing.

    Nearest qualifying world wins. If none does, the base wanders.
    """
    entry = base_data[base_id.Index]
    base_xy = get_coord(game, base_id)
    flt_sh = get_ships(game, base_id)
    base_lams = get_defns(game, base_id)[T.LAM]
    base_power = military_power(flt_sh, defns_array())

    if base_power < MIN_BASE_POWER:
        entry.Mission = BM.FindHomeBMS
        return

    best_distance = NO_CANDIDATE
    best_target_id = None
    best_target_xy = None

    for i in range(1, game.NoOfPlanets + 1):
        test_id = IDNumber(ObjectTypes.Pln, i)
        if get_status(game, test_id) == emp:
            continue

        test_cr = get_cargo(game, test_id)
        if not (test_cr[T.met] + test_cr[T.che] > 2000 or test_cr[T.tri] > 1000):
            continue

        test_sh = get_ships(game, test_id)
        test_df = get_defns(game, test_id) if base_lams < 4000 else defns_array()

        if base_power + pascal_round(base_power * pascal_random_real()) > military_power(
            test_sh, test_df
        ):
            test_xy = get_coord(game, test_id)
            dist = distance(test_xy, base_xy)
            if dist < best_distance:
                best_distance = dist
                best_target_id = test_id
                best_target_xy = test_xy

    if best_distance < NO_CANDIDATE:
        entry.Mission = BM.AttackBMS
        entry.TargetID = best_target_id
        set_fleet_destination(game, base_id, best_target_xy)
    else:
        entry.Mission = BM.WanderAroundBMS
        entry.Count = 0
        set_fleet_destination(
            game,
            base_id,
            XYCoord(rnd(1, game.Galaxy.size), rnd(1, game.Galaxy.size)),
        )


def _bsrk_destroy_world(game: GameEnvironment, emp: Empire, target_id: IDNumber) -> None:
    """Wreck a world: kill the people, gut the industry, undo the technology.

    Deaths are at least 100 and at most everything bar ten, and industries are
    halved or shaved by a random 10--50 on a coin flip each. Technology is
    reset to a *random* one of the bottom three levels, so a world can come out
    of this having technically advanced -- there is no check that the new level
    is below the old.
    """
    owner = get_status(game, target_id)
    loc = Location(XY=limbo(), ID=target_id)
    add_news(game, owner, NewsTypes.WHolo, loc, 0, 0, 0)

    pop = get_population(game, target_id)
    deaths = lesser_int(pop - 10, greater_int(pop // 2, 100 + rnd(1, 100)))
    set_population(game, target_id, pop - deaths)
    add_news(game, owner, NewsTypes.DthHolo, loc, deaths, 0, 0)

    indus = get_indus(game, target_id)
    for ind in indus_range(IndusTypes.BioInd, IndusTypes.TriInd):
        if rnd(1, 2) == 1:
            # GreaterInt of a value and that value minus a positive number is
            # always the value itself, so this arm destroys the industry
            # outright rather than shaving 10-50 off it.
            ind_lost = greater_int(indus[ind], indus[ind] - rnd(10, 50))
        else:
            ind_lost = indus[ind] // 2

        if ind_lost > 0:
            indus[ind] -= ind_lost
            add_news(game, owner, NewsTypes.IndDs, loc, ind_lost, int(ind), 0)
    put_indus(game, target_id, indus)

    new_tech = TechLevel(rnd(0, 2))
    set_tech(game, target_id, new_tech)
    add_news(game, owner, NewsTypes.RTech, loc, int(new_tech), 0, 0)


def _bsrk_course_correction(
    game: GameEnvironment, flt_id: IDNumber, fleet_data: list
) -> None:
    """Keep a returning fleet aimed at its base, which moves under it.

    This is the whole reason berserker fleets need special handling: their home
    is a starbase that crawls a sector a year, so a destination fixed at launch
    would miss.
    """
    entry = fleet_data[npe_data_index(game, flt_id)]
    if entry.Mission == MissionTypes.BSRKReturnMSN:
        set_fleet_destination(game, flt_id, get_coord(game, entry.TargetID))


def _get_power_to_use(game: GameEnvironment, target_id: IDNumber) -> tuple[int, int]:
    """Size a berserker strike: 50000 plus two to five times the defense.

    Far heavier than the kingdoms' 1.5--2.5x, and with a 50000 floor that makes
    even an undefended world draw a large fleet.
    """
    ships = get_ships(game, target_id)
    cargo = get_cargo(game, target_id)
    defns = get_defns(game, target_id)

    target_defense = military_power(ships, defns)
    target_men = cargo[T.men] + 4 * cargo[T.nnj] + 10

    fleet_power = (
        50_000 + (rnd(2, 5) * target_defense) + (target_defense // rnd(2, 25))
    )
    fleet_gat = 2 * target_men
    return fleet_power, fleet_gat


def _deploy_bsrk_attack_msn(
    game: GameEnvironment,
    emp: Empire,
    base_id: IDNumber,
    target_id: IDNumber,
    fleet_data: list,
) -> None:
    fleet_power, fleet_gat = _get_power_to_use(game, target_id)
    deploy_battle_fleet(
        game,
        emp,
        fleet_data,
        base_id,
        fleet_power,
        fleet_gat,
        MissionTypes.BSRKAttackMSN,
        target_id,
    )


def _implement_bsrk_return_msn(
    game: GameEnvironment,
    emp: Empire,
    flt_id: IDNumber,
    base_id: IDNumber,
    data: BerserkerDataRecord,
) -> None:
    """A strike force reaches its base and folds back into it.

    If the base has changed hands while the fleet was away, the fleet is simply
    destroyed with everything it was carrying -- a berserker has nowhere else
    to put it.
    """
    if emp == get_status(game, base_id):
        abort_fleet(game, flt_id, base_id, True)
        destroy_fleet(game, flt_id)
        _new_bsrk_base_target(game, emp, base_id, data.BaseData)
    else:
        destroy_fleet(game, flt_id)


def _implement_bsrk_attack_msn(
    game: GameEnvironment,
    emp: Empire,
    flt_id: IDNumber,
    base_id: IDNumber,
    target_id: IDNumber,
    data: BerserkerDataRecord,
) -> None:
    """Hit the world, loot it, and one time in three raze it."""
    result = implement_jump_attack_msn(
        game, emp, flt_id, target_id, base_id, data.FleetData
    )

    if result == AttackResultTypes.DefConqueredART:
        plunder_world(game, emp, flt_id, target_id)
        if rnd(1, 3) == 1:
            _bsrk_destroy_world(game, emp, target_id)

    if result == AttackResultTypes.AttDestroyedART:
        # Nothing came back; the base needs something else to do.
        _new_bsrk_base_target(game, emp, base_id, data.BaseData)
    else:
        entry = fleet_entry(game, flt_id, data.FleetData)
        if entry is None:
            return
        entry.Mission = MissionTypes.BSRKReturnMSN
        entry.TargetID = base_id
        set_fleet_destination(game, flt_id, get_coord(game, base_id))


def _implement_attack_bms(
    game: GameEnvironment, emp: Empire, base_id: IDNumber, data: BerserkerDataRecord
) -> None:
    """Launch once the base is close enough. A fortress reaches five times further."""
    entry = data.BaseData[base_id.Index]
    s_typ = get_base_type(game, base_id)
    dist = distance(get_coord(game, base_id), get_coord(game, entry.TargetID))

    if (s_typ == T.frt and dist <= 5) or dist == 1:
        _deploy_bsrk_attack_msn(game, emp, base_id, entry.TargetID, data.FleetData)
        entry.Mission = BM.WaitForAttackBMS
        entry.Count = 0


def _implement_defend_bms(
    game: GameEnvironment, emp: Empire, base_id: IDNumber, base_data: list
) -> None:
    """Do nothing.

    An empty handler in the original, and nothing ever assigns ``DefendBMS`` --
    it is declared in `BaseMissionTypes` and used nowhere. A base that somehow
    reached this mission would sit still forever, since only the handlers
    change `Mission`.
    """


def _implement_find_home_bms(
    game: GameEnvironment,
    emp: Empire,
    base_id: IDNumber,
    rcap: list[IDNumber],
    base_data: list,
) -> None:
    """Head for the nearest regional capital, or wander if none is near enough."""
    from ..misc import same_id
    from ..types import empty_quadrant

    entry = base_data[base_id.Index]
    base_xy = get_coord(game, base_id)
    best_distance = NO_CANDIDATE
    best_home_id = None

    for i in range(1, MAX_NO_OF_REGIONS + 1):
        if same_id(rcap[i], empty_quadrant()):
            continue
        dist = distance(get_coord(game, rcap[i]), base_xy)
        if dist < best_distance:
            best_distance = dist
            best_home_id = rcap[i]

    if best_distance <= MAX_DISTANCE_TO_HOME:
        entry.Mission = BM.RefuelBMS
        entry.TargetID = best_home_id
        set_fleet_destination(game, base_id, get_coord(game, best_home_id))
    else:
        entry.Mission = BM.WanderAroundBMS
        entry.Count = 0
        set_fleet_destination(
            game,
            base_id,
            XYCoord(rnd(1, game.Galaxy.size), rnd(1, game.Galaxy.size)),
        )


def _implement_refuel_bms(
    game: GameEnvironment,
    emp: Empire,
    base_id: IDNumber,
    rcap: list[IDNumber],
    data: BerserkerDataRecord,
) -> None:
    """Once alongside the capital, have it fire everything into the base.

    The 9,000,000 power and troop figures are not a budget so much as "send
    all of it" -- `get_fleet_composition` caps against what the world actually
    holds, so this asks for more than any world could field.
    """
    entry = data.BaseData[base_id.Index]
    base_xy = get_coord(game, base_id)
    target_xy = get_coord(game, entry.TargetID)

    if distance(base_xy, target_xy) < 5 and get_status(game, entry.TargetID) == emp:
        deploy_battle_fleet(
            game,
            emp,
            data.FleetData,
            entry.TargetID,
            9_000_000,
            9_000_000,
            MissionTypes.BSRKReturnMSN,
            base_id,
        )
        entry.Mission = BM.WaitForAttackBMS
        entry.Count = 0


def _implement_wait_for_attack_bms(
    game: GameEnvironment, emp: Empire, base_id: IDNumber, base_data: list
) -> None:
    """Hold station while the strike is out.

    At exactly 3 the base re-anchors on its own sector -- it has been drifting
    toward the target and this stops it overrunning. Past 10 it assumes the
    strike is not coming back.
    """
    entry = base_data[base_id.Index]
    if entry.Count > 10:
        _new_bsrk_base_target(game, emp, base_id, base_data)
    elif entry.Count == 3:
        set_fleet_destination(game, base_id, get_coord(game, base_id))
        entry.Count += 1
    else:
        entry.Count += 1


def _implement_wander_around_bms(
    game: GameEnvironment, emp: Empire, base_id: IDNumber, base_data: list
) -> None:
    """Drift for up to ten years, then look for something to do."""
    entry = base_data[base_id.Index]
    if entry.Count > 10:
        _new_bsrk_base_target(game, emp, base_id, base_data)
    else:
        entry.Count += 1


def _bsrk_review_news(
    game: GameEnvironment, emp: Empire, data: BerserkerDataRecord
) -> None:
    """React to bases that could not move. A berserker reads only ``BseBlocked``.

    Blocked while closing on a target: strike now if within 8 sectors --
    further than `_implement_attack_bms` would normally allow -- otherwise give
    up and wander. Blocked while waiting: re-anchor. Blocked while refuelling
    or wandering: pick a new random heading.
    """
    news_list = get_news_list(game, emp)

    i = 0
    while i < len(news_list):
        item = news_list[i]
        if item.Headline == NewsTypes.BseBlocked:
            base_id = item.Loc1.ID
            entry = data.BaseData[base_id.Index]
            base_xy = get_coord(game, base_id)
            target_xy = get_coord(game, entry.TargetID)

            if entry.Mission == BM.AttackBMS:
                if distance(base_xy, target_xy) < 8:
                    _deploy_bsrk_attack_msn(
                        game, emp, base_id, entry.TargetID, data.FleetData
                    )
                    entry.Mission = BM.WaitForAttackBMS
                    entry.Count = 0
                else:
                    entry.Mission = BM.WanderAroundBMS
                    entry.Count = 0
                    set_fleet_destination(
                        game,
                        base_id,
                        XYCoord(rnd(1, game.Galaxy.size), rnd(1, game.Galaxy.size)),
                    )
            elif entry.Mission == BM.DefendBMS:
                pass
            elif entry.Mission == BM.RefuelBMS:
                entry.Mission = BM.WanderAroundBMS
                entry.Count = 0
                set_fleet_destination(
                    game,
                    base_id,
                    XYCoord(rnd(1, game.Galaxy.size), rnd(1, game.Galaxy.size)),
                )
            elif entry.Mission == BM.WaitForAttackBMS:
                set_fleet_destination(game, base_id, base_xy)
            elif entry.Mission == BM.WanderAroundBMS:
                set_fleet_destination(
                    game,
                    base_id,
                    XYCoord(rnd(1, game.Galaxy.size), rnd(1, game.Galaxy.size)),
                )
        i += 1


def _update_bases(
    game: GameEnvironment, emp: Empire, rcap: list[IDNumber], data: BerserkerDataRecord
) -> None:
    """Advance each towable base's state machine one year."""
    for i in range(1, MAX_NO_OF_STARBASES + 1):
        if i not in game.GlobalSets.SetOfStarbasesOf[emp]:
            continue
        base_id = IDNumber(ObjectTypes.Base, i)
        if get_base_type(game, base_id) not in (T.cmm, T.frt):
            continue

        mission = data.BaseData[i].Mission
        if mission == BM.AttackBMS:
            _implement_attack_bms(game, emp, base_id, data)
        elif mission == BM.DefendBMS:
            _implement_defend_bms(game, emp, base_id, data.BaseData)
        elif mission == BM.FindHomeBMS:
            _implement_find_home_bms(game, emp, base_id, rcap, data.BaseData)
        elif mission == BM.RefuelBMS:
            _implement_refuel_bms(game, emp, base_id, rcap, data)
        elif mission == BM.WaitForAttackBMS:
            _implement_wait_for_attack_bms(game, emp, base_id, data.BaseData)
        elif mission == BM.WanderAroundBMS:
            _implement_wander_around_bms(game, emp, base_id, data.BaseData)
        else:
            # NoBMS, i.e. a base that has never been given orders.
            _new_bsrk_base_target(game, emp, base_id, data.BaseData)


def _update_fleets(
    game: GameEnvironment, emp: Empire, rcap: list[IDNumber], data: BerserkerDataRecord
) -> None:
    """Run arrival handlers. Only the two berserker missions have one.

    ``HomeBaseID`` rather than the regional capital is what an attacking fleet
    is told to return to -- the base that launched it, which has been moving
    the whole time.
    """
    for i in range(1, NO_OF_FLEETS_PER_EMPIRE + 1):
        entry = data.FleetData[i]
        index = entry.Index
        if index <= 0 or index not in game.GlobalSets.SetOfActiveFleets:
            continue

        flt_id = IDNumber(ObjectTypes.Flt, index)
        _bsrk_course_correction(game, flt_id, data.FleetData)

        if get_fleet_status(game, flt_id) != FleetStatus.FReady:
            continue

        if entry.Mission == MissionTypes.BSRKReturnMSN:
            _implement_bsrk_return_msn(game, emp, flt_id, entry.TargetID, data)
        elif entry.Mission == MissionTypes.BSRKAttackMSN:
            _implement_bsrk_attack_msn(
                game, emp, flt_id, entry.HomeBaseID, entry.TargetID, data
            )
        else:
            destroy_fleet(game, flt_id)


def initialize_berserker_npe(
    game: GameEnvironment, emp: Empire, data: BerserkerDataRecord
) -> None:
    """Give every towable base a first target, and roll defenses."""
    for i in range(1, MAX_NO_OF_STARBASES + 1):
        if i not in game.GlobalSets.SetOfStarbasesOf[emp]:
            continue
        base_id = IDNumber(ObjectTypes.Base, i)
        if get_base_type(game, base_id) in (T.cmm, T.frt):
            _new_bsrk_base_target(game, emp, base_id, data.BaseData)

    set_empire_defenses(game, emp)


def implement_berserker_npe(
    game: GameEnvironment, emp: Empire, data: BerserkerDataRecord
) -> None:
    """One berserker turn: read blocked-base news, run fleets, then run bases."""
    enforce_npe_data_links(game, emp, data.FleetData)
    rcap = create_region_array(game, emp)

    _bsrk_review_news(game, emp, data)
    _update_fleets(game, emp, rcap, data)
    _update_bases(game, emp, rcap, data)


def clean_up_berserker_npe(
    game: GameEnvironment, data: BerserkerDataRecord
) -> None:
    """Release the persona's data. Nothing to unwind."""
