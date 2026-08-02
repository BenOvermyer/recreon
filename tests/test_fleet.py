"""Milestone 4: fleets deploy, carry cargo, burn fuel, move and obey orders."""

import pytest

from conftest import blank_game, place_world
from recreon.datacnst import FUEL_PER_TON, CargoSpace, FltMovementRate
from recreon.fleet import (
    abort_fleet,
    change_composition_of_fleet,
    deploy_fleet,
    destroy_fleet,
    execute_fleet_orders,
    execute_sweep_com,
    execute_trans_com,
    get_fleet_destination,
    get_new_pos,
    get_next_fleet,
    in_range_of_disrupter,
    in_range_of_my_disrupter,
    mine_field_damage,
    move_fleet,
    refuel_fleet,
    set_fleet_destination,
    update_all_fleets,
    update_fleet,
    use_up_fuel,
)
from recreon.galaxy import Location, XYCoord, limbo
from recreon.intrface import balance_fleet, create_stargate, create_starbase
from recreon.misc import fuel_capacity, fuel_consumption
from recreon.news import NewsTypes
from recreon.orders import (
    CommandRecord,
    CommandTypes,
    add_orders,
    set_fleet_code,
    set_fleet_next_statement,
)
from recreon.primintr import (
    get_cargo,
    get_coord,
    get_fleet_fuel,
    get_fleet_status,
    get_ships,
    put_cargo,
    put_mine,
    put_nebula,
    put_ships,
    set_fleet_fuel,
    set_warp_link_freq,
    type_of_fleet,
)
from recreon.types import (
    MAX_NO_OF_FLEETS,
    Empire,
    FleetStatus,
    FleetTypes,
    IDNumber,
    NebulaTypes,
    ObjectTypes,
    TechnologyTypes,
    cargo_array,
    ship_array,
)
from recreon.utils.pascal import set_rand_seed

T = TechnologyTypes


# --- Fixtures ----------------------------------------------------------------


@pytest.fixture
def game():
    """One empire, one capital world at (10, 10) in a 20x20 galaxy."""
    g = blank_game(size=20, empires=2)
    world = place_world(g, 1, XYCoord(10, 10), emp=Empire.Empire1)
    g.Universe.EmpireData[Empire.Empire1].Capital = world
    return g


@pytest.fixture
def world(game):
    return IDNumber(ObjectTypes.Pln, 1)


def stock(game, obj, ships=None, cargo=None):
    """Put a known set of ships and cargo on an object."""
    sh = ship_array()
    sh.update(ships or {})
    cr = cargo_array()
    cr.update(cargo or {})
    put_ships(game, obj, sh)
    put_cargo(game, obj, cr)


def launch(game, world, ships, cargo=None, dest=None, emp=Empire.Empire1):
    """Deploy a fleet carrying exactly ``ships``/``cargo`` from ``world``."""
    sh = ship_array()
    sh.update(ships)
    cr = cargo_array()
    cr.update(cargo or {})
    return deploy_fleet(game, emp, world, sh, cr, dest or get_coord(game, world))


def arr(**kwargs):
    """A ship array with the named types set."""
    sh = ship_array()
    sh.update({T[name]: count for name, count in kwargs.items()})
    return sh


# --- Fleet classification ----------------------------------------------------


@pytest.mark.parametrize(
    "ships,expected",
    [
        ({T.hkr: 100}, FleetTypes.HKFleet),
        ({T.jmp: 100}, FleetTypes.JumpFleet),
        ({T.jmp: 100, T.jtn: 10}, FleetTypes.JumpFleet),
        ({T.pen: 100}, FleetTypes.Penetrator),
        ({T.pen: 100, T.hkr: 10}, FleetTypes.Penetrator),
        ({T.fgt: 10, T.trn: 10}, FleetTypes.Standard),
        ({T.ssp: 10}, FleetTypes.Standard),
        ({T.jmp: 10, T.pen: 10}, FleetTypes.AdvWrpFleet),
    ],
)
def test_fleet_type_is_decided_by_what_is_missing(game, world, ships, expected):
    stock(game, world, ships)
    fleet = launch(game, world, ships)
    assert type_of_fleet(game, fleet) == expected


# --- Slot allocation ---------------------------------------------------------


def test_fleet_slots_are_handed_out_from_the_top(game):
    assert get_next_fleet(game, Empire.Empire1).Index == MAX_NO_OF_FLEETS
    assert get_next_fleet(game, Empire.Empire1).Index == MAX_NO_OF_FLEETS - 1


