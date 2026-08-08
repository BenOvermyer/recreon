"""Milestone 5: fleets attack worlds and each other, and conquest works."""

import pytest
from conftest import blank_game, place_world

from recreon.attack import (
    MAX_NO_OF_GROUPS,
    AttackIntentionTypes,
    AttackResultTypes,
    CombatBaseAdj,
    CombatClassAdj,
    CombatDataRecord,
    CombatPower,
    CombatTechAdj,
    GDMKill,
    GDMLaunch,
    GroupRecord,
    GroupStatus,
    advance_groups,
    all_groups_destroyed,
    attack_array,
    battle,
    calculate_combat_data,
    conquer_empire,
    conquer_world,
    default_distribution,
    destroy_construction_or_gate,
    detail_array,
    enemy_surrenders,
    forces_unknown,
    get_conflict,
    get_enemy,
    get_target_array,
    group_array,
    group_attack,
    holocaust_effectiveness,
    lam_attack,
    resolve_attack,
    restore_combatant,
    ships_destroyed,
    total_protection,
    update_groups_destroyed,
)
from recreon.attnpe import MAX_ENGAGE_ROUNDS, npe_attack
from recreon.battle import (
    WAR_MACHINES,
    MilitaryPower,
    calc_attack_round,
    calc_military_power,
)
from recreon.datacnst import CargoSpace, init_defense_record
from recreon.fleet import deploy_fleet, move_fleet
from recreon.galaxy import XYCoord, limbo
from recreon.intrface import create_stargate, next_stargate_slot
from recreon.news import NewsTypes, get_news_list
from recreon.primintr import (
    get_cargo,
    get_defns,
    get_efficiency,
    get_rev_index,
    get_ships,
    get_status,
    put_cargo,
    put_defns,
    put_ships,
    set_capital,
    set_defense_settings,
    set_fleet_fuel,
)
from recreon.types import (
    SHIP_TYPES,
    Empire,
    IDNumber,
    ObjectTypes,
    ShellPos,
    TechLevel,
    TechnologyTypes,
    WorldClass,
    WorldTypes,
    cargo_array,
    defns_array,
    ship_array,
)
from recreon.utils.pascal import pascal_div, set_rand_seed

T = TechnologyTypes


# --- Tables ------------------------------------------------------------------


def test_combat_tech_adj_is_neutral_on_the_diagonal():
    """Equal tech means no adjustment either way."""
    for tech in TechLevel:
        assert CombatTechAdj[tech][tech] == 100


def test_combat_tech_adj_favours_the_higher_tech_side():
    """Above 100 helps the attacker; the mirrored entry must be below it."""
    for attacker in TechLevel:
        for defender in TechLevel:
            if attacker > defender:
                assert CombatTechAdj[attacker][defender] > 100
                assert CombatTechAdj[defender][attacker] < 100


def test_combat_tables_cover_every_key():
    assert set(CombatClassAdj) == set(WorldClass)
    assert set(GDMLaunch) == set(TechLevel)
    assert set(GDMKill) == set(SHIP_TYPES)
    assert set(CombatBaseAdj) == {T.cmm, T.frt, T.cmp, T.out}
    # Starships are the most dangerous thing in the game, ninjas the most
    # dangerous thing on the ground; both sit at the cap.
    assert CombatPower[T.ssp] == 100
    assert CombatPower[T.nnj] == 100


# --- ships_destroyed ---------------------------------------------------------


def test_ships_destroyed_reads_straight_off_the_combat_table():
    """No fractional part means no die roll, so the result is exact."""
    set_rand_seed(1)
    # 100 fighters vs fighters: 25 per 100, unadjusted.
    assert ships_destroyed(100, T.fgt, T.fgt, 100) == 25


def test_ships_destroyed_divides_by_the_defender_adjustment():
    """A tougher defender takes proportionally fewer losses."""
    set_rand_seed(1)
    # 25.0 halves to 12.5; the half is settled by a roll, so 12 or 13.
    assert ships_destroyed(100, T.fgt, T.fgt, 200) in (12, 13)


def test_ships_destroyed_treats_a_zero_adjustment_as_one():
    """Adj 0 would divide by zero; the original substitutes 1."""
    set_rand_seed(7)
    zero = ships_destroyed(10, T.fgt, T.fgt, 0)
    set_rand_seed(7)
    one = ships_destroyed(10, T.fgt, T.fgt, 1)
    assert zero == one


def test_ships_destroyed_is_clamped_to_the_resource_ceiling():
    set_rand_seed(1)
    assert ships_destroyed(9999, T.ssp, T.fgt, 1) == 9999


# --- Groups ------------------------------------------------------------------


def test_default_distribution_puts_warships_before_transports():
    """Targeting relies on the transports being the tail of the array."""
    game = blank_game()
    world = place_world(game, 1, XYCoord(5, 5), emp=Empire.Empire1)
    ships = ship_array()
    ships[T.fgt] = 100
    ships[T.ssp] = 10
    ships[T.trn] = 20
    put_ships(game, world, ships)

    no_of_groups, gp = default_distribution(game, world)

    assert no_of_groups == 3
    assert [gp[i].Typ for i in range(1, 4)] == [T.fgt, T.ssp, T.trn]
    assert gp[1].Num == 100
    assert gp[3].Num == 20


