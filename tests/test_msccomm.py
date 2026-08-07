"""Defense settings and self-destruct, ported from MSCCOMM.PAS."""

import pytest
from conftest import blank_game, place_world

from recreon.datacnst import init_defense_record
from recreon.galaxy import XYCoord
from recreon.intrface import create_starbase, create_stargate, next_stargate_slot
from recreon.msccomm import (
    DEFAULT_SHELL,
    GROUND_CAPABLE,
    ONLY_SOME_ON_GROUND,
    TOTAL_MUST_BE_100,
    SelfDestructError,
    can_self_destruct,
    clamp_percent,
    defense_settings_for_editing,
    destructible_objects,
    illegal_amounts,
    normalize_defenses,
    save_defense_settings,
    self_destruct_command,
    self_destruct_warning,
    shell_total,
)
from recreon.primintr import get_defense_settings, get_object, set_population
from recreon.types import (
    SHIP_TYPES,
    Empire,
    IDNumber,
    ObjectTypes,
    ShellPos,
    TechnologyTypes,
    empty_quadrant,
)
from recreon.utils.pascal import set_rand_seed

T = TechnologyTypes
PLAYER = Empire.Empire1


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


@pytest.fixture
def game():
    g = blank_game(size=20, empires=2)
    place_world(g, 1, XYCoord(5, 5), emp=PLAYER)
    g.Universe.EmpireData[PLAYER].Capital = IDNumber(ObjectTypes.Pln, 1)
    return g


@pytest.fixture
def dist():
    return init_defense_record().ShellDefDist


def only(dist, ship, **shells):
    """Set one ship type's row and zero the rest of it."""
    for shell in ShellPos:
        dist[shell][ship] = 0
    for name, value in shells.items():
        dist[ShellPos[name]][ship] = value


# --- The shipped defaults ----------------------------------------------------


def test_the_default_settings_are_already_legal(dist):
    """`InitDefenseRecord` is what a new empire starts with, so if it needed
    normalising every empire would begin with its orders rewritten."""
    assert illegal_amounts(dist) is None
    assert all(shell_total(dist, ship) == 100 for ship in SHIP_TYPES)


# --- Legality ----------------------------------------------------------------


def test_a_row_that_does_not_add_to_a_hundred_is_illegal(dist):
    only(dist, T.fgt, DpSpc=20)
    assert illegal_amounts(dist) == TOTAL_MUST_BE_100


def test_a_starship_on_the_ground_is_illegal(dist):
    only(dist, T.ssp, Grnd=100)
    assert illegal_amounts(dist) == ONLY_SOME_ON_GROUND


@pytest.mark.parametrize("ship", [T.fgt, T.trn, T.jtn])
def test_the_three_landers_may_sit_on_the_ground(dist, ship):
    only(dist, ship, Grnd=100)
    assert illegal_amounts(dist) is None
    assert ship in GROUND_CAPABLE


def test_the_ground_complaint_wins_when_both_rules_break(dist):
    """`ErrorStr` is overwritten rather than collected, and the ground test
    runs second, so it is the one reported."""
    only(dist, T.ssp, Grnd=50)
    assert illegal_amounts(dist) == ONLY_SOME_ON_GROUND


# --- Normalising -------------------------------------------------------------


def test_a_shortfall_goes_to_sub_orbit(dist):
    only(dist, T.fgt, DpSpc=20)
    normalize_defenses(dist)

    assert dist[ShellPos.DpSpc][T.fgt] == 20
    assert dist[DEFAULT_SHELL][T.fgt] == 80
    assert shell_total(dist, T.fgt) == 100


def test_an_empty_row_becomes_all_sub_orbit(dist):
    only(dist, T.fgt)
    normalize_defenses(dist)

    assert dist[DEFAULT_SHELL][T.fgt] == 100


def test_a_surplus_is_scaled_down_and_the_remainder_lands_in_sub_orbit(dist):
    """300 across three shells scales to 33/33/33, and truncation always
    rounds down -- so sub-orbit collects the leftover 1 rather than the split
    being evened out."""
    only(dist, T.hkr, DpSpc=100, HiOrb=100, Orbit=100)
    normalize_defenses(dist)

    assert dist[ShellPos.DpSpc][T.hkr] == 33
    assert dist[ShellPos.HiOrb][T.hkr] == 33
    assert dist[ShellPos.Orbit][T.hkr] == 33
    assert dist[DEFAULT_SHELL][T.hkr] == 1
    assert shell_total(dist, T.hkr) == 100


def test_a_grounded_starship_is_moved_not_discarded(dist):
    """The percentage goes to sub-orbit, so the ships stay in the defence."""
    only(dist, T.ssp, Grnd=100)
    normalize_defenses(dist)

    assert dist[ShellPos.Grnd][T.ssp] == 0
    assert dist[DEFAULT_SHELL][T.ssp] == 100


def test_grounded_ships_are_cleared_before_the_total_is_taken(dist):
    """Order matters: clearing first means the moved percentage counts toward
    the 100, rather than being lost and then made up again."""
    only(dist, T.pen, DpSpc=40, Grnd=60)
    normalize_defenses(dist)

    assert dist[ShellPos.DpSpc][T.pen] == 40
    assert dist[DEFAULT_SHELL][T.pen] == 60
    assert dist[ShellPos.Grnd][T.pen] == 0


