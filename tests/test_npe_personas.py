"""The four AI personas and the dispatcher, ported from NPE01-NPE04 and NPE.PAS."""

import pytest
from conftest import blank_game, place_world

from recreon.galaxy import XYCoord
from recreon.intrface import get_nearest_worlds, update_probes
from recreon.npe import berserker, dispatch, guardian, kingdom, pirate
from recreon.npe.types import (
    BaseMissionTypes,
    BerserkerDataRecord,
    GuardianDataRecord,
    Kingdom1DataRecord,
    MissionTypes,
    NPEmpireTypes,
    PirateDataRecord,
    PolicyTypes,
)
from recreon.primintr import (
    get_defns,
    get_status,
    put_cargo,
    put_defns,
    put_ships,
    scout_object,
    set_status,
)
from recreon.types import (
    NO_OF_FLEETS_PER_EMPIRE,
    Empire,
    IDNumber,
    ObjectTypes,
    ProbeStatus,
    TechLevel,
    TechnologyTypes,
    WorldTypes,
    cargo_array,
    defns_array,
    ship_array,
)
from recreon.utils.pascal import set_rand_seed

T = TechnologyTypes
WT = WorldTypes
BM = BaseMissionTypes

CAP_XY = XYCoord(10, 10)


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


def stock(game, obj, ships=None, cargo=None, defns=None):
    sh = ship_array()
    sh.update(ships or {})
    cr = cargo_array()
    cr.update(cargo or {})
    df = defns_array()
    df.update(defns or {})
    put_ships(game, obj, sh)
    put_cargo(game, obj, cr)
    put_defns(game, obj, df)


def world(index):
    return IDNumber(ObjectTypes.Base, index) if False else IDNumber(ObjectTypes.Pln, index)


def place_base(game, index, xy, styp, emp=Empire.Empire1):
    """A starbase of a given type, seated at ``xy``."""
    from recreon.intrface import create_starbase

    base = IDNumber(ObjectTypes.Base, index)
    create_starbase(game, base, emp, xy, styp)
    return base


@pytest.fixture
def game():
    g = blank_game(size=20, empires=2)
    cap = place_world(g, 1, CAP_XY, emp=Empire.Empire1, typ=WT.CapTyp)
    g.Universe.EmpireData[Empire.Empire1].Capital = cap
    stock(
        g,
        cap,
        {T.fgt: 6000, T.hkr: 3000, T.jmp: 5000, T.jtn: 6000, T.trn: 300},
        {T.men: 9000, T.nnj: 900, T.tri: 9000, T.met: 5000, T.che: 5000},
    )
    return g


@pytest.fixture
def cap():
    return world(1)


# --- set_status keeps the per-empire sets honest ------------------------------


def test_taking_a_world_moves_it_between_the_owner_sets(game):
    """The port used to write only Planet.Emp, leaving every empire reading as
    landless from the moment a scenario loaded. See issue #11."""
    w = place_world(game, 2, XYCoord(5, 5), emp=Empire.Indep)

    assert 2 in game.GlobalSets.SetOfPlanetsOf[Empire.Indep]
    assert 2 not in game.GlobalSets.SetOfPlanetsOf[Empire.Empire1]

    set_status(game, w, Empire.Empire1)

    assert 2 not in game.GlobalSets.SetOfPlanetsOf[Empire.Indep]
    assert 2 in game.GlobalSets.SetOfPlanetsOf[Empire.Empire1]
    assert get_status(game, w) == Empire.Empire1


def test_a_scenario_load_leaves_every_owner_set_correct(scenario_path):
    from recreon.newgame import load_scenario
    from recreon.primintr import get_status as status

    g = load_scenario(scenario_path, {Empire.Empire1: "A"})

    for i in range(1, g.NoOfPlanets + 1):
        owner = status(g, IDNumber(ObjectTypes.Pln, i))
        assert i in g.GlobalSets.SetOfPlanetsOf[owner], f"world {i} missing from {owner}"


# --- get_nearest_worlds -------------------------------------------------------


def test_nearest_worlds_come_back_in_distance_order(game):
    place_world(game, 2, XYCoord(10, 13), emp=Empire.Empire1)  # 3 away
    place_world(game, 3, XYCoord(10, 11), emp=Empire.Empire1)  # 1 away
    place_world(game, 4, XYCoord(10, 16), emp=Empire.Empire1)  # 6 away

    near = get_nearest_worlds(
        game, CAP_XY, 4, game.GlobalSets.SetOfPlanetsOf[Empire.Empire1]
    )

    assert [n.Index for n in near] == [1, 3, 2, 4]


