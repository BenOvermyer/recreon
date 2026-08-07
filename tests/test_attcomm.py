"""Attack commands, ported from ATTCOMM.PAS."""

import pytest
from conftest import blank_game, place_world

from recreon.attack import AttackResultTypes
from recreon.attcomm import (
    attack_targets,
    auto_attack_command,
    casualty_report,
    result_message,
)
from recreon.fleet import get_next_fleet, move_fleet
from recreon.galaxy import XYCoord
from recreon.intrface import create_stargate, next_stargate_slot
from recreon.primintr import get_ships, put_ships
from recreon.types import (
    SHIP_TYPES,
    Empire,
    IDNumber,
    ObjectTypes,
    TechnologyTypes,
    ship_array,
)
from recreon.utils.pascal import set_rand_seed

T = TechnologyTypes
PLAYER = Empire.Empire1
THEIRS = Empire.Empire2
HERE = XYCoord(5, 5)


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


@pytest.fixture
def game():
    g = blank_game(size=20, empires=2)
    g.Universe.EmpireData[PLAYER].Capital = place_world(
        g, 1, XYCoord(2, 2), emp=PLAYER
    )
    return g


def a_fleet(game, emp=PLAYER, xy=HERE, scouted_by=(PLAYER,), **ships):
    flt = get_next_fleet(game, emp)
    move_fleet(game, flt, xy)
    for who in scouted_by:
        game.Universe.Fleet[flt.Index].ScoutedBy.add(who)
    stock = ship_array()
    for kind, count in ships.items():
        stock[T[kind]] = count
    put_ships(game, flt, stock)
    return flt


# --- Choosing a target -------------------------------------------------------


def test_an_enemy_fleet_in_the_sector_is_a_target(game):
    mine = a_fleet(game, fgt=100)
    theirs = a_fleet(game, emp=THEIRS, fgt=50)

    assert [obj for obj, _ in attack_targets(game, PLAYER, mine)] == [theirs]


def test_an_unscouted_enemy_fleet_is_not_offered(game):
    mine = a_fleet(game, fgt=100)
    a_fleet(game, emp=THEIRS, scouted_by=(), fgt=50)

    assert attack_targets(game, PLAYER, mine) == []


def test_your_own_fleet_is_never_a_target(game):
    mine = a_fleet(game, fgt=100)
    a_fleet(game, fgt=50)

    assert attack_targets(game, PLAYER, mine) == []


def test_an_enemy_world_under_the_fleet_is_a_target(game):
    place_world(game, 2, HERE, emp=THEIRS)
    mine = a_fleet(game, fgt=100)

    assert [obj.ObjTyp for obj, _ in attack_targets(game, PLAYER, mine)] == [
        ObjectTypes.Pln
    ]


def test_a_fleet_in_orbit_screens_the_world_beneath_it(game):
    """`IF ListSize=0 THEN add object` -- the world is only offered once no
    enemy fleet is in the sector, so a screening fleet must be destroyed
    first. A real mechanic, not a display quirk.
    """
    place_world(game, 2, HERE, emp=THEIRS)
    mine = a_fleet(game, fgt=100)
    screen = a_fleet(game, emp=THEIRS, fgt=50)

    offered = [obj for obj, _ in attack_targets(game, PLAYER, mine)]
    assert offered == [screen]

    # Remove the screen and the world becomes reachable.
    game.GlobalSets.SetOfActiveFleets.discard(screen.Index)
    assert [obj.ObjTyp for obj, _ in attack_targets(game, PLAYER, mine)] == [
        ObjectTypes.Pln
    ]


def test_your_own_world_is_not_a_target(game):
    place_world(game, 2, HERE, emp=PLAYER)
    mine = a_fleet(game, fgt=100)

    assert attack_targets(game, PLAYER, mine) == []


def test_a_stargate_can_be_targeted(game):
    gate = IDNumber(ObjectTypes.Gate, next_stargate_slot(game))
    create_stargate(game, gate, THEIRS, T.gte, HERE)
    mine = a_fleet(game, fgt=100)

    assert [obj for obj, _ in attack_targets(game, PLAYER, mine)] == [gate]


# --- Casualties --------------------------------------------------------------