def test_running_out_of_slots_returns_a_void_id(game):
    game.GlobalSets.SetOfActiveFleets = set(range(1, MAX_NO_OF_FLEETS + 1))
    assert get_next_fleet(game, Empire.Empire1).ObjTyp == ObjectTypes.Void


# --- Deployment --------------------------------------------------------------


def test_deploy_moves_ships_off_the_world(game, world):
    stock(game, world, {T.jmp: 150})
    fleet = launch(game, world, {T.jmp: 100})

    assert get_ships(game, fleet)[T.jmp] == 100
    assert get_ships(game, world)[T.jmp] == 50


def test_deploy_starts_the_fleet_at_the_launch_point(game, world):
    stock(game, world, {T.jmp: 100})
    fleet = launch(game, world, {T.jmp: 100}, dest=XYCoord(15, 15))

    assert get_coord(game, fleet) == XYCoord(10, 10)
    assert get_fleet_destination(game, fleet) == XYCoord(15, 15)
    assert get_fleet_status(game, fleet) == FleetStatus.FInTrans


def test_deploy_buys_fuel_with_the_worlds_trillum(game, world):
    stock(game, world, {T.jmp: 100}, {T.tri: 500})
    fleet = launch(game, world, {T.jmp: 100})

    # Filled to the fleet's capacity, paid for out of the world's stock.
    assert get_fleet_fuel(game, fleet) == pytest.approx(
        fuel_capacity(get_ships(game, fleet)), abs=1
    )
    assert get_cargo(game, world)[T.tri] < 500


def test_deploy_with_no_trillum_anywhere_still_gets_a_token_ten(game, world):
    """A fleet launched bone dry could never move or be recovered, so the
    original hands it enough to be going on with."""
    stock(game, world, {T.jmp: 100})
    fleet = launch(game, world, {T.jmp: 100})

    assert get_fleet_fuel(game, fleet) == 10


def test_deploy_marks_the_sector_as_holding_a_fleet(game, world):
    stock(game, world, {T.jmp: 100})
    launch(game, world, {T.jmp: 100})

    assert Empire.Empire1 in game.Galaxy.sector(XYCoord(10, 10)).Flts


# --- Movement bookkeeping ----------------------------------------------------


def test_move_fleet_clears_the_flag_it_leaves_behind(game, world):
    stock(game, world, {T.jmp: 100})
    fleet = launch(game, world, {T.jmp: 100})

    move_fleet(game, fleet, XYCoord(12, 12))

    assert Empire.Empire1 not in game.Galaxy.sector(XYCoord(10, 10)).Flts
    assert Empire.Empire1 in game.Galaxy.sector(XYCoord(12, 12)).Flts


def test_a_second_fleet_keeps_the_sector_flagged(game, world):
    stock(game, world, {T.jmp: 200})
    first = launch(game, world, {T.jmp: 100})
    launch(game, world, {T.jmp: 100})

    move_fleet(game, first, XYCoord(12, 12))

    assert Empire.Empire1 in game.Galaxy.sector(XYCoord(10, 10)).Flts


def test_setting_a_destination_the_fleet_is_already_at_makes_it_ready(game, world):
    """Which is what lets a fleet run its next order the same year it is
    ordered somewhere it already sits."""
    stock(game, world, {T.jmp: 100})
    fleet = launch(game, world, {T.jmp: 100}, dest=XYCoord(15, 15))
    assert get_fleet_status(game, fleet) == FleetStatus.FInTrans

    set_fleet_destination(game, fleet, XYCoord(10, 10))

    assert get_fleet_status(game, fleet) == FleetStatus.FReady


def test_destroy_fleet_frees_the_slot_and_clears_the_sector(game, world):
    stock(game, world, {T.jmp: 100})
    fleet = launch(game, world, {T.jmp: 100})

    destroy_fleet(game, fleet)

    assert fleet.Index not in game.GlobalSets.SetOfActiveFleets
    assert fleet.Index not in game.GlobalSets.SetOfFleetsOf[Empire.Empire1]
    assert game.Universe.Fleet[fleet.Index] is None
    assert Empire.Empire1 not in game.Galaxy.sector(XYCoord(10, 10)).Flts


# --- Stepping ----------------------------------------------------------------


def test_a_step_moves_both_axes_at_once(game):
    assert get_new_pos(game, XYCoord(5, 5), XYCoord(9, 8)) == XYCoord(6, 6)


def test_a_step_that_would_enter_a_dense_nebula_returns_limbo(game):
    put_nebula(game, XYCoord(6, 6), NebulaTypes.DenseNebula)
    assert get_new_pos(game, XYCoord(5, 5), XYCoord(9, 9)) == limbo()


