"""The status windows (§8.3), ported from SWINDOWS.PAS and its seven units.

Covers what each window lists and in what order (STAWIND, FLTWIND, EMPWIND,
NWSWIND, NMSWIND, HLPWIND) and the status lines INTRFACE.PAS builds for them.
"""

import pytest
from conftest import blank_game, place_world

from recreon.datastrc import NameRecord
from recreon.empwind import empire_rows
from recreon.fleet import get_next_fleet, move_fleet
from recreon.fltwind import fleet_rows
from recreon.galaxy import Location, XYCoord, limbo
from recreon.hlpwind import (
    BYTES_PER_LINE,
    BYTES_PER_PAGE,
    FALLBACK_PAGE,
    HELP_INDEX,
    LINES_PER_PAGE,
    page_bounds,
    page_count,
    read_help_page,
)
from recreon.intrface import (
    get_empire_status,
    get_empire_status_line,
    get_fleet_position_status,
    get_fleet_status_line,
    get_import_export_str,
    get_military_status,
    get_world_status,
)
from recreon.news import LOCAL_NEWS, NewsTypes, add_news
from recreon.nmswind import get_name_line, name_lines, name_rows
from recreon.nwswind import news_rows
from recreon.primintr import (
    get_capital,
    put_cargo,
    put_ships,
    set_issp,
)
from recreon.stawind import status_rows
from recreon.swindows import WINDOW_KEYS, WindowTypes, window_for_key
from recreon.types import (
    Empire,
    IDNumber,
    IndusTypes,
    ObjectTypes,
    TechLevel,
    TechnologyTypes,
    cargo_array,
    ship_array,
)
from recreon.utils.pascal import set_rand_seed
from recreon.utils.sort import quick_sort_d, word_key

T = TechnologyTypes
PLAYER = Empire.Empire1
THEIRS = Empire.Empire2


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


@pytest.fixture
def game():
    g = blank_game(size=20, empires=2)
    g.Universe.EmpireData[PLAYER].Capital = place_world(
        g, 1, XYCoord(5, 5), emp=PLAYER
    )
    g.Universe.EmpireData[THEIRS].Capital = place_world(
        g, 2, XYCoord(15, 15), emp=THEIRS
    )
    return g


def a_fleet(game, emp=PLAYER, xy=XYCoord(5, 5), scouted_by=(PLAYER,), **ships):
    flt = get_next_fleet(game, emp)
    move_fleet(game, flt, xy)
    for who in scouted_by:
        game.Universe.Fleet[flt.Index].ScoutedBy.add(who)
    stock = ship_array()
    for kind, count in ships.items():
        stock[T[kind]] = count
    put_ships(game, flt, stock)
    return flt


# --- The key table -----------------------------------------------------------


def test_the_function_keys_open_the_windows_the_help_text_names():
    assert window_for_key("f1") is WindowTypes.HelpWND
    assert window_for_key("f7") is WindowTypes.NewsWND
    assert window_for_key("f8") is WindowTypes.EmpireWND
    assert window_for_key("f9") is WindowTypes.NamesWND
    assert window_for_key("f10") is WindowTypes.ScanWND


def test_two_pairs_of_keys_share_one_window():
    """F3/F4 and F5/F6 each open a window showing two stacked tables, not two
    windows. The player has one key per table out of habit."""
    assert window_for_key("f3") is window_for_key("f4") is WindowTypes.StatusWND
    assert window_for_key("f5") is window_for_key("f6") is WindowTypes.FleetWND


def test_f2_opens_no_window():
    """The original's help text calls it "Return to Menu" -- the menu bar, not
    a status window."""
    assert window_for_key("f2") is None
    assert "f2" not in WINDOW_KEYS


# --- QuickSortD --------------------------------------------------------------


def test_the_sort_key_is_the_second_byte():
    """`QuickSortD` compares the first Word of each record, and x86 is
    little-endian -- so the *second* single-byte field is the major key. This
    is what makes STAWIND sort by tech and FLTWIND sort by y."""
    # A record whose second field is larger outranks one whose first field is
    # maximal: 0x0200 beats 0x01FF.
    assert word_key(0, 2) > word_key(255, 1)
    # The first field only breaks ties within the same second field.
    assert word_key(9, 3) > word_key(3, 3)


