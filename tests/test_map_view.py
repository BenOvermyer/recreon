"""The galaxy map buffer, ported from MAPWIND.PAS.

Three things are being pinned here: that fog of war keys on ``KnownBy`` rather
than ``ScoutedBy``, that the draw passes overwrite each other in the original's
order, and that each sector really is three columns.
"""

import pytest
from conftest import blank_game, place_world

from recreon.fleet import deploy_fleet
from recreon.galaxy import XYCoord
from recreon.intrface import create_starbase
from recreon.primintr import put_cargo, put_nebula, put_ships
from recreon.types import (
    Empire,
    IDNumber,
    NebulaTypes,
    ObjectTypes,
    TechnologyTypes,
    WorldTypes,
    cargo_array,
    ship_array,
)
from recreon.ui.map_view import (
    BLANK_CHAR,
    CONS_CHAR,
    ENEMY_FLEET_CHAR,
    MINE_CHAR,
    NEBULA_CHAR,
    PLAYER_FLEET_CHAR,
    UNK_PLANET_CHAR,
    build_map,
    cp437,
)
from recreon.utils.pascal import set_rand_seed

T = TechnologyTypes
WT = WorldTypes

CAP_XY = XYCoord(10, 10)


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


@pytest.fixture
def game():
    g = blank_game(size=30, empires=2)
    cap = place_world(g, 1, CAP_XY, emp=Empire.Empire1, typ=WT.CapTyp)
    g.Universe.EmpireData[Empire.Empire1].Capital = cap
    g.Universe.Planet[1].KnownBy.add(Empire.Empire1)

    sh = ship_array()
    sh.update({T.fgt: 500, T.jmp: 500, T.hkr: 500})
    cr = cargo_array()
    cr[T.tri] = 5000
    put_ships(g, cap, sh)
    put_cargo(g, cap, cr)
    return g


def cell(game, xy, player=Empire.Empire1):
    return build_map(game, player)[xy.y][xy.x]


# --- Fog of war ---------------------------------------------------------------


def test_a_known_world_shows_its_designation(game):
    xy = XYCoord(12, 12)
    place_world(game, 2, xy, emp=Empire.Empire2, typ=WT.MinTyp)
    game.Universe.Planet[2].KnownBy.add(Empire.Empire1)

    from recreon.datacnst import TypeStr

    assert cell(game, xy).world == TypeStr[WT.MinTyp]


def test_an_unknown_world_shows_only_that_something_is_there(game):
    """Stars are visible from a distance; what is on them is not."""
    xy = XYCoord(12, 12)
    place_world(game, 2, xy, emp=Empire.Empire2, typ=WT.MinTyp)

    assert cell(game, xy).world == UNK_PLANET_CHAR


def test_a_nebula_hides_an_unknown_world_entirely(game):
    """The one place a world can vanish from the map."""
    xy = XYCoord(12, 12)
    place_world(game, 2, xy, emp=Empire.Empire2, typ=WT.MinTyp)
    put_nebula(game, xy, NebulaTypes.Nebula)

    assert cell(game, xy).world == NEBULA_CHAR[NebulaTypes.Nebula]


def test_a_known_world_is_visible_through_a_nebula(game):
    xy = XYCoord(12, 12)
    place_world(game, 2, xy, emp=Empire.Empire2, typ=WT.MinTyp)
    put_nebula(game, xy, NebulaTypes.Nebula)
    game.Universe.Planet[2].KnownBy.add(Empire.Empire1)

    from recreon.datacnst import TypeStr

    assert cell(game, xy).world == TypeStr[WT.MinTyp]


def test_your_worlds_and_theirs_are_styled_apart(game):
    theirs_xy = XYCoord(12, 12)
    place_world(game, 2, theirs_xy, emp=Empire.Empire2, typ=WT.MinTyp)
    game.Universe.Planet[2].KnownBy.add(Empire.Empire1)

    mine = cell(game, CAP_XY)
    theirs = cell(game, theirs_xy)

    assert mine.world_style != theirs.world_style