def test_a_thin_nebula_does_not_block(game):
    put_nebula(game, XYCoord(6, 6), NebulaTypes.Nebula)
    assert get_new_pos(game, XYCoord(5, 5), XYCoord(9, 9)) == XYCoord(6, 6)


# --- Aborting and composition ------------------------------------------------


def test_abort_returns_ships_and_cargo_to_the_world(game, world):
    stock(game, world, {T.jmp: 150, T.trn: 20}, {T.met: 100})
    fleet = launch(game, world, {T.jmp: 100, T.trn: 10}, {T.met: 30})

    abort_fleet(game, fleet, world, report=False)
    destroy_fleet(game, fleet)

    assert get_ships(game, world)[T.jmp] == 150
    assert get_ships(game, world)[T.trn] == 20
    assert get_cargo(game, world)[T.met] == 100


def test_abort_converts_leftover_fuel_back_to_trillum(game, world):
    stock(game, world, {T.jmp: 100})
    fleet = launch(game, world, {T.jmp: 100})
    set_fleet_fuel(game, fleet, 3 * FUEL_PER_TON)

    abort_fleet(game, fleet, world, report=False)

    assert get_cargo(game, world)[T.tri] == 3


def test_abort_onto_another_fleet_moves_fuel_as_fuel(game, world):
    """Reconverting to trillum would round away everything under a ton."""
    stock(game, world, {T.jmp: 200})
    first = launch(game, world, {T.jmp: 100})
    second = launch(game, world, {T.jmp: 100})
    set_fleet_fuel(game, first, 100)
    set_fleet_fuel(game, second, 50)

    abort_fleet(game, first, second, report=False)

    assert get_fleet_fuel(game, second) == 150


def test_abort_onto_a_foreign_world_files_news_for_its_owner(game, world):
    other = place_world(game, 2, XYCoord(11, 11), emp=Empire.Empire2)
    stock(game, world, {T.jmp: 100})
    fleet = launch(game, world, {T.jmp: 100})

    abort_fleet(game, fleet, other, report=True)

    headlines = [n.Headline for n in game.News[Empire.Empire2]]
    assert NewsTypes.TrnsShp in headlines
    assert NewsTypes.Trns2 in headlines


def test_emptying_a_fleet_of_ships_aborts_and_destroys_it(game, world):
    stock(game, world, {T.jmp: 100})
    fleet = launch(game, world, {T.jmp: 100})

    change_composition_of_fleet(
        game, fleet, world, ship_array(), cargo_array(), arr(jmp=100), cargo_array()
    )

    assert fleet.Index not in game.GlobalSets.SetOfActiveFleets
    assert get_ships(game, world)[T.jmp] == 100


# --- Refuelling --------------------------------------------------------------


def test_refuel_spends_trillum_and_caps_at_capacity(game, world):
    stock(game, world, {T.jmp: 100}, {T.tri: 500})
    fleet = launch(game, world, {T.jmp: 100})
    set_fleet_fuel(game, fleet, 0)
    put_cargo(game, world, {**get_cargo(game, world), T.tri: 500})

    refuel_fleet(game, fleet, world, 50)

    assert get_fleet_fuel(game, fleet) == pytest.approx(
        fuel_capacity(get_ships(game, fleet))
    )
    # The trillum is spent whether or not it all fitted.
    assert get_cargo(game, world)[T.tri] == 450


def test_refuelling_an_inactive_fleet_makes_it_ready_again(game, world):
    stock(game, world, {T.jmp: 100}, {T.tri: 100})
    fleet = launch(game, world, {T.jmp: 100})
    set_fleet_fuel(game, fleet, 0)
    game.Universe.Fleet[fleet.Index].Status = FleetStatus.FInactive

    refuel_fleet(game, fleet, world, 5)

    assert get_fleet_status(game, fleet) == FleetStatus.FReady


def test_a_fleet_refuels_itself_from_its_own_trillum(game, world):
    stock(game, world, {T.jmp: 100, T.trn: 10}, {T.tri: 60})
    fleet = launch(game, world, {T.jmp: 100, T.trn: 10}, {T.tri: 60})
    set_fleet_fuel(game, fleet, 0)

    assert use_up_fuel(game, fleet) is True
    assert get_cargo(game, fleet)[T.tri] < 60


def test_a_fleet_with_no_fuel_and_no_trillum_goes_inactive(game, world):
    stock(game, world, {T.jmp: 100})
    fleet = launch(game, world, {T.jmp: 100})
    set_fleet_fuel(game, fleet, 0)

    assert use_up_fuel(game, fleet) is False
    assert get_fleet_status(game, fleet) == FleetStatus.FInactive
    assert NewsTypes.NoFuel in [n.Headline for n in game.News[Empire.Empire1]]


