"""Milestone 3: worlds produce, populations grow, tech advances."""

import pytest
from conftest import blank_game, place_world

from recreon.datacnst import BasePop, OptMilitary, TechDev, ThgAdj
from recreon.galaxy import XYCoord
from recreon.news import NewsTypes
from recreon.primintr import change_rev_index, get_issp, set_issp
from recreon.types import (
    MAX_RESOURCES,
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

    # A second world starts behind the capital and should catch up.
    place_world(
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


# --- The supply links --------------------------------------------------------
#
# `SupplyLink` and `SurplusLink` are a pair, and only make sense together: an
# industrial complex pulls raw materials in from the mines around it, runs its
# economy, and pushes back whatever it could not keep. Both sweep the same eight
# sectors under the same test for a friendly raw-material world.


def complex_with_a_mine(mine_typ=WorldTypes.MinTyp, mine_emp=Empire.Empire1):
    """An industrial complex at 10,10 with one mine due north of it."""
    from recreon.intrface import create_starbase

    game = blank_game(size=20, empires=2)
    base = IDNumber(ObjectTypes.Base, 1)
    create_starbase(game, base, Empire.Empire1, XYCoord(10, 10), T.cmp)
    mine = place_world(game, 1, XYCoord(10, 9), emp=mine_emp, typ=mine_typ)
    return game, base, mine


def test_supply_link_draws_a_mine_down_to_a_working_reserve():
    from recreon.primintr import get_cargo, put_cargo
    from recreon.types import cargo_array
    from recreon.update import supply_link

    game, base, mine = complex_with_a_mine()
    cargo = cargo_array()
    cargo[T.che] = 5000
    put_cargo(game, mine, cargo)
    temp = {k: 0 for k in T}

    supply_link(game, base, temp)

    # `Rnd(200,250)` is what stays behind, so the mine keeps a working stock
    # and the complex takes the rest.
    assert 200 <= get_cargo(game, mine)[T.che] <= 250
    assert temp[T.che] == 5000 - get_cargo(game, mine)[T.che]


def test_supply_link_leaves_a_mine_that_is_barely_stocked_alone():
    from recreon.primintr import get_cargo, put_cargo
    from recreon.types import cargo_array
    from recreon.update import supply_link

    game, base, mine = complex_with_a_mine()
    cargo = cargo_array()
    cargo[T.che] = 250
    put_cargo(game, mine, cargo)
    temp = {k: 0 for k in T}

    supply_link(game, base, temp)

    assert get_cargo(game, mine)[T.che] == 250
    assert temp[T.che] == 0


def test_surplus_link_pushes_back_only_what_is_over_the_ceiling():
    """`MaxResources` is what a complex can hold, and `PutTotalCargo` clamps to
    it on the next line -- so the overflow is stock that is about to evaporate.
    This is salvage rather than generosity."""
    from recreon.primintr import get_cargo, put_cargo
    from recreon.types import cargo_array
    from recreon.update import surplus_link

    game, base, mine = complex_with_a_mine()
    cargo = cargo_array()
    cargo[T.che] = 9000
    put_cargo(game, mine, cargo)
    temp = {k: 0 for k in T}
    temp[T.che] = 12000

    surplus_link(game, base, temp)

    # The mine had room for 999 and the complex had 2001 to spare, so the
    # mine's headroom is what binds.
    assert get_cargo(game, mine)[T.che] == MAX_RESOURCES
    assert temp[T.che] == 12000 - 999


def test_surplus_link_is_bounded_by_the_overflow_when_that_is_smaller():
    from recreon.primintr import get_cargo, put_cargo
    from recreon.types import cargo_array
    from recreon.update import surplus_link

    game, base, mine = complex_with_a_mine()
    put_cargo(game, mine, cargo_array())
    temp = {k: 0 for k in T}
    temp[T.che] = MAX_RESOURCES + 40

    surplus_link(game, base, temp)

    assert get_cargo(game, mine)[T.che] == 40
    assert temp[T.che] == MAX_RESOURCES


def test_surplus_link_does_nothing_below_the_ceiling():
    from recreon.primintr import get_cargo, put_cargo
    from recreon.types import cargo_array
    from recreon.update import surplus_link

    game, base, mine = complex_with_a_mine()
    cargo = cargo_array()
    cargo[T.che] = 100
    put_cargo(game, mine, cargo)
    temp = {k: 0 for k in T}
    temp[T.che] = MAX_RESOURCES

    surplus_link(game, base, temp)

    assert get_cargo(game, mine)[T.che] == 100
    assert temp[T.che] == MAX_RESOURCES


def test_the_links_carry_supplies_as_well_as_raw_materials():
    """`FOR RawI := che TO tri` is che, met, **sup**, tri -- so supplies travel
    with the ores, while troops, ninjas and ambrosia stay put. Checking the
    endpoints of a Pascal subrange rather than trusting its name."""
    from recreon.primintr import get_cargo, put_cargo
    from recreon.types import cargo_array
    from recreon.update import surplus_link

    game, base, mine = complex_with_a_mine()
    put_cargo(game, mine, cargo_array())
    temp = {k: 0 for k in T}
    for thing in (T.che, T.met, T.sup, T.tri, T.men, T.nnj, T.amb):
        temp[thing] = MAX_RESOURCES + 500

    surplus_link(game, base, temp)

    moved = get_cargo(game, mine)
    for thing in (T.che, T.met, T.sup, T.tri):
        assert moved[thing] == 500, thing
    for thing in (T.men, T.nnj, T.amb):
        assert moved[thing] == 0, thing


def test_neither_link_touches_another_empires_mine():
    from recreon.primintr import get_cargo, put_cargo
    from recreon.types import cargo_array
    from recreon.update import supply_link, surplus_link

    game, base, mine = complex_with_a_mine(mine_emp=Empire.Empire2)
    cargo = cargo_array()
    cargo[T.che] = 5000
    put_cargo(game, mine, cargo)

    temp = {k: 0 for k in T}
    supply_link(game, base, temp)
    assert temp[T.che] == 0, "a rival's mine is not a supply line"

    temp[T.che] = MAX_RESOURCES + 500
    surplus_link(game, base, temp)
    assert get_cargo(game, mine)[T.che] == 5000
    assert temp[T.che] == MAX_RESOURCES + 500


def test_neither_link_touches_a_world_that_is_not_a_mine():
    """The filter is `[AgrTyp,CheTyp,MinTyp,RawTyp,TriTyp]` -- a research world
    or a shipyard next door is not part of the network."""
    from recreon.primintr import get_cargo, put_cargo
    from recreon.types import cargo_array
    from recreon.update import surplus_link

    game, base, mine = complex_with_a_mine(mine_typ=WorldTypes.RsrTyp)
    put_cargo(game, mine, cargo_array())
    temp = {k: 0 for k in T}
    temp[T.che] = MAX_RESOURCES + 500

    surplus_link(game, base, temp)

    assert get_cargo(game, mine)[T.che] == 0
    assert temp[T.che] == MAX_RESOURCES + 500


def test_surplus_link_spends_no_randomness():
    """`SupplyLink` draws `Rnd(200,250)` per mine and this draws nothing, so
    wiring it in leaves the generator stream where it was."""
    from recreon.primintr import put_cargo
    from recreon.types import cargo_array
    from recreon.update import surplus_link
    from recreon.utils import pascal

    game, base, mine = complex_with_a_mine()
    put_cargo(game, mine, cargo_array())
    temp = {k: 0 for k in T}
    temp[T.che] = MAX_RESOURCES + 500

    before = pascal._rand_seed
    surplus_link(game, base, temp)

    assert pascal._rand_seed == before


def test_a_complex_hands_its_overflow_to_the_mine_over_a_full_year():
    """End to end through `update_world`, which is where the call actually
    sits -- between Production and the clamp that would otherwise discard it."""
    from recreon.primintr import get_cargo, put_cargo
    from recreon.types import cargo_array
    from recreon.update import update_world

    game, base, mine = complex_with_a_mine()
    put_cargo(game, mine, cargo_array())

    record = game.Universe.Starbase[1]
    record.Pop = 900
    record.Eff = 90
    record.Tech = TechLevel.WrpTchLvl
    for ind in (
        IndusTypes.CheInd,
        IndusTypes.MinInd,
        IndusTypes.SupInd,
        IndusTypes.TriInd,
    ):
        record.Indus[ind] = 200
    for thing in (T.che, T.met, T.sup, T.tri):
        record.Cargo[thing] = MAX_RESOURCES

    update_world(game, base)

    # Whatever the complex produced on top of a full hold had to go somewhere,
    # and the mine next door is where.
    assert sum(get_cargo(game, mine).values()) > 0


# --- Empire research ---------------------------------------------------------
#
# `UpdateEmpire` is the last two statements of `UpdateUniverse` and was
# unported for a long time, so no empire advanced in technology on its own.


def research_game(worlds=1):
    """An empire with a capital and `worlds` university worlds beside it."""
    game = blank_game(size=20, empires=1)
    cap = place_world(
        game, 1, XYCoord(5, 5), emp=Empire.Empire1, typ=WorldTypes.CapTyp, eff=100
    )
    game.Universe.EmpireData[Empire.Empire1].Capital = cap
    for i in range(worlds):
        place_world(
            game,
            2 + i,
            XYCoord(6 + i, 5),
            emp=Empire.Empire1,
            typ=WorldTypes.RsrTyp,
            eff=100,
        )
    return game, cap


def test_an_empire_missing_a_technology_discovers_one_before_it_levels_up():
    """Breadth before depth: an empire fills out its current tier first, and
    only a complete tier lets the same roll advance a level."""
    from recreon.update import new_tech_level

    set_rand_seed(4021)
    game, _ = research_game()
    data = game.Universe.EmpireData[Empire.Empire1]
    data.TechnologyLevel = TechLevel.WrpTchLvl
    full = set(TechDev[TechLevel.WrpTchLvl])
    data.Technology = set(list(full)[:-1])  # one short of the tier

    for _ in range(80):
        new_tech_level(game, Empire.Empire1)
        if data.Technology == full:
            break

    assert data.Technology == full
    assert data.TechnologyLevel == TechLevel.WrpTchLvl, "the level waits"


def test_a_complete_tier_lets_the_empire_advance_a_level():
    from recreon.update import new_tech_level

    set_rand_seed(4021)
    game, _ = research_game()
    data = game.Universe.EmpireData[Empire.Empire1]
    data.TechnologyLevel = TechLevel.WrpTchLvl
    data.Technology = set(TechDev[TechLevel.WrpTchLvl])

    for _ in range(80):
        new_tech_level(game, Empire.Empire1)
        if data.TechnologyLevel != TechLevel.WrpTchLvl:
            break

    assert data.TechnologyLevel == TechLevel.JmpTchLvl


def test_advancing_a_level_drags_the_research_worlds_up_with_it():
    """Every university or capital world exactly one level behind comes along,
    which is how an empire's labs stay at the frontier without being upgraded
    by hand."""
    from recreon.update import new_tech_level

    set_rand_seed(4021)
    game, cap = research_game(worlds=2)
    data = game.Universe.EmpireData[Empire.Empire1]
    data.TechnologyLevel = TechLevel.WrpTchLvl
    data.Technology = set(TechDev[TechLevel.WrpTchLvl])
    for i in (1, 2, 3):
        game.Universe.Planet[i].Tech = TechLevel.WrpTchLvl

    for _ in range(80):
        new_tech_level(game, Empire.Empire1)
        if data.TechnologyLevel != TechLevel.WrpTchLvl:
            break

    for i in (1, 2, 3):
        assert game.Universe.Planet[i].Tech == TechLevel.JmpTchLvl, i


def test_an_empire_at_the_top_stops_researching():
    """A full `GteTchLvl` set is the end of the tree; nothing rolls."""
    from recreon.update import new_tech_level

    set_rand_seed(4021)
    game, _ = research_game()
    data = game.Universe.EmpireData[Empire.Empire1]
    data.TechnologyLevel = TechLevel.GteTchLvl
    data.Technology = set(TechDev[TechLevel.GteTchLvl])

    for _ in range(50):
        new_tech_level(game, Empire.Empire1)

    assert data.TechnologyLevel == TechLevel.GteTchLvl
    assert data.Technology == set(TechDev[TechLevel.GteTchLvl])


def test_more_labs_mean_a_better_chance():
    """The chances sum, which is the whole mechanic -- and what makes #87's
    overflow reachable."""
    from recreon.update import _get_chance_for_new_tech

    set_rand_seed(4021)
    one, _ = research_game(worlds=1)
    many, _ = research_game(worlds=5)

    chance_one, _ = _get_chance_for_new_tech(one, Empire.Empire1, TechLevel.WrpTchLvl)
    chance_many, _ = _get_chance_for_new_tech(
        many, Empire.Empire1, TechLevel.WrpTchLvl
    )

    assert chance_many > chance_one


def test_the_research_chance_wraps_past_a_byte():
    """Original bug #87. `TotalChance` is an `Index` (0..100) in a byte, and
    twenty labs at 17 each reach 340 -- so a big enough research empire wraps
    and gets *worse* at research. Do not "fix" by widening the accumulator."""
    from recreon.update import MAX_NO_OF_LABS, _get_chance_for_new_tech

    set_rand_seed(4021)
    game = blank_game(size=40, empires=1)
    cap = place_world(
        game, 1, XYCoord(5, 5), emp=Empire.Empire1, typ=WorldTypes.CapTyp, eff=100
    )
    game.Universe.EmpireData[Empire.Empire1].Capital = cap
    # Ruins universities are worth 17 each at full efficiency.
    for i in range(2, 2 + MAX_NO_OF_LABS + 2):
        place_world(
            game,
            i,
            XYCoord(5 + (i % 30), 6 + (i // 30)),
            emp=Empire.Empire1,
            cls=WorldClass.RnsCls,
            typ=WorldTypes.RsrTyp,
            eff=100,
        )

    chance, _ = _get_chance_for_new_tech(game, Empire.Empire1, TechLevel.WrpTchLvl)

    # 12 (capital) + 19 x 17 = 335, which wraps to 79 rather than saturating.
    assert chance < 100, "an unbounded sum would be far above 100"
    assert chance == 335 % 256


def test_update_universe_researches_and_clears_read_messages():
    """The two calls that close `UpdateUniverse` and were missing."""
    from recreon.mess import MessageRecord

    set_rand_seed(4021)
    game, _ = research_game(worlds=3)
    data = game.Universe.EmpireData[Empire.Empire1]
    data.TechnologyLevel = TechLevel.WrpTchLvl
    data.Technology = set(list(TechDev[TechLevel.WrpTchLvl])[:-1])

    read = MessageRecord()
    read.Read = True
    unread = MessageRecord()
    unread.Read = False
    game.MessageList.extend([read, unread])

    before = len(data.Technology)
    for _ in range(60):
        update_universe(game)

    assert len(data.Technology) > before or data.TechnologyLevel != TechLevel.WrpTchLvl
    assert read not in game.MessageList, "a read message should be swept"
    assert unread in game.MessageList, "an unread one should survive"


def test_empire_unrest_is_a_yearly_figure_not_a_running_total():
    """`UpdateEmpire` *replaces* TotalRevIndex with the year's accumulation.
    Without it the value drifts unboundedly -- a 300-turn game reached -605."""
    from recreon.primintr import change_total_rev_index, total_rev_index

    set_rand_seed(4021)
    game, _ = research_game()

    change_total_rev_index(game, Empire.Empire1, 500)
    assert total_rev_index(game, Empire.Empire1) == 500

    update_universe(game)

    assert total_rev_index(game, Empire.Empire1) != 500, (
        "the year's own figure replaces whatever combat accumulated"
    )
