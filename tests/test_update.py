"""Milestone 3: worlds produce, populations grow, tech advances."""

import pytest

from recreon.datacnst import BasePop, OptMilitary, ThgAdj
from recreon.galaxy import XYCoord
from conftest import blank_game, place_world
from recreon.news import NewsTypes
from recreon.primintr import change_rev_index, get_issp, set_issp
from recreon.types import (
    Empire,
    IDNumber,
    IndusTypes,
    ObjectTypes,
    SpecialConditions,
    TechLevel,
    TechnologyTypes,
    WorldClass,
    WorldTypes,
    indus_range,
)
from recreon.update import (
    MaxPop,
    hostile_life,
    produce_raw_material,
    production,
    update_efficiency,
    update_military,
    update_population,
    update_universe,
    update_world,
    use_up_ambrosia,
    use_up_food,
)
from recreon.utils.pascal import set_rand_seed

T = TechnologyTypes


@pytest.fixture(autouse=True)
def _seeded():
    set_rand_seed(1234)


def make_world(
    game=None,
    *,
    typ=WorldTypes.CapTyp,
    cls=WorldClass.EthCls,
    pop=800,
    eff=60,
    emp=Empire.Empire1,
):
    game = game or blank_game(size=20, empires=1)
    world = place_world(
        game, 1, XYCoord(5, 5), emp=emp, cls=cls, typ=typ, pop=pop, eff=eff
    )
    game.Universe.EmpireData[Empire.Empire1].Capital = world
    return game, world


# --- The industry-range trap -------------------------------------------------


def test_raw_material_production_includes_supply_industry():
    # Pascal's `FOR IndI := CheInd TO TriInd` is an ordinal range covering
    # 1..8, not the three raw-material industries. SupInd sits inside it and
    # is the only source of food; excluding it starves every world.
    assert IndusTypes.SupInd in indus_range(IndusTypes.CheInd, IndusTypes.TriInd)
    assert ThgAdj[IndusTypes.SupInd][T.sup] == 320

    game, world = make_world()
    indus = dict.fromkeys(IndusTypes, 0)
    indus[IndusTypes.SupInd] = 60
    cargo = dict.fromkeys(
        (T.men, T.nnj, T.amb, T.che, T.met, T.sup, T.tri), 0
    )

    produce_raw_material(game, world, indus, {T.sup}, 0.01, cargo)
    assert cargo[T.sup] > 0


def test_manufacturing_excludes_supply_and_trillum_industries():
    # Production runs BioInd..SYTInd; Sup and Tri are raw-material only.
    assert indus_range(IndusTypes.BioInd, IndusTypes.SYTInd) == (
        IndusTypes.BioInd,
        IndusTypes.CheInd,
        IndusTypes.MinInd,
        IndusTypes.SYGInd,
        IndusTypes.SYJInd,
        IndusTypes.SYSInd,
        IndusTypes.SYTInd,
    )


# --- A world over time -------------------------------------------------------


def test_world_sustains_itself_over_a_decade():
    game, world = make_world()
    planet = game.Universe.Planet[1]

    for _ in range(12):
        update_universe(game)

    assert planet.Pop > 800, "population should grow"
    assert planet.Eff > 60, "efficiency should climb"
    assert planet.Cargo[T.sup] > 0, "world should feed itself"
    assert planet.Ships[T.fgt] > 0, "shipyards should build"
    assert planet.RevIndex == 0, "a fed, garrisoned capital should be calm"


def test_industry_grows_toward_its_optimum():
    game, world = make_world()
    planet = game.Universe.Planet[1]
    before = planet.Indus[IndusTypes.SYGInd]

    for _ in range(8):
        update_universe(game)

    assert planet.Indus[IndusTypes.SYGInd] > before