# --- Cargo balancing ---------------------------------------------------------


def test_balance_fleet_dumps_the_cheapest_cargo_first(game):
    ships = arr(trn=1)
    cargo = cargo_array()
    cargo[T.che] = CargoSpace[T.che]
    cargo[T.amb] = CargoSpace[T.amb]

    balance_fleet(ships, cargo)

    assert cargo[T.che] == 0
    assert cargo[T.amb] == CargoSpace[T.amb]


def test_balance_fleet_partly_refills_the_last_type_it_dumps(game):
    """Dumping a whole type usually overshoots, so the space that freed up is
    given back to that same type rather than left empty."""
    ships = arr(trn=2)
    cargo = cargo_array()
    cargo[T.che] = CargoSpace[T.che] * 3

    balance_fleet(ships, cargo)

    assert cargo[T.che] == CargoSpace[T.che] * 2


# --- Transfers ---------------------------------------------------------------


def test_transfer_picks_cargo_up_from_the_world_below(game, world):
    stock(game, world, {T.trn: 50}, {T.met: 1000})
    fleet = launch(game, world, {T.trn: 20})

    execute_trans_com(game, fleet, T.met, 30)

    assert get_cargo(game, fleet)[T.met] == 30
    assert get_cargo(game, world)[T.met] == 970


def test_transfer_is_clipped_to_what_the_world_has(game, world):
    stock(game, world, {T.trn: 50}, {T.met: 10})
    fleet = launch(game, world, {T.trn: 20})

    execute_trans_com(game, fleet, T.met, 500)

    assert get_cargo(game, fleet)[T.met] == 10


def test_transfer_is_clipped_to_the_fleets_transport_space(game, world):
    stock(game, world, {T.trn: 50}, {T.met: 9999})
    fleet = launch(game, world, {T.trn: 2})

    execute_trans_com(game, fleet, T.met, 9999)

    assert get_cargo(game, fleet)[T.met] == 2 * CargoSpace[T.met]


def test_a_negative_transfer_drops_cargo_off(game, world):
    stock(game, world, {T.trn: 50}, {T.met: 100})
    fleet = launch(game, world, {T.trn: 20}, {T.met: 40})

    execute_trans_com(game, fleet, T.met, -25)

    assert get_cargo(game, fleet)[T.met] == 15
    # The world kept 60 after the fleet launched with 40; 25 comes back.
    assert get_cargo(game, world)[T.met] == 85


def test_transfer_over_a_foreign_world_does_nothing(game, world):
    other = place_world(game, 2, XYCoord(11, 11), emp=Empire.Empire2)
    stock(game, other, {}, {T.met: 1000})
    stock(game, world, {T.trn: 50})
    fleet = launch(game, world, {T.trn: 20})
    move_fleet(game, fleet, XYCoord(11, 11))

    execute_trans_com(game, fleet, T.met, 30)

    assert get_cargo(game, fleet)[T.met] == 0
    assert get_cargo(game, other)[T.met] == 1000


def test_transfer_over_empty_space_does_nothing(game, world):
    stock(game, world, {T.trn: 50}, {T.met: 100})
    fleet = launch(game, world, {T.trn: 20})
    move_fleet(game, fleet, XYCoord(15, 15))

    execute_trans_com(game, fleet, T.met, 30)

    assert get_cargo(game, fleet)[T.met] == 0


# --- Minesweeping ------------------------------------------------------------


def test_sweeping_needs_a_hundred_starships(game, world):
    stock(game, world, {T.ssp: 200})
    fleet = launch(game, world, {T.ssp: 99})
    put_mine(game, XYCoord(10, 10), Empire.Empire2)

    execute_sweep_com(game, fleet)

    from recreon.primintr import enemy_mine

    assert enemy_mine(game, XYCoord(10, 10)) == Empire.Empire2
    assert NewsTypes.OrdersNoSSP in [n.Headline for n in game.News[Empire.Empire1]]


def test_sweeping_clears_the_field_and_tells_its_owner(game, world):
    stock(game, world, {T.ssp: 200})
    fleet = launch(game, world, {T.ssp: 100})
    put_mine(game, XYCoord(10, 10), Empire.Empire2)
    game.Galaxy.set_mine_scout(Empire.Empire1, XYCoord(10, 10))

    execute_sweep_com(game, fleet)

    from recreon.primintr import enemy_mine

    assert enemy_mine(game, XYCoord(10, 10)) == Empire.Indep
    assert game.Galaxy.sector(XYCoord(10, 10)).MineScout == set()
    assert NewsTypes.SRMClear in [n.Headline for n in game.News[Empire.Empire2]]


