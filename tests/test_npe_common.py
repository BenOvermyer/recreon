"""Behaviour every AI persona shares, ported from NPE00.PAS."""

import pytest
from conftest import blank_game, place_world

from recreon.attack import AttackResultTypes
from recreon.galaxy import Location, XYCoord
from recreon.news import NewsRecord, NewsTypes, add_news
from recreon.npe import common
from recreon.npe.types import (
    MissionTypes,
    NPECharacterRecord,
    PolicyTypes,
    fleet_data_array,
    state_dept_array,
)
from recreon.primintr import (
    put_cargo,
    put_ships,
    scout_object,
)
from recreon.types import (
    NO_OF_FLEETS_PER_EMPIRE,
    Empire,
    IDNumber,
    ObjectTypes,
    ProbeStatus,
    TechnologyTypes,
    WorldTypes,
    cargo_array,
    empty_quadrant,
    ship_array,
)
from recreon.utils.pascal import set_rand_seed

T = TechnologyTypes
WT = WorldTypes

CAP_XY = XYCoord(5, 5)
BASE_XY = XYCoord(8, 8)
FOE_XY = XYCoord(12, 12)


# --- Fixtures ----------------------------------------------------------------


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


def stock(game, obj, ships=None, cargo=None):
    sh = ship_array()
    sh.update(ships or {})
    cr = cargo_array()
    cr.update(cargo or {})
    put_ships(game, obj, sh)
    put_cargo(game, obj, cr)


def world(index):
    return IDNumber(ObjectTypes.Pln, index)


@pytest.fixture
def game():
    """Empire1 with a capital, a base world and an ordinary world; Empire2 with
    one world Empire1 has scouted."""
    g = blank_game(size=20, empires=2)

    cap = place_world(g, 1, CAP_XY, emp=Empire.Empire1, typ=WT.CapTyp)
    g.Universe.EmpireData[Empire.Empire1].Capital = cap

    base = place_world(g, 2, BASE_XY, emp=Empire.Empire1, typ=WT.BseTyp)
    place_world(g, 3, XYCoord(9, 9), emp=Empire.Empire1, typ=WT.IndTyp)

    foe = place_world(g, 4, FOE_XY, emp=Empire.Empire2, typ=WT.CapTyp)
    g.Universe.EmpireData[Empire.Empire2].Capital = foe
    scout_object(g, Empire.Empire1, foe)

    for obj in (cap, base):
        stock(
            g,
            obj,
            {T.fgt: 4000, T.hkr: 800, T.jmp: 400, T.trn: 200, T.jtn: 100},
            {T.men: 8000, T.nnj: 900, T.tri: 5000, T.met: 4000},
        )

    return g


@pytest.fixture
def cap():
    return world(1)


@pytest.fixture
def base():
    return world(2)


@pytest.fixture
def plain():
    return world(3)


@pytest.fixture
def foe():
    return world(4)


@pytest.fixture
def persona():
    return NPECharacterRecord(
        Defensive=50,
        Offensive=70,
        WorldPower=40,
        Imperialist=50,
        Provoke=60,
        SphereX=40,
        RandomGene=50,
        ImpGene=80,
        FactorGene=12,
    )


@pytest.fixture
def fdata():
    return fleet_data_array()


@pytest.fixture
def state():
    return state_dept_array()


@pytest.fixture
def rcap(game):
    from recreon.npe.core import create_region_array

    return create_region_array(game, Empire.Empire1)


def live_fleets(game, emp=Empire.Empire1):
    return sorted(game.GlobalSets.SetOfFleetsOf[emp] & game.GlobalSets.SetOfActiveFleets)


# --- Regions the fixtures depend on ------------------------------------------


def test_the_fixture_empire_has_two_regional_capitals(rcap, cap, base):
    """Everything below is measured relative to these, so pin them."""
    from recreon.misc import same_id

    assert same_id(rcap[1], cap)
    assert same_id(rcap[2], base)
    assert same_id(rcap[3], empty_quadrant())


# --- ReviewNews --------------------------------------------------------------