def test_nearest_worlds_stops_at_n(game):
    for i, y in enumerate((11, 12, 13), start=2):
        place_world(game, i, XYCoord(10, y), emp=Empire.Empire1)

    near = get_nearest_worlds(
        game, CAP_XY, 2, game.GlobalSets.SetOfPlanetsOf[Empire.Empire1]
    )
    assert len(near) == 2


def test_nearest_worlds_of_nothing_is_empty(game):
    assert get_nearest_worlds(game, CAP_XY, 1, set()) == []


# --- Probes -------------------------------------------------------------------


def test_probes_come_back_ready_the_next_turn(game, cap):
    from recreon.primintr import get_probe, launch_probe

    num = get_probe(game, Empire.Empire1)
    launch_probe(game, Empire.Empire1, num, XYCoord(12, 12))
    assert game.Universe.EmpireData[Empire.Empire1].Probe[num].Status != ProbeStatus.PReady

    update_probes(game, Empire.Empire1)

    assert game.Universe.EmpireData[Empire.Empire1].Probe[num].Status == ProbeStatus.PReady


def test_a_probe_reveals_what_it_flies_over(game):
    from recreon.primintr import get_probe, launch_probe, scouted

    target = place_world(game, 2, XYCoord(15, 15), emp=Empire.Empire2)
    assert not scouted(game, Empire.Empire1, target)

    num = get_probe(game, Empire.Empire1)
    launch_probe(game, Empire.Empire1, num, XYCoord(15, 15))
    update_probes(game, Empire.Empire1)

    assert scouted(game, Empire.Empire1, target)


# --- Guardian -----------------------------------------------------------------


def test_a_guardian_fires_lams_at_a_fleet_in_range(game, cap):
    from recreon.fleet import deploy_fleet

    stock(game, cap, {T.fgt: 100}, {}, {T.LAM: 5000})
    sh = ship_array()
    sh[T.fgt] = 200
    enemy = deploy_fleet(game, Empire.Empire2, cap, sh, cargo_array(), XYCoord(12, 12))
    scout_object(game, Empire.Empire1, enemy)

    guardian.implement_guardian_npe(game, Empire.Empire1, GuardianDataRecord())

    assert get_defns(game, cap)[T.LAM] < 5000, "the guardian should have fired"


def test_a_guardian_ignores_fleets_out_of_range(game, cap):
    from recreon.fleet import deploy_fleet

    stock(game, cap, {T.fgt: 100}, {}, {T.LAM: 5000})
    far = place_world(game, 2, XYCoord(19, 19), emp=Empire.Empire2)
    sh = ship_array()
    sh[T.fgt] = 200
    enemy = deploy_fleet(game, Empire.Empire2, far, sh, cargo_array(), XYCoord(19, 19))
    scout_object(game, Empire.Empire1, enemy)

    guardian.implement_guardian_npe(game, Empire.Empire1, GuardianDataRecord())

    assert get_defns(game, cap)[T.LAM] == 5000


def test_a_guardian_never_shoots_its_own_fleets(game, cap):
    from recreon.fleet import deploy_fleet

    stock(game, cap, {T.fgt: 100}, {}, {T.LAM: 5000})
    sh = ship_array()
    sh[T.fgt] = 200
    deploy_fleet(game, Empire.Empire1, cap, sh, cargo_array(), XYCoord(12, 12))

    guardian.implement_guardian_npe(game, Empire.Empire1, GuardianDataRecord())

    assert get_defns(game, cap)[T.LAM] == 5000


def test_a_guardian_with_no_missiles_does_nothing(game, cap):
    from recreon.fleet import deploy_fleet

    stock(game, cap, {T.fgt: 100}, {}, {T.LAM: 0})
    sh = ship_array()
    sh[T.fgt] = 200
    enemy = deploy_fleet(game, Empire.Empire2, cap, sh, cargo_array(), XYCoord(12, 12))
    scout_object(game, Empire.Empire1, enemy)

    guardian.implement_guardian_npe(game, Empire.Empire1, GuardianDataRecord())

    assert game.GlobalSets.SetOfActiveFleets == {enemy.Index}