def test_sweeping_empty_space_reports_no_mines(game, world):
    stock(game, world, {T.ssp: 200})
    fleet = launch(game, world, {T.ssp: 100})

    execute_sweep_com(game, fleet)

    assert NewsTypes.OrdersNoSRMs in [n.Headline for n in game.News[Empire.Empire1]]


# --- Minefield damage --------------------------------------------------------


def test_mines_destroy_part_of_a_jump_fleet(game, world):
    set_rand_seed(7)
    stock(game, world, {T.jmp: 1000})
    fleet = launch(game, world, {T.jmp: 1000})

    assert mine_field_damage(game, fleet, Empire.Empire2) is False

    assert 0 < get_ships(game, fleet)[T.jmp] < 1000
    headlines = [n.Headline for n in game.News[Empire.Empire1]]
    assert NewsTypes.MinesDm in headlines
    assert NewsTypes.DestDetail in headlines


def test_mines_can_wipe_out_a_small_fleet(game, world):
    """The flat 1..100 term dominates for small fleets, so they go under."""
    set_rand_seed(7)
    stock(game, world, {T.jmp: 5})
    fleet = launch(game, world, {T.jmp: 5})

    assert mine_field_damage(game, fleet, Empire.Empire2) is True
    assert fleet.Index not in game.GlobalSets.SetOfActiveFleets
    assert NewsTypes.MinesDs in [n.Headline for n in game.News[Empire.Empire1]]


# --- Disrupters --------------------------------------------------------------


def make_disrupter(game, index, xy, emp):
    gate = IDNumber(ObjectTypes.Gate, index)
    create_stargate(game, gate, emp, T.dis, xy)
    return gate


def test_a_mistuned_disrupter_is_hostile_within_three_sectors(game):
    gate = make_disrupter(game, 1, XYCoord(10, 10), Empire.Empire2)
    set_warp_link_freq(game, Empire.Empire1, gate, 7)

    assert in_range_of_disrupter(game, Empire.Empire1, XYCoord(13, 10)) == Empire.Empire2
    assert in_range_of_disrupter(game, Empire.Empire1, XYCoord(14, 10)) is None


def test_a_matching_frequency_makes_a_disrupter_harmless(game):
    make_disrupter(game, 1, XYCoord(10, 10), Empire.Empire2)

    assert in_range_of_disrupter(game, Empire.Empire1, XYCoord(11, 10)) is None


def test_a_friendly_disrupter_helps_only_within_two_sectors(game):
    """Strictly shorter than the hostile range, so the band where a disrupter
    helps is inside the band where it obstructs."""
    make_disrupter(game, 1, XYCoord(10, 10), Empire.Empire1)

    assert in_range_of_my_disrupter(game, Empire.Empire1, XYCoord(12, 10)) is True
    assert in_range_of_my_disrupter(game, Empire.Empire1, XYCoord(13, 10)) is False


# --- The annual move ---------------------------------------------------------


def test_a_standard_fleet_moves_one_sector_a_year(game, world):
    stock(game, world, {T.fgt: 10, T.trn: 10}, {T.tri: 500})
    fleet = launch(game, world, {T.fgt: 10, T.trn: 10}, dest=XYCoord(15, 10))

    update_fleet(game, fleet)

    assert get_coord(game, fleet) == XYCoord(11, 10)
    assert get_fleet_status(game, fleet) == FleetStatus.FInTrans


def test_a_jump_fleet_covers_its_full_movement_rate(game, world):
    stock(game, world, {T.jmp: 100}, {T.tri: 500})
    fleet = launch(game, world, {T.jmp: 100}, dest=XYCoord(20, 10))

    update_fleet(game, fleet)

    assert get_coord(game, fleet).x == 10 + FltMovementRate[FleetTypes.JumpFleet]


def test_moving_burns_one_years_fuel_regardless_of_distance(game, world):
    stock(game, world, {T.jmp: 100}, {T.tri: 500})
    fleet = launch(game, world, {T.jmp: 100}, dest=XYCoord(20, 10))
    before = get_fleet_fuel(game, fleet)
    burn = fuel_consumption(get_ships(game, fleet), get_cargo(game, fleet))

    update_fleet(game, fleet)

    assert get_fleet_fuel(game, fleet) == pytest.approx(before - burn, abs=1)


