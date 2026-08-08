"""Fleet commands, ported from FLTCOMM.PAS.

The *mechanics* -- deploy, abort, transfer, refuel, movement, running orders --
are `test_fleet.py`, against `fleet.py`. This is the nine commands a player
drives them with, and the guards each puts in front of the mechanic.
"""

import pytest
from conftest import blank_game, place_world

from recreon.fleet import execute_fleet_orders, get_next_fleet, move_fleet
from recreon.fltcomm import (
    MAX_SHIPS_PER_STACK,
    OrderCompileError,
    abort_fleet_command,
    abort_warnings,
    change_destination_command,
    fleet_cancel_orders_command,
    fleet_order_source,
    fleet_orders_command,
    ground_candidates,
    launch_fleet_command,
    launch_probe_command,
    max_trillum_to_use,
    mine_sweeper_command,
    player_fleets,
    refuel_fleet_command,
    trillum_to_use,
)
from recreon.galaxy import Location, XYCoord, limbo
from recreon.news import NewsTypes
from recreon.orders import (
    CommandRecord,
    fleet_next_statement,
    get_fleet_code,
    set_fleet_next_statement,
)
from recreon.primintr import (
    enemy_mine,
    get_cargo,
    get_fleet_fuel,
    get_probe,
    get_ships,
    location2index,
    put_cargo,
    put_mine,
    put_ships,
)
from recreon.types import (
    NO_OF_PROBES_PER_EMPIRE,
    Empire,
    IDNumber,
    ObjectTypes,
    TechnologyTypes,
    cargo_array,
    empty_quadrant,
    ship_array,
)
from recreon.utils.pascal import set_rand_seed

T = TechnologyTypes
PLAYER = Empire.Empire1
HOME_XY = XYCoord(5, 5)


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


@pytest.fixture
def game():
    g = blank_game(size=20, empires=2)
    home = place_world(g, 1, HOME_XY, emp=PLAYER)
    g.Universe.EmpireData[PLAYER].Capital = home
    ships = ship_array()
    ships[T.fgt] = 500
    ships[T.trn] = 500
    put_ships(g, home, ships)
    return g


@pytest.fixture
def home():
    return IDNumber(ObjectTypes.Pln, 1)


def a_fleet(game, xy=HOME_XY, emp=PLAYER, **ships):
    """A fleet at ``xy``, scouted by its own empire.

    The scouting matters: `GetGround` filters on `Scouted(Player, Flt2)`
    without exempting your own fleets, so an unscouted fleet of yours is
    offered by none of these menus. A real turn sets it -- `set_up_turn` runs
    `scout_fleets` before the player does anything -- and this stands in for
    that.
    """
    flt = get_next_fleet(game, emp)
    move_fleet(game, flt, xy)
    game.Universe.Fleet[flt.Index].ScoutedBy.add(emp)
    stock = ship_array()
    for kind, count in ships.items():
        stock[T[kind]] = count
    put_ships(game, flt, stock)
    return flt


# --- Choosing a target -------------------------------------------------------


def test_the_world_under_a_fleet_is_a_candidate(game, home):
    flt = a_fleet(game, fgt=10)
    offered = [obj for obj, _ in ground_candidates(game, PLAYER, flt, False, False)]

    assert home in offered
    assert flt not in offered  # include_fleet is False


def test_refuelling_can_target_the_fleet_itself(game):
    """`IncludeFleet` is what lets a fleet burn the trillum in its own hold."""
    flt = a_fleet(game, fgt=10)
    offered = [obj for obj, _ in ground_candidates(game, PLAYER, flt, True, True)]

    assert flt in offered


def test_another_empires_fleet_is_offered_only_once_scouted(game):
    """You cannot transfer to something whose composition you cannot see."""
    mine = a_fleet(game, fgt=10)
    theirs = a_fleet(game, emp=Empire.Empire2, fgt=10)

    offered = [obj for obj, _ in ground_candidates(game, PLAYER, mine, False, False)]
    assert theirs not in offered

    game.Universe.Fleet[theirs.Index].ScoutedBy.add(PLAYER)  # now we can see it
    offered = [obj for obj, _ in ground_candidates(game, PLAYER, mine, False, False)]
    assert theirs in offered


def test_refuelling_only_offers_your_own(game):
    mine = a_fleet(game, fgt=10)
    theirs = a_fleet(game, emp=Empire.Empire2, fgt=10)
    game.Universe.Fleet[theirs.Index].ScoutedBy.add(PLAYER)

    offered = [obj for obj, _ in ground_candidates(game, PLAYER, mine, True, True)]
    assert theirs not in offered


def test_player_fleets_lists_only_yours(game):
    mine = a_fleet(game, fgt=10)
    a_fleet(game, emp=Empire.Empire2, fgt=10)

    assert [obj for obj, _ in player_fleets(game, PLAYER)] == [mine]


# --- Launch ------------------------------------------------------------------


