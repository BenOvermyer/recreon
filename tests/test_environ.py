"""Milestone 2: a game starts, has a galaxy, and advances turns."""

from recreon.environ import DEFAULT_STARTING_YEAR, GameEnvironment
from recreon.galaxy import MAX_SIZE_OF_GALAXY, NO_SRM_FIELD, Galaxy, XYCoord
from recreon.main import new_game, update_turn
from recreon.primintr import (
    empire_active,
    empire_player,
    enemy_mine,
    get_coord,
    get_fleets,
    get_nebula,
    get_object,
    next_empire,
    no_more_players,
    put_mine,
    put_nebula,
    put_object,
    scout_object,
    scouted,
)
from recreon.types import Empire, IDNumber, NebulaTypes, ObjectTypes


def test_galaxy_is_allocated_inclusive_of_zero():
    galaxy = Galaxy(10)
    assert galaxy.size == 10
    # Row and column 0 exist but are outside the playable area.
    assert galaxy.sector(XYCoord(0, 0)) is not None
    assert not galaxy.in_galaxy(0, 0)
    assert galaxy.in_galaxy(1, 1)
    assert galaxy.in_galaxy(10, 10)
    assert not galaxy.in_galaxy(11, 10)


def test_galaxy_size_is_clamped():
    assert Galaxy(500).size == MAX_SIZE_OF_GALAXY
    assert Galaxy(0).size == 0


def test_new_sectors_carry_the_no_minefield_sentinel():
    galaxy = Galaxy(5)
    sector = galaxy.sector(XYCoord(3, 3))
    assert sector.Special == NO_SRM_FIELD
    assert sector.Obj.ObjTyp == ObjectTypes.Void


def test_sector_access_rejects_negatives():
    # Python would otherwise wrap to the far edge of the galaxy silently.
    galaxy = Galaxy(5)
    for bad in (XYCoord(-1, 1), XYCoord(1, -1), XYCoord(6, 1)):
        try:
            galaxy.sector(bad)
        except IndexError:
            continue
        raise AssertionError(f"expected IndexError for {bad}")


def test_nebula_and_mine_share_the_special_byte():
    game = GameEnvironment()
    game.initialize_universe(size=10)
    pos = XYCoord(4, 4)

    put_nebula(game, pos, NebulaTypes.DenseNebula)
    assert get_nebula(game, pos) == NebulaTypes.DenseNebula
    # Setting the nebula must not disturb the minefield nibble.
    assert enemy_mine(game, pos) == Empire.Indep

    put_mine(game, pos, Empire.Empire3)
    assert enemy_mine(game, pos) == Empire.Empire3
    assert get_nebula(game, pos) == NebulaTypes.DenseNebula


def test_get_nebula_outside_the_galaxy_is_noneb():
    game = GameEnvironment()
    game.initialize_universe(size=10)
    assert get_nebula(game, XYCoord(0, 0)) == NebulaTypes.NoNeb


def test_initialize_universe_starts_blank():
    game = GameEnvironment()
    game.initialize_universe(starting_year=4021, size=20, planets=30)

    assert game.Year == 4021
    assert game.Galaxy.size == 20
    assert game.NoOfPlanets == 30
    assert game.TimePerTurn == 300
    assert game.GlobalSets.SetOfActivePlanets == set()
    # The Independent pseudo-empire is set up but is not a player.
    assert game.Universe.EmpireData[Empire.Indep].EmpireName == "Independent"
    assert not empire_active(game, Empire.Empire1)


def test_planet_count_is_clamped():
    game = GameEnvironment()
    game.initialize_universe(planets=9999)
    assert game.NoOfPlanets == 200


def test_new_game_activates_requested_empires():
    game = new_game(size=20, empires=3)
    assert game.Year == DEFAULT_STARTING_YEAR
    for emp in (Empire.Empire1, Empire.Empire2, Empire.Empire3):
        assert empire_active(game, emp)
        assert empire_player(game, emp)
    assert not empire_active(game, Empire.Empire4)
    assert game.EmpiresToMove == {Empire.Empire1, Empire.Empire2, Empire.Empire3}


def test_year_advances_once_per_full_rotation_not_per_turn():
    # Three empires means three player turns to one game year.
    game = new_game(size=20, empires=3)
    start = game.Year

    assert game.Player == Empire.Empire1
    update_turn(game)
    assert (game.Player, game.Year) == (Empire.Empire2, start)
    update_turn(game)
    assert (game.Player, game.Year) == (Empire.Empire3, start)
    update_turn(game)
    # Wrapping past Empire8 back to Empire1 is what advances the year.
    assert (game.Player, game.Year) == (Empire.Empire1, start + 1)


def test_single_empire_advances_a_year_every_turn():
    game = new_game(size=20, empires=1)
    start = game.Year
    update_turn(game)
    assert game.Player == Empire.Empire1
    assert game.Year == start + 1


def test_empires_to_move_refills_on_rotation():
    game = new_game(size=20, empires=2)
    update_turn(game)
    assert game.EmpiresToMove == {Empire.Empire2}
    update_turn(game)
    assert game.EmpiresToMove == {Empire.Empire1, Empire.Empire2}


def test_next_empire_skips_inactive_and_wraps():
    game = new_game(size=20, empires=1)
    game.Universe.EmpireData[Empire.Empire5].InUse = True

    assert next_empire(game, Empire.Empire1) == Empire.Empire5
    assert next_empire(game, Empire.Empire5) == Empire.Empire1


def test_no_more_players_detects_a_finished_game():
    game = new_game(size=20, empires=1)
    assert not no_more_players(game)

    game.Universe.EmpireData[Empire.Empire1].InUse = False
    assert no_more_players(game)


def test_object_placement_and_lookup():
    game = new_game(size=20)
    pos = XYCoord(7, 9)
    planet_id = IDNumber(ObjectTypes.Pln, 1)

    game.Universe.Planet[1].XY = pos
    put_object(game, pos, planet_id)

    assert get_object(game, pos) == planet_id
    assert get_coord(game, planet_id) == pos
    # An object type with no record reports Limbo rather than raising.
    assert get_coord(game, IDNumber(ObjectTypes.BlkHl, 1)) == XYCoord(0, 0)


def test_get_fleets_finds_only_active_fleets_at_the_position():
    from recreon.datastrc import FleetRecord

    game = new_game(size=20)
    pos = XYCoord(3, 3)

    game.Universe.Fleet[1] = FleetRecord(XY=pos)
    game.Universe.Fleet[2] = FleetRecord(XY=XYCoord(4, 4))
    game.GlobalSets.SetOfActiveFleets = {1, 2}
    assert get_fleets(game, pos) == {1}

    # An inactive fleet at the same spot is invisible.
    game.GlobalSets.SetOfActiveFleets = {2}
    assert get_fleets(game, pos) == set()


def test_scouting_marks_both_scouted_and_known():
    game = new_game(size=20)
    planet_id = IDNumber(ObjectTypes.Pln, 1)

    assert not scouted(game, Empire.Empire1, planet_id)
    scout_object(game, Empire.Empire1, planet_id)
    assert scouted(game, Empire.Empire1, planet_id)
    assert Empire.Empire1 in game.Universe.Planet[1].KnownBy


def test_games_are_independent():
    # The Pascal kept one global universe; the point of GameEnvironment is
    # that tests can hold several.
    a = new_game(size=10, empires=1)
    b = new_game(size=20, empires=2)
    update_turn(a)

    assert a.Year != b.Year
    assert a.Galaxy.size == 10
    assert b.Galaxy.size == 20