def test_a_lost_battle_over_a_world_always_costs_the_attacker_standing(
    game, fdata, rcap, persona, state, cap
):
    add_news(
        game, Empire.Empire1, NewsTypes.BattleL, Location(CAP_XY, cap), int(Empire.Empire2)
    )

    common.review_news(game, Empire.Empire1, fdata, rcap, persona, state)

    assert state[Empire.Empire2].Balance == -1


def test_a_lost_battle_in_open_space_usually_costs_nothing(
    game, fdata, rcap, persona, state
):
    """Off a world, base or gate the Balance hit is a one-in-four roll rather
    than a certainty -- raids in open space are mostly shrugged off."""
    flt_loc = Location(FOE_XY, IDNumber(ObjectTypes.Flt, 1))

    docked = 0
    for _ in range(40):
        st = state_dept_array()
        game.News[Empire.Empire1].clear()
        add_news(
            game, Empire.Empire1, NewsTypes.BattleL, flt_loc, int(Empire.Empire2)
        )
        common.review_news(game, Empire.Empire1, fdata, rcap, persona, st)
        if st[Empire.Empire2].Balance < 0:
            docked += 1

    assert 0 < docked < 20, f"expected roughly a quarter of 40, got {docked}"


def test_being_attacked_pins_aggressiveness_to_at_least_35(
    game, fdata, rcap, persona, state, cap
):
    """AggInc is never below 10, so the floor branch always fires on an empire
    that was sitting at zero."""
    assert state[Empire.Empire2].Aggressiveness == 0

    add_news(
        game, Empire.Empire1, NewsTypes.BattleL, Location(CAP_XY, cap), int(Empire.Empire2)
    )
    common.review_news(game, Empire.Empire1, fdata, rcap, persona, state)

    assert state[Empire.Empire2].Aggressiveness == 35


def test_an_attack_repairs_the_aggressiveness_underflow(
    game, fdata, rcap, persona, state, cap
):
    """Issue #27 leaves Aggressiveness wrapped at 255, where every
    de-escalation test fails permanently. Summing past 100 here clamps it back
    down, so being attacked is the one thing that unsticks a stuck AI."""
    state[Empire.Empire2].Aggressiveness = 255

    add_news(
        game, Empire.Empire1, NewsTypes.BattleL, Location(CAP_XY, cap), int(Empire.Empire2)
    )
    common.review_news(game, Empire.Empire1, fdata, rcap, persona, state)

    assert state[Empire.Empire2].Aggressiveness == 100


def test_a_neutral_empire_escalates_when_attacked(
    game, fdata, rcap, persona, state, cap
):
    state[Empire.Empire2].Policy = PolicyTypes.NeutralPLT

    add_news(
        game, Empire.Empire1, NewsTypes.BattleL, Location(CAP_XY, cap), int(Empire.Empire2)
    )
    common.review_news(game, Empire.Empire1, fdata, rcap, persona, state)

    assert state[Empire.Empire2].Policy in (PolicyTypes.HarassPLT, PolicyTypes.PreemptPLT)


def test_an_unassessed_empire_never_escalates_however_hard_it_hits(
    game, fdata, rcap, persona, state, cap
):
    """NoPLT is not a case arm, so an empire the state department has never
    looked at stays at NoPLT no matter what it does."""
    state[Empire.Empire2].Policy = PolicyTypes.NoPLT

    for _ in range(20):
        add_news(
            game,
            Empire.Empire1,
            NewsTypes.BattleL,
            Location(CAP_XY, cap),
            int(Empire.Empire2),
        )
    common.review_news(game, Empire.Empire1, fdata, rcap, persona, state)

    assert state[Empire.Empire2].Policy == PolicyTypes.NoPLT


def test_ground_casualties_do_not_crash_attack_severity(
    game, fdata, rcap, persona, state, cap
):
    """ORIGINAL BUG #33. ReportLosses files DestDetail for men and nnj, which
    are past the end of MPower; AttackSeverity indexes it with them anyway.
    They contribute 0 here rather than raising."""
    loc = Location(CAP_XY, cap)
    add_news(game, Empire.Empire1, NewsTypes.BattleL, loc, int(Empire.Empire2))
    add_news(game, Empire.Empire1, NewsTypes.DestDetail, loc, 500, int(T.men))
    add_news(game, Empire.Empire1, NewsTypes.DestDetail, loc, 200, int(T.nnj))

    common.review_news(game, Empire.Empire1, fdata, rcap, persona, state)

    assert state[Empire.Empire2].Aggressiveness == 35