# --- Pirate -------------------------------------------------------------------


def test_the_hunting_grid_starts_uniform(game):
    data = PirateDataRecord()
    pirate.initialize_pirate_npe(game, Empire.Empire1, data)

    assert data.HuntingGround[1][1] == pirate.INITIAL_ATTRACTION
    assert data.HuntingGround[2][3] == pirate.INITIAL_ATTRACTION


def test_a_dry_block_wraps_past_zero(game):
    """ORIGINAL BUG #37. HuntingGround is a Byte with no floor, so the sixth
    failure on a fresh block turns it from the least attractive into the most."""
    assert pirate._byte(25 - 5 * 5) == 0
    assert pirate._byte(0 - 5) == 251


def test_a_productive_block_wraps_past_the_top(game):
    """The other half of #37: 250 + 15 comes back as 9."""
    assert pirate._byte(250 + 15) == 9


def test_patrol_destinations_land_in_the_block_they_name(game):
    data = PirateDataRecord()
    pirate.initialize_pirate_npe(game, Empire.Empire1, data)

    for _ in range(30):
        bx, by, xy = pirate._get_patrol_destination(game, data.HuntingGround)
        assert 1 + (bx - 1) * 5 <= xy.x <= bx * 5
        assert 1 + (by - 1) * 5 <= xy.y <= by * 5


def test_the_wheel_favours_the_attractive_block(game):
    data = PirateDataRecord()
    for row in data.HuntingGround:
        for i in range(len(row)):
            row[i] = 0
    data.HuntingGround[2][2] = 200
    data.HuntingGround[3][3] = 1

    picks = {pirate._get_patrol_destination(game, data.HuntingGround)[:2] for _ in range(20)}
    assert (2, 2) in picks


def test_a_pirate_sends_patrols_out(game, cap):
    data = PirateDataRecord()
    pirate.initialize_pirate_npe(game, Empire.Empire1, data)

    pirate.implement_pirate_npe(game, Empire.Empire1, data)

    live = game.GlobalSets.SetOfFleetsOf[Empire.Empire1] & game.GlobalSets.SetOfActiveFleets
    assert live, "a world this rich should field a patrol"
    missions = {data.FleetData[i].Mission for i in range(1, NO_OF_FLEETS_PER_EMPIRE + 1)}
    assert missions & {MissionTypes.WaitForTrnMSN, MissionTypes.AttackWrldMSN}


def test_a_pirate_world_too_poor_for_hulls_fields_nothing(game, cap):
    stock(game, cap, {T.fgt: 10}, {})
    data = PirateDataRecord()
    pirate.initialize_pirate_npe(game, Empire.Empire1, data)

    pirate.implement_pirate_npe(game, Empire.Empire1, data)

    assert not (
        game.GlobalSets.SetOfFleetsOf[Empire.Empire1] & game.GlobalSets.SetOfActiveFleets
    )


def test_a_raider_will_not_take_on_a_heavy_escort(game, cap):
    """FindTarget wants transports present, escorts no larger than its own, and
    heavy escorts no more than half its hunter-killers."""
    from recreon.fleet import deploy_fleet

    raider_sh = ship_array()
    raider_sh.update({T.hkr: 100, T.jmp: 100})
    raider = deploy_fleet(game, Empire.Empire1, cap, raider_sh, cargo_array(), XYCoord(12, 12))

    convoy_sh = ship_array()
    convoy_sh.update({T.trn: 50, T.ssp: 900})  # far too well escorted
    deploy_fleet(game, Empire.Empire2, cap, convoy_sh, cargo_array(), XYCoord(12, 12))

    assert pirate._find_target(game, Empire.Empire1, raider).ObjTyp == ObjectTypes.Void


def test_a_raider_takes_a_soft_convoy(game, cap):
    from recreon.fleet import deploy_fleet

    raider_sh = ship_array()
    raider_sh.update({T.hkr: 500, T.jmp: 500})
    raider = deploy_fleet(game, Empire.Empire1, cap, raider_sh, cargo_array(), XYCoord(12, 12))

    convoy_sh = ship_array()
    convoy_sh.update({T.trn: 50})
    convoy = deploy_fleet(
        game, Empire.Empire2, cap, convoy_sh, cargo_array(), XYCoord(12, 12)
    )

    found = pirate._find_target(game, Empire.Empire1, raider)
    assert found.Index == convoy.Index


