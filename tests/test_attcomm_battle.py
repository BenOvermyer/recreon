"""The interactive attack, ported from ATTCOMM.PAS.

`tests/test_attcomm.py` covers target selection and the auto-attack. This file
covers the half a player steers: splitting the fleet into groups
(``GetGroups``), the round-by-round loop (``Engage``) and the aftermath
(``CleanUp``).
"""

import pytest
from conftest import blank_game, place_world

from recreon.attack import MAX_NO_OF_GROUPS, AttackResultTypes, GroupStatus
from recreon.attcomm import (
    ATSymb,
    BattleSession,
    GroupSplitter,
    PosN,
    TypN,
    attack_command,
    raze_command,
)
from recreon.fleet import get_next_fleet, move_fleet
from recreon.galaxy import XYCoord
from recreon.intrface import create_stargate, next_stargate_slot
from recreon.primintr import get_ships, put_cargo, put_ships
from recreon.types import (
    ATTACK_TYPES,
    Empire,
    IDNumber,
    ObjectTypes,
    ShellPos,
    TechLevel,
    TechnologyTypes,
    cargo_array,
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


def a_fleet(game, emp=PLAYER, xy=HERE, cargo=None, **ships):
    flt = get_next_fleet(game, emp)
    move_fleet(game, flt, xy)
    game.Universe.Fleet[flt.Index].ScoutedBy.add(PLAYER)
    stock = ship_array()
    for kind, count in ships.items():
        stock[T[kind]] = count
    put_ships(game, flt, stock)
    if cargo:
        hold = cargo_array()
        for kind, count in cargo.items():
            hold[T[kind]] = count
        put_cargo(game, flt, hold)
    return flt


def fight_to_a_finish(
    session: BattleSession, target: TechnologyTypes = T.fgt, limit: int = 200
) -> None:
    """Play a whole battle the way a player would: aim, close, keep firing.

    Neither the aiming nor the closing is optional. ``Engage`` has no
    counterpart to ATTNPE's ``AllAdvance`` or its target prioritisation, so a
    fleet that is left alone sits in deep space with no orders and trades no
    fire at all -- see the two tests below.
    """
    for _ in range(limit):
        session.set_targets(dict.fromkeys(session.target_options(), target))
        session.set_moves(
            {
                option.group: GroupStatus.GAdvc
                for option in session.move_options()
                if option.can_advance
            }
        )
        session.engage()
        if session.end_battle:
            return
    raise AssertionError("battle did not end")


# --- The display tables ------------------------------------------------------


def test_the_display_tables_cover_every_attack_type():
    assert set(ATSymb) == set(ATTACK_TYPES)
    assert set(TypN) == set(ATTACK_TYPES)
    assert set(PosN) == set(ShellPos)


def test_a_landed_group_of_soldiers_reads_as_GAT():
    """`TypN[men]` is 'GAT', not 'legions': by the time a group *is* men it has
    landed, and what the player is looking at is a ground assault."""
    assert TypN[T.men].strip() == "GAT"
    assert ATSymb[T.men] == "M"


# --- Splitting the fleet into groups (GetGroups) -----------------------------


def test_the_splitter_starts_with_the_whole_manifest_in_the_pool(game):
    s = GroupSplitter(game, a_fleet(game, fgt=100, ssp=20))

    assert s.sh[T.fgt] == 100
    assert s.sh[T.ssp] == 20
    assert all(s.gp[i].Num == 0 for i in range(1, MAX_NO_OF_GROUPS + 1))


def test_loading_moves_ships_out_of_the_pool_and_advances_the_cursor(game):
    s = GroupSplitter(game, a_fleet(game, fgt=100))

    s.add_to_group(40)

    assert s.gp[1].Num == 40
    assert s.gp[1].Typ is T.fgt
    assert s.sh[T.fgt] == 60
    assert s.cg == 2  # the cursor fell to the next slot


def test_a_negative_count_takes_ships_back(game):
    s = GroupSplitter(game, a_fleet(game, fgt=100))
    s.add_to_group(40)
    s.select(1)

    s.add_to_group(-15)

    assert s.gp[1].Num == 25
    assert s.sh[T.fgt] == 75


def test_loading_is_clamped_to_what_is_there(game):
    s = GroupSplitter(game, a_fleet(game, fgt=10))

    s.add_to_group(500)

    assert s.gp[1].Num == 10
    assert s.sh[T.fgt] == 0


def test_return_with_no_number_takes_every_ship_of_the_slots_type(game):
    s = GroupSplitter(game, a_fleet(game, fgt=100))

    s.add_to_group(None)

    assert s.gp[1].Num == 100


def test_changing_a_slots_type_empties_it_back_into_the_pool(game):
    s = GroupSplitter(game, a_fleet(game, fgt=100, ssp=20))
    s.add_to_group(60)
    s.select(1)

    while s.cur_typ is not T.ssp:
        s.change_type(forward=True)
    s.add_to_group(5)

    assert s.sh[T.fgt] == 100  # the fighters came back
    assert s.gp[1].Typ is T.ssp
    assert s.gp[1].Num == 5


def test_the_type_cursor_wraps_both_ways(game):
    s = GroupSplitter(game, a_fleet(game, fgt=1))

    s.change_type(forward=False)
    assert s.cur_typ is T.trn
    s.change_type(forward=True)
    assert s.cur_typ is T.fgt


def test_selecting_a_slot_adopts_its_type(game):
    s = GroupSplitter(game, a_fleet(game, fgt=100, ssp=20))
    while s.cur_typ is not T.ssp:
        s.change_type(forward=True)
    s.add_to_group(20)  # slot 1 becomes starships, cursor moves to 2

    s.select(1)

    assert s.cur_typ is T.ssp


def test_loading_troops_fills_the_carrying_capacity(game):
    s = GroupSplitter(game, a_fleet(game, trn=10, cargo={"men": 1000}))
    while s.cur_typ is not T.trn:
        s.change_type(forward=True)
    s.add_to_group(10)
    s.select(1)

    s.load_transports(ninja=False)

    # One transport carries CargoSpace[men] = 5 legions.
    assert s.gp[1].GAT == 50
    assert s.gp[1].GATTyp is T.men
    assert s.cr[T.men] == 950


def test_troops_cannot_ride_on_fighters(game):
    """`TrnAdj` is 0 for every hull that is not a transport, and nothing checks
    the type first -- so the original lets you try, and nothing happens."""
    s = GroupSplitter(game, a_fleet(game, fgt=100, cargo={"men": 1000}))
    s.add_to_group(100)
    s.select(1)

    s.load_transports(ninja=False)

    assert s.gp[1].GAT == 0
    assert s.cr[T.men] == 1000


def test_swapping_the_troop_type_returns_the_old_load_first(game):
    s = GroupSplitter(game, a_fleet(game, trn=10, cargo={"men": 1000, "nnj": 1000}))
    while s.cur_typ is not T.trn:
        s.change_type(forward=True)
    s.add_to_group(10)
    s.select(1)
    s.load_transports(ninja=False)

    s.load_transports(ninja=True)

    assert s.cr[T.men] == 1000
    assert s.gp[1].GATTyp is T.nnj
    assert s.gp[1].GAT == 50


def test_adding_ships_to_a_loaded_group_spills_the_troops(game):
    """The second `IF GAT>0` in `LoadShips` runs unconditionally, so any change
    to the ship count unloads every soldier aboard. Faithful, not a slip."""
    s = GroupSplitter(game, a_fleet(game, trn=20, cargo={"men": 1000}))
    while s.cur_typ is not T.trn:
        s.change_type(forward=True)
    s.add_to_group(10)
    s.select(1)
    s.load_transports(ninja=False)
    assert s.gp[1].GAT == 50

    s.select(1)
    s.add_to_group(5)

    assert s.gp[1].GAT == 0
    assert s.cr[T.men] == 1000


def test_finish_puts_warships_first_and_transports_last(game):
    """The invariant the whole of ATTNPE leans on: "the transports" is always a
    suffix of the array, never an interleaving."""
    s = GroupSplitter(game, a_fleet(game, fgt=100, ssp=20, trn=10))

    while s.cur_typ is not T.trn:
        s.change_type(forward=True)
    s.add_to_group(10)  # slot 1: transports
    s.select(2)
    s.cur_typ = T.fgt
    s.add_to_group(100)  # slot 2: fighters
    s.select(3)
    s.cur_typ = T.ssp
    s.add_to_group(20)  # slot 3: starships

    count, gp = s.finish()

    assert count == 3
    assert [gp[i].Typ for i in (1, 2, 3)] == [T.fgt, T.ssp, T.trn]


def test_finish_loads_idle_transports_and_prefers_men_over_ninjas(game):
    """The opposite of `DefaultDistribution`, which prefers ninjas because they
    are worth five men each. Both are the original; nothing reconciles them."""
    s = GroupSplitter(game, a_fleet(game, trn=10, cargo={"men": 1000, "nnj": 1000}))
    while s.cur_typ is not T.trn:
        s.change_type(forward=True)
    s.add_to_group(10)

    count, gp = s.finish()

    assert count == 1
    assert gp[1].GATTyp is T.men
    assert gp[1].GAT == 50


def test_finish_leaves_a_hand_loaded_group_alone(game):
    s = GroupSplitter(game, a_fleet(game, trn=10, cargo={"men": 1000, "nnj": 1000}))
    while s.cur_typ is not T.trn:
        s.change_type(forward=True)
    s.add_to_group(10)
    s.select(1)
    s.load_transports(ninja=True)

    _, gp = s.finish()

    assert gp[1].GATTyp is T.nnj


def test_empty_slots_are_dropped(game):
    s = GroupSplitter(game, a_fleet(game, fgt=100))
    s.select(4)
    s.add_to_group(100)

    count, gp = s.finish()

    assert count == 1
    assert gp[1].Num == 100


def test_ships_left_in_the_pool_do_not_fight(game):
    s = GroupSplitter(game, a_fleet(game, fgt=100))
    s.add_to_group(30)

    count, gp = s.finish()

    assert count == 1
    assert gp[1].Num == 30


# --- Opening a session -------------------------------------------------------


def test_a_session_starts_undecided(game):
    theirs = a_fleet(game, emp=THEIRS, fgt=50)
    mine = a_fleet(game, fgt=500)

    s = attack_command(game, PLAYER, mine, theirs)

    assert s is not None
    assert s.result is AttackResultTypes.NoART
    assert not s.end_battle
    assert s.no_of_groups == 1


def test_a_fleet_with_nothing_aboard_cannot_attack(game):
    theirs = a_fleet(game, emp=THEIRS, fgt=50)

    assert attack_command(game, PLAYER, a_fleet(game), theirs) is None


def test_a_custom_configuration_is_used_when_given(game):
    theirs = a_fleet(game, emp=THEIRS, fgt=50)
    mine = a_fleet(game, fgt=100, ssp=20)
    s = GroupSplitter(game, mine)
    s.add_to_group(40)

    session = attack_command(game, PLAYER, mine, theirs, groups=s.finish())

    assert session.no_of_groups == 1
    assert session.gp[1].Num == 40


def test_a_gate_is_not_a_battle(game):
    gate = IDNumber(ObjectTypes.Gate, next_stargate_slot(game))
    create_stargate(game, gate, THEIRS, T.gte, HERE)

    assert attack_command(game, PLAYER, a_fleet(game, fgt=100), gate) is None


# --- Fighting ----------------------------------------------------------------


def test_a_battle_where_nobody_closes_never_starts(game):
    """`Engage` has no auto-advance. ATTNPE gets `AllAdvance` when no group can
    find a target; the interactive loop has nothing of the kind, so a fleet
    parked in deep space trades no fire at all, round after round. Closing is
    the player's job, and it is the decision the whole screen exists for.
    """
    theirs = a_fleet(game, emp=THEIRS, fgt=50)
    s = attack_command(game, PLAYER, a_fleet(game, fgt=500), theirs)

    for _ in range(20):
        s.engage()

    assert not s.end_battle
    assert s.gp[1].Pos is ShellPos.DpSpc
    assert sum(s.casualties.values()) == 0
    assert sum(s.killed.values()) == 0


def test_a_group_with_no_target_fires_nothing(game):
    """Groups start on `NoRes` -- the `(-)` in the roster -- and there is no
    automatic prioritisation here the way `_targetting_fleet` does it for the
    AI. An unaimed group closes into range and then stands there.
    """
    theirs = a_fleet(game, emp=THEIRS, fgt=50)
    s = attack_command(game, PLAYER, a_fleet(game, fgt=5000), theirs)

    for _ in range(10):
        s.set_moves(
            {
                option.group: GroupStatus.GAdvc
                for option in s.move_options()
                if option.can_advance
            }
        )
        s.engage()

    assert s.gp[1].Pos is ShellPos.Orbit  # closed as far as a fleet fight allows
    assert sum(s.killed.values()) == 0  # and killed nothing on the way


def test_an_overwhelming_force_wins_by_engaging(game):
    theirs = a_fleet(game, emp=THEIRS, fgt=1)
    mine = a_fleet(game, fgt=5000, ssp=500)

    s = attack_command(game, PLAYER, mine, theirs)
    fight_to_a_finish(s)

    assert s.result is AttackResultTypes.DefConqueredART
    assert "THE ENEMY HAS SURRENDERED" in s.report


def test_a_hopeless_attack_is_wiped_out(game):
    theirs = a_fleet(game, emp=THEIRS, fgt=9000, ssp=900)
    mine = a_fleet(game, fgt=1)

    s = attack_command(game, PLAYER, mine, theirs)
    fight_to_a_finish(s)

    assert s.result is AttackResultTypes.AttDestroyedART
    assert "ALL GROUPS DESTROYED" in s.report


def test_details_are_per_round_but_casualties_accumulate(game):
    """`GroupEngage` clears `Details` every round, so the D screen shows what
    the *last* round cost; `Casualties` is what gets written back at the end."""
    theirs = a_fleet(game, emp=THEIRS, fgt=2000)
    mine = a_fleet(game, fgt=3000)
    s = attack_command(game, PLAYER, mine, theirs)
    s.set_moves({1: GroupStatus.GAdvc})

    s.engage()
    first = sum(s.casualties.values())
    s.engage()

    assert sum(s.casualties.values()) >= first


# --- Moving between shells ---------------------------------------------------


def test_nothing_retreats_out_of_deep_space(game):
    theirs = a_fleet(game, emp=THEIRS, fgt=50)
    s = attack_command(game, PLAYER, a_fleet(game, fgt=500), theirs)

    options = s.move_options()

    assert [o.group for o in options] == [1]
    assert options[0].can_advance
    assert not options[0].can_retreat


def test_against_a_fleet_nothing_goes_below_standard_orbit(game):
    """There is no surface to assault, so `Orbit` is as close as it gets."""
    theirs = a_fleet(game, emp=THEIRS, fgt=50)
    s = attack_command(game, PLAYER, a_fleet(game, fgt=500), theirs)
    s.gp[1].Pos = ShellPos.Orbit

    options = s.move_options()

    assert not options[0].can_advance
    assert options[0].can_retreat


def test_against_a_world_the_same_group_may_close_further(game):
    place_world(game, 2, HERE, emp=THEIRS)
    world = IDNumber(ObjectTypes.Pln, 2)
    s = attack_command(game, PLAYER, a_fleet(game, fgt=500), world)
    s.gp[1].Pos = ShellPos.Orbit

    assert s.move_options()[0].can_advance


def test_only_fighters_and_transports_can_land(game):
    place_world(game, 2, HERE, emp=THEIRS)
    world = IDNumber(ObjectTypes.Pln, 2)
    s = attack_command(game, PLAYER, a_fleet(game, ssp=500), world)
    s.gp[1].Pos = ShellPos.SbOrb

    assert not s.move_options()[0].can_advance

    s.gp[1].Typ = T.fgt
    assert s.move_options()[0].can_advance


def test_once_troops_are_down_only_fighters_lift_off(game):
    place_world(game, 2, HERE, emp=THEIRS)
    world = IDNumber(ObjectTypes.Pln, 2)
    s = attack_command(game, PLAYER, a_fleet(game, fgt=500), world)
    s.gp[1].Pos = ShellPos.Grnd

    assert s.move_options()[0].can_retreat

    s.gp[1].Typ = T.men
    assert s.move_options() == []  # neither advance nor retreat: not offered


def test_a_destroyed_group_is_not_offered_a_move(game):
    theirs = a_fleet(game, emp=THEIRS, fgt=50)
    s = attack_command(game, PLAYER, a_fleet(game, fgt=400, ssp=100), theirs)
    s.gp[1].Sta = GroupStatus.GDst

    assert [o.group for o in s.move_options()] == [2]


def test_standing_fast_costs_nothing(game):
    """`Ok` stays false when every group holds, so `GroupEngage` never runs and
    the enemy gets no free round of fire."""
    theirs = a_fleet(game, emp=THEIRS, fgt=50)
    s = attack_command(game, PLAYER, a_fleet(game, fgt=500), theirs)

    assert s.set_moves({1: GroupStatus.GReady}) is False


def test_an_ordered_advance_moves_a_shell_on_the_next_round(game):
    theirs = a_fleet(game, emp=THEIRS, fgt=50)
    s = attack_command(game, PLAYER, a_fleet(game, fgt=5000), theirs)

    assert s.set_moves({1: GroupStatus.GAdvc}) is True
    s.engage()

    assert s.gp[1].Pos is ShellPos.HiOrb


def test_cancelling_puts_staged_groups_back(game):
    theirs = a_fleet(game, emp=THEIRS, fgt=50)
    s = attack_command(game, PLAYER, a_fleet(game, fgt=500), theirs)
    s.set_moves({1: GroupStatus.GAdvc})

    s.cancel_moves()

    assert s.gp[1].Sta is GroupStatus.GReady


# --- Targeting and retreat ---------------------------------------------------


def test_targets_can_be_set_by_hand(game):
    theirs = a_fleet(game, emp=THEIRS, fgt=50)
    s = attack_command(game, PLAYER, a_fleet(game, fgt=500), theirs)

    s.set_targets({1: T.ssp})

    assert s.gp[1].Trg is T.ssp


def test_a_destroyed_group_cannot_be_retargeted(game):
    theirs = a_fleet(game, emp=THEIRS, fgt=50)
    s = attack_command(game, PLAYER, a_fleet(game, fgt=500), theirs)
    s.gp[1].Sta = GroupStatus.GDst

    assert s.target_options() == []
    s.set_targets({1: T.ssp})
    assert s.gp[1].Trg is not T.ssp


def test_retreating_ends_the_battle_and_costs_one_round(game):
    theirs = a_fleet(game, emp=THEIRS, fgt=50)
    s = attack_command(game, PLAYER, a_fleet(game, fgt=5000), theirs)

    s.retreat()

    assert s.end_battle
    assert s.result is AttackResultTypes.AttRetreatsART
    assert "ALL GROUPS RETREATING" in s.report


def test_a_fleet_leaving_cannot_accept_a_surrender(game):
    """The retreat is declared before the round is fought, which is what
    suppresses the surrender check inside `GroupEngage` -- so a fleet that could
    have won by staying still leaves with a retreat on its record."""
    theirs = a_fleet(game, emp=THEIRS, fgt=1)
    s = attack_command(game, PLAYER, a_fleet(game, fgt=5000, ssp=500), theirs)

    s.retreat()

    assert s.result is AttackResultTypes.AttRetreatsART


def test_a_retreat_can_still_end_in_annihilation(game):
    """`GroupEngage` overwrites the result when the last group dies, so the
    round on the way out can turn a retreat into a massacre."""
    theirs = a_fleet(game, emp=THEIRS, fgt=9000, ssp=900)
    s = attack_command(game, PLAYER, a_fleet(game, fgt=1), theirs)
    s.set_moves({1: GroupStatus.GAdvc})
    s.engage()  # close to contact, where breaking off is actually costly

    s.retreat()

    assert s.result is AttackResultTypes.AttDestroyedART


# --- What the screens show ---------------------------------------------------


def test_the_group_roster_reads_like_the_original(game):
    theirs = a_fleet(game, emp=THEIRS, fgt=50)
    s = attack_command(game, PLAYER, a_fleet(game, fgt=500), theirs)

    assert s.group_lines() == [" 1:  500 fgt sq O:DSp (-)"]


def test_a_cloaked_hunter_killer_says_so(game):
    """The only place the cloak is visible to the player."""
    theirs = a_fleet(game, emp=THEIRS, fgt=50)
    s = attack_command(game, PLAYER, a_fleet(game, hkr=500), theirs)

    assert s.group_lines()[0].endswith("Clk")


def test_a_transport_group_shows_its_troops(game):
    place_world(game, 2, HERE, emp=THEIRS)
    world = IDNumber(ObjectTypes.Pln, 2)
    mine = a_fleet(game, trn=10, cargo={"men": 1000})

    s = attack_command(game, PLAYER, mine, world)

    assert s.group_lines()[0].endswith("50")


def test_a_destroyed_group_reads_Dst(game):
    theirs = a_fleet(game, emp=THEIRS, fgt=50)
    s = attack_command(game, PLAYER, a_fleet(game, fgt=500), theirs)
    s.gp[1].Sta = GroupStatus.GDst

    assert s.group_lines()[0].endswith("Dst")


def test_the_details_screen_lists_only_weapons_that_scored(game):
    theirs = a_fleet(game, emp=THEIRS, fgt=2000)
    s = attack_command(game, PLAYER, a_fleet(game, fgt=3000), theirs)
    s.set_moves({1: GroupStatus.GAdvc})
    s.engage()
    s.engage()

    for name, per_group in s.detail_rows():
        assert name
        assert len(per_group) == s.no_of_groups


# --- CleanUp -----------------------------------------------------------------


def test_a_conquest_is_announced_and_settled(game):
    theirs = a_fleet(game, emp=THEIRS, fgt=1)
    mine = a_fleet(game, fgt=5000, ssp=500)
    s = attack_command(game, PLAYER, mine, theirs)
    fight_to_a_finish(s)
    assert s.result is AttackResultTypes.DefConqueredART

    report = s.conclude()
    assert report.lines
    s.settle(report, capture=True)

    assert theirs.Index not in game.GlobalSets.SetOfActiveFleets


def test_conclude_writes_the_losses_back_before_it_narrates(game):
    theirs = a_fleet(game, emp=THEIRS, fgt=2000)
    mine = a_fleet(game, fgt=5000, ssp=500)
    s = attack_command(game, PLAYER, mine, theirs)
    fight_to_a_finish(s)

    s.conclude()

    assert get_ships(game, mine)[T.fgt] == 5000 - s.casualties[T.fgt]


def test_a_beaten_fleet_with_ships_left_asks_to_be_spared(game):
    theirs = a_fleet(game, emp=THEIRS, fgt=200)
    mine = a_fleet(game, fgt=5000, ssp=500)
    s = attack_command(game, PLAYER, mine, theirs)
    fight_to_a_finish(s)

    report = s.conclude()

    if s.result is AttackResultTypes.DefConqueredART and get_ships(game, theirs)[
        T.fgt
    ] > 0:
        assert report.capture_question is not None
        assert report.capture_question.lines
        assert report.capture_question.ships


def test_a_conquered_world_is_never_asked_about(game):
    world = place_world(game, 2, HERE, emp=THEIRS)
    s = attack_command(game, PLAYER, a_fleet(game, fgt=5000), world)
    s.result = AttackResultTypes.DefConqueredART

    assert s.conclude().capture_question is None


def test_losing_the_whole_force_draws_a_lecture(game):
    theirs = a_fleet(game, emp=THEIRS, fgt=9000, ssp=900)
    mine = a_fleet(game, fgt=1)
    s = attack_command(game, PLAYER, mine, theirs)
    fight_to_a_finish(s)
    assert s.result is AttackResultTypes.AttDestroyedART

    report = s.conclude()
    assert any("destroy" in line or "lost" in line for line in report.lines)

    s.settle(report)
    assert mine.Index not in game.GlobalSets.SetOfActiveFleets


def test_a_retreat_is_reported_briefly(game):
    theirs = a_fleet(game, emp=THEIRS, fgt=50)
    s = attack_command(game, PLAYER, a_fleet(game, fgt=5000), theirs)
    s.retreat()

    report = s.conclude()

    assert len(report.lines) == 1
    assert "retreated" in report.lines[0]


def test_obsolete_ships_over_an_independent_world_are_reported(game):
    """An independent can be sitting on hulls its own tech could never have
    built -- left over from whoever held the world before it went its own way."""
    world = place_world(game, 2, HERE, emp=Empire.Indep, tech=TechLevel.PreWrpLvl)
    stock = ship_array()
    stock[T.ssp] = 40
    put_ships(game, world, stock)

    s = attack_command(game, PLAYER, a_fleet(game, fgt=5000, ssp=500), world)
    s.result = AttackResultTypes.DefConqueredART
    report = s.conclude()

    assert report.old_ships == {T.ssp: 40}


def test_an_owned_world_reports_no_obsolete_ships(game):
    world = place_world(game, 2, HERE, emp=THEIRS, tech=TechLevel.PreWrpLvl)
    stock = ship_array()
    stock[T.ssp] = 40
    put_ships(game, world, stock)

    s = attack_command(game, PLAYER, a_fleet(game, fgt=5000), world)
    s.result = AttackResultTypes.DefConqueredART

    assert s.conclude().old_ships == {}


def test_razing_a_gate_really_destroys_it(game):
    """Unlike `AutoAttackCommand`, which only says it did."""
    gate = IDNumber(ObjectTypes.Gate, next_stargate_slot(game))
    create_stargate(game, gate, THEIRS, T.gte, HERE)
    mine = a_fleet(game, fgt=100)

    lines = raze_command(game, PLAYER, mine, gate)

    assert "has been destroyed" in lines[0]
    assert gate.Index not in game.GlobalSets.SetOfActiveGates