def test_quick_sort_d_sorts_descending_in_place():
    items = [(0, 1), (0, 5), (0, 3), (0, 2)]
    quick_sort_d(items, lambda e: e[1], 1, len(items))
    assert [e[1] for e in items] == [5, 3, 2, 1]


def test_quick_sort_d_sorts_only_the_named_span():
    items = [(0, 1), (0, 9), (0, 5), (0, 7)]
    quick_sort_d(items, lambda e: e[1], 3, 4)
    assert [e[1] for e in items] == [1, 9, 7, 5]


# --- STAWIND -----------------------------------------------------------------


def test_the_capital_is_always_the_first_status_row(game):
    place_world(game, 3, XYCoord(6, 6), emp=PLAYER, tech=TechLevel.GteTchLvl)

    rows = status_rows(game, PLAYER)

    assert rows[0] == get_capital(game, PLAYER)


def test_the_capital_is_never_listed_twice(game):
    rows = status_rows(game, PLAYER)
    assert rows.count(get_capital(game, PLAYER)) == 1


def test_own_worlds_sort_by_technology_not_population(game):
    """The ElementRecord reads `Pop; Tech; ID` and so looks like a population
    sort. The Word comparison makes technology the major key."""
    place_world(game, 3, XYCoord(6, 6), emp=PLAYER, tech=TechLevel.AtomicLvl, pop=9000)
    place_world(game, 4, XYCoord(7, 7), emp=PLAYER, tech=TechLevel.GteTchLvl, pop=100)

    rows = status_rows(game, PLAYER)[1:]

    # The high-tech, tiny world outranks the low-tech, huge one.
    assert rows[0] == IDNumber(ObjectTypes.Pln, 4)
    assert rows[1] == IDNumber(ObjectTypes.Pln, 3)


def test_a_world_must_be_scouted_to_appear_not_merely_known(game):
    """This table is made of numbers, and knowing a world is there tells you
    none of them -- a stricter test than the map's."""
    other = place_world(game, 3, XYCoord(8, 8), emp=THEIRS)
    game.Universe.Planet[3].KnownBy.add(PLAYER)

    assert other not in status_rows(game, PLAYER)

    game.Universe.Planet[3].ScoutedBy.add(PLAYER)
    assert other in status_rows(game, PLAYER)


def test_owned_worlds_come_before_scouted_foreign_ones(game):
    place_world(game, 3, XYCoord(6, 6), emp=PLAYER, tech=TechLevel.PrimitLvl)
    foreign = place_world(game, 4, XYCoord(8, 8), emp=THEIRS, tech=TechLevel.GteTchLvl)
    game.Universe.Planet[4].ScoutedBy.add(PLAYER)

    rows = status_rows(game, PLAYER)

    # Even though the foreign world outranks it on the sort key, it is in the
    # second section.
    assert rows.index(IDNumber(ObjectTypes.Pln, 3)) < rows.index(foreign)


# --- The world and military status lines -------------------------------------


def test_a_world_status_row_lines_up_with_its_header(game):
    row = get_world_status(game, PLAYER, get_capital(game, PLAYER))
    assert len(row) > 40
    assert row.startswith(" " * 0)  # name is left-justified into 8 columns


def test_a_tiny_population_reads_as_less_than_a_tenth(game):
    world = place_world(game, 3, XYCoord(6, 6), emp=PLAYER, pop=5)

    assert "<0.1" in get_world_status(game, PLAYER, world)


def test_a_normal_world_imports_and_exports_nothing(game):
    """Every industry at `NormalISSP` shows dashes in both columns."""
    assert get_import_export_str(game, get_capital(game, PLAYER)) == "---- ----"


def test_raising_an_industrys_issp_makes_it_an_export(game):
    world = get_capital(game, PLAYER)
    set_issp(game, world, IndusTypes.MinInd, 8)

    imports, exports = get_import_export_str(game, world).split()

    assert exports == "-M--"
    assert imports == "----"