def test_a_pirate_skips_pre_atomic_worlds(game, cap):
    poor = place_world(
        game, 2, XYCoord(12, 12), emp=Empire.Indep, tech=TechLevel.PreAtmLvl
    )
    stock(game, poor, {}, {T.tri: 9000, T.met: 9000})

    flt_sh = ship_array()
    flt_sh.update({T.hkr: 5000, T.jmp: 5000})

    assert pirate._get_raid_target(game, Empire.Empire1, flt_sh, 99999).ObjTyp == (
        ObjectTypes.Void
    )


def test_a_pirate_picks_a_rich_soft_world(game, cap):
    rich = place_world(game, 2, XYCoord(12, 12), emp=Empire.Indep)
    stock(game, rich, {}, {T.tri: 9000, T.met: 9000, T.men: 5})

    flt_sh = ship_array()
    flt_sh.update({T.hkr: 5000, T.jmp: 5000})

    found = pirate._get_raid_target(game, Empire.Empire1, flt_sh, 99999)
    assert found.Index == 2


# --- Kingdom ------------------------------------------------------------------


def test_the_two_kingdoms_differ_only_in_their_numbers(game):
    k1, k2 = Kingdom1DataRecord(), Kingdom1DataRecord()
    kingdom.initialize_kingdom1_npe(game, Empire.Empire1, k1)
    set_rand_seed(4021)
    kingdom.initialize_kingdom2_npe(game, Empire.Empire1, k2)

    assert k1.State[Empire.Empire2].Policy == PolicyTypes.NeutralPLT
    assert k2.State[Empire.Empire2].Policy == PolicyTypes.HarassPLT

    assert 1 <= k1.Persona.ImpGene <= 5
    assert 50 <= k2.Persona.ImpGene <= 100
    assert 50 <= k1.Persona.DefGene <= 75
    assert 5 <= k2.Persona.DefGene <= 10
    assert k1.Persona.FactorGene == 15
    assert k2.Persona.FactorGene == 25
    assert k1.Persona.Provoke == 75


def test_a_kingdom_turn_runs_end_to_end(game, cap):
    data = Kingdom1DataRecord()
    kingdom.initialize_kingdom1_npe(game, Empire.Empire1, data)

    for _ in range(12):
        kingdom.implement_kingdom1_npe(game, Empire.Empire1, data)

    assert data.Persona.Clock == 12


def test_the_kingdom_clock_drives_the_seventh_year_review(game, cap):
    """StateDeptReport and ReDesignateEmpire fire when (Clock+Offset) mod 7 is
    zero, and Offset is rolled per empire so the AIs do not sync up."""
    data = Kingdom1DataRecord()
    kingdom.initialize_kingdom1_npe(game, Empire.Empire1, data)
    assert 1 <= data.Persona.Offset <= 10

    fired = [
        (c + data.Persona.Offset) % kingdom.REVIEW_PERIOD == 0 for c in range(21)
    ]
    assert sum(fired) == 3


def test_a_kingdom_launches_a_conquest_fleet_at_a_neighbour(game, cap):
    """Given independent neighbours it knows about, a keen kingdom sends fleets.

    Only the launch is asserted here: `implement_kingdom1_npe` decides and
    deploys, but nothing inside it *moves* a fleet -- that is `update_all_fleets`
    from the turn loop. Arrival and conquest are covered by
    `test_an_npe_conquers_worlds_over_a_full_game` below.
    """
    for i, xy in enumerate(
        (XYCoord(11, 11), XYCoord(12, 10), XYCoord(9, 11)), start=2
    ):
        w = place_world(game, i, xy, emp=Empire.Indep)
        stock(game, w, {}, {T.men: 5})
        scout_object(game, Empire.Empire1, w)

    data = Kingdom1DataRecord()
    kingdom.initialize_kingdom2_npe(game, Empire.Empire1, data)
    data.Persona.Imperialist = 100

    for _ in range(20):
        kingdom.implement_kingdom1_npe(game, Empire.Empire1, data)

    missions = {
        data.FleetData[i].Mission for i in range(1, NO_OF_FLEETS_PER_EMPIRE + 1)
    }
    assert MissionTypes.ConquerMSN in missions
    assert game.GlobalSets.SetOfFleetsOf[Empire.Empire1] & game.GlobalSets.SetOfActiveFleets