def test_production_consumes_raw_materials():
    game, world = make_world()
    planet = game.Universe.Planet[1]
    planet.Indus = dict.fromkeys(IndusTypes, 0)
    planet.Indus[IndusTypes.SYGInd] = 100
    planet.Cargo[T.met] = 1000
    planet.Cargo[T.che] = 1000
    # Fighters need trillum too; without it RawM cuts production to zero.
    planet.Cargo[T.tri] = 1000

    ships = dict(planet.Ships)
    cargo = {c: planet.Cargo[c] for c in planet.Cargo}
    production(
        game, world, planet.Typ, planet.Indus, {T.fgt, T.met, T.che}, 0.01, ships, cargo, set()
    )

    assert ships[T.fgt] > 0
    assert cargo[T.met] < 1000, "building fighters should consume metal"
    assert cargo[T.tri] < 1000, "and trillum"


def test_production_is_capped_by_available_raw_material():
    game, world = make_world()
    planet = game.Universe.Planet[1]
    planet.Indus = dict.fromkeys(IndusTypes, 0)
    planet.Indus[IndusTypes.SYGInd] = 300

    ships = dict(planet.Ships)
    cargo = dict.fromkeys(planet.Cargo, 0)
    cargo[T.met] = 30  # exactly one fighter's worth
    cargo[T.che] = 5

    reports: set = set()
    production(
        game, world, planet.Typ, planet.Indus, {T.fgt}, 1.0, ships, cargo, reports
    )

    assert ships[T.fgt] <= 100
    assert cargo[T.met] >= 0


def test_shortage_is_reported_once_per_material():
    game, world = make_world()
    planet = game.Universe.Planet[1]
    planet.Indus = dict.fromkeys(IndusTypes, 0)
    planet.Indus[IndusTypes.SYGInd] = 300

    ships = dict(planet.Ships)
    cargo = dict.fromkeys(planet.Cargo, 0)
    reports: set = set()

    production(game, world, planet.Typ, planet.Indus, {T.fgt}, 1.0, ships, cargo, reports)
    first = len(game.News[Empire.Empire1])
    production(game, world, planet.Typ, planet.Indus, {T.fgt}, 1.0, ships, cargo, reports)

    assert len(game.News[Empire.Empire1]) == first, "same material reported twice"


# --- Population --------------------------------------------------------------


def test_population_growth_is_exponential_then_linear():
    cls, tech = WorldClass.EthCls, TechLevel.WrpTchLvl
    # Below the tech base population, growth scales with current size.
    small = update_population(cls, tech, 100) - 100
    bigger = update_population(cls, tech, 400) - 400
    assert bigger > small

    # Above it, growth is a flat rate.
    above = update_population(cls, tech, BasePop[tech] + 100)
    assert above - (BasePop[tech] + 100) == pytest.approx(BasePop[tech] / 100, abs=1)


def test_population_stalls_at_the_class_ceiling():
    cls = WorldClass.IceCls
    ceiling = MaxPop[cls]
    result = update_population(cls, TechLevel.WrpTchLvl, ceiling + 50)
    assert abs(result - (ceiling + 50)) <= 10


def test_tiny_populations_grow_slowly():
    assert 2 <= update_population(WorldClass.EthCls, TechLevel.PreTchLvl, 10) - 10 <= 5


# --- Food and famine ---------------------------------------------------------


def test_well_fed_world_just_consumes():
    game, world = make_world()
    pop, food = use_up_food(game, world, 800, 5000)
    assert pop == 800
    assert food == 5000 - int((800 / 100) * 25)


def test_famine_kills_and_raises_the_revolution_index():
    game, world = make_world()
    planet = game.Universe.Planet[1]

    pop, food = use_up_food(game, world, 1000, 0)
    assert pop < 1000, "people should starve"
    assert food == 0
    assert planet.RevIndex > 0
    assert any(n.Headline == NewsTypes.Starv for n in game.News[Empire.Empire1])


def test_starvation_is_capped_at_a_tenth_of_the_population():
    game, world = make_world()
    pop, _ = use_up_food(game, world, 1000, 0)
    assert pop >= 900


