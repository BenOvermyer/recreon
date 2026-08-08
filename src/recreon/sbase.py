"""Starbases that move, and objects that scuttle themselves.

Port of SBASE.PAS.

Two unrelated jobs share this unit in the original. ``SelfDestructObject``
scuttles a starbase or stargate, taking every fleet in the sector with it --
including the owner's own. ``MovePlayerStarbases`` is the starbase half of the
turn rotation: command bases and fortresses carry a destination like a fleet
does, burn a flat 100 tons of trillum a year to crawl one sector toward it,
and stop where they stand when the trillum runs out.

Base movement is *not* fleet movement. A base cannot pass through another
object at all, so ``GetNewBasePos`` adds a sidestep the fleet code has no
equivalent of: when the direct step is blocked it tries the two neighbouring
compass points, and each of those has to be clear *and* leave a clear step
beyond it before the base will take it. That two-deep lookahead is what keeps
a towed base out of pockets it could not crawl back out of.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .datacnst import DirX, DirY
from .fleet import (
    destroy_fleet,
    fleet_name_destruction,
    get_fleet_destination,
    get_new_pos,
)
from .galaxy import Location, XYCoord, limbo
from .misc import same_xy
from .news import NewsTypes, add_news
from .primintr import (
    empire_active,
    get_base_type,
    get_coord,
    get_fleets,
    get_nebula,
    get_object,
    get_ships,
    get_status,
    get_trillum,
    put_trillum,
    scouted,
    set_fleet_status,
)
from .types import (
    MAX_NO_OF_FLEETS,
    MAX_NO_OF_STARBASES,
    PLAYER_EMPIRES,
    SHIP_TYPES,
    Directions,
    Empire,
    FleetStatus,
    IDNumber,
    NebulaTypes,
    ObjectTypes,
    TechnologyTypes,
    empty_quadrant,
)
from .utils.int_utils import sgn

if TYPE_CHECKING:
    from .environ import GameEnvironment

#: Trillum a command base or fortress burns per year under way, blocked or not.
BASE_FUEL_CONSUMPTION = 100


# --- Self-destruct -----------------------------------------------------------


def self_destruct_object(game: GameEnvironment, obj_id: IDNumber) -> None:
    """Scuttle a starbase or stargate, destroying every fleet in its sector.

    Fleets are destroyed outright -- the owner's included, and without the
    cargo recovery ``abort_fleet`` would do. Only *other* empires get news:
    the empire that pushed the button is told nothing, on the reasoning that
    it already knows.
    """
    xy = get_coord(game, obj_id)
    set_of_fleets = get_fleets(game, xy)
    emp = get_status(game, obj_id)

    for other_emp in PLAYER_EMPIRES:
        if (
            empire_active(game, other_emp)
            and other_emp != emp
            and scouted(game, other_emp, obj_id)
        ):
            add_news(
                game,
                other_emp,
                NewsTypes.BseSD,
                Location(limbo(), obj_id),
                int(emp),
            )

    for i in range(1, MAX_NO_OF_FLEETS + 1):
        if i not in set_of_fleets:
            continue

        flt_id = IDNumber(ObjectTypes.Flt, i)
        other_emp = get_status(game, flt_id)
        ships = get_ships(game, flt_id)

        if other_emp != emp:
            loc = fleet_name_destruction(game, other_emp, flt_id)
            add_news(game, other_emp, NewsTypes.FltSD, loc)
            for shp in SHIP_TYPES:
                if ships[shp] > 0:
                    add_news(
                        game, other_emp, NewsTypes.DestDetail, loc, ships[shp], int(shp)
                    )

        destroy_fleet(game, flt_id)

    if obj_id.ObjTyp == ObjectTypes.Base:
        game.GlobalSets.SetOfStarbasesOf[emp].discard(obj_id.Index)
        game.GlobalSets.SetOfActiveStarbases.discard(obj_id.Index)
    else:
        game.GlobalSets.SetOfActiveGates.discard(obj_id.Index)

    game.Galaxy.sector(xy).Obj = empty_quadrant()


# --- Movement ----------------------------------------------------------------


def xy2dir(pos: XYCoord, dest: XYCoord) -> Directions:
    """The compass point pointing from ``pos`` at ``dest``.

    Searches DirX/DirY downward from Nw, so it lands on NoDir when the two
    coordinates are the same -- NoDir's entries are (0, 0), which is exactly
    the pair a zero delta produces.
    """
    dx = sgn(dest.x - pos.x)
    dy = sgn(dest.y - pos.y)

    direction = Directions.Nw
    while direction != Directions.NoDir and (
        dx != DirX[direction] or dy != DirY[direction]
    ):
        direction = Directions(direction - 1)

    return direction


def _tentative_move(game: GameEnvironment, pos: XYCoord, dest: XYCoord) -> XYCoord:
    """One step from ``pos`` toward ``dest``, or Limbo if anything is in the way.

    Unlike the fleet version this refuses *any* occupied sector, not just a
    dense nebula: bases cannot share a sector with another object.
    """
    new_pos = get_new_pos(game, pos, dest)
    if same_xy(new_pos, limbo()):
        return new_pos
    if get_object(game, new_pos).ObjTyp != ObjectTypes.Void:
        return limbo()
    return new_pos


def _sidestep_clear(game: GameEnvironment, pos: XYCoord) -> bool:
    """Whether a base may sit on the sideways candidate ``pos``.

    The original tests the dense nebula and then the sector's object, with no
    bounds check of any kind. A sideways step can leave the playable galaxy in
    a way a direct step never does -- the direct step always moves toward an
    in-galaxy destination, the sidestep moves across it -- so a base hugging
    an edge can be pushed into row or column 0, or one sector past the far
    edge. Row/column 0 exists in the grid and is preserved here as the
    original has it: the base really does slip out of the playable area.

    One sector *past* the far edge does not exist in the grid at all. The DOS
    build read it through an unallocated row pointer and would have seen
    garbage, which for a one-byte object type almost certainly failed the
    ``<> Void`` test and read as blocked. Blocked is what this returns, which
    matches the practical outcome without the wild read. See issue #20.
    """
    size = game.Galaxy.size
    if not (0 <= pos.x <= size and 0 <= pos.y <= size):
        return False
    if get_nebula(game, pos) == NebulaTypes.DenseNebula:
        return False
    return get_object(game, pos).ObjTyp == ObjectTypes.Void


def _sidestep_directions(direction: Directions) -> tuple[Directions, Directions]:
    """The two compass points flanking ``direction``, right one first.

    No..Nw is a ring of eight with NoDir sitting below it, so both steps wrap
    around that gap rather than through it.
    """
    right = Directions.No if direction == Directions.Nw else Directions(direction + 1)
    left = Directions.Nw if direction == Directions.No else Directions(direction - 1)
    return right, left


def get_new_base_pos(game: GameEnvironment, pos: XYCoord, dest: XYCoord) -> XYCoord:
    """Where a base under tow ends up this year, or Limbo if it is boxed in.

    Tries the direct step first. If that is blocked it tries the compass point
    one to the right of the bearing, then the one to the left, and takes
    either only when the sidestep square *and* the square one step onward from
    it toward ``dest`` are both clear. Only the sidestep square is actually
    moved to -- the lookahead is a test, not part of the move.

    ``pos`` must differ from ``dest``. A base already at its destination gives
    a NoDir bearing, and the original's ``Pred(Dir)`` on the second sidestep
    would then run off the bottom of the enum; the only caller,
    :func:`move_player_starbases`, guards against it.
    """
    direction = xy2dir(pos, dest)
    pos_test = _tentative_move(game, pos, dest)

    if not same_xy(pos_test, limbo()):
        return pos_test

    for dir_test in _sidestep_directions(direction):
        pos_test = XYCoord(pos.x + DirX[dir_test], pos.y + DirY[dir_test])
        beyond = _tentative_move(game, pos_test, dest)
        if _sidestep_clear(game, pos_test) and not same_xy(beyond, limbo()):
            return pos_test

    return limbo()


def move_base(game: GameEnvironment, base_id: IDNumber, new_pos: XYCoord) -> None:
    """Put a base in a new sector, clearing the one it left."""
    base = game.Universe.Starbase[base_id.Index]
    game.Galaxy.sector(base.XY).Obj = empty_quadrant()
    game.Galaxy.sector(new_pos).Obj = base_id
    base.XY = new_pos


def move_player_starbases(game: GameEnvironment, emp: Empire) -> None:
    """Advance every command base and fortress of ``emp`` one sector.

    Only ``cmm`` and ``frt`` bases move; the rest are fixed installations.
    Movement costs a flat 100 tons of trillum a year regardless of distance,
    and a base too poor to pay simply stays put and files a fuel warning.

    A base that pays but finds itself boxed in files ``BseBlocked``, is
    "moved" to the sector it already occupies, and is charged anyway. That is
    the original's behaviour, not a transcription slip -- see issue #21.
    """
    for i in range(1, MAX_NO_OF_STARBASES + 1):
        if i not in game.GlobalSets.SetOfStarbasesOf[emp]:
            continue

        base_id = IDNumber(ObjectTypes.Base, i)
        loc = Location(limbo(), base_id)
        styp = get_base_type(game, base_id)

        if styp not in (TechnologyTypes.cmm, TechnologyTypes.frt):
            continue

        old_pos = get_coord(game, base_id)
        dest = get_fleet_destination(game, base_id)
        if same_xy(dest, old_pos):
            continue

        tri_left = get_trillum(game, base_id)
        if tri_left < BASE_FUEL_CONSUMPTION:
            add_news(game, emp, NewsTypes.BseFuel, loc)
            continue

        new_pos = get_new_base_pos(game, old_pos, dest)
        if same_xy(new_pos, limbo()):
            new_pos = old_pos
            add_news(game, emp, NewsTypes.BseBlocked, loc)

        # The original leaves a "check for black holes, gates, etc." comment
        # here. Nothing was ever written: get_new_base_pos rejects every
        # occupied sector, so a base cannot reach one to begin with.
        move_base(game, base_id, new_pos)

        put_trillum(game, base_id, tri_left - BASE_FUEL_CONSUMPTION)

        if same_xy(dest, new_pos):
            set_fleet_status(game, base_id, FleetStatus.FReady)