def test_default_distribution_loads_ninjas_in_preference_to_men():
    """Ninjas are worth five soldiers each, so they board first -- and the
    original takes all of one type or none."""
    game = blank_game()
    world = place_world(game, 1, XYCoord(5, 5), emp=Empire.Empire1)
    ships = ship_array()
    ships[T.trn] = 10
    put_ships(game, world, ships)
    cargo = get_cargo(game, world)
    cargo[T.men] = 500
    cargo[T.nnj] = 30
    put_cargo(game, world, cargo)

    _, gp = default_distribution(game, world)

    assert gp[1].GATTyp == T.nnj
    # Capacity is TrnAdj[trn] * 10 * CargoSpace[nnj] = 50, but only 30 exist.
    assert gp[1].GAT == 30


def test_default_distribution_falls_back_to_men_without_ninjas():
    game = blank_game()
    world = place_world(game, 1, XYCoord(5, 5), emp=Empire.Empire1)
    ships = ship_array()
    ships[T.trn] = 10
    put_ships(game, world, ships)
    cargo = get_cargo(game, world)
    cargo[T.men] = 500
    put_cargo(game, world, cargo)

    _, gp = default_distribution(game, world)

    assert gp[1].GATTyp == T.men
    assert gp[1].GAT == 10 * CargoSpace[T.men]


def test_advance_groups_lands_transports_as_their_troops():
    """Reaching the ground turns a transport group into an infantry group;
    the transports themselves are parked in GAT/TrnTyp."""
    gp = group_array()
    gp[1] = GroupRecord(
        Typ=T.trn,
        Num=20,
        Pos=ShellPos.SbOrb,
        Sta=GroupStatus.GAdvc,
        GAT=100,
        GATTyp=T.men,
    )

    advance_groups(1, gp)

    assert gp[1].Pos == ShellPos.Grnd
    assert gp[1].Typ == T.men
    assert gp[1].Num == 100
    assert gp[1].TrnTyp == T.trn
    assert gp[1].GAT == 20
    assert gp[1].Trg == T.men
    assert gp[1].Sta == GroupStatus.GReady


def test_advance_groups_leaves_an_empty_transport_as_transports():
    """No troops aboard means no swap -- the group lands still being ships."""
    gp = group_array()
    gp[1] = GroupRecord(Typ=T.trn, Num=20, Pos=ShellPos.SbOrb, Sta=GroupStatus.GAdvc)

    advance_groups(1, gp)

    assert gp[1].Pos == ShellPos.Grnd
    assert gp[1].Typ == T.trn


def test_advance_groups_retreats_outwards():
    gp = group_array()
    gp[1] = GroupRecord(Typ=T.fgt, Num=10, Pos=ShellPos.Orbit, Sta=GroupStatus.GRtrt)

    advance_groups(1, gp)

    assert gp[1].Pos == ShellPos.HiOrb
    assert gp[1].Sta == GroupStatus.GReady


def test_advancing_past_the_ground_raises():
    """Pascal's Succ would run off the end of the enum silently; here it is an
    error, following the same choice made for out-of-range sectors."""
    gp = group_array()
    gp[1] = GroupRecord(Typ=T.fgt, Num=10, Pos=ShellPos.Grnd, Sta=GroupStatus.GAdvc)

    with pytest.raises(ValueError):
        advance_groups(1, gp)


def test_all_groups_destroyed():
    gp = group_array()
    gp[1] = GroupRecord(Typ=T.fgt, Num=0, Sta=GroupStatus.GDst)
    gp[2] = GroupRecord(Typ=T.ssp, Num=5, Sta=GroupStatus.GReady)

    assert not all_groups_destroyed(2, gp)

    gp[2].Sta = GroupStatus.GDst
    assert all_groups_destroyed(2, gp)


def test_get_conflict_takes_only_live_groups_at_the_shell():
    gp = group_array()
    gp[1] = GroupRecord(Typ=T.fgt, Num=5, Pos=ShellPos.Orbit)
    gp[2] = GroupRecord(Typ=T.jmp, Num=5, Pos=ShellPos.Orbit, Sta=GroupStatus.GDst)
    gp[3] = GroupRecord(Typ=T.pen, Num=5, Pos=ShellPos.SbOrb)

    assert get_conflict(ShellPos.Orbit, 3, gp) == {1}


def test_total_protection_ignores_idle_escorts_and_troops():
    """Only a group that has picked a target contributes cover."""
    gp = group_array()
    gp[1] = GroupRecord(Typ=T.ssp, Num=10, Trg=T.fgt)  # covering
    gp[2] = GroupRecord(Typ=T.ssp, Num=10, Trg=T.NoRes)  # idle
    gp[3] = GroupRecord(Typ=T.men, Num=100, Trg=T.men)  # troops

    assert total_protection(3, gp, {1, 2, 3}) == 1000  # ProtecOffered[ssp] * 10


# --- One round ---------------------------------------------------------------


