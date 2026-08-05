"""Starbase movement and self-destruct, ported from SBASE.PAS."""

import pytest
from conftest import blank_game, place_world

from recreon.fleet import deploy_fleet, set_fleet_destination
from recreon.galaxy import XYCoord, limbo
from recreon.intrface import create_starbase, create_stargate
from recreon.misc import same_xy
from recreon.news import NewsTypes, get_news_list
from recreon.primintr import (
    get_coord,
    get_fleet_status,
    get_object,
    get_trillum,
    put_cargo,
    put_nebula,
    put_ships,
    scout_object,
)
from recreon.sbase import (
    BASE_FUEL_CONSUMPTION,
    get_new_base_pos,
    move_base,
    move_player_starbases,
    self_destruct_object,
    xy2dir,
)
from recreon.types import (
    Directions,
    Empire,
    FleetStatus,
    IDNumber,
    NebulaTypes,
    ObjectTypes,
    TechnologyTypes,
    cargo_array,
    ship_array,
)

T = TechnologyTypes

BASE_XY = XYCoord(10, 10)


# --- Fixtures ----------------------------------------------------------------


@pytest.fixture
def game():
    """Two empires, Empire1's capital at (5, 5) in a 20x20 galaxy."""
    g = blank_game(size=20, empires=2)
    world = place_world(g, 1, XYCoord(5, 5), emp=Empire.Empire1)
    g.Universe.EmpireData[Empire.Empire1].Capital = world
    other = place_world(g, 2, XYCoord(18, 18), emp=Empire.Empire2)
    g.Universe.EmpireData[Empire.Empire2].Capital = other
    return g


def make_base(
    game,
    index=1,
    xy=BASE_XY,
    emp=Empire.Empire1,
    styp=T.cmm,
    trillum=500,
    dest=None,
):
    """A starbase of a given type, fuelled and optionally under way."""
    base = IDNumber(ObjectTypes.Base, index)
    create_starbase(game, base, emp, xy, styp)

    cargo = cargo_array()
    cargo[T.tri] = trillum
    put_cargo(game, base, cargo)

    if dest is not None:
        set_fleet_destination(game, base, dest)
    return base


def block(game, xy, index=9):
    """Put an unrelated starbase at ``xy`` so nothing else may enter it."""
    return make_base(game, index=index, xy=xy, styp=T.cmp, trillum=0)


def launch(game, world, ships, emp=Empire.Empire1):
    sh = ship_array()
    sh.update(ships)
    cr = cargo_array()
    return deploy_fleet(game, emp, world, sh, cr, get_coord(game, world))


# --- xy2dir ------------------------------------------------------------------


@pytest.mark.parametrize(
    "dest,expected",
    [
        (XYCoord(10, 9), Directions.No),
        (XYCoord(11, 9), Directions.Ne),
        (XYCoord(11, 10), Directions.Ea),
        (XYCoord(11, 11), Directions.Se),
        (XYCoord(10, 11), Directions.So),
        (XYCoord(9, 11), Directions.Sw),
        (XYCoord(9, 10), Directions.We),
        (XYCoord(9, 9), Directions.Nw),
    ],
)
def test_xy2dir_names_every_compass_point(dest, expected):
    assert xy2dir(BASE_XY, dest) == expected


def test_xy2dir_is_a_bearing_not_a_distance():
    """Only the sign of each delta matters, so a far destination reads the
    same as an adjacent one."""
    assert xy2dir(BASE_XY, XYCoord(20, 1)) == Directions.Ne


def test_xy2dir_gives_nodir_for_no_movement():
    assert xy2dir(BASE_XY, BASE_XY) == Directions.NoDir


# --- get_new_base_pos --------------------------------------------------------


def test_a_clear_path_takes_the_direct_step(game):
    assert get_new_base_pos(game, BASE_XY, XYCoord(15, 10)) == XYCoord(11, 10)


def test_the_step_is_diagonal_when_both_axes_differ(game):
    """Movement is Chebyshev, so a diagonal costs no more than an orthogonal
    step and both axes advance at once."""
    assert get_new_base_pos(game, BASE_XY, XYCoord(15, 15)) == XYCoord(11, 11)