# --- Berserker ----------------------------------------------------------------


def test_a_weak_base_goes_looking_for_home(game):
    base = place_base(game, 1, XYCoord(12, 12), T.cmm)
    stock(game, base, {T.fgt: 1}, {})

    data = BerserkerDataRecord()
    berserker._new_bsrk_base_target(game, Empire.Empire1, base, data.BaseData)

    assert data.BaseData[base.Index].Mission == BM.FindHomeBMS


def test_a_strong_base_hunts_a_loot_rich_world(game):
    base = place_base(game, 1, XYCoord(12, 12), T.cmm)
    stock(game, base, {T.ssp: 5000}, {})  # MPower 100 each -> well over 100000

    loot = place_world(game, 2, XYCoord(13, 13), emp=Empire.Indep)
    stock(game, loot, {}, {T.met: 5000, T.che: 5000})

    data = BerserkerDataRecord()
    berserker._new_bsrk_base_target(game, Empire.Empire1, base, data.BaseData)

    assert data.BaseData[base.Index].Mission == BM.AttackBMS
    assert data.BaseData[base.Index].TargetID.Index == 2


def test_a_base_with_nothing_worth_taking_wanders(game):
    base = place_base(game, 1, XYCoord(12, 12), T.cmm)
    stock(game, base, {T.ssp: 5000}, {})

    data = BerserkerDataRecord()
    berserker._new_bsrk_base_target(game, Empire.Empire1, base, data.BaseData)

    assert data.BaseData[base.Index].Mission == BM.WanderAroundBMS


def test_a_wandering_base_retargets_after_ten_years(game):
    base = place_base(game, 1, XYCoord(12, 12), T.cmm)
    stock(game, base, {T.ssp: 5000}, {})
    data = BerserkerDataRecord()
    entry = data.BaseData[base.Index]
    entry.Mission = BM.WanderAroundBMS
    entry.Count = 11

    berserker._implement_wander_around_bms(game, Empire.Empire1, base, data.BaseData)

    assert entry.Count == 0  # retargeted, so the counter was reset


def test_a_fortress_reaches_five_times_further_than_a_command_base():
    results = {}
    for s_typ in (T.frt, T.cmm):
        g = blank_game(size=20, empires=2)
        cap = place_world(g, 1, CAP_XY, emp=Empire.Empire1, typ=WT.CapTyp)
        g.Universe.EmpireData[Empire.Empire1].Capital = cap
        stock(g, cap, {T.jmp: 9000, T.jtn: 9000}, {T.men: 9000, T.tri: 9000})
        w = place_world(g, 2, XYCoord(16, 12), emp=Empire.Indep)
        stock(g, w, {}, {T.met: 5000, T.che: 5000})

        base = place_base(g, 1, XYCoord(12, 12), s_typ)
        stock(g, base, {T.ssp: 5000}, {})
        data = BerserkerDataRecord()
        data.BaseData[base.Index].Mission = BM.AttackBMS
        data.BaseData[base.Index].TargetID = w

        berserker._implement_attack_bms(g, Empire.Empire1, base, data)
        results[s_typ] = data.BaseData[base.Index].Mission

    # Distance is 4: inside a fortress's reach of 5, outside a command base's 1.
    assert results[T.frt] == BM.WaitForAttackBMS
    assert results[T.cmm] == BM.AttackBMS


def test_razing_a_world_kills_people_and_technology(game):
    from recreon.primintr import get_population, get_tech

    target = place_world(game, 2, XYCoord(12, 12), emp=Empire.Empire2, pop=5000)
    before_pop = get_population(game, target)

    berserker._bsrk_destroy_world(game, Empire.Empire1, target)

    assert get_population(game, target) < before_pop
    assert get_tech(game, target) <= TechLevel(2)


def test_razing_never_kills_the_last_ten_people(game):
    from recreon.primintr import get_population

    target = place_world(game, 2, XYCoord(12, 12), emp=Empire.Empire2, pop=120)
    berserker._bsrk_destroy_world(game, Empire.Empire1, target)

    assert get_population(game, target) >= 10


# --- Dispatcher ---------------------------------------------------------------