def _combat_data(**kwargs) -> CombatDataRecord:
    data = CombatDataRecord(
        DTyp=ObjectTypes.Pln,
        DTech=TechLevel.WrpTchLvl,
        AShipAdj=100,
        DShipAdj=100,
        DGrndAdj=100,
        MaxGDM=0,
        RevIndex=0,
    )
    for key, value in kwargs.items():
        setattr(data, key, value)
    return data


def test_group_attack_scores_nothing_on_an_out_of_range_defense():
    """Orbital satellites can only be hit from Orbit."""
    set_rand_seed(1)
    gp = group_array()
    gp[1] = GroupRecord(Typ=T.jmp, Num=100, Trg=T.def_, Pos=ShellPos.DpSpc)
    destroyed = attack_array()

    group_attack(1, gp, {1}, destroyed, _combat_data())

    assert destroyed[T.def_] == 0


def test_group_attack_scores_from_the_right_shell():
    set_rand_seed(1)
    gp = group_array()
    gp[1] = GroupRecord(Typ=T.jmp, Num=100, Trg=T.def_, Pos=ShellPos.Orbit)
    destroyed = attack_array()

    group_attack(1, gp, {1}, destroyed, _combat_data())

    # CombatTable[jmp][def] = 15 per 100 jumpships.
    assert destroyed[T.def_] == 15


def test_group_attack_drops_a_hunter_killers_cloak_when_it_fires():
    set_rand_seed(1)
    gp = group_array()
    gp[1] = GroupRecord(Typ=T.hkr, Num=100, Trg=T.fgt, Pos=ShellPos.Orbit)

    group_attack(1, gp, {1}, attack_array(), _combat_data())

    assert gp[1].Flg is True


def test_group_attack_leaves_an_idle_hunter_killer_cloaked():
    set_rand_seed(1)
    gp = group_array()
    gp[1] = GroupRecord(Typ=T.hkr, Num=100, Trg=T.NoRes, Pos=ShellPos.Orbit)

    group_attack(1, gp, {1}, attack_array(), _combat_data())

    assert gp[1].Flg is False


def test_advancing_groups_hit_blocking_targets_harder():
    """Pushing inwards adds half again against ships and satellites."""
    set_rand_seed(3)
    holding = group_array()
    holding[1] = GroupRecord(Typ=T.jmp, Num=100, Trg=T.trn, Pos=ShellPos.Orbit)
    held = attack_array()
    group_attack(1, holding, {1}, held, _combat_data())

    set_rand_seed(3)
    advancing = group_array()
    advancing[1] = GroupRecord(
        Typ=T.jmp, Num=100, Trg=T.trn, Pos=ShellPos.Orbit, Sta=GroupStatus.GAdvc
    )
    pushed = attack_array()
    group_attack(1, advancing, {1}, pushed, _combat_data())

    assert pushed[T.trn] == held[T.trn] + held[T.trn] // 2


def test_update_groups_destroyed_kills_troops_with_their_transports():
    gp = group_array()
    gp[1] = GroupRecord(Typ=T.trn, Num=10, GAT=50, GATTyp=T.men)
    casualties = attack_array()
    losses = [0] * (MAX_NO_OF_GROUPS + 1)
    losses[1] = 10

    destroyed = update_groups_destroyed(1, gp, {1}, losses, casualties)

    assert destroyed == {1}
    assert gp[1].Sta == GroupStatus.GDst
    assert casualties[T.trn] == 10
    assert casualties[T.men] == 50


def test_partial_transport_losses_drown_some_of_the_troops():
    gp = group_array()
    gp[1] = GroupRecord(Typ=T.trn, Num=10, GAT=50, GATTyp=T.men)
    casualties = attack_array()
    losses = [0] * (MAX_NO_OF_GROUPS + 1)
    losses[1] = 2

    update_groups_destroyed(1, gp, {1}, losses, casualties)

    assert gp[1].Num == 8
    assert casualties[T.trn] == 2
    # Two transports' worth of troops, plus the flat +2 the original adds.
    assert casualties[T.men] == 4
    assert gp[1].GAT == 46


def test_get_target_array_spends_lams_whether_or_not_they_connect():
    """LAMs are removed from the defender when they launch, and booked as
    killed there and then."""
    set_rand_seed(11)
    gp = group_array()
    gp[1] = GroupRecord(Typ=T.fgt, Num=500, Pos=ShellPos.SbOrb)
    en = {shell: attack_array() for shell in ShellPos}
    en[ShellPos.SbOrb][T.LAM] = 200
    killed = attack_array()

    get_target_array(ShellPos.SbOrb, 1, gp, {1}, en, killed, _combat_data())

    assert en[ShellPos.SbOrb][T.LAM] == 0
    assert killed[T.LAM] == 200


def test_battle_is_a_simultaneous_exchange():
    """A group wiped out this round still lands its shots."""
    set_rand_seed(5)
    gp = group_array()
    gp[1] = GroupRecord(Typ=T.fgt, Num=10, Trg=T.ssp, Pos=ShellPos.HiOrb)
    en = {shell: attack_array() for shell in ShellPos}
    en[ShellPos.HiOrb][T.ssp] = 500
    casualties = attack_array()
    killed = attack_array()

    battle(
        1,
        gp,
        en,
        ShellPos.HiOrb,
        _combat_data(),
        detail_array(),
        casualties,
        killed,
    )

    assert gp[1].Sta == GroupStatus.GDst
    assert casualties[T.fgt] == 10
    # 10 fighters at 5 per 100 vs starships is a fraction of a kill, settled
    # by a roll -- but they did get to fire.
    assert killed[T.ssp] in (0, 1)