def test_a_blocked_step_sidesteps_to_the_right_first(game):
    """Heading east into an occupied sector, the base tries Se before Ne --
    the original takes Succ(Dir) first."""
    block(game, XYCoord(11, 10))

    assert get_new_base_pos(game, BASE_XY, XYCoord(15, 10)) == XYCoord(11, 11)


def test_the_left_sidestep_is_the_fallback(game):
    block(game, XYCoord(11, 10))
    block(game, XYCoord(11, 11), index=8)

    assert get_new_base_pos(game, BASE_XY, XYCoord(15, 10)) == XYCoord(11, 9)


def test_a_base_boxed_in_on_all_three_sides_goes_nowhere(game):
    block(game, XYCoord(11, 10))
    block(game, XYCoord(11, 11), index=8)
    block(game, XYCoord(11, 9), index=7)

    assert same_xy(get_new_base_pos(game, BASE_XY, XYCoord(15, 10)), limbo())


def test_a_dense_nebula_blocks_the_direct_step(game):
    put_nebula(game, XYCoord(11, 10), NebulaTypes.DenseNebula)

    assert get_new_base_pos(game, BASE_XY, XYCoord(15, 10)) == XYCoord(11, 11)


def test_a_dense_nebula_blocks_a_sidestep_too(game):
    block(game, XYCoord(11, 10))
    put_nebula(game, XYCoord(11, 11), NebulaTypes.DenseNebula)

    assert get_new_base_pos(game, BASE_XY, XYCoord(15, 10)) == XYCoord(11, 9)


def test_a_sidestep_needs_a_clear_square_beyond_it(game):
    """The lookahead is what stops a base crawling into a pocket. Heading Se,
    the right sidestep (10, 11) is itself clear, but the step onward from it
    toward the destination is not -- so the base takes the left one instead.
    Note it moves to the sidestep square, never to the square looked ahead at."""
    dest = XYCoord(15, 12)
    block(game, XYCoord(11, 11))
    block(game, XYCoord(11, 12), index=8)

    assert get_new_base_pos(game, BASE_XY, dest) == XYCoord(11, 10)


# --- Sidesteps at the galaxy edge (original bug) -----------------------------


def test_a_sidestep_can_push_a_base_out_of_the_playable_galaxy(game):
    """ORIGINAL BUG, preserved. A direct step always moves toward an in-galaxy
    destination and so stays inside it. A sidestep moves *across* the bearing
    and is bounds-checked nowhere, so a base hugging column 1 heading north
    with the direct step blocked lands in column 0 -- a sector that exists in
    the grid but fails InGalaxy."""
    pos = XYCoord(1, 10)
    block(game, XYCoord(1, 9))
    block(game, XYCoord(2, 9), index=8)

    new_pos = get_new_base_pos(game, pos, XYCoord(1, 1))

    assert new_pos == XYCoord(0, 9)
    assert not game.Galaxy.in_galaxy(new_pos.x, new_pos.y)


def test_a_sidestep_past_the_far_edge_reads_as_blocked(game):
    """The one deviation. A base in the last column heading north with the
    direct step blocked sidesteps to column size+1, which the DOS build read
    through an unallocated row pointer. Treated as blocked here, which is what
    the garbage it read would almost certainly have produced anyway."""
    size = game.Galaxy.size
    pos = XYCoord(size, 10)
    block(game, XYCoord(size, 9))

    # Ne is off the grid entirely, so the base falls through to the Nw step.
    assert get_new_base_pos(game, pos, XYCoord(size, 1)) == XYCoord(size - 1, 9)


# --- move_base ---------------------------------------------------------------


def test_move_base_clears_the_sector_it_left(game):
    base = make_base(game)

    move_base(game, base, XYCoord(11, 10))

    assert get_coord(game, base) == XYCoord(11, 10)
    assert get_object(game, XYCoord(11, 10)) == base
    assert get_object(game, BASE_XY).ObjTyp == ObjectTypes.Void


# --- move_player_starbases ---------------------------------------------------


def test_a_command_base_crawls_one_sector_a_year(game):
    base = make_base(game, dest=XYCoord(15, 10))

    move_player_starbases(game, Empire.Empire1)

    assert get_coord(game, base) == XYCoord(11, 10)


def test_a_fortress_moves_too(game):
    base = make_base(game, styp=T.frt, dest=XYCoord(15, 10))

    move_player_starbases(game, Empire.Empire1)

    assert get_coord(game, base) == XYCoord(11, 10)