def test_launching_names_the_fleet_and_the_name_follows_it(game, home):
    ships = ship_array()
    ships[T.fgt] = 100

    flt, message = launch_fleet_command(
        game, PLAYER, "vanguard", home, ships, cargo_array(), XYCoord(8, 8)
    )

    assert flt.Index in game.GlobalSets.SetOfActiveFleets
    assert "Vanguard deployed" in message
    named = location2index(game, PLAYER, Location(XY=limbo(), ID=flt))
    assert named is not None and named.Name == "Vanguard"


def test_a_fleet_with_no_ships_is_not_launched(game, home):
    """`IF NOT NoShips(FltSh)` -- cargo alone cannot make a fleet."""
    cargo = cargo_array()
    cargo[T.tri] = 100

    flt, message = launch_fleet_command(
        game, PLAYER, "Ghost", home, ship_array(), cargo, XYCoord(8, 8)
    )

    assert flt == empty_quadrant()
    assert message == ""
    assert not game.GlobalSets.SetOfActiveFleets


# --- Abort -------------------------------------------------------------------


def test_aborting_onto_your_own_world_warns_about_nothing(game, home):
    flt = a_fleet(game, fgt=10)
    assert abort_warnings(game, PLAYER, flt, home) == []


def test_aborting_onto_another_empire_warns_but_is_allowed(game):
    """The only way to give ships away, so it asks rather than refuses."""
    place_world(game, 2, XYCoord(9, 9), emp=Empire.Empire2)
    theirs = IDNumber(ObjectTypes.Pln, 2)
    flt = a_fleet(game, xy=XYCoord(9, 9), fgt=10)

    warnings = abort_warnings(game, PLAYER, flt, theirs)
    assert len(warnings) == 1
    assert "is not part of" in warnings[0]

    message = abort_fleet_command(game, PLAYER, flt, theirs)
    assert "aborted to" in message
    assert get_ships(game, theirs)[T.fgt] == 10


def test_an_overflowing_stack_warns_about_losses(game, home):
    ships = ship_array()
    ships[T.fgt] = MAX_SHIPS_PER_STACK
    put_ships(game, home, ships)
    flt = a_fleet(game, fgt=500)

    warnings = abort_warnings(game, PLAYER, flt, home)
    assert any("cannot hold so many ships" in w for w in warnings)


def test_aborting_onto_another_fleet_reads_as_joining(game):
    first = a_fleet(game, fgt=10)
    second = a_fleet(game, fgt=10)

    message = abort_fleet_command(game, PLAYER, first, second)

    assert "joined with" in message
    assert first.Index not in game.GlobalSets.SetOfActiveFleets
    assert get_ships(game, second)[T.fgt] == 20


# --- Destination -------------------------------------------------------------


def test_changing_destination_reports_where(game):
    flt = a_fleet(game, fgt=10)
    message = change_destination_command(game, PLAYER, flt, XYCoord(8, 8))

    assert game.Universe.Fleet[flt.Index].Dest == XYCoord(8, 8)
    assert "New destination" in message


# --- Refuel ------------------------------------------------------------------


def test_the_refuel_maximum_is_the_lesser_of_need_and_supply(game, home):
    flt = a_fleet(game, trn=100)
    stock = get_cargo(game, home)
    stock[T.tri] = 3
    put_cargo(game, home, stock)

    # Only three tons on the ground, however thirsty the fleet is.
    assert max_trillum_to_use(game, flt, home) == 3


@pytest.mark.parametrize("requested,maximum,expected", [(5, 10, 5), (0, 10, 10)])
def test_a_trillum_request_in_range_is_taken(requested, maximum, expected):
    """Zero means "as much as possible" -- the original's default."""
    assert trillum_to_use(requested, maximum) == expected


def test_too_much_trillum_is_refused():
    with pytest.raises(ValueError, match="maximum amount allowable"):
        trillum_to_use(20, 10)


def test_a_negative_request_is_refused():
    with pytest.raises(ValueError, match="bizarre"):
        trillum_to_use(-1, 10)


def test_refuelling_burns_trillum_into_fuel(game, home):
    flt = a_fleet(game, trn=100)
    stock = get_cargo(game, home)
    stock[T.tri] = 50
    put_cargo(game, home, stock)
    before = get_fleet_fuel(game, flt)

    refuel_fleet_command(game, PLAYER, flt, home, 10)

    assert get_fleet_fuel(game, flt) > before
    assert get_cargo(game, home)[T.tri] == 40


# --- Probes ------------------------------------------------------------------


def test_probes_are_numbered_upward_as_they_are_used(game):
    """`GetProbe` hands back the highest free slot and the message prints
    `11 - PNum`, so the first launch is Probe #1."""
    first = launch_probe_command(game, PLAYER, XYCoord(9, 9))
    second = launch_probe_command(game, PLAYER, XYCoord(10, 10))

    assert "Probe #1 " in first
    assert "Probe #2 " in second


def test_running_out_of_probes_says_so(game):
    for _ in range(NO_OF_PROBES_PER_EMPIRE):
        launch_probe_command(game, PLAYER, XYCoord(9, 9))

    assert get_probe(game, PLAYER) == 0
    assert "no more probes" in launch_probe_command(game, PLAYER, XYCoord(9, 9))


