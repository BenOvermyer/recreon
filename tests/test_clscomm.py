"""World close-up and production screens, ported from CLSCOMM.PAS."""

import pytest
from conftest import blank_game, place_world

from recreon.clscomm import (
    MAX_ATIP,
    available_tip,
    basic_info,
    close_up,
    defense_forecast,
    industry_info,
    outpost_info,
    production_com,
)
from recreon.datacnst import TechDev
from recreon.fleet import get_next_fleet, move_fleet
from recreon.galaxy import Location, XYCoord, limbo
from recreon.intrface import create_starbase
from recreon.primintr import (
    add_name,
    set_population,
    set_type,
)
from recreon.types import (
    Empire,
    IDNumber,
    IndusTypes,
    ObjectTypes,
    SpecialConditions,
    TechLevel,
    TechnologyTypes,
    WorldTypes,
)
from recreon.utils.pascal import set_rand_seed

T = TechnologyTypes
IT = IndusTypes
PLAYER = Empire.Empire1
HOME_XY = XYCoord(5, 5)


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


@pytest.fixture
def game():
    g = blank_game(size=20, empires=2)
    place_world(g, 1, HOME_XY, emp=PLAYER)
    # A second world stands in as the capital, so the first one's relative
    # coordinates are not 0,0 and the naming rule is worth testing.
    capital = place_world(g, 2, XYCoord(10, 10), emp=PLAYER)
    g.Universe.EmpireData[PLAYER].Capital = capital
    return g


@pytest.fixture
def home():
    return IDNumber(ObjectTypes.Pln, 1)


# --- Basic information -------------------------------------------------------


def test_an_unnamed_world_reads_as_its_coordinate(game, home):
    info = basic_info(game, PLAYER, home)
    assert "," in info.name


def test_a_named_world_gains_its_coordinate_in_brackets(game, home):
    add_name(game, PLAYER, Location(XY=limbo(), ID=home), "The Deeps")

    info = basic_info(game, PLAYER, home)

    assert info.name.startswith("The Deeps")
    assert "(" in info.name and ")" in info.name


def test_a_name_containing_a_comma_is_left_un_annotated(game, home):
    """The original's test is `Pos(',', Name) = 0` -- "does this look like a
    coordinate already?". A name with a comma in it fools it."""
    add_name(game, PLAYER, Location(XY=limbo(), ID=home), "Kandii, Second")

    assert basic_info(game, PLAYER, home).name == "Kandii, Second"


def test_basic_info_reports_the_worlds_state(game, home):
    planet = game.Universe.Planet[1]
    planet.Special.add(SpecialConditions.AmbAddict)

    info = basic_info(game, PLAYER, home)

    assert info.pop == planet.Pop
    assert info.eff == planet.Eff
    assert info.tech is planet.Tech
    assert info.amb_addict


# --- TIP ---------------------------------------------------------------------


def test_addiction_raises_the_available_production(game, home):
    """`AmbrosiaAdj` is 1.45, so an addicted world works *harder* -- the drug
    is an industrial stimulant, and the cost shows up as the ambrosia it then
    has to be supplied with and the unrest when it is not."""
    clean = basic_info(game, PLAYER, home)
    before = available_tip(game, home, clean)

    game.Universe.Planet[1].Special.add(SpecialConditions.AmbAddict)
    addicted = basic_info(game, PLAYER, home)

    assert available_tip(game, home, addicted) > before


def test_tip_is_capped(game, home):
    set_population(game, home, 100000)
    info = basic_info(game, PLAYER, home)

    assert available_tip(game, home, info) == MAX_ATIP


# --- Industry ----------------------------------------------------------------


def test_the_optimum_is_floored_at_one_where_the_player_asked_for_industry(game, home):
    """A world never reads "you want this industry and it should be zero"."""
    info = basic_info(game, PLAYER, home)
    table = industry_info(game, home, 1, info.cls)

    for ind, share in table.distribution.items():
        if share:
            assert table.optimum[ind] >= 1


def test_a_bigger_world_wants_more_industry(game, home):
    info = basic_info(game, PLAYER, home)
    small = industry_info(game, home, 50, info.cls)
    large = industry_info(game, home, 500, info.cls)

    assert sum(large.optimum.values()) > sum(small.optimum.values())


def test_an_outpost_has_no_economy_to_show(game):
    """`GetOutpostInfo` zeroes the table -- a base that is not an industrial
    complex has no industry of its own."""
    table = outpost_info()

    assert all(value == 0 for value in table.class_adj.values())
    assert all(value == 0 for value in table.distribution.values())
    assert all(value == 0 for value in table.optimum.values())


def test_a_non_complex_base_gets_the_outpost_table(game):
    base = IDNumber(ObjectTypes.Base, 1)
    create_starbase(game, base, PLAYER, XYCoord(8, 8), T.out)

    report = production_com(game, PLAYER, base)

    assert all(value == 0 for value in report.industry.optimum.values())


# --- The production forecast -------------------------------------------------


def test_a_working_world_forecasts_output(game, home):
    report = production_com(game, PLAYER, home)

    assert any(report.forecast.ships.values())
    assert any(report.forecast.cargo.values())


def test_supplies_are_consumed_in_proportion_to_population(game, home):
    report = production_com(game, PLAYER, home)
    small = report.forecast.consumed[T.sup]

    set_population(game, home, game.Universe.Planet[1].Pop * 4)
    bigger = production_com(game, PLAYER, home).forecast.consumed[T.sup]

    assert bigger > small


def test_an_addicted_world_consumes_ambrosia(game, home):
    before = production_com(game, PLAYER, home).forecast.consumed[T.amb]
    game.Universe.Planet[1].Special.add(SpecialConditions.AmbAddict)

    assert production_com(game, PLAYER, home).forecast.consumed[T.amb] > before