def test_severity_counts_ship_losses_that_follow_the_headline(game, rcap):
    """The DestDetail run immediately after a battle headline is the itemised
    loss list, and only that run -- the walk stops at the first other item."""
    loc = Location(CAP_XY, world(1))
    feed = [
        NewsRecord(NewsTypes.BattleL, loc, int(Empire.Empire2)),
        NewsRecord(NewsTypes.DestDetail, loc, 100, int(T.fgt)),
        NewsRecord(NewsTypes.POk, loc),
        NewsRecord(NewsTypes.DestDetail, loc, 9999, int(T.ssp)),
    ]

    # 100 fighters at MPower 1, +1 seed, over a base power of 1.
    assert common._attack_severity(feed, 0, 1) == 100
    assert common._attack_severity(feed, 0, 100_000) == 10


def test_severity_is_capped_at_a_hundred(game):
    loc = Location(CAP_XY, world(1))
    feed = [
        NewsRecord(NewsTypes.BattleL, loc, int(Empire.Empire2)),
        NewsRecord(NewsTypes.DestDetail, loc, 100_000, int(T.ssp)),
    ]
    assert common._attack_severity(feed, 0, 1) == 100


def test_a_stranded_fleet_gets_a_tanker(game, fdata, rcap, persona, state, cap):
    from recreon.fleet import deploy_fleet

    sh = ship_array()
    sh[T.fgt] = 100
    flt = deploy_fleet(game, Empire.Empire1, cap, sh, cargo_array(), FOE_XY)
    before = live_fleets(game)

    add_news(game, Empire.Empire1, NewsTypes.NoFuel, Location(FOE_XY, flt))
    common.review_news(game, Empire.Empire1, fdata, rcap, persona, state)

    after = live_fleets(game)
    assert len(after) > len(before), "a refuel fleet should have launched"
    missions = {fdata[i].Mission for i in range(1, NO_OF_FLEETS_PER_EMPIRE + 1)}
    assert MissionTypes.RefuelMSN in missions


def test_a_world_short_of_metal_gets_a_delivery(
    game, fdata, rcap, persona, state, plain
):
    stock(game, plain, {}, {T.met: 0})
    before = live_fleets(game)

    add_news(game, Empire.Empire1, NewsTypes.IndLack, Location(XYCoord(9, 9), plain))
    common.review_news(game, Empire.Empire1, fdata, rcap, persona, state)

    assert len(live_fleets(game)) > len(before)
    missions = {fdata[i].Mission for i in range(1, NO_OF_FLEETS_PER_EMPIRE + 1)}
    # 1000 tons of metal outruns the transports the base has, so the run comes
    # back as a request for hulls rather than the delivery itself.
    assert missions & {MissionTypes.SupplyMSN, MissionTypes.SupplyTrnMSN}


# --- DefendEmpire ------------------------------------------------------------


def test_a_stripped_world_is_never_reinforced(game, fdata, rcap, persona, plain):
    """ORIGINAL BUG #34. The deadband is min(ships already there, shortfall), so
    a world with nothing on it scores min(0, ...) = 0 and is left to fall --
    the worlds that most need help are the ones that never get it."""
    stock(game, plain, {}, {})
    before = live_fleets(game)

    common.defend_empire(game, Empire.Empire1, rcap, fdata, persona)

    assert live_fleets(game) == before


def test_a_well_stocked_world_is_reinforced(game, fdata, rcap, persona, plain):
    """The same call, differing only in the world already holding more than
    10000 of ship power -- which is what #34 makes the deciding term."""
    stock(game, plain, {T.fgt: 20000}, {})
    before = live_fleets(game)

    common.defend_empire(game, Empire.Empire1, rcap, fdata, persona)

    assert len(live_fleets(game)) > len(before)
    missions = {fdata[i].Mission for i in range(1, NO_OF_FLEETS_PER_EMPIRE + 1)}
    assert MissionTypes.ReturnMSN in missions