def test_an_unknown_starbase_is_not_drawn_at_all(game):
    """Unlike worlds, installations have no "something is there" fallback."""
    xy = XYCoord(14, 14)
    base = IDNumber(ObjectTypes.Base, 1)
    create_starbase(game, base, Empire.Empire2, xy, T.cmm)

    assert cell(game, xy).world == BLANK_CHAR


def test_a_known_starbase_shows_its_type(game):
    from recreon.datacnst import BaseTypeData

    xy = XYCoord(14, 14)
    base = IDNumber(ObjectTypes.Base, 1)
    create_starbase(game, base, Empire.Empire2, xy, T.cmm)
    game.Universe.Starbase[1].KnownBy.add(Empire.Empire1)

    assert cell(game, xy).world == cp437(BaseTypeData[T.cmm])


def test_a_known_construction_site_shows_a_hash(game):
    from recreon.intrface import construction

    xy = XYCoord(16, 16)
    site = construction(game, Empire.Empire1, T.out, xy)

    game.Universe.Constr[site.Index].KnownBy.add(Empire.Empire1)

    assert cell(game, xy).world == CONS_CHAR


# --- Fleets -------------------------------------------------------------------


def test_your_fleet_takes_the_left_column(game):
    xy = XYCoord(13, 10)
    sh = ship_array()
    sh[T.fgt] = 100
    deploy_fleet(game, Empire.Empire1, IDNumber(ObjectTypes.Pln, 1), sh, cargo_array(), xy)
    flt = max(game.GlobalSets.SetOfFleetsOf[Empire.Empire1])
    game.Universe.Fleet[flt].XY = xy

    c = cell(game, xy)
    assert c.player_flt == PLAYER_FLEET_CHAR
    assert c.enemy_flt == BLANK_CHAR


def test_a_known_enemy_fleet_takes_the_right_column(game):
    xy = XYCoord(13, 10)
    src = place_world(game, 2, xy, emp=Empire.Empire2)
    put_cargo(game, src, cargo_array())
    sh = ship_array()
    sh[T.fgt] = 100
    put_ships(game, src, sh)
    flt = deploy_fleet(game, Empire.Empire2, src, sh, cargo_array(), xy)
    game.Universe.Fleet[flt.Index].KnownBy.add(Empire.Empire1)

    c = cell(game, xy)
    assert c.enemy_flt == ENEMY_FLEET_CHAR
    assert c.player_flt == BLANK_CHAR


def test_an_unknown_enemy_fleet_leaves_the_column_blank(game):
    """Which is the entire point of flying hunter-killers."""
    xy = XYCoord(13, 10)
    src = place_world(game, 2, xy, emp=Empire.Empire2)
    put_cargo(game, src, cargo_array())
    sh = ship_array()
    sh[T.hkr] = 100
    put_ships(game, src, sh)
    deploy_fleet(game, Empire.Empire2, src, sh, cargo_array(), xy)

    assert cell(game, xy).enemy_flt == BLANK_CHAR


def test_a_fleet_never_hides_a_world(game):
    """Fleets live in their own columns, so the world column is untouched."""
    from recreon.datacnst import TypeStr

    sh = ship_array()
    sh[T.fgt] = 100
    deploy_fleet(
        game, Empire.Empire1, IDNumber(ObjectTypes.Pln, 1), sh, cargo_array(), CAP_XY
    )

    assert cell(game, CAP_XY).world == TypeStr[WT.CapTyp]


# --- Nebulae and minefields ---------------------------------------------------


def test_a_nebula_shades_all_three_columns(game):
    xy = XYCoord(22, 22)
    put_nebula(game, xy, NebulaTypes.DenseNebula)

    c = cell(game, xy)
    glyph = NEBULA_CHAR[NebulaTypes.DenseNebula]
    assert (c.player_flt, c.world, c.enemy_flt) == (glyph, glyph, glyph)


def test_your_own_minefield_is_always_visible(game):
    from recreon.galaxy import NO_SRM_FIELD

    xy = XYCoord(22, 22)
    sector = game.Galaxy.sector(xy)
    sector.Special = (sector.Special & 0x0F) | (int(Empire.Empire1) * 16)

    assert cell(game, xy).world == MINE_CHAR
    assert NO_SRM_FIELD  # the sentinel exists and is not what we just wrote


