"""The pirate empire.

Port of NPE01.PAS. A pirate does not conquer, defend or negotiate -- it has no
`StateDeptArray` and no `NPECharacterRecord` at all. It hunts. Two loops make
up its whole behaviour:

**Commerce raiding.** Fleets are sent to patrol a 5x5 block of the galaxy,
loiter there on ``WaitForTrnMSN`` looking for a transport convoy weak enough to
take, intercept it where it is *going* rather than where it is, strip it, and
run home. Blocks that yield prizes get more attractive, blocks that do not get
less -- this is the ``HuntingGround`` grid, and it is the only memory a pirate
keeps between years.

**World raiding.** Separately, any pirate world with a large enough stock of
hunter-killers, jumpships and jump transports assembles a raid on the richest
poorly defended world in the galaxy, takes it, and strips it bare via
`plunder_world`. Nothing is held: the world is left independent and empty.

A pirate never repairs a stranded fleet -- `_review_news` destroys any fleet
that reports out of fuel outright.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..attack import AttackIntentionTypes, AttackResultTypes
from ..attnpe import npe_attack
from ..fleet import (
    deploy_fleet,
    destroy_fleet,
    get_fleet_destination,
    get_new_pos,
    set_fleet_destination,
)
from ..galaxy import XYCoord
from ..intrface import balance_fleet, get_nearest_worlds
from ..misc import distance, no_ships, same_xy
from ..news import NewsTypes, get_news_list
from ..primintr import (
    get_cargo,
    get_coord,
    get_defns,
    get_fleet_status,
    get_fleets,
    get_object,
    get_ships,
    get_tech,
    npe_data_index,
    put_cargo,
    put_ships,
    set_npe_data_index,
)
from ..types import (
    MAX_NO_OF_FLEETS,
    NO_OF_FLEETS_PER_EMPIRE,
    Empire,
    FleetStatus,
    IDNumber,
    ObjectTypes,
    TechLevel,
    TechnologyTypes,
    cargo_array,
    empty_quadrant,
    ship_array,
)
from ..utils.int_utils import greater_int, lesser_int, rnd, rnd_var
from ..utils.pascal import pascal_round
from .core import next_fleet_data_slot, plunder_world, set_empire_defenses
from .types import MissionTypes, PirateDataRecord

if TYPE_CHECKING:
    from ..environ import GameEnvironment

T = TechnologyTypes

#: Sectors on a side of one hunting-ground block.
BLOCK_SIZE = 5

#: What every block starts at. ``FillChar(HuntingGround,SizeOf(...),25)`` fills
#: bytes, and the array really is ``OF Byte``, so this is 25 and not a
#: FillChar-widened value.
INITIAL_ATTRACTION = 25

#: How far a loitering raider will look for a convoy.
INTERCEPT_RANGE = 5


def _byte(value: int) -> int:
    """Wrap to an unsigned byte.

    ``HuntingGroundArray`` is ``ARRAY [...] OF Byte`` (NPETYPES.PAS:125) and
    the two updates to it -- ``Dec(...,5)`` on a dry block and ``Inc(...,15)``
    on a productive one -- have no floor and no ceiling. See issue #37: both
    ends wrap, and the wrap inverts the grid's meaning, so it is modelled
    rather than clamped.
    """
    return value & 0xFF


def _find_target(game: GameEnvironment, emp: Empire, flt_id: IDNumber) -> IDNumber:
    """The first enemy convoy in range this raider can take.

    Three conditions, all of which must hold: the target is actually carrying
    transports, its escort of jumpships and hunter-killers is no larger than
    this fleet's, and its heavy escort (penetrators and starships) is no more
    than *half* this fleet's hunter-killer count. A pirate will not pick a
    fair fight.

    First match wins -- the original ``Exit``s out of the loop -- so this is
    the lowest-numbered qualifying fleet, not the richest or the nearest.
    """
    set_of_target_fleets = (
        game.GlobalSets.SetOfActiveFleets - game.GlobalSets.SetOfFleetsOf[emp]
    )
    flt_xy = get_coord(game, flt_id)
    flt_sh = get_ships(game, flt_id)

    for i in range(1, MAX_NO_OF_FLEETS + 1):
        if i not in set_of_target_fleets:
            continue
        target_id = IDNumber(ObjectTypes.Flt, i)
        if distance(get_coord(game, target_id), flt_xy) > INTERCEPT_RANGE:
            continue

        sh = get_ships(game, target_id)
        if (
            sh[T.jtn] + sh[T.trn] > 0
            and (sh[T.jmp] + sh[T.hkr]) <= (flt_sh[T.jmp] + flt_sh[T.hkr])
            and (sh[T.pen] + sh[T.ssp]) <= (flt_sh[T.hkr] // 2)
        ):
            return target_id

    return empty_quadrant()


def _find_nearest_base(game: GameEnvironment, emp: Empire, xy: XYCoord) -> XYCoord:
    """Where the nearest pirate world is, for a raider heading home.

    ORIGINAL BUG, preserved -- see issue #38. `GetNearestWorlds` returns a nil
    list when the empire holds no worlds, and the original dereferences it
    without checking. A pirate that has lost its last world crashes here rather
    than losing gracefully. The port raises `IndexError` at the same point;
    there is no defined behaviour to fall back to.
    """
    near = get_nearest_worlds(game, xy, 1, game.GlobalSets.SetOfPlanetsOf[emp])
    return get_coord(game, near[0])


def _get_patrol_destination(
    game: GameEnvironment, hunting_ground: list[list[int]]
) -> tuple[int, int, XYCoord]:
    """Roll a patrol block weighted by how well it has paid, and a point in it.

    A roulette wheel over the whole grid: each block's attraction is its slice.
    Returns ``(block_x, block_y, xy)``.

    The grid is ``SizeOfGalaxy DIV 5`` blocks square, so a galaxy whose size is
    not a multiple of 5 leaves an unpatrolled margin at the far edge -- blocks
    are laid from (1,1) and the remainder is never covered.
    """
    max_bx = game.Galaxy.size // BLOCK_SIZE
    max_by = game.Galaxy.size // BLOCK_SIZE

    total = 0
    for x in range(1, max_bx + 1):
        for y in range(1, max_by + 1):
            total += hunting_ground[x][y]

    rn = rnd(1, total)
    for x in range(1, max_bx + 1):
        for y in range(1, max_by + 1):
            if rn <= hunting_ground[x][y]:
                return (
                    x,
                    y,
                    XYCoord(
                        rnd(1 + (x - 1) * BLOCK_SIZE, x * BLOCK_SIZE),
                        rnd(1 + (y - 1) * BLOCK_SIZE, y * BLOCK_SIZE),
                    ),
                )
            rn -= hunting_ground[x][y]

    # Falls off the end only when every block has decayed to zero, which the
    # original leaves with BX, BY and XY undefined. Limbo and block (0,0) are
    # the port's defined stand-in; see issue #37, which is what gets the grid
    # to all-zero in the first place.
    return 0, 0, XYCoord(0, 0)


def _update_fleets(
    game: GameEnvironment, emp: Empire, data: PirateDataRecord
) -> None:
    """Run the arrival handler for every raider that has reached its waypoint."""
    for i in range(1, NO_OF_FLEETS_PER_EMPIRE + 1):
        entry = data.FleetData[i]
        if entry.Index not in game.GlobalSets.SetOfActiveFleets:
            continue

        flt_id = IDNumber(ObjectTypes.Flt, entry.Index)
        if get_fleet_status(game, flt_id) != FleetStatus.FReady:
            continue

        flt_xy = get_coord(game, flt_id)

        if entry.Mission == MissionTypes.ReturnMSN:
            # Home is whatever is in this sector, not the recorded target.
            ground_id = get_object(game, flt_xy)
            from .core import implement_return_msn

            implement_return_msn(game, flt_id, ground_id)

        elif entry.Mission == MissionTypes.WaitForTrnMSN:
            target_id = _find_target(game, emp, flt_id)
            if target_id.ObjTyp == ObjectTypes.Void:
                if entry.Waiting == 0:
                    # Nothing here -- go home and mark the block down.
                    set_fleet_destination(
                        game, flt_id, _find_nearest_base(game, emp, flt_xy)
                    )
                    entry.Mission = MissionTypes.ReturnMSN
                    data.HuntingGround[entry.BlockX][entry.BlockY] = _byte(
                        data.HuntingGround[entry.BlockX][entry.BlockY] - 5
                    )
                else:
                    entry.Waiting -= 1
            else:
                # Intercept where the convoy is going, not where it is: one
                # step is taken along its course before the raider is aimed.
                target_xy = get_coord(game, target_id)
                target_dest_xy = get_fleet_destination(game, target_id)
                target_xy = get_new_pos(game, target_xy, target_dest_xy)
                set_fleet_destination(game, flt_id, target_xy)
                entry.TargetID = target_id
                entry.Waiting = rnd(1, 2)
                entry.Mission = MissionTypes.AttackTrnMSN
                data.HuntingGround[entry.BlockX][entry.BlockY] = _byte(
                    data.HuntingGround[entry.BlockX][entry.BlockY] + 15
                )

        elif entry.Mission == MissionTypes.AttackTrnMSN:
            target_xy = get_coord(game, entry.TargetID)
            if (
                same_xy(target_xy, flt_xy)
                and entry.TargetID.Index in game.GlobalSets.SetOfActiveFleets
            ):
                # Turn for home *before* fighting, so the survivors leave with
                # the prize whatever the battle costs.
                entry.Mission = MissionTypes.ReturnMSN
                entry.Waiting = 0
                set_fleet_destination(
                    game, flt_id, _find_nearest_base(game, emp, flt_xy)
                )
                npe_attack(
                    game, flt_id, entry.TargetID, AttackIntentionTypes.CaptTrnAIT
                )

                # Captured hulls a pirate has no use for are dumped: fighters
                # are too slow to run with and ordinary transports too fragile,
                # so only the jump-capable prizes are kept.
                #
                # ORIGINAL BUG, deviated from -- see issue #39. A raider that
                # picked a fight it lost is destroyed by NPEAttack, and the
                # original strips the wreck's hulls regardless. Skipped here
                # rather than writing through a freed pointer.
                if flt_id.Index not in game.GlobalSets.SetOfActiveFleets:
                    continue

                sh = get_ships(game, flt_id)
                cr = get_cargo(game, flt_id)
                sh[T.fgt] = 0
                sh[T.trn] = 0
                balance_fleet(sh, cr)
                put_ships(game, flt_id, sh)
                put_cargo(game, flt_id, cr)
            elif entry.Waiting == 0:
                entry.Mission = MissionTypes.ReturnMSN
                set_fleet_destination(
                    game, flt_id, _find_nearest_base(game, emp, flt_xy)
                )
            else:
                entry.Waiting -= 1

        elif entry.Mission == MissionTypes.AttackWrldMSN:
            target_xy = get_coord(game, entry.TargetID)
            fleets_at_target = (
                get_fleets(game, target_xy) - game.GlobalSets.SetOfFleetsOf[emp]
            )

            # Escorts first. The flag reads as "we lost one of these", and any
            # result other than a conquest sets it -- including a draw.
            abort_mission = False
            for j in range(1, MAX_NO_OF_FLEETS + 1):
                if j in fleets_at_target and not abort_mission:
                    sec_targ_id = IDNumber(ObjectTypes.Flt, j)
                    result, _ = npe_attack(
                        game, flt_id, sec_targ_id, AttackIntentionTypes.CaptTrnAIT
                    )
                    if result != AttackResultTypes.DefConqueredART:
                        abort_mission = True

            entry.Mission = MissionTypes.ReturnMSN
            entry.Waiting = 0
            set_fleet_destination(game, flt_id, _find_nearest_base(game, emp, flt_xy))

            if not abort_mission:
                result, _ = npe_attack(
                    game, flt_id, entry.TargetID, AttackIntentionTypes.CaptTrnAIT
                )
                if result == AttackResultTypes.DefConqueredART:
                    plunder_world(game, emp, flt_id, entry.TargetID)


def _get_raid_target(
    game: GameEnvironment, emp: Empire, flt_sh: dict[T, int], gat: int
) -> IDNumber:
    """The richest world this raid can take, weighted by what it is worth.

    Value is cargo -- trillum counts fivefold, supplies at half -- discounted
    by how completely the raid outguns the defense. A world is only considered
    at all if the raid outguns it outright *and* out-troops its garrison, so a
    pirate never commits to a fight it might lose.

    Worlds below `AtomicLvl` are skipped: pre-atomic worlds have nothing worth
    the trip.
    """
    good_targets = set(range(1, game.NoOfPlanets + 1)) - game.GlobalSets.SetOfPlanetsOf[
        emp
    ]
    possible: dict[int, int] = {}
    flt_power = greater_int(1, flt_sh[T.jmp] + 2 * flt_sh[T.hkr])

    for i in range(1, game.NoOfPlanets + 1):
        if i not in good_targets:
            continue
        test_id = IDNumber(ObjectTypes.Pln, i)
        if get_tech(game, test_id) < TechLevel.AtomicLvl:
            continue

        sh = get_ships(game, test_id)
        cr = get_cargo(game, test_id)
        df = get_defns(game, test_id)

        gain = cr[T.che] + cr[T.met] + 5 * cr[T.tri] + (cr[T.sup] // 2)
        protect = (
            10 * df[T.def_]
            + df[T.GDM]
            + 5 * df[T.ion]
            + 2 * sh[T.hkr]
            + sh[T.jmp]
            + 4 * sh[T.pen]
            + 10 * sh[T.ssp]
        )
        if protect < flt_power and gat > (cr[T.men] + 2 * cr[T.nnj]):
            possible[i] = pascal_round((1 - (protect / flt_power)) * (gain // 10))

    # The comparison jitters by 25% but the assignment does not, so the running
    # best is the raw score while the test that admitted it was a jittered one.
    # Reproduced: it makes the pick noisier than a plain argmax, which is
    # presumably the intent, but the two are not the same number.
    best_target = 0
    best_value = 0
    for i in range(1, game.NoOfPlanets + 1):
        if rnd_var(possible.get(i, 0), 25) > best_value:
            best_target = i
            best_value = possible.get(i, 0)

    if best_target != 0:
        return IDNumber(ObjectTypes.Pln, best_target)
    return empty_quadrant()


def _deploy_raiders(game: GameEnvironment, emp: Empire, data: PirateDataRecord) -> None:
    """Assemble a world-raid from any pirate world rich enough in hulls.

    The thresholds are absolute, not relative: 1500 hunter-killers, 2500
    jumpships and 4000 jump transports on one world. A pirate empire that never
    accumulates that much never raids a world at all and lives on convoys alone.
    """
    for i in range(1, game.NoOfPlanets + 1):
        if i not in game.GlobalSets.SetOfPlanetsOf[emp]:
            continue

        base_id = IDNumber(ObjectTypes.Pln, i)
        ships = get_ships(game, base_id)
        cargo = get_cargo(game, base_id)

        if not (
            ships[T.hkr] > 1500 and ships[T.jmp] > 2500 and ships[T.jtn] > 4000
        ):
            continue

        flt_sh = ship_array()
        flt_cr = cargo_array()
        flt_sh[T.hkr] = lesser_int(rnd(1500, 5000), ships[T.hkr])
        flt_sh[T.jmp] = lesser_int(rnd(2500, 9500), ships[T.jmp])
        flt_sh[T.jtn] = lesser_int(rnd(4000, 9500), ships[T.jtn])
        # Troops are capped by the world's *whole* jump-transport stock rather
        # than by what this fleet is actually taking.
        flt_cr[T.men] = lesser_int(ships[T.jtn] // 2, cargo[T.men])

        targ_id = _get_raid_target(game, emp, flt_sh, flt_cr[T.men])
        if targ_id.ObjTyp == ObjectTypes.Void:
            continue

        dest_xy = get_coord(game, targ_id)
        slot = next_fleet_data_slot(game, data.FleetData)
        if slot == 0:
            continue

        flt_id = deploy_fleet(game, emp, base_id, flt_sh, flt_cr, dest_xy)
        set_npe_data_index(game, flt_id, slot)
        entry = data.FleetData[slot]
        entry.Mission = MissionTypes.AttackWrldMSN
        entry.Waiting = 1
        entry.TargetID = targ_id
        entry.Index = flt_id.Index


def _deploy_new_fleets(
    game: GameEnvironment, emp: Empire, data: PirateDataRecord
) -> None:
    """Send a patrol out from every world that can crew one.

    Three tiers, tried in order: a full raiding pack, a light jump pack (only
    three times in four), or a bare hunter-killer squadron. A world with fewer
    than 250 hunter-killers and no jump capability fields nothing.
    """
    for i in range(1, game.NoOfPlanets + 1):
        if i not in game.GlobalSets.SetOfPlanetsOf[emp]:
            continue

        pirate_base_id = IDNumber(ObjectTypes.Pln, i)
        ships = get_ships(game, pirate_base_id)
        flt_sh = ship_array()
        flt_cr = cargo_array()

        if ships[T.jtn] > 4000 and ships[T.jmp] > 2000:
            flt_sh[T.hkr] = lesser_int(rnd(1000, 5000), ships[T.hkr])
            flt_sh[T.jmp] = lesser_int(rnd(1900, 9200), ships[T.jmp])
            flt_sh[T.jtn] = lesser_int(rnd(3900, 9200), ships[T.jtn])
        elif ships[T.jtn] > 1000 and ships[T.jmp] > 1000 and rnd(1, 100) <= 75:
            flt_sh[T.jmp] = lesser_int(rnd(900, 3100), ships[T.jmp])
            flt_sh[T.jtn] = lesser_int(rnd(1900, 2100), ships[T.jtn])
        elif ships[T.hkr] > 250:
            flt_sh[T.hkr] = lesser_int(rnd(400, 2500), ships[T.hkr])

        if no_ships(flt_sh):
            continue

        bx, by, dest_xy = _get_patrol_destination(game, data.HuntingGround)
        slot = next_fleet_data_slot(game, data.FleetData)
        if slot == 0:
            continue

        flt_id = deploy_fleet(game, emp, pirate_base_id, flt_sh, flt_cr, dest_xy)
        set_npe_data_index(game, flt_id, slot)
        entry = data.FleetData[slot]
        entry.Mission = MissionTypes.WaitForTrnMSN
        entry.Waiting = rnd(2, 5)
        entry.BlockX = bx
        entry.BlockY = by
        entry.Index = flt_id.Index


def _review_news(game: GameEnvironment, emp: Empire, data: PirateDataRecord) -> None:
    """React to the year's headlines. A pirate cares about exactly two.

    A blocked fleet is redirected to a fresh patrol block. A fleet out of fuel
    is destroyed where it sits -- no pirate rescue mission exists, unlike the
    kingdoms' `RefuelMSN`.
    """
    news_list = get_news_list(game, emp)

    i = 0
    while i < len(news_list):
        item = news_list[i]
        if item.Headline == NewsTypes.FltBlocked:
            flt_id = item.Loc1.ID
            # ORIGINAL BUG, deviated from -- see issue #39. A headline names
            # the object it was filed about, and news is read at the end of
            # the year, so that object may have died in between. Only fleets
            # matter here: they are the one entity the port frees outright,
            # and this handler writes through the pointer twice.
            if flt_id.Index not in game.GlobalSets.SetOfActiveFleets:
                i += 1
                continue
            bx, by, new_xy = _get_patrol_destination(game, data.HuntingGround)
            set_fleet_destination(game, flt_id, new_xy)
            entry = data.FleetData[npe_data_index(game, flt_id)]
            entry.BlockX = bx
            entry.BlockY = by
        elif item.Headline == NewsTypes.NoFuel:
            destroy_fleet(game, item.Loc1.ID)
        i += 1


def initialize_pirate_npe(
    game: GameEnvironment, emp: Empire, data: PirateDataRecord
) -> None:
    """Start every hunting block equally attractive, and roll defenses."""
    for x in range(len(data.HuntingGround)):
        for y in range(len(data.HuntingGround[x])):
            data.HuntingGround[x][y] = INITIAL_ATTRACTION

    set_empire_defenses(game, emp)


def implement_pirate_npe(
    game: GameEnvironment, emp: Empire, data: PirateDataRecord
) -> None:
    """One pirate turn.

    News, then both deployment passes, then arrivals. Note deployment runs
    *before* `_update_fleets`, so a fleet launched this year is not given its
    arrival handler until next year even if it had no distance to travel.
    """
    from .core import enforce_npe_data_links

    enforce_npe_data_links(game, emp, data.FleetData)
    _review_news(game, emp, data)
    _deploy_raiders(game, emp, data)
    _deploy_new_fleets(game, emp, data)
    _update_fleets(game, emp, data)


def clean_up_pirate_npe(game: GameEnvironment, data: PirateDataRecord) -> None:
    """Release the persona's data. Nothing to unwind."""