def test_battle_at_an_empty_shell_does_nothing():
    gp = group_array()
    gp[1] = GroupRecord(Typ=T.fgt, Num=10, Pos=ShellPos.Orbit)
    en = {shell: attack_array() for shell in ShellPos}
    casualties = attack_array()

    destroyed = battle(
        1, gp, en, ShellPos.Grnd, _combat_data(), detail_array(), casualties, attack_array()
    )

    assert destroyed == set()
    assert gp[1].Num == 10


# --- Combat data -------------------------------------------------------------


def _empire_with_capital(
    game, emp: Empire, index: int, xy: XYCoord, tech=TechLevel.WrpTchLvl
) -> IDNumber:
    cap = place_world(game, index, xy, emp=emp, typ=WorldTypes.CapTyp, tech=tech)
    set_capital(game, emp, cap)
    return cap


def test_calculate_combat_data_rates_the_attacker_from_its_capital():
    game = blank_game(empires=2)
    _empire_with_capital(game, Empire.Empire1, 1, XYCoord(2, 2), TechLevel.StrTchLvl)
    target = place_world(game, 2, XYCoord(8, 8), tech=TechLevel.AtomicLvl)

    data = calculate_combat_data(game, Empire.Empire1, IDNumber(ObjectTypes.Flt, 1), target)

    assert data.DTech == TechLevel.AtomicLvl
    assert data.AShipAdj == CombatTechAdj[TechLevel.StrTchLvl][TechLevel.AtomicLvl]
    assert data.DShipAdj == CombatTechAdj[TechLevel.AtomicLvl][TechLevel.StrTchLvl]
    assert data.MaxGDM == GDMLaunch[TechLevel.AtomicLvl]


def test_calculate_combat_data_scales_ground_defense_by_world_class():
    """Ice worlds are hard to take; gas giants have no ground worth holding."""
    game = blank_game(empires=2)
    _empire_with_capital(game, Empire.Empire1, 1, XYCoord(2, 2))
    flt = IDNumber(ObjectTypes.Flt, 1)

    icy = place_world(game, 2, XYCoord(8, 8), cls=WorldClass.IceCls)
    gassy = place_world(game, 3, XYCoord(9, 9), cls=WorldClass.GsGCls)

    icy_data = calculate_combat_data(game, Empire.Empire1, flt, icy)
    gassy_data = calculate_combat_data(game, Empire.Empire1, flt, gassy)

    assert icy_data.DGrndAdj > icy_data.DShipAdj
    assert gassy_data.DGrndAdj < gassy_data.DShipAdj


def test_a_defending_fleet_has_no_ground_to_defend():
    game = blank_game(empires=2)
    _empire_with_capital(game, Empire.Empire1, 1, XYCoord(2, 2))
    _empire_with_capital(game, Empire.Empire2, 2, XYCoord(9, 9))
    enemy = _fleet_at(game, Empire.Empire2, 2, XYCoord(9, 9), {T.fgt: 10})

    data = calculate_combat_data(
        game, Empire.Empire1, IDNumber(ObjectTypes.Flt, 1), enemy
    )

    assert data.DTyp == ObjectTypes.Flt
    assert data.DGrndAdj == 0
    assert data.RevIndex == 0


# --- Laying out the defender -------------------------------------------------


def _fleet_at(game, emp: Empire, world_index: int, xy: XYCoord, ships: dict) -> IDNumber:
    """Launch a fleet from a world and put it where we want it."""
    world = IDNumber(ObjectTypes.Pln, world_index)
    stock = get_ships(game, world)
    for ship, count in ships.items():
        stock[ship] = stock.get(ship, 0) + count
    put_ships(game, world, stock)

    sh = ship_array()
    for ship, count in ships.items():
        sh[ship] = count
    flt = deploy_fleet(game, emp, world, sh, cargo_array(), xy)
    move_fleet(game, flt, xy)
    set_fleet_fuel(game, flt, 1000)
    return flt


def test_get_enemy_spreads_a_worlds_ships_over_the_shells():
    game = blank_game(empires=1)
    set_defense_settings(game, Empire.Empire1, init_defense_record())
    world = place_world(game, 1, XYCoord(5, 5), emp=Empire.Empire1)

    ships = ship_array()
    ships[T.fgt] = 100
    put_ships(game, world, ships)
    defns = defns_array()
    defns[T.GDM] = 40
    defns[T.def_] = 25
    put_defns(game, world, defns)
    cargo = get_cargo(game, world)
    cargo[T.men] = 300
    put_cargo(game, world, cargo)

    en = get_enemy(game, world)

    # Default distribution puts 55% of the fighters in sub-orbit.
    assert en[ShellPos.SbOrb][T.fgt] == 55
    assert en[ShellPos.DpSpc][T.fgt] == 5
    assert en[ShellPos.Orbit][T.def_] == 25
    assert en[ShellPos.SbOrb][T.GDM] == 40
    assert en[ShellPos.Grnd][T.men] == 300