# --- Mine sweeping -----------------------------------------------------------


def test_sweeping_an_empty_sector_finds_nothing(game):
    flt = a_fleet(game, fgt=10)
    assert "No SRMs found" in mine_sweeper_command(game, PLAYER, flt)


def test_sweeping_clears_the_field_and_tells_its_owner(game):
    flt = a_fleet(game, xy=XYCoord(9, 9), fgt=10)
    put_mine(game, XYCoord(9, 9), Empire.Empire2)

    message = mine_sweeper_command(game, PLAYER, flt)

    assert "completed" in message
    assert enemy_mine(game, XYCoord(9, 9)) is Empire.Indep
    assert any(
        item.Headline is NewsTypes.SRMClear for item in game.News[Empire.Empire2]
    )


def test_clearing_your_own_field_tells_nobody(game):
    flt = a_fleet(game, xy=XYCoord(9, 9), fgt=10)
    put_mine(game, XYCoord(9, 9), PLAYER)

    mine_sweeper_command(game, PLAYER, flt)

    assert not any(
        item.Headline is NewsTypes.SRMClear for item in game.News[PLAYER]
    )


def test_the_command_needs_no_starships_though_the_order_needs_a_hundred(game):
    """Original bug #60, reproduced.

    `ExecuteSweepCom` refuses under 100 starships; `MineSweeperCommand` asks
    nothing at all. A single fighter clears a field from the menu.
    """
    flt = a_fleet(game, xy=XYCoord(9, 9), fgt=1)
    put_mine(game, XYCoord(9, 9), Empire.Empire2)

    assert get_ships(game, flt)[T.ssp] == 0
    assert "completed" in mine_sweeper_command(game, PLAYER, flt)
    assert enemy_mine(game, XYCoord(9, 9)) is Empire.Indep


# --- Orders ------------------------------------------------------------------


def orders_of(game, flt, *commands):
    code = get_fleet_code(game, flt)
    code[:] = [CommandRecord(c) for c in commands]
    return code


def test_compiling_orders_installs_them(game):
    flt = a_fleet(game, fgt=10)

    message = fleet_orders_command(game, PLAYER, flt, ["WAIT", "WAIT"])

    assert "completed" in message
    assert len(get_fleet_code(game, flt)) == 2
    assert fleet_next_statement(game, flt) == 1


def test_an_empty_order_list_cancels(game):
    flt = a_fleet(game, fgt=10)
    fleet_orders_command(game, PLAYER, flt, ["WAIT"])

    message = fleet_orders_command(game, PLAYER, flt, [])

    assert "cancelled" in message
    assert fleet_next_statement(game, flt) == 0
    assert get_fleet_code(game, flt) == []


def test_a_bad_order_line_names_the_line(game):
    flt = a_fleet(game, fgt=10)

    with pytest.raises(OrderCompileError, match="line 2"):
        fleet_orders_command(game, PLAYER, flt, ["WAIT", "NONSENSE"])


def test_the_resume_point_survives_an_edit(game):
    """Editing orders must not restart a route already half-flown."""
    flt = a_fleet(game, fgt=10)
    fleet_orders_command(game, PLAYER, flt, ["WAIT", "WAIT", "WAIT"])
    set_fleet_next_statement(game, flt, 3)

    fleet_orders_command(game, PLAYER, flt, ["WAIT", "WAIT", "WAIT", "WAIT"])

    assert fleet_next_statement(game, flt) == 3


def test_shortening_the_orders_clamps_the_resume_point(game):
    """Original bug #59, deviated from.

    The original writes the old position back unchecked, so a shorter list
    leaves the fleet indexing past the end -- undefined in Pascal, an
    IndexError here. Clamped to the last command instead.
    """
    flt = a_fleet(game, fgt=10)
    fleet_orders_command(game, PLAYER, flt, ["WAIT"] * 5)
    set_fleet_next_statement(game, flt, 4)

    fleet_orders_command(game, PLAYER, flt, ["WAIT", "WAIT"])

    assert fleet_next_statement(game, flt) == 2
    # And the fleet can still take its turn, which is the point.
    execute_fleet_orders(game, PLAYER, flt)


def test_order_text_round_trips_through_the_editor(game):
    flt = a_fleet(game, fgt=10)
    fleet_orders_command(game, PLAYER, flt, ["WAIT", "REPE"])

    assert [line.strip().upper()[:4] for line in fleet_order_source(game, PLAYER, flt)] == [
        "WAIT",
        "REPE",
    ]


def test_a_fleet_with_no_orders_decompiles_to_nothing(game):
    flt = a_fleet(game, fgt=10)
    assert fleet_order_source(game, PLAYER, flt) == []


def test_cancelling_throws_the_orders_away(game):
    flt = a_fleet(game, fgt=10)
    fleet_orders_command(game, PLAYER, flt, ["WAIT", "WAIT"])

    message = fleet_cancel_orders_command(game, PLAYER, flt)

    assert "cancelled" in message
    assert fleet_next_statement(game, flt) == 0
    assert get_fleet_code(game, flt) == []