@pytest.mark.parametrize(
    "e_typ,cls",
    [
        (NPEmpireTypes.PirateNPE, PirateDataRecord),
        (NPEmpireTypes.Kingdom1NPE, Kingdom1DataRecord),
        (NPEmpireTypes.Kingdom2NPE, Kingdom1DataRecord),
        (NPEmpireTypes.BerserkerNPE, BerserkerDataRecord),
        (NPEmpireTypes.GuardianNPE, GuardianDataRecord),
    ],
)
def test_each_type_gets_its_own_payload(game, e_typ, cls):
    dispatch.initialize_npe(game, Empire.Empire1, e_typ)

    assert game.NPEData[Empire.Empire1].Typ == e_typ
    assert isinstance(game.NPEData[Empire.Empire1].Data, cls)


def test_an_undeclared_type_plays_as_a_pirate(game):
    """Every CASE in NPE.PAS has an ELSE falling through to the pirate, so an
    empire whose Typ was never set still gets an AI."""
    dispatch.initialize_npe(game, Empire.Empire1, NPEmpireTypes.NoNPE)

    assert isinstance(game.NPEData[Empire.Empire1].Data, PirateDataRecord)


def test_a_trader_plays_as_a_pirate_too(game):
    """TraderNPE is declared in NPEmpireTypes and implemented nowhere."""
    dispatch.initialize_npe(game, Empire.Empire1, NPEmpireTypes.TraderNPE)

    assert isinstance(game.NPEData[Empire.Empire1].Data, PirateDataRecord)


def test_both_kingdoms_dispatch_to_the_kingdom1_implementation(game, cap):
    dispatch.initialize_npe(game, Empire.Empire1, NPEmpireTypes.Kingdom2NPE)
    dispatch.implement_npe(game, Empire.Empire1)

    assert game.NPEData[Empire.Empire1].Data.Persona.Clock == 1


def test_implement_initialises_a_type_that_was_never_set_up(game, cap):
    """A scenario that names a type but never allocated the payload."""
    game.NPEData[Empire.Empire1].Typ = NPEmpireTypes.GuardianNPE
    game.NPEData[Empire.Empire1].Data = None

    dispatch.implement_npe(game, Empire.Empire1)

    assert isinstance(game.NPEData[Empire.Empire1].Data, GuardianDataRecord)


def test_cleanup_releases_the_payload(game):
    dispatch.initialize_npe(game, Empire.Empire1, NPEmpireTypes.PirateNPE)
    dispatch.clean_up_npe(game, Empire.Empire1)

    assert game.NPEData[Empire.Empire1].Data is None


def test_cleanup_of_an_empire_that_never_had_an_ai_is_harmless(game):
    dispatch.clean_up_npe(game, Empire.Empire1)


# --- The turn loop actually drives all this -----------------------------------


def test_the_turn_loop_runs_an_npe(scenario_path):
    """The whole point of the phase: update_turn no longer skips an NPE."""
    from recreon.main import update_turn
    from recreon.newgame import load_scenario

    g = load_scenario(scenario_path, {Empire.Empire1: "A"})
    npes = [e for e in game_npes(g)]
    assert npes, "the default scenario should define at least one NPE"

    for _ in range(40):
        update_turn(g)

    assert g.Year > 4021


def test_an_npe_conquers_worlds_over_a_full_game():
    """End to end through the real turn loop: an AI that starts with one world
    should be visibly bigger after 200 years.

    This is the test that would have caught the `set_status` slip in #11 -- with
    the per-empire sets broken every AI read as landless and nothing moved.
    """
    import pathlib

    from recreon.main import update_turn
    from recreon.newgame import load_scenario

    scn = pathlib.Path(__file__).resolve().parent.parent / "original" / "scenarios"
    g = load_scenario(scn / "INTRO.SCN", {Empire.Empire1: "A"})

    before = {e: len(s) for e, s in g.GlobalSets.SetOfPlanetsOf.items()}
    for _ in range(200):
        update_turn(g)
    after = {e: len(s) for e, s in g.GlobalSets.SetOfPlanetsOf.items()}

    grew = [e for e in game_npes(g) if after[e] > before[e]]
    assert grew, f"no NPE gained a world: {before} -> {after}"
    assert after[Empire.Indep] < before[Empire.Indep]


def game_npes(g):
    from recreon.primintr import empire_active
    from recreon.types import PLAYER_EMPIRES

    return [
        e
        for e in PLAYER_EMPIRES
        if empire_active(g, e) and g.NPEData[e].Typ != NPEmpireTypes.NoNPE
    ]