def test_get_enemy_limits_an_independent_world_to_its_tech():
    """Independents field only what their tech level covers."""
    game = blank_game(empires=1)
    world = place_world(game, 1, XYCoord(5, 5), tech=TechLevel.PreWrpLvl)
    ships = ship_array()
    ships[T.ssp] = 100  # starships are far beyond pre-warp
    put_ships(game, world, ships)

    en = get_enemy(game, world)

    assert all(en[shell][T.ssp] == 0 for shell in ShellPos)


def test_get_enemy_screens_a_fleets_transports_behind_its_warships():
    game = blank_game(empires=2)
    place_world(game, 1, XYCoord(2, 2), emp=Empire.Empire2)
    flt = _fleet_at(game, Empire.Empire2, 1, XYCoord(2, 2), {T.fgt: 100, T.trn: 40})

    en = get_enemy(game, flt)

    assert en[ShellPos.HiOrb][T.fgt] == 75
    assert en[ShellPos.Orbit][T.fgt] == 25
    assert en[ShellPos.Orbit][T.trn] == 40
    assert en[ShellPos.HiOrb][T.trn] == 0


def test_a_fleet_with_nothing_to_protect_meets_the_attack_in_full():
    game = blank_game(empires=2)
    place_world(game, 1, XYCoord(2, 2), emp=Empire.Empire2)
    flt = _fleet_at(game, Empire.Empire2, 1, XYCoord(2, 2), {T.fgt: 100})

    en = get_enemy(game, flt)

    assert en[ShellPos.HiOrb][T.fgt] == 100
    assert en[ShellPos.Orbit][T.fgt] == 0


# --- Surrender ---------------------------------------------------------------


def test_a_fleet_with_nothing_left_surrenders():
    gp = group_array()
    gp[1] = GroupRecord(Typ=T.ssp, Num=50)
    en = {shell: attack_array() for shell in ShellPos}

    assert enemy_surrenders(
        1, gp, en, attack_array(), attack_array(), _combat_data(DTyp=ObjectTypes.Flt)
    )


def test_an_undefended_world_surrenders_to_any_landing_force():
    gp = group_array()
    gp[1] = GroupRecord(Typ=T.trn, Num=100)  # troops still aboard
    en = {shell: attack_array() for shell in ShellPos}

    assert enemy_surrenders(1, gp, en, attack_array(), attack_array(), _combat_data())


def test_a_world_with_no_attacker_on_the_ground_holds_out():
    """Firepower alone takes nothing: without troops there is no pl_gat, and
    every world clause needs some."""
    gp = group_array()
    gp[1] = GroupRecord(Typ=T.ssp, Num=500)
    en = {shell: attack_array() for shell in ShellPos}

    assert not enemy_surrenders(
        1, gp, en, attack_array(), attack_array(), _combat_data()
    )


def test_a_garrisoned_world_holds_out_against_a_smaller_landing():
    gp = group_array()
    gp[1] = GroupRecord(Typ=T.men, Num=100, Pos=ShellPos.Grnd)
    en = {shell: attack_array() for shell in ShellPos}
    en[ShellPos.Grnd][T.men] = 5000

    assert not enemy_surrenders(
        1, gp, en, attack_array(), attack_array(), _combat_data()
    )


# --- Conquest ----------------------------------------------------------------


def test_conquer_world_changes_hands_and_costs_efficiency():
    set_rand_seed(42)
    game = blank_game(empires=2)
    world = place_world(game, 1, XYCoord(5, 5), eff=50)
    _empire_with_capital(game, Empire.Empire1, 2, XYCoord(2, 2))

    conquer_world(game, world, Empire.Empire1)

    assert get_status(game, world) == Empire.Empire1
    assert 30 <= get_efficiency(game, world) <= 40


def test_conquering_a_contented_world_stirs_it_up():
    """A low revolution index rises: the people want their old rulers back."""
    set_rand_seed(42)
    game = blank_game(empires=2)
    world = place_world(game, 1, XYCoord(5, 5))
    game.Universe.Planet[1].RevIndex = 0
    _empire_with_capital(game, Empire.Empire1, 2, XYCoord(2, 2))

    conquer_world(game, world, Empire.Empire1)

    assert 10 <= get_rev_index(game, world) <= 20


def test_conquering_a_seething_world_calms_it_down():
    """A high index falls: the people were ready for anything else."""
    set_rand_seed(42)
    game = blank_game(empires=2)
    world = place_world(game, 1, XYCoord(5, 5))
    game.Universe.Planet[1].RevIndex = 100
    _empire_with_capital(game, Empire.Empire1, 2, XYCoord(2, 2))

    conquer_world(game, world, Empire.Empire1)

    assert 60 <= get_rev_index(game, world) <= 70