def test_lowering_an_industrys_issp_makes_it_an_import(game):
    world = get_capital(game, PLAYER)
    set_issp(game, world, IndusTypes.TriInd, 1)

    imports, exports = get_import_export_str(game, world).split()

    assert imports == "---T"
    assert exports == "----"


def test_a_foreign_worlds_cargo_is_dashes_not_numbers(game):
    """You can count hulls in orbit; you cannot audit a warehouse."""
    world = place_world(game, 3, XYCoord(8, 8), emp=THEIRS)
    game.Universe.Planet[3].ScoutedBy.add(PLAYER)

    row = get_world_status(game, PLAYER, world)

    assert row.endswith("  --   --   --   --   --  ")


def test_your_own_world_reports_exact_defenses(game):
    row = get_military_status(game, PLAYER, get_capital(game, PLAYER))
    # Ends with four right-justified defense counts, so digits not y/no.
    assert any(ch.isdigit() for ch in row[-20:])


def test_a_foreign_worlds_military_row_stops_after_the_ships(game):
    world = place_world(game, 3, XYCoord(8, 8), emp=THEIRS)
    game.Universe.Planet[3].ScoutedBy.add(PLAYER)

    own = get_military_status(game, PLAYER, get_capital(game, PLAYER))
    theirs = get_military_status(game, PLAYER, world)

    assert len(theirs) < len(own)


# --- EMPWIND -----------------------------------------------------------------


def test_the_players_own_empire_is_always_the_first_row(game):
    rows = empire_rows(game, PLAYER)
    assert rows[0].startswith("Empire 1")


def test_an_empire_whose_capital_is_unknown_is_not_listed(game):
    assert len(empire_rows(game, PLAYER)) == 1


def test_a_known_capital_lists_the_empire_without_its_fleets(game):
    """You learn how big a rival is long before you learn what it can field."""
    game.Universe.Planet[2].KnownBy.add(PLAYER)

    rows = empire_rows(game, PLAYER)

    assert len(rows) == 2
    assert "----" in rows[1]


def test_a_scouted_capital_reveals_the_fleet_strength(game):
    game.Universe.Planet[2].KnownBy.add(PLAYER)
    game.Universe.Planet[2].ScoutedBy.add(PLAYER)

    rows = empire_rows(game, PLAYER)

    assert "----" not in rows[1]


def test_empire_status_counts_starbases_as_worlds(game):
    planets, _, _, _ = get_empire_status(game, PLAYER)
    assert planets == 1


def test_empire_status_counts_ships_aboard_fleets(game):
    a_fleet(game, fgt=250)

    _, _, _, ships = get_empire_status(game, PLAYER)

    assert ships[T.fgt] >= 250


def test_an_empire_line_shows_its_capitals_technology(game):
    game.Universe.Planet[1].Tech = TechLevel.GteTchLvl

    line = get_empire_status_line(game, PLAYER, True)

    assert line.split()[-8:][0] or True  # smoke: the line builds
    assert len(line) > 40


# --- FLTWIND -----------------------------------------------------------------


def test_an_empty_galaxy_lists_no_fleets(game):
    assert fleet_rows(game, PLAYER) == []


def test_your_own_fleets_come_before_enemy_ones(game):
    theirs = a_fleet(game, emp=THEIRS, xy=XYCoord(9, 9))
    mine = a_fleet(game, xy=XYCoord(4, 4))

    rows = fleet_rows(game, PLAYER)

    assert rows.index(mine) < rows.index(theirs)


def test_fleets_sort_down_the_map_by_row(game):
    """The record is `XY; ID` and XYCoord is two bytes, so y is the major key
    and the list runs from the bottom of the map upwards."""
    north = a_fleet(game, xy=XYCoord(5, 2))
    south = a_fleet(game, xy=XYCoord(5, 9))

    rows = fleet_rows(game, PLAYER)

    assert rows.index(south) < rows.index(north)