# --- Ambrosia ----------------------------------------------------------------


def test_addicted_world_consumes_ambrosia():
    game, world = make_world()
    special = {SpecialConditions.AmbAddict}
    pop, eff, tech, amb = use_up_ambrosia(
        game,
        world,
        Empire.Empire1,
        special,
        800,
        60,
        TechLevel.WrpTchLvl,
        dict.fromkeys(IndusTypes, 100),
        5000,
    )
    assert amb < 5000
    assert pop == 800, "a supplied addiction harms nobody"


def test_withdrawal_kills_and_wrecks_efficiency():
    game, world = make_world()
    indus = dict.fromkeys(IndusTypes, 100)
    special = {SpecialConditions.AmbAddict}

    pop, eff, tech, amb = use_up_ambrosia(
        game, world, Empire.Empire1, special, 2000, 90, TechLevel.WrpTchLvl, indus, 0
    )

    assert pop < 2000
    assert eff < 90
    assert amb == 0
    assert any(
        n.Headline in (NewsTypes.AddictDie, NewsTypes.RiotsDie)
        for n in game.News[Empire.Empire1]
    )


def test_deaths_from_withdrawal_are_capped_at_a_seventh():
    game, world = make_world()
    special = {SpecialConditions.AmbAddict}
    pop, _, _, _ = use_up_ambrosia(
        game,
        world,
        Empire.Empire1,
        special,
        700,
        90,
        TechLevel.WrpTchLvl,
        dict.fromkeys(IndusTypes, 100),
        0,
    )
    # A seventh of 700 is 100, and riots may take a further share.
    assert pop >= 700 - 100 - 120


# --- Efficiency and tech -----------------------------------------------------


def test_efficiency_climbs_fastest_when_low():
    low = [update_efficiency(Empire.Empire1, 10) - 10 for _ in range(40)]
    high = [update_efficiency(Empire.Empire1, 95) - 95 for _ in range(40)]
    assert sum(low) / len(low) > sum(high) / len(high)


def test_efficiency_never_exceeds_one_hundred():
    for _ in range(50):
        assert update_efficiency(Empire.Empire1, 99) <= 100


def test_independent_worlds_improve_barely():
    values = [update_efficiency(Empire.Indep, 10) - 10 for _ in range(40)]
    assert max(values) <= 1


def test_tech_follows_the_capital():
    game, world = make_world()
    planet = game.Universe.Planet[1]

    # A second world starts behind the capital and should catch up.
    other = place_world(
        game, 2, XYCoord(9, 9), emp=Empire.Empire1, tech=TechLevel.AtomicLvl
    )
    game.Universe.Planet[2].Tech = TechLevel.AtomicLvl

    for _ in range(40):
        update_universe(game)

    assert game.Universe.Planet[2].Tech > TechLevel.AtomicLvl


# --- Military and revolution -------------------------------------------------


def test_military_recruits_toward_the_optimum():
    mpop = update_military(WorldTypes.CapTyp, 1000, 0)
    assert mpop > 0
    # A world already over its optimum recruits nobody.
    assert update_military(WorldTypes.CapTyp, 1000, 9999) == 9999


def test_outposts_raise_no_troops():
    assert OptMilitary[WorldTypes.OutTyp] == 0
    assert update_military(WorldTypes.OutTyp, 1000, 0) == 0


def test_high_revolution_index_can_cost_a_world():
    game, world = make_world(typ=WorldTypes.IndTyp)
    planet = game.Universe.Planet[1]
    change_rev_index(game, world, 100)
    planet.Cargo[T.men] = 0
    planet.Cargo[T.nnj] = 0

    for _ in range(30):
        if planet.Emp == Empire.Indep:
            break
        update_universe(game)

    assert planet.Emp == Empire.Indep, "an ungarrisoned, furious world should secede"