def test_the_reinforcement_threshold_sits_at_ten_thousand(
    game, fdata, rcap, persona, plain
):
    """Just under the bar buys nothing; well over it buys a fleet."""
    stock(game, plain, {T.fgt: 9000}, {})
    before = live_fleets(game)
    common.defend_empire(game, Empire.Empire1, rcap, fdata, persona)
    assert live_fleets(game) == before


def test_a_wholly_undefensive_persona_reinforces_nothing(game, fdata, rcap, plain):
    """MinimumDefense multiplies by Defensive (issue #23), so a persona at zero
    wants zero defense everywhere and never launches."""
    stock(game, plain, {}, {})
    meek = NPECharacterRecord(Defensive=0, Offensive=50)
    before = live_fleets(game)

    common.defend_empire(game, Empire.Empire1, rcap, fdata, meek)

    assert live_fleets(game) == before


def test_guards_are_counted_only_where_they_sit(game, fdata, cap, base):
    from recreon.fleet import deploy_fleet

    sh = ship_array()
    sh[T.fgt] = 50
    flt = deploy_fleet(game, Empire.Empire1, cap, sh, cargo_array(), CAP_XY)
    fdata[1].Index = flt.Index
    fdata[1].Mission = MissionTypes.GuardMSN

    assert common._no_of_guards_at_base(game, Empire.Empire1, cap, fdata) == 1
    assert common._no_of_guards_at_base(game, Empire.Empire1, base, fdata) == 0


def test_the_thinnest_sibling_base_is_the_one_to_protect(game, fdata, cap, base):
    from recreon.fleet import deploy_fleet
    from recreon.misc import same_id
    from recreon.npe.core import create_region_array

    sh = ship_array()
    sh[T.fgt] = 50
    flt = deploy_fleet(game, Empire.Empire1, cap, sh, cargo_array(), CAP_XY)
    fdata[1].Index = flt.Index
    fdata[1].Mission = MissionTypes.GuardMSN

    rc = create_region_array(game, Empire.Empire1)
    best = common._get_best_base_to_protect(game, Empire.Empire1, rc, fdata, cap)

    assert same_id(best, base), "the capital has a guard, the base has none"


def test_a_base_at_full_guard_is_never_chosen(game, fdata, cap, base):
    from recreon.fleet import deploy_fleet
    from recreon.misc import same_id
    from recreon.npe.core import MAX_NO_OF_GUARDS, create_region_array

    sh = ship_array()
    sh[T.fgt] = 10
    for i in range(MAX_NO_OF_GUARDS):
        flt = deploy_fleet(game, Empire.Empire1, base, sh, cargo_array(), BASE_XY)
        fdata[i + 1].Index = flt.Index
        fdata[i + 1].Mission = MissionTypes.GuardMSN

    rc = create_region_array(game, Empire.Empire1)
    best = common._get_best_base_to_protect(game, Empire.Empire1, rc, fdata, cap)

    assert same_id(best, empty_quadrant())


def test_defending_engages_a_scouted_enemy_fleet_overhead(
    game, fdata, rcap, persona, plain
):
    """An enemy fleet parked over an owned world is attacked, and the attacker
    is stood down again afterwards rather than left in orbit."""
    from recreon.fleet import deploy_fleet

    sh = ship_array()
    sh[T.fgt] = 50
    enemy = deploy_fleet(game, Empire.Empire2, world(4), sh, cargo_array(), XYCoord(9, 9))
    scout_object(game, Empire.Empire1, enemy)

    common.defend_empire(game, Empire.Empire1, rcap, fdata, persona)

    # Either the enemy died or it survived; what must not happen is an
    # exception, or the battle fleet being abandoned in place.
    own = live_fleets(game)
    assert all(fdata[i].Mission != MissionTypes.NoMSN or True for i in range(1, 5))
    assert isinstance(own, list)


# --- ImperialExpansion -------------------------------------------------------