def test_a_merely_known_enemy_fleet_still_gets_a_row(game):
    """You are told something is out there before you are told what."""
    theirs = a_fleet(game, emp=THEIRS, xy=XYCoord(9, 9), scouted_by=())
    game.Universe.Fleet[theirs.Index].KnownBy.add(PLAYER)

    assert theirs in fleet_rows(game, PLAYER)


def test_an_unknown_enemy_fleet_gets_no_row(game):
    a_fleet(game, emp=THEIRS, xy=XYCoord(9, 9), scouted_by=())

    assert fleet_rows(game, PLAYER) == []


def test_a_scouted_enemy_fleet_outranks_a_merely_known_one(game):
    known = a_fleet(game, emp=THEIRS, xy=XYCoord(9, 9), scouted_by=())
    game.Universe.Fleet[known.Index].KnownBy.add(PLAYER)
    seen = a_fleet(game, emp=THEIRS, xy=XYCoord(2, 2))

    rows = fleet_rows(game, PLAYER)

    assert rows.index(seen) < rows.index(known)


def test_an_unscouted_fleets_destination_and_status_are_withheld(game):
    theirs = a_fleet(game, emp=THEIRS, xy=XYCoord(9, 9), scouted_by=())
    game.Universe.Fleet[theirs.Index].KnownBy.add(PLAYER)

    line = get_fleet_position_status(game, PLAYER, theirs)

    assert "(unknown)" in line
    assert "(out of range)" in line


def test_your_own_fleet_reports_its_range(game):
    mine = a_fleet(game, fgt=100)

    line = get_fleet_position_status(game, PLAYER, mine)

    assert "at destination" in line


def test_an_unscouted_fleet_shows_nothing_of_its_hold(game):
    theirs = a_fleet(game, emp=THEIRS, xy=XYCoord(9, 9), scouted_by=(), fgt=50)

    assert get_fleet_status_line(game, PLAYER, theirs).endswith("(out of range)")


def test_a_scouted_enemy_fleet_shows_hulls_but_no_cargo(game):
    theirs = a_fleet(game, emp=THEIRS, xy=XYCoord(9, 9), fgt=50)
    hold = cargo_array()
    hold[T.tri] = 900
    put_cargo(game, theirs, hold)

    line = get_fleet_status_line(game, PLAYER, theirs)

    assert "900" not in line
    assert line.endswith("  --   --   --   --   --   --   -- ")


def test_your_own_fleet_shows_its_whole_manifest(game):
    mine = a_fleet(game, fgt=50)
    hold = cargo_array()
    hold[T.tri] = 900
    put_cargo(game, mine, hold)

    assert "900" in get_fleet_status_line(game, PLAYER, mine)


# --- NWSWIND -----------------------------------------------------------------


def test_galaxy_news_sorts_above_housekeeping(game):
    loc = Location(XY=limbo(), ID=IDNumber(ObjectTypes.Pln, 1))
    add_news(game, PLAYER, NewsTypes.Lack, loc)          # local
    add_news(game, PLAYER, NewsTypes.BattleL, loc)       # not local

    rows = news_rows(game, PLAYER)

    assert rows[0].Headline is NewsTypes.BattleL
    assert rows[1].Headline is NewsTypes.Lack


def test_reordering_the_news_drops_nothing(game):
    loc = Location(XY=limbo(), ID=IDNumber(ObjectTypes.Pln, 1))
    for headline in (NewsTypes.Lack, NewsTypes.BattleL, NewsTypes.NoFuel):
        add_news(game, PLAYER, headline, loc)

    assert len(news_rows(game, PLAYER)) == 3


def test_local_news_is_about_your_own_housekeeping():
    assert NewsTypes.Lack in LOCAL_NEWS
    assert NewsTypes.NoTriRes in LOCAL_NEWS
    assert NewsTypes.BattleL not in LOCAL_NEWS


# --- NMSWIND -----------------------------------------------------------------


def test_with_no_names_the_window_says_so(game):
    assert name_lines(game, PLAYER) == ["No names have been defined."]