def test_ambrosia_needs_the_right_world_type_and_class(game, home):
    """Chained ELSE IF in the original: the type test runs first, so a world
    of the wrong type never reaches the class test."""
    set_type(game, home, WorldTypes.IndTyp)
    assert production_com(game, PLAYER, home).forecast.cargo[T.amb] == 0


def test_the_forecast_ignores_exhausted_trillum_reserves(game, home):
    """Original bug #62, reproduced.

    `GetProdInfo` re-derives the production formula instead of calling it, and
    misses `ProduceTrillum`'s reserve gate. A mined-out world forecasts its
    full trillum output and produces none.
    """
    with_reserves = production_com(game, PLAYER, home).forecast.cargo[T.tri]
    assert with_reserves > 0

    game.Universe.Planet[1].TriReserve = 0
    report = production_com(game, PLAYER, home)

    assert report.forecast.trillum_reserves == 0
    assert report.forecast.cargo[T.tri] == with_reserves


def test_technology_the_empire_lacks_is_not_forecast(game, home):
    """The forecast intersects the empire's technology with the world's."""
    game.Universe.EmpireData[PLAYER].Technology = set()
    report = production_com(game, PLAYER, home)

    assert not any(report.forecast.ships.values())
    assert not any(report.forecast.cargo.values())


# --- Defenses ----------------------------------------------------------------


def test_defenses_scale_with_manpower(game, home):
    """Manpower, not population: troops build and crew the defences.

    Kept well below MaxResources, or both figures clamp and the comparison
    says nothing.
    """
    info = basic_info(game, PLAYER, home)

    few = defense_forecast(game, PLAYER, home, info, 100)
    many = defense_forecast(game, PLAYER, home, info, 1000)

    assert sum(many.optimum.values()) > sum(few.optimum.values())
    assert any(few.optimum.values())  # GDM is available at warp level


def advanced(game, obj, level=TechLevel.StrTchLvl):
    """Raise the world and the empire to a level that grants every defence."""
    game.Universe.Planet[obj.Index].Tech = level
    game.Universe.EmpireData[PLAYER].TechnologyLevel = level
    game.Universe.EmpireData[PLAYER].Technology = set(TechDev[level])


def test_only_a_base_or_capital_gets_lam(game, home):
    """LAMs need starship technology to exist at all, and then a base or a
    capital to be worth stationing on."""
    advanced(game, home)
    info = basic_info(game, PLAYER, home)
    assert info.typ is not WorldTypes.CapTyp

    forecast = defense_forecast(game, PLAYER, home, info, 1000)
    assert forecast.optimum[T.LAM] == 0

    set_type(game, home, WorldTypes.CapTyp)
    capital_info = basic_info(game, PLAYER, home)
    assert defense_forecast(game, PLAYER, home, capital_info, 1000).optimum[T.LAM] > 0


def a_base(game, index, kind, xy, level=TechLevel.StrTchLvl):
    """A starbase advanced enough for its defences to exist."""
    base = IDNumber(ObjectTypes.Base, index)
    create_starbase(game, base, PLAYER, xy, kind)
    game.Universe.Starbase[index].Tech = level
    game.Universe.EmpireData[PLAYER].TechnologyLevel = level
    game.Universe.EmpireData[PLAYER].Technology = set(TechDev[level])
    return base


def test_an_outpost_builds_no_planetary_defense(game):
    base = a_base(game, 1, T.out, XYCoord(8, 8))

    info = basic_info(game, PLAYER, base)
    forecast = defense_forecast(game, PLAYER, base, info, 1000)

    assert forecast.optimum[T.def_] == 0
    assert forecast.buildable[T.def_] == 0
    # ...but it still wants the others.
    assert forecast.optimum[T.GDM] > 0


def test_a_command_base_wants_far_more_defenses_than_an_outpost(game):
    """An outpost wants a quarter of the optimum; a command base four times
    it -- a sixteenfold spread from the same manpower."""
    outpost = a_base(game, 1, T.out, XYCoord(8, 8))
    command = a_base(game, 2, T.cmm, XYCoord(9, 9))

    out_forecast = defense_forecast(
        game, PLAYER, outpost, basic_info(game, PLAYER, outpost), 100
    )
    cmd_forecast = defense_forecast(
        game, PLAYER, command, basic_info(game, PLAYER, command), 100
    )

    # Not exactly sixteen: each side is truncated by ThgLmt independently, so
    # the outpost's quarter-share loses its fraction before the comparison.
    assert cmd_forecast.optimum[T.GDM] > out_forecast.optimum[T.GDM] * 15


# --- Close-up ----------------------------------------------------------------


def test_the_close_up_lists_scouted_fleets_in_the_sector(game, home):
    """How a player sees a siege forming."""
    mine = get_next_fleet(game, PLAYER)
    move_fleet(game, mine, HOME_XY)
    game.Universe.Fleet[mine.Index].ScoutedBy.add(PLAYER)

    theirs = get_next_fleet(game, Empire.Empire2)
    move_fleet(game, theirs, HOME_XY)

    report = close_up(game, PLAYER, home)
    listed = [flt for flt, _, _ in report.fleets]

    assert mine in listed
    assert theirs not in listed  # not scouted

    game.Universe.Fleet[theirs.Index].ScoutedBy.add(PLAYER)
    assert theirs in [flt for flt, _, _ in close_up(game, PLAYER, home).fleets]


def test_the_close_up_reports_what_is_on_the_world(game, home):
    report = close_up(game, PLAYER, home)

    assert report.info.name
    assert report.cargo[T.met] > 0
