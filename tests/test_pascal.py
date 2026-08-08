"""Turbo Pascal builtins whose behaviour Python does not share."""

import pytest

from recreon.utils.int_utils import rnd, rnd_var
from recreon.utils.pascal import (
    RAND_MODULUS,
    RAND_MULTIPLIER,
    pascal_random,
    pascal_random_real,
    pascal_round,
    pascal_val,
    rand_seed,
    randomize,
    set_rand_seed,
    trunc,
)

# --- Rounding and truncation -------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [(0.5, 1), (1.5, 2), (2.5, 3), (-0.5, -1), (-2.5, -3), (2.4, 2), (-2.4, -2)],
)
def test_pascal_round_breaks_ties_away_from_zero(value, expected):
    """Python's round is banker's rounding and gives 0, 2, 2 for the first
    three -- the difference is a silent balance change wherever it leaks in."""
    assert pascal_round(value) == expected


@pytest.mark.parametrize("value,expected", [(2.9, 2), (-2.9, -2), (0.0, 0)])
def test_trunc_goes_toward_zero(value, expected):
    assert trunc(value) == expected


# --- Val ---------------------------------------------------------------------


def test_pascal_val_parses_plain_integers():
    assert pascal_val("42") == 42
    assert pascal_val("-7") == -7
    assert pascal_val("+7") == 7


@pytest.mark.parametrize("text", [" 42", "42 ", "4_2", "42.0", "", "-", "0x10"])
def test_pascal_val_rejects_what_python_would_accept(text):
    """Python's int() takes surrounding whitespace and underscore separators;
    Pascal's Val reports an error at the offending character."""
    with pytest.raises(ValueError):
        pascal_val(text)


# --- The random number generator ---------------------------------------------


def test_seed_sequence_matches_borland():
    """The published Borland Pascal 7 sequence through zero. Getting this
    right is the whole point: it is what makes a scenario seed regenerate the
    galaxy the DOS build produced."""
    set_rand_seed(0)
    seen = []
    for _ in range(3):
        pascal_random_real()
        seen.append(rand_seed())

    assert seen == [1, 134775814, -596792289]


def test_the_sequence_runs_backward_to_the_published_predecessor():
    set_rand_seed(649090867)
    pascal_random_real()
    assert rand_seed() == 0


def test_rand_seed_reads_back_as_a_signed_longint():
    set_rand_seed(-1)
    assert rand_seed() == -1
    set_rand_seed(RAND_MODULUS - 1)
    assert rand_seed() == -1


def test_the_multiplier_is_borlands():
    assert RAND_MULTIPLIER == 0x08088405


def test_random_is_the_top_of_the_product_not_a_modulus():
    """`seed mod range` is the common but wrong description of this generator
    and gives a different sequence; check against the definition directly."""
    set_rand_seed(12345)
    expected = ((12345 * RAND_MULTIPLIER + 1) % RAND_MODULUS * 1000) >> 32

    set_rand_seed(12345)
    assert pascal_random(1000) == expected


def test_random_of_one_is_always_zero():
    """A quirk of the original that ATTACK.PAS depends on -- `Random(1)` can
    never be anything else, since the seed is always below 2**32."""
    set_rand_seed(1)
    assert [pascal_random(1) for _ in range(20)] == [0] * 20


def test_random_of_zero_is_zero():
    set_rand_seed(1)
    assert pascal_random(0) == 0


def test_random_stays_inside_its_range():
    set_rand_seed(99)
    values = [pascal_random(6) for _ in range(500)]
    assert min(values) == 0
    assert max(values) == 5


def test_random_real_stays_in_the_unit_interval():
    set_rand_seed(2024)
    values = [pascal_random_real() for _ in range(500)]
    assert all(0.0 <= v < 1.0 for v in values)


def test_the_same_seed_replays_the_same_sequence():
    set_rand_seed(4021)
    first = [pascal_random(100) for _ in range(50)]
    set_rand_seed(4021)
    assert [pascal_random(100) for _ in range(50)] == first


def test_randomize_moves_off_the_current_seed():
    set_rand_seed(0)
    randomize()
    assert rand_seed() != 0


# --- Rnd, which every draw in the game funnels through -----------------------


def test_rnd_is_inclusive_at_both_ends():
    set_rand_seed(7)
    values = {rnd(3, 5) for _ in range(200)}
    assert values == {3, 4, 5}


def test_rnd_returns_the_minimum_when_the_range_is_empty():
    assert rnd(5, 5) == 5
    assert rnd(5, 2) == 5


def test_rnd_handles_negative_ranges():
    set_rand_seed(11)
    values = [rnd(-25, 25) for _ in range(300)]
    assert min(values) == -25
    assert max(values) == 25


def test_rnd_is_reproducible_from_a_seed():
    set_rand_seed(1234)
    first = [rnd(1, 100) for _ in range(30)]
    set_rand_seed(1234)
    assert [rnd(1, 100) for _ in range(30)] == first


def test_rnd_var_stays_within_the_named_percentage():
    set_rand_seed(31)
    values = [rnd_var(1000, 10) for _ in range(300)]
    assert min(values) >= 900
    assert max(values) <= 1100