def test_casualties_count_only_losses():
    before = {ship: 0 for ship in SHIP_TYPES}
    after = dict(before)
    before[T.fgt] = 100
    after[T.fgt] = 60
    # A captured transport is a *gain*, and the report has no column for it.
    before[T.trn] = 10
    after[T.trn] = 25

    assert casualty_report(before, after) == {T.fgt: 40}


# --- The outcome message -----------------------------------------------------


def test_a_destroyed_force_draws_a_consolation(game):
    lines = result_message(
        game, PLAYER, IDNumber(ObjectTypes.Pln, 1), AttackResultTypes.AttDestroyedART
    )

    assert "entire attack force has been destroyed" in lines[0]
    assert len(lines) == 2  # plus one of the two excuses


def test_a_retreat_says_so(game):
    lines = result_message(
        game, PLAYER, IDNumber(ObjectTypes.Pln, 1), AttackResultTypes.AttRetreatsART
    )
    assert "forced to retreat" in lines[0]


def test_conquering_a_fleet_is_reported_plainly(game):
    lines = result_message(
        game, PLAYER, IDNumber(ObjectTypes.Flt, 1), AttackResultTypes.DefConqueredART
    )
    assert "enemy fleet has been destroyed" in lines[0]


def test_conquering_a_world_is_announced_in_the_rulers_name(game):
    game.Universe.EmpireData[PLAYER].IsAnEmpress = False
    lines = result_message(
        game, PLAYER, IDNumber(ObjectTypes.Pln, 1), AttackResultTypes.DefConqueredART
    )
    assert "His Imperial Majesty" in lines[0]

    game.Universe.EmpireData[PLAYER].IsAnEmpress = True
    lines = result_message(
        game, PLAYER, IDNumber(ObjectTypes.Pln, 1), AttackResultTypes.DefConqueredART
    )
    assert "Her Imperial Majesty" in lines[0]


# --- Resolving ---------------------------------------------------------------


def test_a_gate_is_razed_rather_than_fought(game):
    """It has nothing to fight with, so there is no casualty list."""
    gate = IDNumber(ObjectTypes.Gate, next_stargate_slot(game))
    create_stargate(game, gate, THEIRS, T.gte, HERE)
    mine = a_fleet(game, fgt=100)

    outcome = auto_attack_command(game, PLAYER, mine, gate)

    assert outcome.result is AttackResultTypes.NoART
    assert outcome.casualties == {}
    assert "has been destroyed" in outcome.lines[0]


def test_an_overwhelming_attack_takes_the_target(game):
    theirs = a_fleet(game, emp=THEIRS, fgt=1)
    mine = a_fleet(game, fgt=5000, ssp=500)

    outcome = auto_attack_command(game, PLAYER, mine, theirs)

    assert outcome.result is AttackResultTypes.DefConqueredART
    assert outcome.lines


def test_a_hopeless_attack_does_not_take_it(game):
    theirs = a_fleet(game, emp=THEIRS, fgt=5000, ssp=500)
    mine = a_fleet(game, fgt=1)

    outcome = auto_attack_command(game, PLAYER, mine, theirs)

    assert outcome.result is not AttackResultTypes.DefConqueredART
    assert outcome.lines


def test_a_destroyed_fleet_reports_everything_lost(game):
    """Original bug #65, deviated from.

    The original reads the fleet's ships after the fight without checking it
    survived, so a destroyed attack force builds its casualty list out of a
    disposed record. Here that is a `None` slot, so the port reports the whole
    complement lost -- which is what the subtraction was reaching for.
    """
    theirs = a_fleet(game, emp=THEIRS, fgt=9000, ssp=900)
    mine = a_fleet(game, fgt=1)

    outcome = auto_attack_command(game, PLAYER, mine, theirs)

    if mine.Index not in game.GlobalSets.SetOfActiveFleets:
        assert outcome.casualties == {T.fgt: 1}


def test_casualties_are_measured_across_the_fight(game):
    theirs = a_fleet(game, emp=THEIRS, fgt=400)
    mine = a_fleet(game, fgt=2000, ssp=200)
    before = get_ships(game, mine)[T.fgt]

    outcome = auto_attack_command(game, PLAYER, mine, theirs)

    if mine.Index in game.GlobalSets.SetOfActiveFleets:
        after = get_ships(game, mine)[T.fgt]
        assert outcome.casualties.get(T.fgt, 0) == max(0, before - after)