def test_a_fleet_already_at_its_destination_burns_nothing(game, world):
    stock(game, world, {T.jmp: 100}, {T.tri: 500})
    fleet = launch(game, world, {T.jmp: 100})
    before = get_fleet_fuel(game, fleet)

    update_fleet(game, fleet)

    assert get_fleet_fuel(game, fleet) == before


def test_arriving_sets_the_fleet_ready(game, world):
    stock(game, world, {T.jmp: 100}, {T.tri: 500})
    fleet = launch(game, world, {T.jmp: 100}, dest=XYCoord(13, 10))

    update_fleet(game, fleet)

    assert get_coord(game, fleet) == XYCoord(13, 10)
    assert get_fleet_status(game, fleet) == FleetStatus.FReady


def test_a_dense_nebula_stops_a_fleet_short_of_it(game, world):
    stock(game, world, {T.jmp: 100}, {T.tri: 500})
    fleet = launch(game, world, {T.jmp: 100}, dest=XYCoord(20, 10))
    put_nebula(game, XYCoord(14, 10), NebulaTypes.DenseNebula)

    update_fleet(game, fleet)

    assert get_coord(game, fleet) == XYCoord(13, 10)
    assert NewsTypes.FltBlocked in [n.Headline for n in game.News[Empire.Empire1]]


def test_a_minefield_stops_a_jump_fleet_in_the_mined_sector(game, world):
    set_rand_seed(11)
    stock(game, world, {T.jmp: 2000}, {T.tri: 500})
    fleet = launch(game, world, {T.jmp: 2000}, dest=XYCoord(20, 10))
    put_mine(game, XYCoord(13, 10), Empire.Empire2)

    update_fleet(game, fleet)

    assert get_coord(game, fleet) == XYCoord(13, 10)
    assert get_ships(game, fleet)[T.jmp] < 2000
    assert NewsTypes.Mines in [n.Headline for n in game.News[Empire.Empire2]]
    assert Empire.Empire1 in game.Galaxy.sector(XYCoord(13, 10)).MineScout


def test_a_warp_fleet_ignores_minefields(game, world):
    stock(game, world, {T.fgt: 10, T.trn: 10}, {T.tri: 500})
    fleet = launch(game, world, {T.fgt: 10, T.trn: 10}, dest=XYCoord(15, 10))
    put_mine(game, XYCoord(11, 10), Empire.Empire2)

    update_fleet(game, fleet)

    assert get_ships(game, fleet)[T.fgt] == 10


def test_a_hostile_disrupter_stops_a_jump_fleet(game, world):
    stock(game, world, {T.jmp: 100}, {T.tri: 500})
    fleet = launch(game, world, {T.jmp: 100}, dest=XYCoord(20, 10))
    gate = make_disrupter(game, 1, XYCoord(15, 10), Empire.Empire2)
    set_warp_link_freq(game, Empire.Empire1, gate, 7)

    update_fleet(game, fleet)

    assert get_coord(game, fleet) == XYCoord(12, 10)
    assert NewsTypes.Disrupt in [n.Headline for n in game.News[Empire.Empire1]]


def test_a_friendly_disrupter_carries_a_warp_fleet_at_jump_speed(game, world):
    """A Standard fleet normally makes one sector a year. Inside its owner's
    disrupter field it keeps stepping while it stays in range: one ordinary
    step to 11, then on to 16, the first sector out of the field."""
    stock(game, world, {T.fgt: 10, T.trn: 10}, {T.tri: 500})
    fleet = launch(game, world, {T.fgt: 10, T.trn: 10}, dest=XYCoord(20, 10))
    make_disrupter(game, 1, XYCoord(13, 10), Empire.Empire1)

    update_fleet(game, fleet)

    assert get_coord(game, fleet) == XYCoord(16, 10)


# --- Gates and fortresses ----------------------------------------------------


def test_a_gate_teleports_a_fleet_straight_to_its_destination(game, world):
    stock(game, world, {T.fgt: 10, T.trn: 10}, {T.tri: 500})
    fleet = launch(game, world, {T.fgt: 10, T.trn: 10}, dest=XYCoord(20, 20))
    create_stargate(
        game, IDNumber(ObjectTypes.Gate, 1), Empire.Empire1, T.gte, XYCoord(10, 10)
    )

    update_fleet(game, fleet)

    assert get_coord(game, fleet) == XYCoord(20, 20)
    assert get_fleet_status(game, fleet) == FleetStatus.FReady


