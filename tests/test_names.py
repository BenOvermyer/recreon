"""Place names and the empire status report, ported from NAMES.PAS."""

import pytest
from conftest import blank_game, place_world

from recreon.galaxy import Location, XYCoord
from recreon.names import (
    REPORT_COLUMNS,
    STATUS_HEADER,
    add_name_command,
    delete_name_command,
    resource_entry,
    status_report,
    world_status_line,
)
from recreon.primintr import get_capital, get_ships_known, location2index, put_ships
from recreon.types import (
    DEFNS_TYPES,
    SHIP_TYPES,
    Empire,
    IDNumber,
    ObjectTypes,
    TechLevel,
    TechnologyTypes,
    ship_array,
)
from recreon.utils.pascal import set_rand_seed

T = TechnologyTypes
P = Empire.Empire1


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


@pytest.fixture
def game():
    g = blank_game(size=20, empires=2)
    home = place_world(g, 1, XYCoord(5, 5), emp=P)
    g.Universe.EmpireData[P].Capital = home
    return g


@pytest.fixture
def home():
    return IDNumber(ObjectTypes.Pln, 1)


# --- Naming ------------------------------------------------------------------


def test_naming_capitalises_only_the_first_letter(game, home):
    """`NameVar[1]:=UpCase(NameVar[1])` -- the rest is left as typed."""
    message = add_name_command(game, P, home, XYCoord(5, 5), "the deeps")

    assert '"The deeps"' in message
    assert location2index(game, P, Location(XY=XYCoord(5, 5), ID=home)) is not None


def test_a_name_on_a_world_follows_the_world(game, home):
    add_name_command(game, P, home, XYCoord(5, 5), "Home")
    record = location2index(game, P, Location(XY=XYCoord(5, 5), ID=home))

    assert record.Coord.ID == home


def test_removing_a_name_reports_success_either_way(game, home):
    """`DeleteName` is silent about a miss and the command does not ask."""
    add_name_command(game, P, home, XYCoord(5, 5), "Home")

    assert '"Home"' in delete_name_command(game, P, "Home")
    assert '"Nowhere"' in delete_name_command(game, P, "Nowhere")


# --- The resource encoding ---------------------------------------------------


def test_your_own_holdings_read_in_hundreds():
    assert resource_entry(P, P, T.met, 4200) == "42"
    assert resource_entry(P, P, T.met, 0) == " 0"


def test_a_large_holding_of_your_own_reads_as_plus():
    assert resource_entry(P, P, T.met, 999999) == "++"


def test_another_empires_raw_materials_are_invisible():
    """You cannot see what someone else's world is made of at all."""
    for res in (T.amb, T.che, T.met, T.sup, T.tri):
        assert resource_entry(P, Empire.Empire2, res, 5000) == "--"


def test_another_empires_ships_read_as_an_estimate():
    assert resource_entry(P, Empire.Empire2, T.fgt, 0) == "no"
    assert resource_entry(P, Empire.Empire2, T.fgt, 3000) == "y3"
    assert resource_entry(P, Empire.Empire2, T.fgt, 99999) == "y+"


# --- Ships known -------------------------------------------------------------


def test_an_owned_world_reports_all_its_ships(game, home):
    ships = ship_array()
    ships[T.ssp] = 500
    put_ships(game, home, ships)

    assert get_ships_known(game, P, home)[T.ssp] == 500


def test_an_independent_world_reports_only_plausible_ships(game):
    """A plausibility check on scouting reports: an unclaimed world does not
    show ships its own technology could not have built."""
    world = place_world(game, 2, XYCoord(9, 9), emp=Empire.Indep,
                        tech=TechLevel.PreWrpLvl)
    ships = ship_array()
    ships[T.ssp] = 500   # starships are far above pre-warp
    ships[T.fgt] = 100
    put_ships(game, world, ships)

    known = get_ships_known(game, P, world)
    assert known[T.ssp] == 0
    assert known[T.fgt] == 100


# --- The report --------------------------------------------------------------


def test_the_report_starts_with_the_empire_and_the_year(game):
    lines = status_report(game, P)

    assert "status: 4021" in lines[0]
    assert lines[2] == STATUS_HEADER[0]


def test_the_capital_comes_first_and_appears_once(game, home):
    place_world(game, 2, XYCoord(9, 9), emp=P)
    lines = status_report(game, P)

    rows = lines[4:]
    assert len(rows) == 2
    capital_line = world_status_line(game, P, get_capital(game, P))
    assert rows[0] == capital_line
    assert rows.count(capital_line) == 1


def test_a_scouted_foreign_world_is_listed(game):
    place_world(game, 2, XYCoord(9, 9), emp=Empire.Empire2)
    lines = status_report(game, P)
    assert len(lines[4:]) == 1  # only the capital so far

    game.Universe.Planet[2].ScoutedBy.add(P)
    assert len(status_report(game, P)[4:]) == 2


def test_an_unscouted_foreign_world_is_not(game):
    place_world(game, 2, XYCoord(9, 9), emp=Empire.Empire2)
    assert len(status_report(game, P)[4:]) == 1


def test_the_columns_cover_materials_troops_ships_and_defenses():
    assert REPORT_COLUMNS[:5] == (T.amb, T.che, T.met, T.sup, T.tri)
    assert set(SHIP_TYPES) <= set(REPORT_COLUMNS)
    assert set(DEFNS_TYPES) <= set(REPORT_COLUMNS)