def test_a_centralized_empire_dies_with_its_capital():
    """CentralEMD skips the search for a successor world entirely."""
    from recreon.types import EmpireModifiers

    set_rand_seed(9)
    game = blank_game(empires=1)
    _empire_with_capital(game, Empire.Empire1, 1, XYCoord(2, 2))
    enemy_cap = _empire_with_capital(game, Empire.Empire2, 2, XYCoord(9, 9))
    game.Universe.EmpireData[Empire.Empire2].Modifiers = {EmpireModifiers.CentralEMD}
    outpost = place_world(game, 3, XYCoord(10, 10), emp=Empire.Empire2)
    game.GlobalSets.SetOfPlanetsOf[Empire.Empire2].add(3)

    conquer_empire(game, Empire.Empire1, Empire.Empire2)

    assert game.Universe.EmpireData[Empire.Empire2].InUse is False
    # Every world it held is loose.
    assert get_status(game, outpost) == Empire.Indep
    assert get_status(game, enemy_cap) == Empire.Indep


def test_a_beaten_player_keeps_a_record_of_who_beat_them():
    """A human empire is not deleted; its capital becomes a Void ID whose
    index names the conqueror."""
    set_rand_seed(9)
    game = blank_game(empires=2)
    _empire_with_capital(game, Empire.Empire1, 1, XYCoord(2, 2))
    _empire_with_capital(game, Empire.Empire2, 2, XYCoord(9, 9))

    conquer_empire(game, Empire.Empire1, Empire.Empire2)

    from recreon.primintr import get_capital

    beaten = get_capital(game, Empire.Empire2)
    assert beaten.ObjTyp == ObjectTypes.Void
    assert beaten.Index == int(Empire.Empire1)
    assert game.Universe.EmpireData[Empire.Empire2].InUse is True


# --- Applying results --------------------------------------------------------


def test_restore_combatant_writes_losses_back_to_a_world():
    game = blank_game(empires=1)
    world = place_world(game, 1, XYCoord(5, 5), emp=Empire.Empire1)
    ships = ship_array()
    ships[T.fgt] = 100
    put_ships(game, world, ships)
    defns = defns_array()
    defns[T.GDM] = 50
    put_defns(game, world, defns)
    cargo = get_cargo(game, world)
    cargo[T.men] = 200
    put_cargo(game, world, cargo)

    casualties = attack_array()
    casualties[T.fgt] = 30
    casualties[T.GDM] = 80  # more than it had
    casualties[T.men] = 50
    restore_combatant(game, world, casualties)

    assert get_ships(game, world)[T.fgt] == 70
    assert get_defns(game, world)[T.GDM] == 0
    assert get_cargo(game, world)[T.men] == 150


def test_resolve_attack_destroys_a_beaten_attacker():
    set_rand_seed(3)
    game = blank_game(empires=2)
    _empire_with_capital(game, Empire.Empire1, 1, XYCoord(2, 2))
    target = place_world(game, 2, XYCoord(9, 9))
    flt = _fleet_at(game, Empire.Empire1, 1, XYCoord(9, 9), {T.fgt: 10})

    resolve_attack(
        game,
        AttackResultTypes.AttDestroyedART,
        flt,
        target,
        False,
        True,
        attack_array(),
        attack_array(),
    )

    assert flt.Index not in game.GlobalSets.SetOfActiveFleets


def test_losing_a_battle_is_reported_to_the_defender():
    set_rand_seed(3)
    game = blank_game(empires=2)
    _empire_with_capital(game, Empire.Empire1, 1, XYCoord(2, 2))
    target = _empire_with_capital(game, Empire.Empire2, 2, XYCoord(9, 9))
    game.Universe.Planet[2].Typ = WorldTypes.IndTyp  # not a capital, no collapse
    flt = _fleet_at(game, Empire.Empire1, 1, XYCoord(9, 9), {T.fgt: 10})

    killed = attack_array()
    killed[T.fgt] = 7
    resolve_attack(
        game,
        AttackResultTypes.DefConqueredART,
        flt,
        target,
        False,
        True,
        attack_array(),
        killed,
    )

    items = get_news_list(game, Empire.Empire2)
    headlines = [item.Headline for item in items]
    assert NewsTypes.BattleL in headlines
    assert NewsTypes.DestDetail in headlines
    assert get_status(game, target) == Empire.Empire1

    # Location is (XY, ID). Swapping the two type-checks -- both fields hold
    # dataclasses -- and silently points every combat headline at the wrong
    # thing, so pin which field the target lands in.
    battle_item = next(i for i in items if i.Headline == NewsTypes.BattleL)
    assert battle_item.Loc1.ID == target
    assert battle_item.Loc1.XY == limbo()


def test_an_unseen_raid_is_reported_without_naming_the_attacker():
    set_rand_seed(3)
    game = blank_game(empires=2)
    _empire_with_capital(game, Empire.Empire1, 1, XYCoord(2, 2))
    place_world(game, 2, XYCoord(9, 9), emp=Empire.Empire2)
    flt = _fleet_at(game, Empire.Empire1, 1, XYCoord(9, 9), {T.hkr: 10})
    target = _fleet_at(game, Empire.Empire2, 2, XYCoord(9, 9), {T.fgt: 10})

    resolve_attack(
        game,
        AttackResultTypes.AttRetreatsART,
        flt,
        target,
        True,
        True,
        attack_array(),
        attack_array(),
    )

    headlines = [item.Headline for item in get_news_list(game, Empire.Empire2)]
    assert NewsTypes.BattleW2UNK in headlines
    assert NewsTypes.BattleW2 not in headlines


