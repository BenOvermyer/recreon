"""Checks on the calculations ported from MISC.PAS, INT.PAS and REAL1.PAS."""

import pytest

from recreon.datacnst import MPower
from recreon.galaxy import XYCoord
from recreon.misc import (
    add_things,
    distance,
    fleet_cargo_space,
    fuel_capacity,
    fuel_consumption,
    hi_lo,
    military_power,
    move_things,
    no_ships,
    ship_yard_ind,
    sub_things,
    tech_range,
    thg_lmt,
    total_prod,
    yes_no,
)
from recreon.types import (
    MAX_RESOURCES,
    IndusTypes,
    TechLevel,
    TechnologyTypes,
    cargo_array,
    defns_array,
    indus_array,
    ship_array,
)
from recreon.utils.int_utils import int_lmt, isqrt, rnd, rnd_var, sgn
from recreon.utils.pascal import pascal_round, trunc

T = TechnologyTypes


def test_pascal_round_breaks_ties_away_from_zero():
    # Python's round() is banker's rounding and would give 0, 2 and -2 here.
    assert pascal_round(0.5) == 1
    assert pascal_round(2.5) == 3
    assert pascal_round(-2.5) == -3
    assert pascal_round(1.4) == 1
    assert pascal_round(1.6) == 2


def test_trunc_rounds_toward_zero():
    assert trunc(1.9) == 1
    assert trunc(-1.9) == -1


def test_distance_is_chebyshev():
    # Diagonal movement costs the same as orthogonal, so a knight's-move
    # offset is 2, not 3 (Manhattan) and not 2.24 (Euclidean).
    assert distance(XYCoord(1, 1), XYCoord(2, 3)) == 2
    assert distance(XYCoord(5, 5), XYCoord(5, 5)) == 0
    assert distance(XYCoord(10, 2), XYCoord(4, 4)) == 6
    # Symmetric.
    assert distance(XYCoord(3, 9), XYCoord(1, 1)) == distance(
        XYCoord(1, 1), XYCoord(3, 9)
    )


def test_thg_lmt_clamps_and_truncates():
    assert thg_lmt(-5) == 0
    assert thg_lmt(99999) == MAX_RESOURCES
    assert thg_lmt(12.9) == 12


def test_fuel_capacity_starts_at_one():
    # The original seeds the accumulator with 1 rather than 0; an empty fleet
    # therefore has capacity 1, not 0. Preserved deliberately.
    ships = ship_array()
    assert fuel_capacity(ships) == 1.0

    ships[T.ssp] = 2
    assert fuel_capacity(ships) == pytest.approx(1 + 2 * 2854 / 100)


def test_fuel_consumption_counts_ships_and_cargo():
    ships, cargo = ship_array(), cargo_array()
    ships[T.trn] = 1
    cargo[T.tri] = 100
    assert fuel_consumption(ships, cargo) == pytest.approx(1 + 994 / 1000 + 100 * 20 / 1000)


def test_fleet_cargo_space_goes_negative_when_overloaded():
    ships, cargo = ship_array(), cargo_array()
    ships[T.trn] = 10
    assert fleet_cargo_space(ships, cargo) == 10

    # Each transport holds 3 megatons of metal; 60 needs 20 transports.
    cargo[T.met] = 60
    assert fleet_cargo_space(ships, cargo) == -10


def test_jump_transports_carry_a_fifth_of_a_transport():
    ships, cargo = ship_array(), cargo_array()
    ships[T.jtn] = 10
    assert fleet_cargo_space(ships, cargo) == 2


def test_no_ships():
    ships = ship_array()
    assert no_ships(ships)
    ships[T.fgt] = 1
    assert not no_ships(ships)


def test_total_prod_is_clamped_to_the_indus_index():
    # Pop is forced to at least 1, so a dead world still has a defined TIP.
    assert total_prod(0, TechLevel.PreTchLvl) == total_prod(1, TechLevel.PreTchLvl)
    # Higher tech and population both raise output, and it never exceeds 999.
    assert total_prod(500, TechLevel.GteTchLvl) > total_prod(500, TechLevel.PreTchLvl)
    assert total_prod(9999, TechLevel.GteTchLvl) <= 999


def test_ship_yard_ind_breaks_ties_toward_the_lowest_ordinal():
    indus = indus_array()
    assert ship_yard_ind(indus) == IndusTypes.SYGInd

    indus[IndusTypes.SYSInd] = 50
    assert ship_yard_ind(indus) == IndusTypes.SYSInd

    # A tie must not displace the incumbent -- the original compares with >.
    indus[IndusTypes.SYTInd] = 50
    assert ship_yard_ind(indus) == IndusTypes.SYSInd


def test_add_and_sub_things_clamp():
    ships, cargo = ship_array(), cargo_array()
    other_ships, other_cargo = ship_array(), cargo_array()
    other_ships[T.fgt] = 100
    other_cargo[T.met] = 50

    add_things(ships, cargo, other_ships, other_cargo)
    assert ships[T.fgt] == 100
    assert cargo[T.met] == 50

    # Subtracting past zero floors rather than going negative.
    other_ships[T.fgt] = 500
    sub_things(ships, cargo, other_ships, other_cargo)
    assert ships[T.fgt] == 0
    assert cargo[T.met] == 0


def test_move_things_moves_what_it_can():
    assert move_things(30, 100, 0) == (70, 30)
    # Short source: everything moves and the source empties.
    assert move_things(300, 100, 5) == (0, 105)
    # Exactly equal takes the same branch as short, by the original's `>`.
    assert move_things(100, 100, 0) == (0, 100)


def test_military_power_weights_by_mpower():
    ships, defns = ship_array(), defns_array()
    ships[T.ssp] = 3
    defns[T.LAM] = 2
    expected = 3 * MPower[T.ssp] + 2 * MPower[T.LAM]
    assert military_power(ships, defns) == expected

    # Transports contribute nothing.
    ships[T.trn] = 1000
    assert military_power(ships, defns) == expected


def test_hi_lo_and_yes_no_buckets():
    assert hi_lo(0) == "no "
    assert hi_lo(11) == "Lo-"
    assert hi_lo(50) == "Lo+"
    assert hi_lo(100) == "Hi+"
    assert hi_lo(101) == "---"

    assert yes_no(0) == "   no"
    assert yes_no(500) == " yes-"
    assert yes_no(501) == " yes1"
    assert yes_no(1500) == " yes1"
    assert yes_no(1501) == " yes2"
    assert yes_no(9500) == " yes9"
    assert yes_no(9501) == " yes+"


def test_int_helpers():
    assert sgn(-9) == -1
    assert sgn(0) == 0
    assert sgn(9) == 1
    assert int_lmt(1e9) == 32767
    assert int_lmt(-1e9) == -32767
    assert int_lmt(3.9) == 3


def test_isqrt_rounds_to_nearest():
    assert isqrt(0) == 0
    assert isqrt(1) == 1
    assert isqrt(15) == 4  # 3.87 rounds to 4
    assert isqrt(16) == 4
    assert isqrt(100) == 10
    assert isqrt(101) == 10


def test_rnd_returns_min_when_range_is_empty():
    assert rnd(5, 5) == 5
    assert rnd(9, 2) == 9
    assert 1 <= rnd(1, 6) <= 6


def test_rnd_var_stays_within_variation():
    for _ in range(50):
        assert 80 <= rnd_var(100, 20) <= 120


def test_tech_range_reexport():
    # misc.py re-exports it for the ported code that indexes subranges.
    assert tech_range(T.LAM, T.ion) == (T.LAM, T.def_, T.GDM, T.ion)