@pytest.mark.parametrize("styp", [T.cmp, T.out, T.gte])
def test_other_installations_are_fixed(game, styp):
    """Only cmm and frt are towable; the rest stay where they were built even
    with a destination set and fuel in the hold."""
    base = make_base(game, styp=styp, dest=XYCoord(15, 10))

    move_player_starbases(game, Empire.Empire1)

    assert get_coord(game, base) == BASE_XY


def test_movement_burns_a_flat_hundred_tons(game):
    base = make_base(game, trillum=500, dest=XYCoord(15, 10))

    move_player_starbases(game, Empire.Empire1)

    assert get_trillum(game, base) == 500 - BASE_FUEL_CONSUMPTION


def test_the_cost_does_not_scale_with_distance(game):
    """One year, one sector, one hundred tons -- however far off the
    destination is."""
    near = make_base(game, index=1, xy=XYCoord(10, 10), dest=XYCoord(11, 10))
    far = make_base(game, index=2, xy=XYCoord(3, 3), dest=XYCoord(20, 20))

    move_player_starbases(game, Empire.Empire1)

    assert get_trillum(game, near) == get_trillum(game, far)


def test_a_base_already_at_its_destination_stays_put_and_pays_nothing(game):
    base = make_base(game, dest=BASE_XY)

    move_player_starbases(game, Empire.Empire1)

    assert get_coord(game, base) == BASE_XY
    assert get_trillum(game, base) == 500


def test_arriving_sets_the_base_ready(game):
    base = make_base(game, dest=XYCoord(11, 10))

    move_player_starbases(game, Empire.Empire1)

    assert get_coord(game, base) == XYCoord(11, 10)
    assert get_fleet_status(game, base) == FleetStatus.FReady


def test_a_base_still_under_way_stays_in_transit(game):
    base = make_base(game, dest=XYCoord(15, 10))

    move_player_starbases(game, Empire.Empire1)

    assert get_fleet_status(game, base) == FleetStatus.FInTrans


def test_a_base_out_of_fuel_stops_and_reports(game):
    base = make_base(game, trillum=BASE_FUEL_CONSUMPTION - 1, dest=XYCoord(15, 10))

    move_player_starbases(game, Empire.Empire1)

    assert get_coord(game, base) == BASE_XY
    assert get_trillum(game, base) == BASE_FUEL_CONSUMPTION - 1
    heads = [item.Headline for item in get_news_list(game, Empire.Empire1)]
    assert NewsTypes.BseFuel in heads


def test_exactly_enough_fuel_is_enough(game):
    base = make_base(game, trillum=BASE_FUEL_CONSUMPTION, dest=XYCoord(15, 10))

    move_player_starbases(game, Empire.Empire1)

    assert get_coord(game, base) == XYCoord(11, 10)
    assert get_trillum(game, base) == 0


def test_a_blocked_base_reports_and_is_charged_anyway(game):
    """ORIGINAL BUG, preserved. The fuel is deducted after the move attempt,
    not as part of it, so a base that could not move anywhere still pays its
    hundred tons -- and does so every year it stays boxed in."""
    base = make_base(game, trillum=500, dest=XYCoord(15, 10))
    block(game, XYCoord(11, 10))
    block(game, XYCoord(11, 11), index=8)
    block(game, XYCoord(11, 9), index=7)

    move_player_starbases(game, Empire.Empire1)

    assert get_coord(game, base) == BASE_XY
    assert get_trillum(game, base) == 400
    heads = [item.Headline for item in get_news_list(game, Empire.Empire1)]
    assert NewsTypes.BseBlocked in heads


def test_a_blocked_base_still_occupies_its_own_sector(game):
    """The blocked path runs move_base with the base's current position, which
    clears the sector and then re-fills it. It has to end up still there."""
    base = make_base(game, dest=XYCoord(15, 10))
    block(game, XYCoord(11, 10))
    block(game, XYCoord(11, 11), index=8)
    block(game, XYCoord(11, 9), index=7)

    move_player_starbases(game, Empire.Empire1)

    assert get_object(game, BASE_XY) == base