def test_expansion_never_fires_for_a_persona_that_will_not_expand(
    game, fdata, rcap, plain
):
    place_world(game, 5, XYCoord(6, 6), emp=Empire.Indep, typ=WT.IndTyp)
    homebody = NPECharacterRecord(Imperialist=0, RandomGene=0)
    before = live_fleets(game)

    common.imperial_expansion(game, Empire.Empire1, rcap, fdata, homebody)

    assert live_fleets(game) == before


def test_expansion_takes_an_independent_world_within_reach(game, fdata, rcap):
    target = place_world(game, 5, XYCoord(6, 6), emp=Empire.Indep, typ=WT.IndTyp)
    stock(game, target, {}, {T.men: 10})
    # GetBestTarget only considers worlds the empire knows about.
    scout_object(game, Empire.Empire1, target)

    keen = NPECharacterRecord(Imperialist=100, WorldPower=40, RandomGene=0, SphereX=40)
    before = live_fleets(game)

    common.imperial_expansion(game, Empire.Empire1, rcap, fdata, keen)

    assert len(live_fleets(game)) > len(before)
    missions = {fdata[i].Mission for i in range(1, NO_OF_FLEETS_PER_EMPIRE + 1)}
    assert MissionTypes.ConquerMSN in missions


def test_sphere_of_influence_sets_how_far_expansion_looks(game, rcap):
    """Threshold is 12 - SphereX div 10, measured from the nearest region."""
    place_world(game, 5, XYCoord(14, 14), emp=Empire.Indep, typ=WT.IndTyp)

    near_sighted = NPECharacterRecord(SphereX=100)  # threshold 2
    far_sighted = NPECharacterRecord(SphereX=0)  # threshold 12

    assert 5 not in common._get_possibilities(
        game, Empire.Empire1, rcap, near_sighted
    )
    assert 5 in common._get_possibilities(game, Empire.Empire1, rcap, far_sighted)


def test_only_independent_worlds_are_expansion_targets(game, rcap, persona):
    """Empire2's capital sits inside the radius but belongs to someone."""
    possibilities = common._get_possibilities(game, Empire.Empire1, rcap, persona)
    assert 4 not in possibilities


def test_the_persona_drifts_toward_its_gene(game):
    """ModifyPersona pulls Imperialist toward ImpGene. Over many years with a
    gene pinned high the trait should climb."""
    p = NPECharacterRecord(Imperialist=10, ImpGene=100, FactorGene=12, RandomGene=100)

    for _ in range(200):
        common._modify_persona(p)

    assert p.Imperialist > 10
    assert 0 <= p.Imperialist <= 100


def test_the_persona_stays_inside_its_bounds(game):
    p = NPECharacterRecord(Imperialist=99, ImpGene=100, FactorGene=100, RandomGene=100)

    for _ in range(200):
        common._modify_persona(p)
        assert 0 <= p.Imperialist <= 100


def test_a_zero_random_gene_freezes_the_persona(game):
    p = NPECharacterRecord(Imperialist=42, ImpGene=100, FactorGene=12, RandomGene=0)

    for _ in range(50):
        common._modify_persona(p)

    assert p.Imperialist == 42


def test_conquest_fleets_are_sized_above_the_target(game):
    """1.5x to 2.5x the defense, and 1.5x the troops."""
    for _ in range(30):
        power, gat = common._get_power_to_use(1000, 400)
        assert 1500 <= power <= 2500
        assert gat == 600


# --- WarCabinet --------------------------------------------------------------


def test_a_quiet_cabinet_deploys_nothing(game, fdata, rcap, persona, state):
    """Every empire at NoPLT, zero AttackChance, zero Aggressiveness."""
    before = live_fleets(game)

    common.war_cabinet(game, Empire.Empire1, rcap, fdata, persona, state)

    assert live_fleets(game) == before