def test_normalising_leaves_a_legal_grid_alone(dist):
    before = {shell: dict(dist[shell]) for shell in ShellPos}
    normalize_defenses(dist)

    assert {shell: dict(dist[shell]) for shell in ShellPos} == before


def test_normalising_always_produces_a_legal_grid(dist):
    for ship in SHIP_TYPES:
        only(dist, ship, DpSpc=70, HiOrb=70, Grnd=70)

    normalize_defenses(dist)
    assert illegal_amounts(dist) is None


# --- Typing a percentage -----------------------------------------------------


@pytest.mark.parametrize("value", [0, 1, 50, 100])
def test_a_percentage_in_range_is_kept(value):
    assert clamp_percent(value) == value


@pytest.mark.parametrize("value", [-1, 101, 150, 9999])
def test_a_percentage_out_of_range_becomes_zero_not_the_nearest_bound(value):
    """Surprising, but it is what `ChangePercent` does -- a fat-fingered 150
    empties the shell rather than filling it, and the normaliser then puts the
    missing percentage into sub-orbit."""
    assert clamp_percent(value) == 0


# --- Saving ------------------------------------------------------------------


def test_editing_works_on_a_copy_until_it_is_saved(game):
    editing = defense_settings_for_editing(game, PLAYER)
    editing.ShellDefDist[ShellPos.DpSpc][T.fgt] = 99

    live = get_defense_settings(game, PLAYER)
    assert live.ShellDefDist[ShellPos.DpSpc][T.fgt] != 99

    save_defense_settings(game, PLAYER, editing)
    assert get_defense_settings(game, PLAYER).ShellDefDist[ShellPos.DpSpc][T.fgt] == 99


# --- Self-destruct -----------------------------------------------------------


def make_base(game, xy, owner=PLAYER, styp=T.cmm, index=1):
    obj = IDNumber(ObjectTypes.Base, index)
    create_starbase(game, obj, owner, xy, styp)
    return obj


def make_gate(game, xy, owner=PLAYER):
    obj = IDNumber(ObjectTypes.Gate, next_stargate_slot(game))
    create_stargate(game, obj, owner, T.gte, xy)
    return obj


def test_a_base_and_a_gate_can_be_destroyed(game):
    base = make_base(game, XYCoord(8, 8))
    gate = make_gate(game, XYCoord(9, 9))

    can_self_destruct(game, PLAYER, base)
    can_self_destruct(game, PLAYER, gate)


def test_an_industrial_complex_cannot_be(game):
    """`cmp` is excluded by name: a complex sits on a world rather than
    standing alone, so there is nothing to scuttle independently of it."""
    complex_base = make_base(game, XYCoord(8, 8), styp=T.cmp)

    with pytest.raises(SelfDestructError, match="only bases, and stargates"):
        can_self_destruct(game, PLAYER, complex_base)


def test_a_world_cannot_be_self_destructed(game):
    with pytest.raises(SelfDestructError, match="only bases, and stargates"):
        can_self_destruct(game, PLAYER, IDNumber(ObjectTypes.Pln, 1))


def test_another_empires_base_cannot_be(game):
    theirs = make_base(game, XYCoord(8, 8), owner=Empire.Empire2)

    with pytest.raises(SelfDestructError, match="not a part of"):
        can_self_destruct(game, PLAYER, theirs)


def test_destroying_a_base_empties_its_sector(game):
    base = make_base(game, XYCoord(8, 8))
    assert get_object(game, XYCoord(8, 8)) == base

    message = self_destruct_command(game, PLAYER, base)

    assert "has been destroyed" in message
    assert get_object(game, XYCoord(8, 8)) == empty_quadrant()
    assert base.Index not in game.GlobalSets.SetOfActiveStarbases


def test_the_base_warning_counts_the_dead(game):
    base = make_base(game, XYCoord(8, 8))
    set_population(game, base, 250)

    warning = " ".join(self_destruct_warning(game, PLAYER, base))

    assert "Destruct sequence activated" in warning
    assert "2500 million people" in warning  # Pop * 10
    assert "destroy all ships" in warning


def test_the_gate_warning_only_mourns_the_work(game):
    gate = make_gate(game, XYCoord(9, 9))
    warning = " ".join(self_destruct_warning(game, PLAYER, gate))

    assert "Atomic charges set" in warning
    assert "many years to build" in warning
    assert "people" not in warning


def test_the_list_offers_what_can_be_scuttled(game):
    make_base(game, XYCoord(8, 8), index=1)
    make_base(game, XYCoord(10, 10), styp=T.cmp, index=2)
    make_base(game, XYCoord(11, 11), owner=Empire.Empire2, index=3)
    gate = make_gate(game, XYCoord(9, 9))

    offered = [obj for obj, _ in destructible_objects(game, PLAYER)]

    assert IDNumber(ObjectTypes.Base, 1) in offered
    assert IDNumber(ObjectTypes.Base, 2) not in offered  # industrial complex
    assert IDNumber(ObjectTypes.Base, 3) not in offered  # not ours
    assert gate in offered