def test_only_the_named_empires_bases_move(game):
    mine = make_base(game, index=1, emp=Empire.Empire1, dest=XYCoord(15, 10))
    theirs = make_base(
        game, index=2, xy=XYCoord(15, 15), emp=Empire.Empire2, dest=XYCoord(15, 10)
    )

    move_player_starbases(game, Empire.Empire1)

    assert get_coord(game, mine) == XYCoord(11, 10)
    assert get_coord(game, theirs) == XYCoord(15, 15)


# --- self_destruct_object ----------------------------------------------------


def test_self_destruct_empties_the_sector(game):
    base = make_base(game)

    self_destruct_object(game, base)

    assert get_object(game, BASE_XY).ObjTyp == ObjectTypes.Void


def test_self_destruct_deregisters_a_starbase(game):
    base = make_base(game)

    self_destruct_object(game, base)

    assert base.Index not in game.GlobalSets.SetOfActiveStarbases
    assert base.Index not in game.GlobalSets.SetOfStarbasesOf[Empire.Empire1]


def test_self_destruct_deregisters_a_stargate(game):
    gate = IDNumber(ObjectTypes.Gate, 1)
    create_stargate(game, gate, Empire.Empire1, T.gte, BASE_XY)

    self_destruct_object(game, gate)

    assert gate.Index not in game.GlobalSets.SetOfActiveGates
    assert get_object(game, BASE_XY).ObjTyp == ObjectTypes.Void


def test_self_destruct_takes_the_owners_own_fleets_with_it(game):
    """No exemption for friendlies -- everything in the sector dies."""
    world = IDNumber(ObjectTypes.Pln, 1)
    put_ships(game, world, ship_array() | {T.fgt: 10})
    fleet = launch(game, world, {T.fgt: 10})
    game.Universe.Fleet[fleet.Index].XY = BASE_XY
    base = make_base(game)

    self_destruct_object(game, base)

    assert fleet.Index not in game.GlobalSets.SetOfActiveFleets


def test_an_enemy_fleet_in_the_sector_is_destroyed_and_reported(game):
    other = IDNumber(ObjectTypes.Pln, 2)
    put_ships(game, other, ship_array() | {T.fgt: 10, T.trn: 4})
    fleet = launch(game, other, {T.fgt: 10, T.trn: 4}, emp=Empire.Empire2)
    game.Universe.Fleet[fleet.Index].XY = BASE_XY
    base = make_base(game)

    self_destruct_object(game, base)

    assert fleet.Index not in game.GlobalSets.SetOfActiveFleets
    heads = [item.Headline for item in get_news_list(game, Empire.Empire2)]
    assert NewsTypes.FltSD in heads
    # One DestDetail per ship type that was present, and no more.
    details = [
        item
        for item in get_news_list(game, Empire.Empire2)
        if item.Headline == NewsTypes.DestDetail
    ]
    assert sorted((item.Parm1, item.Parm2) for item in details) == sorted(
        [(10, int(T.fgt)), (4, int(T.trn))]
    )


def test_only_empires_that_had_scouted_the_base_hear_about_it(game):
    base = make_base(game)

    self_destruct_object(game, base)

    heads = [item.Headline for item in get_news_list(game, Empire.Empire2)]
    assert NewsTypes.BseSD not in heads


def test_a_scouting_empire_is_told_who_scuttled_the_base(game):
    base = make_base(game)
    scout_object(game, Empire.Empire2, base)

    self_destruct_object(game, base)

    news = [
        item
        for item in get_news_list(game, Empire.Empire2)
        if item.Headline == NewsTypes.BseSD
    ]
    assert len(news) == 1
    assert news[0].Parm1 == int(Empire.Empire1)


def test_the_owner_is_not_told_about_its_own_self_destruct(game):
    base = make_base(game)
    scout_object(game, Empire.Empire1, base)

    self_destruct_object(game, base)

    heads = [item.Headline for item in get_news_list(game, Empire.Empire1)]
    assert NewsTypes.BseSD not in heads


def test_fleets_elsewhere_survive(game):
    world = IDNumber(ObjectTypes.Pln, 1)
    put_ships(game, world, ship_array() | {T.fgt: 10})
    fleet = launch(game, world, {T.fgt: 10})
    base = make_base(game)

    self_destruct_object(game, base)

    assert fleet.Index in game.GlobalSets.SetOfActiveFleets