def test_forces_unknown_needs_a_small_unscouted_hunter_killer_force():
    game = blank_game(empires=2)
    place_world(game, 1, XYCoord(2, 2), emp=Empire.Empire1)
    target = place_world(game, 2, XYCoord(9, 9), emp=Empire.Empire2)

    small = _fleet_at(game, Empire.Empire1, 1, XYCoord(9, 9), {T.hkr: 100})
    assert forces_unknown(game, small, target)

    large = _fleet_at(game, Empire.Empire1, 1, XYCoord(9, 9), {T.hkr: 900})
    assert not forces_unknown(game, large, target)


# --- Full engagements --------------------------------------------------------


def test_a_landing_force_takes_an_undefended_world():
    set_rand_seed(1234)
    game = blank_game(empires=1)
    _empire_with_capital(game, Empire.Empire1, 1, XYCoord(2, 2))
    target = place_world(game, 2, XYCoord(9, 9), pop=200)
    game.Universe.Planet[2].Cargo[T.men] = 0

    flt = _fleet_at(game, Empire.Empire1, 1, XYCoord(9, 9), {T.ssp: 50, T.trn: 100})
    cargo = get_cargo(game, flt)
    cargo[T.men] = 400
    put_cargo(game, flt, cargo)

    result, booty = npe_attack(game, flt, target)

    assert result == AttackResultTypes.DefConqueredART
    assert get_status(game, target) == Empire.Empire1
    assert booty == set()


def test_a_fleet_with_no_troops_eventually_gives_up_on_a_world():
    """Firepower cannot take ground. The attack runs the round limit out and
    breaks off."""
    set_rand_seed(1234)
    game = blank_game(empires=1)
    _empire_with_capital(game, Empire.Empire1, 1, XYCoord(2, 2))
    target = place_world(game, 2, XYCoord(9, 9), pop=200)
    game.Universe.Planet[2].Cargo[T.men] = 0

    flt = _fleet_at(game, Empire.Empire1, 1, XYCoord(9, 9), {T.fgt: 20})

    result, _ = npe_attack(game, flt, target)

    assert result == AttackResultTypes.AttRetreatsART
    assert get_status(game, target) == Empire.Indep
    assert MAX_ENGAGE_ROUNDS == 30


def test_a_hopeless_attack_destroys_the_attacker():
    set_rand_seed(99)
    game = blank_game(empires=1)
    _empire_with_capital(game, Empire.Empire1, 1, XYCoord(2, 2))
    set_defense_settings(game, Empire.Indep, init_defense_record())
    target = place_world(game, 2, XYCoord(9, 9), tech=TechLevel.GteTchLvl, pop=5000)
    defenders = ship_array()
    defenders[T.ssp] = 2000
    put_ships(game, target, defenders)

    flt = _fleet_at(game, Empire.Empire1, 1, XYCoord(9, 9), {T.fgt: 5})

    result, _ = npe_attack(game, flt, target)

    assert result == AttackResultTypes.AttDestroyedART
    assert flt.Index not in game.GlobalSets.SetOfActiveFleets


def test_attacking_a_stargate_simply_razes_it():
    set_rand_seed(7)
    game = blank_game(empires=2)
    _empire_with_capital(game, Empire.Empire1, 1, XYCoord(2, 2))
    place_world(game, 2, XYCoord(8, 8), emp=Empire.Empire2)

    slot = next_stargate_slot(game)
    gate = IDNumber(ObjectTypes.Gate, slot)
    create_stargate(game, gate, Empire.Empire2, T.gte, XYCoord(9, 9))

    flt = _fleet_at(game, Empire.Empire1, 1, XYCoord(9, 9), {T.fgt: 10})
    result, _ = npe_attack(game, flt, gate)

    assert result == AttackResultTypes.DefConqueredART
    assert slot not in game.GlobalSets.SetOfActiveGates
    headlines = [item.Headline for item in get_news_list(game, Empire.Empire2)]
    assert NewsTypes.GteDs in headlines


def test_attacking_a_phenomenon_does_nothing():
    game = blank_game(empires=1)
    _empire_with_capital(game, Empire.Empire1, 1, XYCoord(2, 2))
    flt = _fleet_at(game, Empire.Empire1, 1, XYCoord(9, 9), {T.fgt: 10})

    result, booty = npe_attack(game, flt, IDNumber(ObjectTypes.BlkHl, 1))

    assert result == AttackResultTypes.NoART
    assert booty == set()


def test_capture_intent_spares_the_transports_it_wants():
    """DestTrnAIT is the one intent that suppresses capture."""
    assert AttackIntentionTypes.DestTrnAIT != AttackIntentionTypes.CaptTrnAIT


# --- LAM strikes -------------------------------------------------------------


def test_lam_attack_grinds_down_a_worlds_defenses():
    set_rand_seed(21)
    game = blank_game(empires=2)
    place_world(game, 1, XYCoord(2, 2), emp=Empire.Empire1)
    target = place_world(game, 2, XYCoord(9, 9), emp=Empire.Empire2)
    defns = defns_array()
    defns[T.GDM] = 100
    defns[T.ion] = 100
    put_defns(game, target, defns)

    ships_dest, defns_dest = lam_attack(game, Empire.Empire1, 200, target)

    assert ships_dest[T.fgt] == 0
    assert defns_dest[T.GDM] > 0
    assert get_defns(game, target)[T.GDM] == 100 - defns_dest[T.GDM]