def test_a_gate_cannot_deliver_into_a_dense_nebula(game, world):
    stock(game, world, {T.fgt: 10, T.trn: 10}, {T.tri: 500})
    fleet = launch(game, world, {T.fgt: 10, T.trn: 10}, dest=XYCoord(20, 20))
    create_stargate(
        game, IDNumber(ObjectTypes.Gate, 1), Empire.Empire1, T.gte, XYCoord(10, 10)
    )
    put_nebula(game, XYCoord(20, 20), NebulaTypes.DenseNebula)

    update_fleet(game, fleet)

    assert get_coord(game, fleet) == XYCoord(10, 10)
    assert NewsTypes.NebGate in [n.Headline for n in game.News[Empire.Empire1]]


def test_a_fortress_teleports_a_fleet_going_five_sectors_or_less(game, world):
    stock(game, world, {T.fgt: 10, T.trn: 10}, {T.tri: 500})
    fleet = launch(game, world, {T.fgt: 10, T.trn: 10}, dest=XYCoord(15, 10))
    create_starbase(
        game, IDNumber(ObjectTypes.Base, 1), Empire.Empire1, XYCoord(10, 10), T.frt
    )

    update_fleet(game, fleet)

    assert get_coord(game, fleet) == XYCoord(15, 10)


def test_a_fortress_gives_a_four_sector_boost_on_a_longer_trip(game, world):
    """The catapult loop runs five times but keeps the position from the pass
    before last, so it advances four sectors, not five. Then the fleet takes
    its own move on top: 10 -> 14 -> 15."""
    stock(game, world, {T.fgt: 10, T.trn: 10}, {T.tri: 500})
    fleet = launch(game, world, {T.fgt: 10, T.trn: 10}, dest=XYCoord(20, 10))
    create_starbase(
        game, IDNumber(ObjectTypes.Base, 1), Empire.Empire1, XYCoord(10, 10), T.frt
    )

    update_fleet(game, fleet)

    assert get_coord(game, fleet) == XYCoord(15, 10)


# --- Order execution ---------------------------------------------------------


def orders(game, fleet, *commands):
    code = []
    for command in commands:
        add_orders(code, command)
    set_fleet_code(game, fleet, code)
    set_fleet_next_statement(game, fleet, 1)


def test_a_dest_order_ends_the_fleets_year(game, world):
    stock(game, world, {T.jmp: 100}, {T.tri: 500})
    fleet = launch(game, world, {T.jmp: 100})
    orders(
        game,
        fleet,
        CommandRecord(Typ=CommandTypes.DestCOM, Loc=Location(XYCoord(15, 15), IDNumber())),
        CommandRecord(Typ=CommandTypes.DestCOM, Loc=Location(XYCoord(1, 1), IDNumber())),
    )

    execute_fleet_orders(game, Empire.Empire1, fleet)

    assert get_fleet_destination(game, fleet) == XYCoord(15, 15)
    from recreon.orders import fleet_next_statement

    assert fleet_next_statement(game, fleet) == 2


def test_a_wait_order_ends_the_fleets_year(game, world):
    stock(game, world, {T.trn: 50}, {T.met: 100})
    fleet = launch(game, world, {T.trn: 20})
    orders(
        game,
        fleet,
        CommandRecord(Typ=CommandTypes.WaitCOM),
        CommandRecord(Typ=CommandTypes.TransCOM, Res=T.met, Trns=10),
    )

    execute_fleet_orders(game, Empire.Empire1, fleet)

    assert get_cargo(game, fleet)[T.met] == 0


def test_orders_run_on_through_transfers(game, world):
    stock(game, world, {T.trn: 50}, {T.met: 100, T.sup: 100})
    fleet = launch(game, world, {T.trn: 40})
    orders(
        game,
        fleet,
        CommandRecord(Typ=CommandTypes.TransCOM, Res=T.met, Trns=9),
        CommandRecord(Typ=CommandTypes.TransCOM, Res=T.sup, Trns=8),
        CommandRecord(Typ=CommandTypes.WaitCOM),
    )

    execute_fleet_orders(game, Empire.Empire1, fleet)

    assert get_cargo(game, fleet)[T.met] == 9
    assert get_cargo(game, fleet)[T.sup] == 8


def test_running_off_the_end_of_the_list_clears_the_orders(game, world):
    stock(game, world, {T.trn: 50}, {T.met: 100})
    fleet = launch(game, world, {T.trn: 20})
    orders(game, fleet, CommandRecord(Typ=CommandTypes.TransCOM, Res=T.met, Trns=5))

    execute_fleet_orders(game, Empire.Empire1, fleet)

    from recreon.orders import fleet_next_statement, get_fleet_code

    assert fleet_next_statement(game, fleet) == 0
    assert get_fleet_code(game, fleet) == []