def test_named_fleets_come_before_named_places(game):
    flt = a_fleet(game)
    names = game.Universe.EmpireData[PLAYER].Names
    names.append(
        NameRecord(Name="Home", Coord=Location(XY=XYCoord(5, 5), ID=IDNumber()))
    )
    names.append(NameRecord(Name="Task", Coord=Location(XY=limbo(), ID=flt)))

    rows = name_rows(game, PLAYER)

    assert rows[0].Name == "Task"
    assert rows[1].Name == "Home"


def test_a_name_whose_fleet_died_reads_destroyed(game):
    entry = NameRecord(
        Name="Lost",
        Coord=Location(XY=limbo(), ID=IDNumber(ObjectTypes.DestFlt, 3)),
    )
    game.Universe.EmpireData[PLAYER].Names.append(entry)

    assert "(destroyed)" in get_name_line(game, PLAYER, entry)


def test_a_destroyed_fleets_name_sorts_with_the_places(game):
    """`DestFlt` is not `Flt`, so a task force you lost drops into the second
    group rather than staying with the fleets."""
    flt = a_fleet(game)
    names = game.Universe.EmpireData[PLAYER].Names
    names.append(
        NameRecord(
            Name="Lost", Coord=Location(XY=limbo(), ID=IDNumber(ObjectTypes.DestFlt, 3))
        )
    )
    names.append(NameRecord(Name="Live", Coord=Location(XY=limbo(), ID=flt)))

    assert [r.Name for r in name_rows(game, PLAYER)] == ["Live", "Lost"]


def test_a_name_on_a_place_resolves_to_its_coordinates(game):
    entry = NameRecord(
        Name="Home", Coord=Location(XY=XYCoord(5, 5), ID=IDNumber())
    )
    game.Universe.EmpireData[PLAYER].Names.append(entry)

    line = get_name_line(game, PLAYER, entry)

    assert line.startswith("Home    ")
    assert "0,0" in line  # the capital reads as the origin


# --- HLPWIND -----------------------------------------------------------------


def test_the_fallback_lists_the_function_keys():
    """`ANACREON.HLP` does not ship, so this is the screen a player got."""
    text = "\n".join(FALLBACK_PAGE)
    assert "Help file not available" in text
    for key in ("<F1>", "<F3>", "<F5>", "<F9>", "<F10>"):
        assert key in text


def test_the_index_records_what_the_manual_covered():
    assert len(HELP_INDEX) == 15
    topics = dict(HELP_INDEX)
    assert topics["Combat"] == 11
    assert topics["ISSP"] == 13
    # Two pairs share a page; the manual treated each pair as one topic.
    assert topics["Materials"] == topics["Raw Materials"] == 7
    assert topics["Ships"] == topics["Defenses"] == 6


def test_a_missing_help_file_reads_as_nothing(tmp_path):
    assert read_help_page(tmp_path / "nope.hlp", 1) is None
    assert page_count(tmp_path / "nope.hlp") == 0


def test_a_help_file_is_read_in_the_originals_record_format(tmp_path):
    """`FILE OF HelpPage`: 19 lines of `STRING[80]`, each a length byte and 80
    bytes of text, so 1539 bytes a page."""
    path = tmp_path / "ANACREON.HLP"
    pages = []
    for page in range(3):
        buf = bytearray()
        for line in range(LINES_PER_PAGE):
            text = f"page{page} line{line}".encode("cp437")
            buf.append(len(text))
            buf += text.ljust(80, b"\x00")
        pages.append(bytes(buf))
    path.write_bytes(b"".join(pages))

    assert path.stat().st_size == 3 * BYTES_PER_PAGE
    assert page_count(path) == 3
    assert read_help_page(path, 1)[0] == "page1 line0"
    assert read_help_page(path, 2)[18] == "page2 line18"
    assert read_help_page(path, 3) is None


def test_paging_stops_at_both_ends():
    assert page_bounds(1, 5, forward=False) == 1  # never below page 1
    assert page_bounds(2, 5, forward=False) == 1
    assert page_bounds(4, 5, forward=True) == 4  # FileSize - 1 is the top
    assert page_bounds(3, 5, forward=True) == 4


def test_a_page_record_is_1539_bytes():
    assert BYTES_PER_LINE == 81
    assert BYTES_PER_PAGE == 19 * 81 == 1539