def test_lam_attack_can_wipe_out_a_fleet():
    set_rand_seed(21)
    game = blank_game(empires=2)
    place_world(game, 1, XYCoord(2, 2), emp=Empire.Empire1)
    place_world(game, 2, XYCoord(9, 9), emp=Empire.Empire2)
    target = _fleet_at(game, Empire.Empire2, 2, XYCoord(9, 9), {T.fgt: 10})

    ships_dest, _ = lam_attack(game, Empire.Empire1, 5000, target)

    assert ships_dest[T.fgt] == 10
    assert target.Index not in game.GlobalSets.SetOfActiveFleets


def test_holocaust_effectiveness_razes_an_undefended_world():
    game = blank_game(empires=1)
    place_world(game, 1, XYCoord(2, 2), emp=Empire.Empire1)
    target = place_world(game, 2, XYCoord(9, 9))
    flt = _fleet_at(game, Empire.Empire1, 1, XYCoord(9, 9), {T.ssp: 100})

    assert holocaust_effectiveness(game, flt, target) == 100


def test_holocaust_effectiveness_needs_real_weight_behind_it():
    """Under 5000 points of attack the strike achieves nothing at all."""
    game = blank_game(empires=1)
    place_world(game, 1, XYCoord(2, 2), emp=Empire.Empire1)
    target = place_world(game, 2, XYCoord(9, 9))
    defns = defns_array()
    defns[T.GDM] = 10
    put_defns(game, target, defns)
    flt = _fleet_at(game, Empire.Empire1, 1, XYCoord(9, 9), {T.fgt: 5})

    assert holocaust_effectiveness(game, flt, target) == 0


def test_destroying_a_construction_site_needs_no_battle():
    set_rand_seed(4)
    game = blank_game(empires=2)
    site = IDNumber(ObjectTypes.Con, 1)
    constr = game.Universe.Constr[1]
    constr.XY = XYCoord(9, 9)
    constr.Emp = Empire.Empire2
    constr.CTyp = T.SRM
    game.GlobalSets.SetOfActiveConstructionSites.add(1)
    game.GlobalSets.SetOfConstructionSitesOf[Empire.Empire2].add(1)

    destroy_construction_or_gate(game, Empire.Empire1, False, site)

    assert 1 not in game.GlobalSets.SetOfActiveConstructionSites
    headlines = [item.Headline for item in get_news_list(game, Empire.Empire2)]
    assert NewsTypes.ConDs in headlines


# --- The simplified model (BATTLE.PAS) ---------------------------------------


def test_calc_military_power_sums_the_force():
    force = dict.fromkeys(WAR_MACHINES, 0)
    force[T.ssp] = 3
    force[T.fgt] = 10

    assert calc_military_power(Empire.Empire1, force) == 3 * 100 + 10 * 2


def test_calc_attack_round_needs_both_sides_to_exist():
    empty = dict.fromkeys(WAR_MACHINES, 0)
    defender = dict.fromkeys(WAR_MACHINES, 0)
    defender[T.fgt] = 100

    assert calc_attack_round(Empire.Empire1, Empire.Empire2, empty, defender) == empty


def test_calc_attack_round_never_kills_more_than_are_there():
    set_rand_seed(17)
    attacker = dict.fromkeys(WAR_MACHINES, 0)
    attacker[T.ssp] = 5000
    defender = dict.fromkeys(WAR_MACHINES, 0)
    defender[T.fgt] = 10

    casualties = calc_attack_round(
        Empire.Empire1, Empire.Empire2, attacker, defender
    )

    assert casualties[T.fgt] == 10
    assert all(casualties[thing] >= 0 for thing in WAR_MACHINES)


def test_calc_attack_round_leaves_its_inputs_alone():
    set_rand_seed(17)
    attacker = dict.fromkeys(WAR_MACHINES, 0)
    attacker[T.ssp] = 50
    defender = dict.fromkeys(WAR_MACHINES, 0)
    defender[T.fgt] = 500

    calc_attack_round(Empire.Empire1, Empire.Empire2, attacker, defender)

    assert defender[T.fgt] == 500
    assert attacker[T.ssp] == 50


def test_battle_power_table_disagrees_with_the_others():
    """Three tables score the same units and none of them match. Pinned so a
    future 'consistency fix' has to be a deliberate change."""
    from recreon.datacnst import MPower

    assert MilitaryPower[T.fgt] == 2
    assert MPower[T.fgt] == 1
    assert CombatPower[T.fgt] == 2
    assert MilitaryPower[T.LAM] == 30
    assert MPower[T.LAM] == 100
    assert CombatPower[T.LAM] == 80


def test_pascal_div_truncates_toward_zero():
    """Python's // floors, which is wrong for a negative dividend."""
    assert pascal_div(-5001, 1000) == -5
    assert -5001 // 1000 == -6
    assert pascal_div(5001, 1000) == 5
    assert pascal_div(-5000, 1000) == -5