def test_repeat_jumps_back_to_the_first_order_exactly_once(game, world):
    """Without the one-shot guard a list of nothing but REPE would spin
    forever; with it the fleet gets one extra pass and stops."""
    stock(game, world, {T.trn: 50}, {T.met: 1000})
    fleet = launch(game, world, {T.trn: 40})
    orders(
        game,
        fleet,
        CommandRecord(Typ=CommandTypes.TransCOM, Res=T.met, Trns=7),
        CommandRecord(Typ=CommandTypes.RepeatCOM),
    )

    execute_fleet_orders(game, Empire.Empire1, fleet)

    # Once on the way down, once after the repeat.
    assert get_cargo(game, fleet)[T.met] == 14


def test_a_fleet_that_aborts_mid_orders_stops_cleanly(game, world):
    """Dropping every ship empties the fleet, which aborts and destroys it
    part-way through the list."""
    stock(game, world, {T.trn: 50}, {T.met: 100})
    fleet = launch(game, world, {T.trn: 20})
    orders(
        game,
        fleet,
        CommandRecord(Typ=CommandTypes.TransCOM, Res=T.trn, Trns=-20),
        CommandRecord(Typ=CommandTypes.TransCOM, Res=T.met, Trns=10),
    )

    execute_fleet_orders(game, Empire.Empire1, fleet)

    assert fleet.Index not in game.GlobalSets.SetOfActiveFleets


def test_arriving_runs_the_next_order_the_same_year(game, world):
    stock(game, world, {T.jmp: 100}, {T.tri: 500})
    fleet = launch(game, world, {T.jmp: 100}, dest=XYCoord(13, 10))
    orders(
        game,
        fleet,
        CommandRecord(Typ=CommandTypes.DestCOM, Loc=Location(XYCoord(5, 5), IDNumber())),
    )

    update_fleet(game, fleet)

    assert get_coord(game, fleet) == XYCoord(13, 10)
    assert get_fleet_destination(game, fleet) == XYCoord(5, 5)


def test_a_dest_order_naming_an_object_resolves_to_where_it_is_now(game, world):
    stock(game, world, {T.jmp: 100}, {T.tri: 500})
    fleet = launch(game, world, {T.jmp: 100})
    target = place_world(game, 2, XYCoord(17, 4), emp=Empire.Empire1)
    orders(
        game,
        fleet,
        CommandRecord(Typ=CommandTypes.DestCOM, Loc=Location(limbo(), target)),
    )

    execute_fleet_orders(game, Empire.Empire1, fleet)

    assert get_fleet_destination(game, fleet) == XYCoord(17, 4)


# --- Turn scheduling ---------------------------------------------------------


def test_warp_fleets_move_for_the_incoming_player(game, world):
    stock(game, world, {T.fgt: 10, T.trn: 10}, {T.tri: 500})
    fleet = launch(game, world, {T.fgt: 10, T.trn: 10}, dest=XYCoord(15, 10))

    update_all_fleets(game, Empire.Empire2, Empire.Empire1)
    assert get_coord(game, fleet) == XYCoord(11, 10)

    # ...and not for the outgoing one.
    update_all_fleets(game, Empire.Empire1, Empire.Empire2)
    assert get_coord(game, fleet) == XYCoord(11, 10)


def test_jump_fleets_move_for_the_outgoing_player(game, world):
    stock(game, world, {T.jmp: 100}, {T.tri: 500})
    fleet = launch(game, world, {T.jmp: 100}, dest=XYCoord(20, 10))

    update_all_fleets(game, Empire.Empire2, Empire.Empire1)
    assert get_coord(game, fleet) == XYCoord(10, 10)

    update_all_fleets(game, Empire.Empire1, Empire.Empire2)
    assert get_coord(game, fleet).x > 10


def test_a_jump_fleet_sitting_on_a_gate_waits_for_the_incoming_player(game, world):
    """Gate traffic is resolved for the arriving player so they see it land at
    the start of their turn, whatever kind of fleet it is."""
    stock(game, world, {T.jmp: 100}, {T.tri: 500})
    fleet = launch(game, world, {T.jmp: 100}, dest=XYCoord(20, 20))
    create_stargate(
        game, IDNumber(ObjectTypes.Gate, 1), Empire.Empire1, T.gte, XYCoord(10, 10)
    )

    update_all_fleets(game, Empire.Empire1, Empire.Empire2)
    assert get_coord(game, fleet) == XYCoord(10, 10)

    update_all_fleets(game, Empire.Empire2, Empire.Empire1)
    assert get_coord(game, fleet) == XYCoord(20, 20)