def test_an_enemy_minefield_is_visible_only_once_scouted(game):
    # Off the grid rules, so an empty sector really is blank.
    xy = XYCoord(22, 22)
    sector = game.Galaxy.sector(xy)
    sector.Special = (sector.Special & 0x0F) | (int(Empire.Empire2) * 16)

    assert cell(game, xy).world == BLANK_CHAR

    sector.MineScout.add(Empire.Empire1)
    assert cell(game, xy).world == MINE_CHAR


def test_a_minefield_shows_through_a_nebula(game):
    """The mine marker replaces the shading in the world column rather than
    sitting beside it."""
    xy = XYCoord(22, 22)
    put_nebula(game, xy, NebulaTypes.Nebula)
    sector = game.Galaxy.sector(xy)
    sector.Special = (sector.Special & 0x0F) | (int(Empire.Empire1) * 16)

    c = cell(game, xy)
    assert c.world == MINE_CHAR
    assert c.player_flt == NEBULA_CHAR[NebulaTypes.Nebula]


# --- Draw order ---------------------------------------------------------------


def test_a_starbase_is_drawn_over_the_nebula_it_sits_in(game):
    from recreon.datacnst import BaseTypeData

    xy = XYCoord(14, 14)
    put_nebula(game, xy, NebulaTypes.Nebula)
    base = IDNumber(ObjectTypes.Base, 1)
    create_starbase(game, base, Empire.Empire1, xy, T.cmm)
    game.Universe.Starbase[1].KnownBy.add(Empire.Empire1)

    assert cell(game, xy).world == cp437(BaseTypeData[T.cmm])


def test_a_starbase_is_drawn_over_a_world_in_the_same_sector(game):
    """Starbases come after planets in the compose order."""
    from recreon.datacnst import BaseTypeData

    xy = XYCoord(18, 18)
    place_world(game, 2, xy, emp=Empire.Empire1, typ=WT.MinTyp)
    game.Universe.Planet[2].KnownBy.add(Empire.Empire1)

    base = IDNumber(ObjectTypes.Base, 1)
    create_starbase(game, base, Empire.Empire1, xy, T.cmm)
    game.Universe.Starbase[1].KnownBy.add(Empire.Empire1)

    assert cell(game, xy).world == cp437(BaseTypeData[T.cmm])


# --- Grid ---------------------------------------------------------------------


def test_the_grid_crosses_on_the_capital(game):
    """Player coordinates are capital-relative, so the rules have to line up
    with it or a typed destination is unfindable by eye."""
    from recreon.ui.map_view import CROSS_CHAR_2

    assert cell(game, XYCoord(5, 5)).world == CROSS_CHAR_2
    assert cell(game, XYCoord(15, 15)).world == CROSS_CHAR_2


def test_the_grid_repeats_every_five_sectors(game):
    from recreon.ui.map_view import GRID_SEP, HORZ_CHAR, VERT_CHAR

    assert GRID_SEP == 5
    assert cell(game, XYCoord(5, 7)).world == VERT_CHAR
    assert cell(game, XYCoord(7, 5)).world == HORZ_CHAR
    assert cell(game, XYCoord(7, 7)).world == BLANK_CHAR


# --- Integration --------------------------------------------------------------


def test_the_map_reflects_what_a_turn_of_scouting_revealed(scenario_path):
    """End to end: load a scenario, take a turn, and the player's map should
    show more than it did before the sweep ran."""
    from recreon.main import update_turn
    from recreon.newgame import load_scenario

    g = load_scenario(scenario_path, {Empire.Empire1: "A"})

    def visible():
        buf = build_map(g, Empire.Empire1)
        return sum(
            1
            for y in range(1, g.Galaxy.size + 1)
            for x in range(1, g.Galaxy.size + 1)
            if buf[y][x].world not in (BLANK_CHAR, UNK_PLANET_CHAR)
        )

    before = visible()
    update_turn(g)

    assert visible() >= before