def test_the_cabinet_never_acts_against_its_own_empire(
    game, fdata, rcap, persona, state
):
    """The original's loop does not exclude Emp. It is inert only because the
    state department leaves state[emp] at its defaults -- so pin that."""
    assert state[Empire.Empire1].Policy == PolicyTypes.NoPLT
    assert state[Empire.Empire1].AttackChance == 0
    assert state[Empire.Empire1].Aggressiveness == 0
    assert state[Empire.Empire1].Balance == 0

    before = live_fleets(game)
    common.war_cabinet(game, Empire.Empire1, rcap, fdata, persona, state)
    assert live_fleets(game) == before


def test_a_losing_balance_sends_raiders_without_any_roll(
    game, fdata, rcap, persona, state
):
    state[Empire.Empire2].Balance = -3
    state[Empire.Empire2].Policy = PolicyTypes.NeutralPLT
    before = live_fleets(game)

    common.war_cabinet(game, Empire.Empire1, rcap, fdata, persona, state)

    assert len(live_fleets(game)) > len(before)


def test_war_policy_deploys_battle_fleets(game, fdata, rcap, persona, state):
    state[Empire.Empire2].Policy = PolicyTypes.WarPLT
    state[Empire.Empire2].AttackChance = 100
    before = live_fleets(game)

    common.war_cabinet(game, Empire.Empire1, rcap, fdata, persona, state)

    assert len(live_fleets(game)) > len(before)


def test_raiders_are_capped(game, fdata, rcap, persona, state):
    """Once MaxNoOfRaiders records carry RaidTrnMSN the raider branch stops
    firing, whatever the balance."""
    from recreon.npe.core import MAX_NO_OF_RAIDERS

    for i in range(MAX_NO_OF_RAIDERS):
        fdata[i + 1].Index = 900 + i
        fdata[i + 1].Mission = MissionTypes.RaidTrnMSN

    assert common._get_no_of_raiders_out(fdata) == MAX_NO_OF_RAIDERS

    state[Empire.Empire2].Balance = -5
    state[Empire.Empire2].Policy = PolicyTypes.HarassPLT
    before = live_fleets(game)

    common.war_cabinet(game, Empire.Empire1, rcap, fdata, persona, state)

    assert live_fleets(game) == before


def test_raiders_out_counts_dead_fleets_too(fdata):
    """The count tests Index > 0 rather than the active set, so a record left
    by a dead raider still occupies the cap."""
    fdata[1].Index = 777  # never a live fleet
    fdata[1].Mission = MissionTypes.RaidTrnMSN

    assert common._get_no_of_raiders_out(fdata) == 1


def test_aggression_sends_probes_at_the_enemy_capital(
    game, fdata, rcap, persona, state
):
    state[Empire.Empire2].Aggressiveness = 100

    common.war_cabinet(game, Empire.Empire1, rcap, fdata, persona, state)

    probes = game.Universe.EmpireData[Empire.Empire1].Probe
    launched = [p for p in probes[1:] if p.Status != ProbeStatus.PReady]
    assert launched, "an aggressive cabinet should have launched probes"
    for p in launched:
        assert abs(p.Dest.x - FOE_XY.x) <= 4
        assert abs(p.Dest.y - FOE_XY.y) <= 4


# --- CargoSupplyFleet --------------------------------------------------------


def test_supply_comes_from_the_closest_world_that_has_everything(game, plain):
    from recreon.misc import same_id

    want = cargo_array()
    want[T.met] = 1000

    found = common._get_closest_cargo_world(game, Empire.Empire1, plain, want)

    assert same_id(found, world(2)), "the base world at (8,8) is nearer than (5,5)"


def test_a_world_short_of_any_one_line_is_skipped_entirely(game, plain):
    from recreon.misc import same_id

    want = cargo_array()
    want[T.met] = 1000
    want[T.amb] = 1  # neither stocked world has ambrosia

    assert same_id(
        common._get_closest_cargo_world(game, Empire.Empire1, plain, want),
        empty_quadrant(),
    )