def test_capitals_do_not_rebel():
    game, world = make_world(typ=WorldTypes.CapTyp)
    planet = game.Universe.Planet[1]
    change_rev_index(game, world, 100)

    for _ in range(25):
        update_universe(game)

    assert planet.Emp == Empire.Empire1


# --- Hostile life ------------------------------------------------------------


def test_hostile_life_only_runs_on_hostile_worlds():
    game, world = make_world(cls=WorldClass.HLfCls, pop=500)
    planet = game.Universe.Planet[1]
    planet.Cargo[T.men] = 0
    planet.Cargo[T.nnj] = 0

    for _ in range(20):
        hostile_life(game, world)

    assert any(
        n.Headline in (NewsTypes.HLPopKill, NewsTypes.HLMenKill, NewsTypes.HLJoin)
        for n in game.News[Empire.Empire1]
    )


def test_a_strong_garrison_deters_the_natives():
    game, world = make_world(cls=WorldClass.HLfCls)
    planet = game.Universe.Planet[1]
    planet.Cargo[T.men] = 9000
    planet.Cargo[T.nnj] = 500
    before = planet.Pop

    for _ in range(20):
        hostile_life(game, world)

    assert planet.Pop == before


# --- Trillum -----------------------------------------------------------------


def test_trillum_reserves_deplete_as_it_is_mined():
    game, world = make_world(typ=WorldTypes.TriTyp)
    planet = game.Universe.Planet[1]
    before = planet.TriReserve

    for _ in range(10):
        update_universe(game)

    assert planet.TriReserve < before
    assert planet.Cargo[T.tri] > 0


def test_exhausted_trillum_stops_production_and_angers_the_world():
    game, world = make_world(typ=WorldTypes.TriTyp)
    planet = game.Universe.Planet[1]
    planet.TriReserve = 0

    update_universe(game)

    assert any(n.Headline == NewsTypes.NoTriRes for n in game.News[Empire.Empire1])
    assert planet.RevIndex > 0


# --- ISSP --------------------------------------------------------------------


def test_issp_nibbles_are_independent():
    game, world = make_world()

    set_issp(game, world, IndusTypes.CheInd, 2)
    set_issp(game, world, IndusTypes.MinInd, 9)
    set_issp(game, world, IndusTypes.SupInd, 3)
    set_issp(game, world, IndusTypes.TriInd, 7)

    assert get_issp(game, world, IndusTypes.CheInd) == 2
    assert get_issp(game, world, IndusTypes.MinInd) == 9
    assert get_issp(game, world, IndusTypes.SupInd) == 3
    assert get_issp(game, world, IndusTypes.TriInd) == 7


def test_production_industries_have_a_fixed_issp():
    game, world = make_world()
    for ind in (IndusTypes.BioInd, IndusTypes.SYGInd, IndusTypes.SYSInd):
        assert get_issp(game, world, ind) == 6
        set_issp(game, world, ind, 0)
        assert get_issp(game, world, ind) == 6, "should be unsettable"


def test_default_issp_is_self_sufficient_across_the_board():
    game, world = make_world()
    from recreon.datacnst import ISSP, NORMAL_ISSP

    for ind in (IndusTypes.CheInd, IndusTypes.MinInd, IndusTypes.SupInd, IndusTypes.TriInd):
        assert get_issp(game, world, ind) == NORMAL_ISSP
        assert ISSP[get_issp(game, world, ind)] == 1.00


# --- Starbases ---------------------------------------------------------------


def test_only_industrial_complexes_have_an_economy():
    from recreon.intrface import create_starbase

    game, _ = make_world()
    outpost = IDNumber(ObjectTypes.Base, 1)
    create_starbase(game, outpost, Empire.Empire1, XYCoord(8, 8), T.out)
    base = game.Universe.Starbase[1]
    base.Pop = 100
    base.Tech = TechLevel.WrpTchLvl
    base.Indus[IndusTypes.SYGInd] = 50

    update_world(game, outpost)

    assert base.Ships[T.fgt] == 0, "an outpost should build nothing"
