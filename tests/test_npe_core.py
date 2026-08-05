"""Shared AI primitives, ported from NPEINTR.PAS."""

import pytest
from conftest import blank_game, place_world

from recreon.attack import AttackResultTypes
from recreon.datacnst import CargoSpace, MPower, TrnAdj, init_defense_record
from recreon.galaxy import XYCoord
from recreon.misc import fleet_cargo_space, military_power
from recreon.npe import core
from recreon.npe.types import (
    MissionTypes,
    NPECharacterRecord,
    PolicyTypes,
    fleet_data_array,
    state_dept_array,
)
from recreon.primintr import (
    get_cargo,
    get_coord,
    get_defns,
    get_ships,
    get_status,
    get_type,
    npe_data_index,
    put_cargo,
    put_defns,
    put_ships,
    scout_object,
    set_npe_data_index,
)
from recreon.types import (
    NO_OF_FLEETS_PER_EMPIRE,
    Empire,
    IDNumber,
    ObjectTypes,
    TechnologyTypes,
    WorldClass,
    WorldTypes,
    cargo_array,
    defns_array,
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
    """Every draw goes through the ported LCG, so seed it per test."""
    set_rand_seed(4021)


@pytest.fixture
def game():
    """Two empires: Empire1 with a capital and a base world, Empire2 with one
    world Empire1 has scouted."""
    g = blank_game(size=20, empires=2)

    cap = place_world(g, 1, CAP_XY, emp=Empire.Empire1, typ=WT.CapTyp)
    g.Universe.EmpireData[Empire.Empire1].Capital = cap

    base = place_world(g, 2, BASE_XY, emp=Empire.Empire1, typ=WT.BseTyp)

    foe = place_world(g, 3, FOE_XY, emp=Empire.Empire2, typ=WT.IndTyp)
    g.Universe.EmpireData[Empire.Empire2].Capital = foe
    scout_object(g, Empire.Empire1, foe)

    for world in (cap, base):
        stock(g, world, {T.fgt: 2000, T.hkr: 500, T.jmp: 200, T.trn: 100, T.jtn: 50},
              {T.men: 3000, T.nnj: 400, T.tri: 2000})

    return g


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
def cap():
    return world(1)


@pytest.fixture
def base():
    return world(2)


@pytest.fixture
def foe():
    return world(3)


@pytest.fixture
def persona():
    return NPECharacterRecord(Defensive=50, Offensive=70, WorldPower=40, Imperialist=50)


@pytest.fixture
def fdata():
    return fleet_data_array()


# --- Fleet-data bookkeeping --------------------------------------------------


def test_the_first_free_data_slot_is_the_highest(game, fdata):
    assert core.next_fleet_data_slot(game, fdata) == NO_OF_FLEETS_PER_EMPIRE


def test_a_slot_naming_a_live_fleet_is_taken(game, fdata, cap):
    flt = launch(game, cap)
    fdata[NO_OF_FLEETS_PER_EMPIRE].Index = flt.Index

    assert core.next_fleet_data_slot(game, fdata) == NO_OF_FLEETS_PER_EMPIRE - 1


def test_a_slot_naming_a_dead_fleet_is_free_again(game, fdata, cap):
    """Nothing clears the record when a fleet dies; the slot frees itself
    because the index it names is no longer active."""
    from recreon.fleet import destroy_fleet

    flt = launch(game, cap)
    fdata[NO_OF_FLEETS_PER_EMPIRE].Index = flt.Index
    destroy_fleet(game, flt)

    assert core.next_fleet_data_slot(game, fdata) == NO_OF_FLEETS_PER_EMPIRE


def test_already_targetted_matches_on_mission_and_target(game, fdata, cap, foe):
    flt = launch(game, cap)
    fdata[1].Index = flt.Index
    fdata[1].Mission = MissionTypes.ConquerMSN
    fdata[1].TargetID = foe

    assert core.already_targetted(game, Empire.Empire1, foe, MissionTypes.ConquerMSN, fdata)
    assert not core.already_targetted(
        game, Empire.Empire1, foe, MissionTypes.RaidTrnMSN, fdata
    )
    assert not core.already_targetted(
        game, Empire.Empire1, world(1), MissionTypes.ConquerMSN, fdata
    )


def test_a_dead_fleets_target_no_longer_counts(game, fdata, cap, foe):
    from recreon.fleet import destroy_fleet

    flt = launch(game, cap)
    fdata[1].Index = flt.Index
    fdata[1].Mission = MissionTypes.ConquerMSN
    fdata[1].TargetID = foe
    destroy_fleet(game, flt)

    assert not core.already_targetted(
        game, Empire.Empire1, foe, MissionTypes.ConquerMSN, fdata
    )


def test_enforce_links_clears_records_no_fleet_points_at(game, fdata, cap):
    flt = launch(game, cap)
    set_npe_data_index(game, flt, 1)
    fdata[1].Index = flt.Index
    # Slot 2 names the same fleet but nothing points back at it.
    fdata[2].Index = flt.Index

    core.enforce_npe_data_links(game, Empire.Empire1, fdata)

    assert fdata[1].Index == flt.Index
    assert fdata[2].Index == 0


# --- Fleet composition -------------------------------------------------------


def launch(game, from_id, ships=None, dest=None, emp=Empire.Empire1):
    from recreon.fleet import deploy_fleet

    sh = ship_array()
    sh.update(ships or {T.hkr: 10})
    return deploy_fleet(
        game, emp, from_id, sh, cargo_array(), dest or get_coord(game, from_id)
    )


@pytest.mark.parametrize(
    "mission,backbone",
    [
        (MissionTypes.ReturnMSN, T.fgt),
        (MissionTypes.ConquerMSN, T.jmp),
        (MissionTypes.StackMSN, T.pen),
        (MissionTypes.JumpAttackMSN, T.jmp),
        (MissionTypes.RaidTrnMSN, T.hkr),
    ],
)
def test_each_mission_draws_on_its_own_ship_sequence(game, cap, mission, backbone):
    """The first entry of the sequence is the backbone, so it is what gets
    filled first and is present whenever the world has any."""
    stock(game, cap, dict.fromkeys((T.fgt, T.hkr, T.jmp, T.pen, T.ssp), 2000))

    ships, _ = core.get_fleet_composition(game, cap, 5000, 0, mission)

    assert ships[backbone] > 0


def test_an_unlisted_mission_falls_back_to_the_jump_sequence(game, cap):
    """SlowAttackMSN is not in the original's CASE, so it takes the ELSE."""
    slow, _ = core.get_fleet_composition(game, cap, 5000, 0, MissionTypes.SlowAttackMSN)
    conquer, _ = core.get_fleet_composition(game, cap, 5000, 0, MissionTypes.ConquerMSN)

    assert slow == conquer


def test_composition_stops_once_the_power_is_met(game, cap):
    ships, _ = core.get_fleet_composition(game, cap, 5000, 0, MissionTypes.ConquerMSN)

    assert military_power(ships, defns_array()) >= 5000


def test_a_fleet_of_only_fighters_gets_trillum_to_move_on(game, cap):
    """Fighters carry no fuel of their own."""
    stock(game, cap, {T.fgt: 2000})

    ships, cargo = core.get_fleet_composition(game, cap, 100, 0, MissionTypes.ReturnMSN)

    assert ships[T.fgt] > 0
    assert cargo[T.tri] == 10


def test_a_fleet_with_real_ships_takes_no_free_trillum(game, cap):
    _, cargo = core.get_fleet_composition(game, cap, 5000, 0, MissionTypes.ConquerMSN)

    assert cargo[T.tri] == 0


def test_troops_leave_five_hundred_men_on_the_world(game, cap):
    """The AI never strips a world bare to fill one invasion."""
    stock(game, cap, {T.trn: 500, T.jtn: 500}, {T.men: 700, T.nnj: 0})

    _, cargo = core.get_fleet_composition(game, cap, 0, 5000, MissionTypes.ConquerMSN)

    assert cargo[T.men] == 200


def test_a_world_at_the_floor_sends_no_men(game, cap):
    stock(game, cap, {T.trn: 500, T.jtn: 500}, {T.men: 500, T.nnj: 0})

    _, cargo = core.get_fleet_composition(game, cap, 0, 5000, MissionTypes.ConquerMSN)

    assert cargo[T.men] == 0


def test_ninjas_count_triple_toward_ground_strength(game, cap):
    stock(game, cap, {T.trn: 500, T.jtn: 500}, {T.men: 5000, T.nnj: 100})

    _, cargo = core.get_fleet_composition(game, cap, 0, 300, MissionTypes.ConquerMSN)

    assert cargo[T.nnj] == 100
    assert cargo[T.men] == 0


def test_a_berserker_strike_takes_every_transport(game, cap):
    ships, _ = core.get_fleet_composition(game, cap, 100, 0, MissionTypes.BSRKAttackMSN)

    assert ships[T.trn] == 100
    assert ships[T.jtn] == 50


def test_troop_loading_ignores_transport_capacity(game, cap):
    """ORIGINAL BUG, preserved. Remaining space is reduced by multiplying by
    CargoSpace where it should divide, so the running total underflows its
    Pascal Word and the men cap becomes effectively infinite. Every man asked
    for is loaded, and the fleet launches overloaded."""
    ships, cargo = core.get_fleet_composition(
        game, cap, 50000, 2000, MissionTypes.JumpAttackMSN
    )

    assert cargo[T.men] == 800  # the full complement asked for
    assert fleet_cargo_space(ships, cargo) < 0  # and it does not fit


def test_potential_res_reads_the_wrong_fleets_entirely(game, fdata, cap):
    """ORIGINAL BUG, preserved. The routine reconstructs a fleet index as
    ``NoOfFleetsPerEmpire * Ord(empire) + i``, assuming fleet slots are
    partitioned into per-empire blocks. They are not -- ``GetNextFleet`` hands
    out the highest free slot from one global pool, so Empire1's first fleet
    is 240, not 1. Every other routine in the unit reads ``FleetData[i].Index``
    instead, which is the index that actually means something.

    The result is that the reinforcement calculation pairs the right *record*
    with the wrong *fleet*: a world's in-transit strength is read off whatever
    occupies the low slots, usually nothing."""
    flt = launch(game, cap, {T.hkr: 77})
    assert flt.Index != NO_OF_FLEETS_PER_EMPIRE * int(Empire.Empire1) + 1
    base_ships = get_ships(game, cap)[T.hkr]
    fdata[1].Mission = MissionTypes.ReturnMSN
    fdata[1].TargetID = cap
    fdata[1].Index = flt.Index

    ships, _ = core.get_potential_res(game, cap, fdata)

    # The inbound fleet is invisible: slot 1 holds no fleet, so nothing is
    # added even though the record names one correctly.
    assert ships[T.hkr] == base_ships


def test_potential_res_starts_from_what_the_world_already_holds(game, fdata, cap):
    ships, cargo = core.get_potential_res(game, cap, fdata)

    assert ships == get_ships(game, cap)
    assert cargo == get_cargo(game, cap)


# --- Assessment --------------------------------------------------------------


def test_average_military_power_counts_ships_not_defenses(game, cap):
    put_defns(game, cap, {d: 9999 for d in defns_array()})
    rcap = core.create_region_array(game, Empire.Empire1)

    expected = (
        military_power(get_ships(game, world(1)), defns_array())
        + military_power(get_ships(game, world(2)), defns_array())
    ) // 2

    assert core.average_military_power(game, rcap) == pytest.approx(expected, abs=1)


def test_average_military_power_of_nothing_is_zero(game):
    empty = [empty_quadrant() for _ in range(core.MAX_NO_OF_REGIONS + 1)]

    assert core.average_military_power(game, empty) == 0


def test_minimum_defense_scales_with_the_defensive_trait(game, cap):
    low = core.minimum_defense(game, cap, NPECharacterRecord(Defensive=1))
    high = core.minimum_defense(game, cap, NPECharacterRecord(Defensive=2))

    assert high == 2 * low


def test_an_undefensive_ai_wants_no_defense_at_all(game, cap):
    """ORIGINAL BUG, preserved. The character adjustment multiplies by
    Defensive rather than scaling by it, so Defensive=0 zeroes the whole
    estimate however valuable the world is."""
    assert core.minimum_defense(game, cap, NPECharacterRecord(Defensive=0)) == 0


def test_nearby_enemy_worlds_compound_the_estimate(game, cap, persona):
    """ORIGINAL BUG, preserved. The x3 proximity adjustment sits inside the
    per-world loop, so it applies once per nearby enemy world rather than
    once overall -- two worlds means x9, not x3."""
    alone = core.minimum_defense(game, cap, persona)

    place_world(game, 10, XYCoord(6, 6), emp=Empire.Empire2, typ=WT.IndTyp)
    one = core.minimum_defense(game, cap, persona)

    place_world(game, 11, XYCoord(7, 7), emp=Empire.Empire2, typ=WT.IndTyp)
    two = core.minimum_defense(game, cap, persona)

    assert one == 3 * alone
    assert two == 9 * alone


def test_a_nearby_enemy_base_doubles_again(game, cap, persona):
    place_world(game, 10, XYCoord(6, 6), emp=Empire.Empire2, typ=WT.IndTyp)
    ordinary = core.minimum_defense(game, cap, persona)

    game.Universe.Planet[10].Typ = WT.BseTyp
    base_type = core.minimum_defense(game, cap, persona)

    assert base_type == 2 * ordinary


def test_independent_worlds_are_not_a_threat(game, cap, persona):
    alone = core.minimum_defense(game, cap, persona)
    place_world(game, 10, XYCoord(6, 6), emp=Empire.Indep, typ=WT.IndTyp)

    assert core.minimum_defense(game, cap, persona) == alone


# --- Regions -----------------------------------------------------------------


def test_the_region_array_holds_bases_and_the_capital(game):
    rcap = core.create_region_array(game, Empire.Empire1)

    assert rcap[1] == world(1)
    assert rcap[2] == world(2)
    assert rcap[3] == empty_quadrant()


def test_ordinary_worlds_are_not_regions(game):
    place_world(game, 10, XYCoord(3, 3), emp=Empire.Empire1, typ=WT.IndTyp)

    rcap = core.create_region_array(game, Empire.Empire1)

    assert rcap[3] == empty_quadrant()


def test_the_regional_capital_is_the_nearest_one(game, foe):
    rcap = core.create_region_array(game, Empire.Empire1)

    # The base at (8,8) is closer to (12,12) than the capital at (5,5).
    assert core.get_regional_capital(game, foe, rcap) == world(2)


def test_an_empire_with_no_regions_gets_empty_quadrant(game, foe):
    """ORIGINAL BUG, preserved as the only defined reading. The original never
    initialises its result and returns stack garbage here."""
    empty = [empty_quadrant() for _ in range(core.MAX_NO_OF_REGIONS + 1)]

    assert core.get_regional_capital(game, foe, empty) == empty_quadrant()


# --- Target selection --------------------------------------------------------


def test_the_best_target_must_be_known(game, persona, fdata, foe):
    """An unscouted world is invisible to targeting however attractive."""
    game.Universe.Planet[foe.Index].ScoutedBy.discard(Empire.Empire1)
    game.Universe.Planet[foe.Index].KnownBy.discard(Empire.Empire1)

    target, _, _ = core.get_best_target(
        game, Empire.Empire1, game.GlobalSets.SetOfPlanetsOf[Empire.Empire2],
        10**9, persona, fdata,
    )

    assert target == empty_quadrant()


def test_a_known_world_is_targetted(game, persona, fdata, foe):
    target, _, _ = core.get_best_target(
        game, Empire.Empire1, game.GlobalSets.SetOfPlanetsOf[Empire.Empire2],
        10**9, persona, fdata,
    )

    assert target == foe


def test_a_world_defended_beyond_the_ais_means_is_skipped(game, persona, fdata, foe):
    stock(game, foe, {T.hkr: 9000})

    target, _, _ = core.get_best_target(
        game, Empire.Empire1, game.GlobalSets.SetOfPlanetsOf[Empire.Empire2],
        1, persona, fdata,
    )

    assert target == empty_quadrant()


def test_a_world_already_targetted_is_skipped(game, persona, fdata, foe, cap):
    flt = launch(game, cap)
    fdata[1].Index = flt.Index
    fdata[1].Mission = MissionTypes.ConquerMSN
    fdata[1].TargetID = foe

    target, _, _ = core.get_best_target(
        game, Empire.Empire1, game.GlobalSets.SetOfPlanetsOf[Empire.Empire2],
        10**9, persona, fdata,
    )

    assert target == empty_quadrant()


def test_target_reports_the_defenses_and_troops_found(game, persona, fdata, foe):
    stock(game, foe, {T.hkr: 10}, {T.men: 100, T.nnj: 10})

    _, defense, men = core.get_best_target(
        game, Empire.Empire1, game.GlobalSets.SetOfPlanetsOf[Empire.Empire2],
        10**9, persona, fdata,
    )

    assert defense == military_power(get_ships(game, foe), get_defns(game, foe))
    assert men == 100 + 4 * 10 + 10


def test_the_best_base_needs_power_and_troops(game, foe):
    """Half the fleet's power and all of its troops, within 15 sectors."""
    assert core.get_best_base(game, Empire.Empire1, foe, 1000, 100) != empty_quadrant()
    assert core.get_best_base(game, Empire.Empire1, foe, 10**9, 100) == empty_quadrant()
    assert core.get_best_base(game, Empire.Empire1, foe, 1000, 10**9) == empty_quadrant()


def test_the_best_planet_to_protect_is_the_weakest_nearby(game, base):
    weak = place_world(game, 10, XYCoord(9, 9), emp=Empire.Empire1, typ=WT.IndTyp)
    strong = place_world(game, 11, XYCoord(7, 7), emp=Empire.Empire1, typ=WT.IndTyp)
    stock(game, weak, {})
    stock(game, strong, {T.hkr: 500})

    assert core.get_best_planet_to_protect(game, base) == weak


def test_protecting_falls_back_to_the_capital(game, base):
    """Bases and capitals defend themselves, so with no ordinary world in
    range the AI is left pointing at its capital."""
    assert core.get_best_planet_to_protect(game, base) == world(1)


# --- Deployment --------------------------------------------------------------


def test_deploying_a_battle_fleet_records_its_mission(game, fdata, cap, foe):
    core.deploy_battle_fleet(
        game, Empire.Empire1, fdata, cap, 5000, 0, MissionTypes.JumpAttackMSN, foe
    )

    live = [i for i in range(1, NO_OF_FLEETS_PER_EMPIRE + 1) if fdata[i].Index]
    assert len(live) == 1
    entry = fdata[live[0]]
    assert entry.Mission == MissionTypes.JumpAttackMSN
    assert entry.TargetID == foe
    assert entry.HomeBaseID == cap


def test_the_deployed_fleet_points_back_at_its_record(game, fdata, cap, foe):
    core.deploy_battle_fleet(
        game, Empire.Empire1, fdata, cap, 5000, 0, MissionTypes.JumpAttackMSN, foe
    )

    slot = [i for i in range(1, NO_OF_FLEETS_PER_EMPIRE + 1) if fdata[i].Index][0]
    flt = IDNumber(ObjectTypes.Flt, fdata[slot].Index)
    assert npe_data_index(game, flt) == slot


def test_a_fleet_that_cannot_reach_its_target_is_recalled(game, fdata, cap):
    """The range check runs after the launch, so the fleet is built, found
    wanting, and unloaded straight back onto the world it came from."""
    far = place_world(game, 10, XYCoord(20, 20), emp=Empire.Empire2, typ=WT.IndTyp)
    stock(game, cap, {T.fgt: 2000}, {T.tri: 0})

    core.deploy_battle_fleet(
        game, Empire.Empire1, fdata, cap, 5000, 0, MissionTypes.JumpAttackMSN, far
    )

    assert not game.GlobalSets.SetOfActiveFleets
    assert all(fdata[i].Index == 0 for i in range(1, NO_OF_FLEETS_PER_EMPIRE + 1))


def test_probes_go_out_ahead_of_an_attack_on_a_foreign_world(game, fdata, cap, foe):
    from recreon.types import ProbeStatus

    core.deploy_battle_fleet(
        game, Empire.Empire1, fdata, cap, 5000, 0, MissionTypes.JumpAttackMSN, foe
    )

    probes = game.Universe.EmpireData[Empire.Empire1].Probe
    assert any(p.Status == ProbeStatus.PInTrans for p in probes[1:])


def test_no_probes_go_out_for_a_friendly_destination(game, fdata, cap, base):
    from recreon.types import ProbeStatus

    core.deploy_battle_fleet(
        game, Empire.Empire1, fdata, cap, 5000, 0, MissionTypes.StackMSN, base
    )

    probes = game.Universe.EmpireData[Empire.Empire1].Probe
    assert all(p.Status == ProbeStatus.PReady for p in probes[1:])


def test_a_cargo_fleet_carries_what_the_world_actually_has(game, fdata, cap, base):
    wanted = cargo_array()
    wanted[T.met] = 99999

    core.deploy_cargo_fleet(
        game, Empire.Empire1, fdata, cap, wanted, True, MissionTypes.SupplyMSN, base
    )

    slot = [i for i in range(1, NO_OF_FLEETS_PER_EMPIRE + 1) if fdata[i].Index][0]
    flt = IDNumber(ObjectTypes.Flt, fdata[slot].Index)
    assert get_cargo(game, flt)[T.met] <= 500


def test_a_cargo_fleet_told_not_to_carry_takes_nothing(game, fdata, cap, base):
    wanted = cargo_array()
    wanted[T.met] = 100

    core.deploy_cargo_fleet(
        game, Empire.Empire1, fdata, cap, wanted, False, MissionTypes.SupplyMSN, base
    )

    slot = [i for i in range(1, NO_OF_FLEETS_PER_EMPIRE + 1) if fdata[i].Index][0]
    flt = IDNumber(ObjectTypes.Flt, fdata[slot].Index)
    assert get_cargo(game, flt)[T.met] == 0


def test_deploy_harass_fleet_does_nothing(game, fdata, persona):
    """ORIGINAL BUG, preserved. The procedure has an empty body in v2.0, so
    HarassPLT -- the first rung of the escalation ladder -- is a policy under
    which the AI never acts."""
    rcap = core.create_region_array(game, Empire.Empire1)
    before = set(game.GlobalSets.SetOfActiveFleets)

    core.deploy_harass_fleet(
        game, Empire.Empire1, Empire.Empire2, rcap, persona, fdata
    )

    assert game.GlobalSets.SetOfActiveFleets == before
    assert all(fdata[i].Index == 0 for i in range(1, NO_OF_FLEETS_PER_EMPIRE + 1))


def test_a_jump_attack_launches_at_the_best_target(game, fdata, persona, foe):
    rcap = core.create_region_array(game, Empire.Empire1)
    stock(game, world(2), {T.hkr: 9000, T.jmp: 9000, T.trn: 200, T.jtn: 200},
          {T.men: 9000, T.nnj: 900, T.tri: 9000})

    core.deploy_jump_attack(
        game, Empire.Empire1, Empire.Empire2, rcap, persona, fdata
    )

    live = [i for i in range(1, NO_OF_FLEETS_PER_EMPIRE + 1) if fdata[i].Index]
    assert len(live) == 1
    assert fdata[live[0]].Mission == MissionTypes.JumpAttackMSN
    assert fdata[live[0]].TargetID == foe


def test_a_slow_attack_from_a_strong_capital_flies_its_own_mission(
    game, fdata, persona, foe
):
    rcap = core.create_region_array(game, Empire.Empire1)
    stock(game, world(2), {T.hkr: 9000, T.jmp: 9000, T.trn: 200, T.jtn: 200},
          {T.men: 9000, T.nnj: 900, T.tri: 9000})

    core.deploy_slow_attack(
        game, Empire.Empire1, Empire.Empire2, rcap, persona, fdata
    )

    live = [i for i in range(1, NO_OF_FLEETS_PER_EMPIRE + 1) if fdata[i].Index]
    assert len(live) == 1
    assert fdata[live[0]].Mission == MissionTypes.SlowAttackMSN


def test_the_slow_attack_fallback_mislabels_itself_a_jump_attack(
    game, fdata, persona, foe
):
    """ORIGINAL BUG, preserved. When the nearest regional capital is too weak
    the fallback branch deploys with JumpAttackMSN -- a copy-paste from
    DeployJumpAttack -- so the fleet is built to the wrong ship sequence and
    the persona later runs the wrong arrival handler."""
    rcap = core.create_region_array(game, Empire.Empire1)
    # Strip the near base so it cannot field the fleet, leaving the far
    # capital as the only qualifying launch site.
    stock(game, world(2), {}, {T.tri: 100})
    stock(game, world(1), {T.hkr: 9000, T.jmp: 9000, T.trn: 200, T.jtn: 200},
          {T.men: 9000, T.nnj: 900, T.tri: 9000})

    core.deploy_slow_attack(
        game, Empire.Empire1, Empire.Empire2, rcap, persona, fdata
    )

    live = [i for i in range(1, NO_OF_FLEETS_PER_EMPIRE + 1) if fdata[i].Index]
    assert len(live) == 1
    assert fdata[live[0]].Mission == MissionTypes.JumpAttackMSN


# --- Designation -------------------------------------------------------------


def test_an_ambrosia_world_with_the_tech_short_circuits_everything(game, persona, base):
    from recreon.types import TechLevel

    game.Universe.Planet[base.Index].Cls = WorldClass.ParCls
    game.Universe.Planet[base.Index].Tech = TechLevel.BioTchLvl
    rcap = core.create_region_array(game, Empire.Empire1)

    assert core.get_new_designation(game, base, persona, rcap) == WT.AmbTyp


def test_designation_never_returns_a_construction_variant(game, persona):
    """The *STyp entries are zeroed in NPETypeDefault, so the roll can never
    land on one."""
    rcap = core.create_region_array(game, Empire.Empire1)
    variants = {WT.BseSTyp, WT.JmpSTyp, WT.RawSTyp, WT.StrSTyp, WT.TrnSTyp}

    seen = {
        core.get_new_designation(game, world(2), persona, rcap) for _ in range(200)
    }

    assert not (seen & variants)


def test_redesignation_leaves_the_capital_alone(game, persona):
    rcap = core.create_region_array(game, Empire.Empire1)
    ordinary = place_world(game, 10, XYCoord(4, 4), emp=Empire.Empire1, typ=WT.IndTyp)

    core.redesignate_empire(game, Empire.Empire1, rcap, persona)

    assert get_type(game, world(1)) == WT.CapTyp


def test_redesignation_leaves_infrastructure_alone(game, persona):
    """Jumpship, starship and base worlds represent investment the AI will
    not throw away."""
    rcap = core.create_region_array(game, Empire.Empire1)
    for i, typ in ((10, WT.JmpTyp), (11, WT.StrTyp)):
        place_world(game, i, XYCoord(3, i - 7), emp=Empire.Empire1, typ=typ)

    core.redesignate_empire(game, Empire.Empire1, rcap, persona)

    assert get_type(game, world(2)) == WT.BseTyp
    assert get_type(game, world(10)) == WT.JmpTyp
    assert get_type(game, world(11)) == WT.StrTyp


# --- Missions ----------------------------------------------------------------


def test_a_returning_fleet_lands_everything_it_carries(game, cap):
    before = get_ships(game, cap)[T.hkr]
    flt = launch(game, cap, {T.hkr: 10})

    core.implement_return_msn(game, flt, cap)

    assert flt.Index not in game.GlobalSets.SetOfActiveFleets
    assert get_ships(game, cap)[T.hkr] == before


def test_setting_a_return_retargets_the_fleet(game, fdata, cap, base):
    flt = launch(game, cap)
    set_npe_data_index(game, flt, 1)
    fdata[1].Index = flt.Index

    core.set_fleet_return(game, Empire.Empire1, flt, base, fdata)

    assert fdata[1].Mission == MissionTypes.ReturnMSN
    assert fdata[1].TargetID == base
    assert game.Universe.Fleet[flt.Index].Dest == BASE_XY


def test_a_supply_run_hands_over_its_cargo_and_turns_around(game, fdata, cap, base):
    flt = launch(game, cap, {T.trn: 50})
    set_npe_data_index(game, flt, 1)
    fdata[1].Index = flt.Index
    stock(game, flt, {T.trn: 50}, {T.met: 200})
    before = get_cargo(game, base)[T.met]

    core.implement_supply_msn(game, Empire.Empire1, flt, base, cap, fdata)

    assert get_cargo(game, base)[T.met] == before + 200
    assert fdata[1].Mission == MissionTypes.ReturnMSN
    assert fdata[1].TargetID == cap


def test_conquering_an_independent_world_takes_it(game, fdata, cap):
    indep = place_world(game, 10, XYCoord(6, 5), emp=Empire.Indep, typ=WT.IndTyp)
    stock(game, indep, {}, {T.men: 1})
    flt = launch(game, cap, {T.jmp: 500, T.jtn: 200}, dest=XYCoord(6, 5))
    stock(game, flt, {T.jmp: 500, T.jtn: 200}, {T.men: 900, T.tri: 500})
    game.Universe.Fleet[flt.Index].XY = XYCoord(6, 5)
    set_npe_data_index(game, flt, 1)
    fdata[1].Index = flt.Index

    result = core.implement_conquer_msn(game, Empire.Empire1, flt, indep, cap, fdata)

    assert result == AttackResultTypes.DefConqueredART
    assert get_status(game, indep) == Empire.Empire1


def test_a_contested_sector_is_not_fought_over(game, fdata, cap):
    """Another empire's fleet in the sector makes the AI wait rather than
    fight, whatever the odds."""
    indep = place_world(game, 10, XYCoord(6, 5), emp=Empire.Indep, typ=WT.IndTyp)
    foe_world = place_world(game, 11, XYCoord(15, 15), emp=Empire.Empire2, typ=WT.IndTyp)
    stock(game, foe_world, {T.hkr: 10})
    enemy = launch(game, foe_world, {T.hkr: 5}, emp=Empire.Empire2)
    game.Universe.Fleet[enemy.Index].XY = XYCoord(6, 5)

    flt = launch(game, cap, {T.jmp: 500})
    game.Universe.Fleet[flt.Index].XY = XYCoord(6, 5)
    set_npe_data_index(game, flt, 1)
    fdata[1].Index = flt.Index

    result = core.implement_conquer_msn(game, Empire.Empire1, flt, indep, cap, fdata)

    assert result == AttackResultTypes.AttRetreatsART
    assert get_status(game, indep) == Empire.Indep


def test_a_raider_destroys_its_own_booty(game, fdata, cap):
    """Raiding denies the enemy its transports; it does not enrich the
    raider. Only hunter-killers survive the purge."""
    flt = launch(game, cap, {T.hkr: 10})
    stock(game, flt, {T.hkr: 10, T.trn: 40, T.fgt: 90}, {T.met: 300, T.men: 50})
    set_npe_data_index(game, flt, 1)
    fdata[1].Index = flt.Index

    core.implement_raid_trn_msn(game, Empire.Empire1, flt, cap, cap, fdata)

    ships = get_ships(game, flt)
    assert ships[T.hkr] == 10
    assert ships[T.trn] == 0
    assert ships[T.fgt] == 0
    assert all(v == 0 for v in get_cargo(game, flt).values())


def test_a_raider_goes_home_after_five_years(game, fdata, cap):
    flt = launch(game, cap, {T.hkr: 10})
    set_npe_data_index(game, flt, 1)
    fdata[1].Index = flt.Index
    fdata[1].Waiting = 4

    core.implement_raid_trn_msn(game, Empire.Empire1, flt, cap, cap, fdata)
    assert fdata[1].Waiting == 5
    assert fdata[1].Mission != MissionTypes.ReturnMSN

    core.implement_raid_trn_msn(game, Empire.Empire1, flt, cap, cap, fdata)
    assert fdata[1].Mission == MissionTypes.ReturnMSN


def test_stacking_makes_the_first_arrivals_guards(game, fdata, cap):
    flt = launch(game, cap, {T.hkr: 10})
    set_npe_data_index(game, flt, 1)
    fdata[1].Index = flt.Index

    core.implement_stack_msn(game, flt, fdata)

    assert fdata[1].Mission == MissionTypes.GuardMSN


def test_a_guard_lands_its_ships_on_the_world(game, cap):
    """Handing over every hull leaves the fleet with none, so it is dissolved
    rather than left as an empty shell."""
    flt = launch(game, cap, {T.hkr: 10})
    before = get_ships(game, cap)[T.hkr]

    core.implement_guard_msn(game, flt, cap)

    assert get_ships(game, cap)[T.hkr] == before + 10
    assert flt.Index not in game.GlobalSets.SetOfActiveFleets


def test_a_returning_fleet_is_redirected_when_home_falls(game, fdata, cap, base):
    flt = launch(game, cap)
    set_npe_data_index(game, flt, 1)
    fdata[1].Index = flt.Index
    fdata[1].Mission = MissionTypes.ReturnMSN
    fdata[1].TargetID = base
    rcap = core.create_region_array(game, Empire.Empire1)

    game.Universe.Planet[base.Index].Emp = Empire.Empire2

    core.mid_course_correction(game, Empire.Empire1, flt, rcap, fdata)

    assert fdata[1].TargetID != base


def test_an_attacking_fleet_is_left_alone(game, fdata, cap, foe):
    flt = launch(game, cap)
    set_npe_data_index(game, flt, 1)
    fdata[1].Index = flt.Index
    fdata[1].Mission = MissionTypes.JumpAttackMSN
    fdata[1].TargetID = foe
    rcap = core.create_region_array(game, Empire.Empire1)

    core.mid_course_correction(game, Empire.Empire1, flt, rcap, fdata)

    assert fdata[1].TargetID == foe


def test_plundering_strips_a_world_and_abandons_it(game, cap):
    taken = place_world(game, 10, XYCoord(6, 5), emp=Empire.Empire1, typ=WT.MinTyp)
    stock(game, taken, {T.fgt: 100}, {T.met: 400})
    flt = launch(game, cap, {T.trn: 500})
    stock(game, flt, {T.trn: 500}, {})

    core.plunder_world(game, Empire.Empire1, flt, taken)

    assert get_cargo(game, flt)[T.met] > 0
    assert all(v == 0 for v in get_ships(game, taken).values())
    assert all(v == 0 for v in get_cargo(game, taken).values())
    assert get_status(game, taken) == Empire.Indep
    assert get_type(game, taken) == WT.IndTyp


def test_plundering_a_world_the_attack_did_not_take_does_nothing(game, cap, foe):
    before = get_cargo(game, foe)
    flt = launch(game, cap, {T.trn: 500})

    core.plunder_world(game, Empire.Empire1, flt, foe)

    assert get_cargo(game, foe) == before
    assert get_status(game, foe) == Empire.Empire2


# --- Diplomacy ---------------------------------------------------------------


def test_the_report_counts_bases_as_worlds(game):
    """GetEmpireStatus counts starbases alongside planets, so "worlds" is
    really "holdings"."""
    state = state_dept_array()
    core.state_dept_report(game, Empire.Empire1, state)

    assert state[Empire.Empire1].Worlds == 2


def test_military_strength_rounds_ships_to_thousands(game, cap):
    """An empire with fewer than 500 of a type contributes nothing for it."""
    stock(game, world(1), {T.hkr: 400})
    stock(game, world(2), {})

    state = state_dept_array()
    core.state_dept_report(game, Empire.Empire1, state)

    assert state[Empire.Empire1].TotalMilitary == 1


def test_military_strength_counts_a_full_thousand(game):
    stock(game, world(1), {T.hkr: 1000})
    stock(game, world(2), {})

    state = state_dept_array()
    core.state_dept_report(game, Empire.Empire1, state)

    assert state[Empire.Empire1].TotalMilitary == 1 + MPower[T.hkr]


def test_technology_never_affects_threat_assessment(game):
    """ORIGINAL BUG, preserved. The per-enemy tech lookup reads the AI's own
    capital instead of the enemy's, so both arms of the tech comparison are
    dead however far apart the two empires are."""
    from recreon.types import TechLevel

    state = state_dept_array()
    core.state_dept_report(game, Empire.Empire1, state)
    baseline = state[Empire.Empire2].ThreatAssess

    game.Universe.Planet[3].Tech = TechLevel.PreTchLvl
    state = state_dept_array()
    core.state_dept_report(game, Empire.Empire1, state)

    assert state[Empire.Empire2].ThreatAssess == baseline


def test_threat_is_capped_at_a_hundred(game):
    stock(game, world(1), {})
    stock(game, world(2), {})
    stock(game, world(3), {T.hkr: 9000, T.ssp: 9000})

    state = state_dept_array()
    core.state_dept_report(game, Empire.Empire1, state)

    assert state[Empire.Empire2].ThreatAssess == 100


def test_a_losing_ai_escalates_regardless_of_temperament(game):
    """Balance short-circuits the whole ladder: an AI that has lost ground
    goes to Conflict without consulting its own Offensive trait."""
    state = state_dept_array()
    state[Empire.Empire2].Policy = PolicyTypes.NeutralPLT
    state[Empire.Empire2].Balance = -2
    state[Empire.Empire2].Aggressiveness = 50

    core.state_department(game, Empire.Empire1, NPECharacterRecord(Offensive=0), state)

    assert state[Empire.Empire2].Policy == PolicyTypes.ConflictPLT


def test_a_slightly_losing_ai_preempts(game):
    state = state_dept_array()
    state[Empire.Empire2].Policy = PolicyTypes.NeutralPLT
    state[Empire.Empire2].Balance = -1
    state[Empire.Empire2].Aggressiveness = 50

    core.state_department(game, Empire.Empire1, NPECharacterRecord(Offensive=0), state)

    assert state[Empire.Empire2].Policy == PolicyTypes.PreemptPLT


def test_aggressiveness_decays_every_year(game):
    state = state_dept_array()
    state[Empire.Empire2].Policy = PolicyTypes.NeutralPLT
    state[Empire.Empire2].Aggressiveness = 50

    core.state_department(game, Empire.Empire1, NPECharacterRecord(Offensive=0), state)

    assert 48 <= state[Empire.Empire2].Aggressiveness <= 49


def test_aggressiveness_underflows_instead_of_bottoming_out(game):
    """ORIGINAL BUG, preserved. Aggressiveness is a Pascal Index (0..100)
    decremented with no floor, so it wraps through a byte. Every
    de-escalation test then fails permanently while the ``> 80`` test starts
    passing, and a long-quiet AI can never stand down."""
    state = state_dept_array()
    state[Empire.Empire2].Policy = PolicyTypes.NeutralPLT
    state[Empire.Empire2].Aggressiveness = 0

    core.state_department(game, Empire.Empire1, NPECharacterRecord(Offensive=0), state)

    assert state[Empire.Empire2].Aggressiveness >= 254


# --- Defenses ----------------------------------------------------------------


def test_every_defense_roll_produces_a_valid_setting(game):
    """Four outcomes across the 1..100 roll; all of them must be one of the
    known distributions."""
    from recreon.primintr import get_defense_settings

    known = [init_defense_record(), core.DEFENSE_1, core.DEFENSE_2, core.DEFENSE_3]
    seen = []
    for _ in range(120):
        core.set_empire_defenses(game, Empire.Empire1)
        got = get_defense_settings(game, Empire.Empire1)
        assert any(got.ShellDefDist == k.ShellDefDist for k in known)
        seen.append(tuple(sorted((s, tuple(sorted(d.items()))) for s, d in got.ShellDefDist.items())))

    assert len(set(seen)) == 4


def test_the_ai_distributions_leave_starbase_defenses_zero(game):
    """The Pascal typed constants specify ShellDefDist only."""
    for record in (core.DEFENSE_1, core.DEFENSE_2, core.DEFENSE_3):
        assert all(
            v == 0 for shell in record.StarbaseDefDist.values() for v in shell.values()
        )