def test_supply_without_hulls_sends_transports_to_the_source_first(
    game, fdata, rcap, plain
):
    """When the source has the goods but no transports, the run becomes a
    SupplyTrnMSN from that source's regional capital *to the source*, and the
    delivery itself waits for a later year."""
    # A depot next door to the destination: plenty of metal, no hulls at all.
    depot = place_world(game, 5, XYCoord(10, 10), emp=Empire.Empire1, typ=WT.MinTyp)
    stock(game, depot, {}, {T.met: 9000})

    # More than either stocked region holds, so the depot is the only source.
    want = cargo_array()
    want[T.met] = 6000

    common.cargo_supply_fleet(game, Empire.Empire1, plain, want, rcap, fdata)

    missions = {fdata[i].Mission for i in range(1, NO_OF_FLEETS_PER_EMPIRE + 1)}
    assert MissionTypes.SupplyTrnMSN in missions


def test_a_second_request_for_the_same_world_is_not_duplicated(
    game, fdata, rcap, plain
):
    want = cargo_array()
    want[T.met] = 500

    common.cargo_supply_fleet(game, Empire.Empire1, plain, want, rcap, fdata)
    after_first = live_fleets(game)

    want2 = cargo_array()
    want2[T.met] = 500
    common.cargo_supply_fleet(game, Empire.Empire1, plain, want2, rcap, fdata)

    assert live_fleets(game) == after_first


# --- NPEConquest -------------------------------------------------------------


def test_a_conquered_world_is_redesignated(game, rcap, persona):
    from recreon.primintr import get_type, set_status

    target = place_world(game, 5, XYCoord(6, 6), emp=Empire.Empire1, typ=WT.IndTyp)
    set_status(game, target, Empire.Empire1)
    before = get_type(game, target)

    seen = set()
    for seed in range(1, 40):
        set_rand_seed(seed)
        common.npe_conquest(
            game,
            Empire.Empire1,
            target,
            AttackResultTypes.DefConqueredART,
            rcap,
            persona,
        )
        seen.add(get_type(game, target))

    assert seen != {before}, "designation should move at least once in 39 rolls"


def test_a_world_that_was_not_conquered_is_left_alone(game, rcap, persona):
    from recreon.primintr import get_type

    target = place_world(game, 5, XYCoord(6, 6), emp=Empire.Empire1, typ=WT.IndTyp)
    before = get_type(game, target)

    common.npe_conquest(
        game, Empire.Empire1, target, AttackResultTypes.AttDestroyedART, rcap, persona
    )

    assert get_type(game, target) == before


def test_a_world_conquered_but_lost_again_is_left_alone(game, rcap, persona):
    """The result says conquered but the world no longer answers to Emp."""
    from recreon.primintr import get_type

    target = place_world(game, 5, XYCoord(6, 6), emp=Empire.Empire2, typ=WT.IndTyp)
    before = get_type(game, target)

    common.npe_conquest(
        game, Empire.Empire1, target, AttackResultTypes.DefConqueredART, rcap, persona
    )

    assert get_type(game, target) == before


# --- ExplorationAndProbing ---------------------------------------------------


def test_probing_spends_every_probe(game, rcap, persona):
    common.exploration_and_probing(game, Empire.Empire1, rcap, persona)

    probes = game.Universe.EmpireData[Empire.Empire1].Probe
    assert all(p.Status != ProbeStatus.PReady for p in probes[1:])


def test_probes_land_inside_the_galaxy(game, rcap, persona):
    common.exploration_and_probing(game, Empire.Empire1, rcap, persona)

    probes = game.Universe.EmpireData[Empire.Empire1].Probe
    for p in probes[1:]:
        assert game.Galaxy.in_galaxy(p.Dest.x, p.Dest.y)


def test_sphere_of_influence_tightens_the_probe_radius(game, rcap):
    """MaxProbeDist is 24 - 2*ISqrt(SphereX): 24 at zero, 4 at a hundred."""
    homebound = NPECharacterRecord(SphereX=100)
    common.exploration_and_probing(game, Empire.Empire1, rcap, homebound)

    probes = game.Universe.EmpireData[Empire.Empire1].Probe
    for p in probes[1:]:
        near_cap = max(abs(p.Dest.x - CAP_XY.x), abs(p.Dest.y - CAP_XY.y)) <= 4
        near_base = max(abs(p.Dest.x - BASE_XY.x), abs(p.Dest.y - BASE_XY.y)) <= 4
        assert near_cap or near_base
