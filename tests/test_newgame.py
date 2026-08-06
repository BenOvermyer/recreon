"""Milestone 3.5: a scenario file loads into a populated galaxy."""

from pathlib import Path

import pytest

from conftest import blank_game
from recreon.galaxy import XYCoord, nebula_of, srm_owner_of
from recreon.main import DEFAULT_SCENARIO
from recreon.newgame import ScenarioError, ScenarioLoader, Zone, load_scenario
from recreon.types import (
    Empire,
    NebulaTypes,
    ObjectTypes,
    WorldTypes,
)
from recreon.update import update_universe
from recreon.utils.dfa import TokenError, TokenReader
from recreon.utils.int_utils import rnd
from recreon.utils.pascal import set_rand_seed

# --- Tokenizer ---------------------------------------------------------------


def tokens(text: str) -> list[str]:
    reader = TokenReader(text)
    out = []
    while True:
        try:
            out.append(reader.next_token())
        except TokenError:
            return out


def test_tokens_split_on_whitespace():
    assert tokens("one two\tthree\nfour") == ["one", "two", "three", "four"]


def test_quoted_tokens_keep_their_spaces():
    assert tokens('"This is a token" next') == ["This is a token", "next"]


def test_backslash_escapes_quote_and_backslash():
    assert tokens(r'"\"quoted\"" x') == ['"quoted"', "x"]
    assert tokens(r'"a backslash (\\)" x') == ["a backslash (\\)", "x"]


def test_semicolon_starts_a_comment():
    assert tokens("alpha ; this is ignored\nbeta") == ["alpha", "beta"]


def test_comment_at_end_of_data_line():
    assert tokens("DefineZone 2 ; coreward\n5") == ["DefineZone", "2", "5"]


def test_punctuation_is_a_legal_token():
    assert tokens("!@#$%^&* 1234") == ["!@#$%^&*", "1234"]


def test_next_integer_rejects_non_numbers():
    reader = TokenReader("42 notanumber")
    assert reader.next_integer() == 42
    with pytest.raises(TokenError):
        reader.next_integer()


def test_read_line_and_tokens_share_a_cursor():
    # The header is read as a raw line, then parsing switches to tokens.
    reader = TokenReader("ANACREON 16 SCENARIO\n\"Title\" 7")
    assert reader.read_line() == "ANACREON 16 SCENARIO"
    assert reader.next_token() == "Title"
    assert reader.next_integer() == 7


# --- Header ------------------------------------------------------------------


def _loader(text: str) -> ScenarioLoader:
    loader = ScenarioLoader(game=blank_game(), reader=TokenReader(text))
    loader.read_header()
    return loader


def test_header_version_comes_from_a_fixed_column():
    loader = _loader('ANACREON 16 SCENARIO\n"T" 0 1 4 40 90 2 50 200 4021')
    assert loader.header.version == 16
    assert loader.header.title == "T"
    assert loader.header.size_of_galaxy == 40
    assert loader.header.first_year == 4021


def test_misaligned_version_is_rejected_not_silently_downgraded():
    # Python's int() strips whitespace where Pascal's Val errors. If a
    # shifted header parsed as some low version it would silently enable the
    # old-format shims and desync every directive after it.
    loader = _loader('ANACREON  16 SCENARIO\n"T" 0 1 4 40 90 2 50 200 4021')
    assert loader.failed
    assert "version" in loader.errors[0].lower()


# --- Coordinate mini-language ------------------------------------------------


def coord_loader(text: str, **kwargs) -> ScenarioLoader:
    loader = ScenarioLoader(game=blank_game(size=40), reader=TokenReader(text))
    loader.zones[1] = Zone(1, 1, 40, 40)
    for key, value in kwargs.items():
        setattr(loader, key, value)
    return loader


def test_absolute_coordinates():
    assert coord_loader("12,34").next_xy(False) == XYCoord(12, 34)


def test_coordinates_outside_the_galaxy_are_rejected():
    loader = coord_loader("99,99")
    assert loader.next_xy(False) == XYCoord(0, 0)
    assert loader.failed


def test_zone_coordinates_land_inside_the_zone():
    loader = coord_loader("Z:2")
    loader.zones[2] = Zone(5, 5, 8, 8)
    for _ in range(20):
        loader.reader = TokenReader("Z:2")
        xy = loader.next_xy(False)
        assert 5 <= xy.x <= 8 and 5 <= xy.y <= 8


def test_random_range_coordinates():
    loader = coord_loader("R:3..6,10..12")
    xy = loader.next_xy(False)
    assert 3 <= xy.x <= 6 and 10 <= xy.y <= 12


def test_relative_coordinates_offset_a_named_point():
    loader = coord_loader("HOME:-2..2,-2..2", xy_points={"HOME": XYCoord(20, 20)})
    xy = loader.next_xy(False)
    assert 18 <= xy.x <= 22 and 18 <= xy.y <= 22


def test_relative_coordinates_need_a_defined_point():
    loader = coord_loader("NOWHERE:0,0")
    loader.next_xy(False)
    assert loader.failed
    assert "XYPoint not found" in loader.errors[0]


def test_check_world_avoids_occupied_sectors():
    from recreon.primintr import put_object
    from recreon.types import IDNumber

    loader = coord_loader("R:5..5,5..5")
    put_object(loader.game, XYCoord(5, 5), IDNumber(ObjectTypes.Pln, 1))
    # The only sector in range is taken, so it gives up rather than looping.
    assert loader.next_xy(True) == XYCoord(0, 0)
    assert "No room" in loader.errors[0]


# --- The shipped scenario ----------------------------------------------------


@pytest.fixture
def game():
    set_rand_seed(99)
    return load_scenario(
        DEFAULT_SCENARIO, {Empire.Empire1: "Vantiss", Empire.Empire2: "Sarkhon"}
    )


def test_scenario_loads_a_populated_galaxy(game):
    assert game.Year == 4021
    assert game.Galaxy.size == 40
    assert game.NoOfPlanets > 40


def test_named_players_become_empires(game):
    assert game.Universe.EmpireData[Empire.Empire1].EmpireName == "Vantiss"
    assert game.Universe.EmpireData[Empire.Empire1].IsAPlayer
    assert game.Universe.EmpireData[Empire.Empire2].EmpireName == "Sarkhon"


def test_unnamed_player_slots_are_skipped(game):
    # The scenario defines four player empires; only two were named, which is
    # how one file supports a range of player counts.
    assert not game.Universe.EmpireData[Empire.Empire3].InUse
    assert not game.Universe.EmpireData[Empire.Empire4].InUse


def test_npe_empires_are_created_with_their_type(game):
    from recreon.npe.types import NPEmpireTypes

    concordance = game.Universe.EmpireData[Empire.Empire6]
    assert concordance.InUse
    assert not concordance.IsAPlayer
    assert game.NPEData[Empire.Empire6].Typ == NPEmpireTypes.Kingdom1NPE
    assert game.NPEData[Empire.Empire7].Typ == NPEmpireTypes.PirateNPE


def test_random_names_are_substituted(game):
    # The pirate empire is declared as RndName in the scenario.
    assert game.Universe.EmpireData[Empire.Empire7].EmpireName not in ("", "RndName")


def test_capitals_are_assigned(game):
    for emp in (Empire.Empire1, Empire.Empire2):
        capital = game.Universe.EmpireData[emp].Capital
        assert capital.ObjTyp == ObjectTypes.Pln
        assert game.Universe.Planet[capital.Index].Typ == WorldTypes.CapTyp
        assert game.Universe.Planet[capital.Index].Emp == emp


def test_empires_hold_their_homeworlds(game):
    for emp in (Empire.Empire1, Empire.Empire2):
        owned = [
            p
            for p in game.Universe.Planet[1 : game.NoOfPlanets + 1]
            if p and p.Emp == emp
        ]
        assert len(owned) >= 3, "a capital plus supporting worlds"


def test_most_worlds_are_independent(game):
    independent = [
        p for p in game.Universe.Planet[1 : game.NoOfPlanets + 1]
        if p and p.Emp == Empire.Indep
    ]
    assert len(independent) > 30


def test_random_worlds_respect_the_tech_minimum_for_their_class(game):
    from recreon.datacnst import MinTechForClass

    for planet in game.Universe.Planet[1 : game.NoOfPlanets + 1]:
        if planet is None:
            continue
        assert planet.Tech >= MinTechForClass[planet.Cls]


def test_worlds_are_registered_in_their_sectors(game):
    from recreon.primintr import get_object

    for index, planet in enumerate(game.Universe.Planet[1 : game.NoOfPlanets + 1], 1):
        if planet is None or planet.XY == XYCoord(0, 0):
            continue
        assert get_object(game, planet.XY).Index == index


def test_no_two_worlds_share_a_sector(game):
    seen = set()
    for planet in game.Universe.Planet[1 : game.NoOfPlanets + 1]:
        if planet is None:
            continue
        key = (planet.XY.x, planet.XY.y)
        assert key not in seen, f"two worlds at {key}"
        seen.add(key)


def test_nebulae_and_minefields_are_placed(game):
    nebula = sum(
        1 for xy in game.Galaxy.coordinates() if nebula_of(game.Galaxy.sector(xy).Special)
    )
    mined = sum(
        1
        for xy in game.Galaxy.coordinates()
        if srm_owner_of(game.Galaxy.sector(xy).Special) != int(Empire.Indep)
    )
    assert nebula > 0
    assert mined > 0


def test_dense_nebula_is_placed_where_the_scenario_says(game):
    from recreon.primintr import get_nebula

    assert get_nebula(game, XYCoord(17, 7)) == NebulaTypes.DenseNebula


def test_starbase_and_stargate_exist(game):
    assert game.GlobalSets.SetOfActiveStarbases
    assert game.GlobalSets.SetOfActiveGates


def test_trillum_reserves_vary_by_class(game):
    reserves = {
        p.TriReserve
        for p in game.Universe.Planet[1 : game.NoOfPlanets + 1]
        if p is not None
    }
    assert len(reserves) > 5, "reserves should be rolled, not constant"


def test_a_seed_makes_the_galaxy_reproducible():
    # Reproducible within this port. Deliberately not matching the DOS build
    # -- see IMPLEMENTATION_PLAN.md §3.5.4.
    def load():
        set_rand_seed(1)
        g = load_scenario(DEFAULT_SCENARIO, {Empire.Empire1: "A"})
        return [
            (p.XY.x, p.XY.y, int(p.Cls), int(p.Tech))
            for p in g.Universe.Planet[1 : g.NoOfPlanets + 1]
            if p
        ]

    assert load() == load()


def test_the_economy_runs_on_a_generated_galaxy(game):
    before = sum(
        p.Pop for p in game.Universe.Planet[1 : game.NoOfPlanets + 1] if p
    )
    for _ in range(50):
        update_universe(game)
    after = sum(p.Pop for p in game.Universe.Planet[1 : game.NoOfPlanets + 1] if p)

    assert game.Year == 4071
    assert after > before, "the galaxy should grow over 50 years"


# --- Error handling ----------------------------------------------------------

#: A minimal valid scenario prefix: header line, header fields, and the
#: BeginText/EndText introduction the loader consumes before any directive.
HEADER = (
    'ANACREON 16 SCENARIO\n"T" 0 1 1 20 10 1 1 1 4021\n'
    "BeginText\nan introduction\nEndText\n"
)




def test_unknown_directive_is_an_error(tmp_path):
    path = tmp_path / "bad.scn"
    path.write_text(HEADER + "FLOOP\n")
    with pytest.raises(ScenarioError, match="Unknown command"):
        load_scenario(path, {Empire.Empire1: "A"})


def test_class_table_must_sum_to_one_hundred(tmp_path):
    path = tmp_path / "bad.scn"
    weights = " ".join(["1"] * 22)  # 22, not 100
    path.write_text(HEADER + f"ClassTable {weights}\n")
    with pytest.raises(ScenarioError, match="do not add up to 100"):
        load_scenario(path, {Empire.Empire1: "A"})


def test_tech_table_must_sum_to_one_hundred(tmp_path):
    path = tmp_path / "bad.scn"
    path.write_text(HEADER + f'TechTable {" ".join(["1"] * 11)}\n')
    with pytest.raises(ScenarioError, match="do not add up to 100"):
        load_scenario(path, {Empire.Empire1: "A"})


def test_truncated_file_is_an_error(tmp_path):
    path = tmp_path / "short.scn"
    path.write_text(HEADER + "CreateWorld 1\n")
    with pytest.raises(ScenarioError):
        load_scenario(path, {Empire.Empire1: "A"})


# --- Format version shims ----------------------------------------------------


def test_pre_12_files_omit_the_trillum_reserve_field():
    # Version 11 has no TriRes column, and no modifier list on empires.
    body = (
        'ANACREON 11 SCENARIO\n"T" 5 1 1 20 10 1 1 1 4021\n'
        "CreateWorld 1 5,5 9 5 6 8 500 50 "
        + " ".join(["0"] * 4)
        + " " + " ".join(["0"] * 7)
        + " " + " ".join(["10"] * 7)
        + "\nEndScenario\n"
    )
    reader = TokenReader(body)
    loader = ScenarioLoader(game=blank_game(size=20), reader=reader)
    loader.read_header()
    assert loader.header.version == 11
    loader.run()
    assert not loader.failed, loader.errors


def test_pre_14_files_shift_class_indices_past_terraforming():
    # TerCls was inserted at ordinal 20, pushing VlcCls from 20 to 21.
    from recreon.types import WorldClass

    body = (
        'ANACREON 13 SCENARIO\n"T" 5 1 1 20 10 1 1 1 4021\n'
        # Version 13 is >= 12, so it does carry the trillum reserve field.
        "CreateWorld 1 5,5 20 5 6 8 500 50 100 "
        + " ".join(["0"] * 4)
        + " " + " ".join(["0"] * 7)
        + " " + " ".join(["10"] * 7)
        + "\nEndScenario\n"
    )
    loader = ScenarioLoader(game=blank_game(size=20), reader=TokenReader(body))
    loader.read_header()
    loader.run()
    assert not loader.failed, loader.errors
    assert loader.game.Universe.Planet[1].Cls == WorldClass.VlcCls


# --- The scenarios that shipped with the original ----------------------------

SCENARIO_DIR = Path(__file__).resolve().parent.parent / "original" / "scenarios"

#: The two shipped scenarios that are malformed. Both would have failed in the
#: DOS build too -- see the tests below for what is wrong with each.
BROKEN_SCENARIOS = {"AWAKEN", "PRINCES"}

ORIGINAL_SCENARIOS = sorted(p.stem for p in SCENARIO_DIR.glob("*.SCN"))

#: How many unseeded rolls a scenario gets to place its worlds before the load
#: is called a genuine failure. GAUNTLET is the tight one at roughly 8% per
#: roll, so three attempts leaves a ~1-in-2000 flake.
RANDOMIZE_ATTEMPTS = 3

FOUR_PLAYERS = {
    Empire.Empire1: "A",
    Empire.Empire2: "B",
    Empire.Empire3: "C",
    Empire.Empire4: "D",
}


def test_the_scenario_directory_is_populated():
    """Guards the parametrised tests below against silently becoming no-ops."""
    assert len(ORIGINAL_SCENARIOS) == 13


@pytest.mark.parametrize(
    "name", [n for n in ORIGINAL_SCENARIOS if n not in BROKEN_SCENARIOS]
)
def test_shipped_scenarios_load(name):
    # This test cannot be seeded. Every shipped scenario carries Seed 0, so
    # `ScenarioLoader.run` calls Randomize itself and discards whatever seed
    # was set beforehand -- an earlier `set_rand_seed` here was dead code, and
    # left the test rolling a fresh galaxy every run.
    #
    # That matters because placement can legitimately fail: GetRandomXY gives
    # up after 101 tries, and GAUNTLET packs 172 worlds tightly enough to trip
    # it on a few per cent of rolls (see the test below). So retry rather than
    # pin -- an unlucky roll is not a regression, but failing every attempt is.
    for attempt in range(RANDOMIZE_ATTEMPTS):
        try:
            game = load_scenario(SCENARIO_DIR / f"{name}.SCN", FOUR_PLAYERS)
            break
        except ScenarioError as exc:
            if "No room for random world" not in str(exc):
                raise
            if attempt == RANDOMIZE_ATTEMPTS - 1:
                raise AssertionError(
                    f"{name} failed to place its worlds on "
                    f"{RANDOMIZE_ATTEMPTS} consecutive rolls: {exc}"
                ) from exc

    assert game.Galaxy.size > 0
    assert game.NoOfPlanets > 0
    assert game.ScenarioIntroduction, "every shipped scenario has intro text"


def test_a_crowded_zone_can_genuinely_fail_to_place_a_world():
    """GetRandomXY gives up after 101 tries and reports an error rather than
    looping. GAUNTLET packs 172 worlds into small zones and trips this on a
    few per cent of unseeded runs -- in the DOS build as much as here, since
    the give-up threshold is the original's."""
    outcomes = set()
    for seed in range(1, 40):
        set_rand_seed(seed)
        try:
            load_scenario(SCENARIO_DIR / "GAUNTLET.SCN", FOUR_PLAYERS)
            outcomes.add("loaded")
        except ScenarioError as exc:
            assert "No room for random world" in str(exc)
            outcomes.add("no room")

    assert "loaded" in outcomes, "most seeds should place every world"


def test_awaken_asks_for_more_worlds_than_the_game_can_hold():
    """36 explicit worlds plus 176 random ones against a limit of 200. The
    original has no check here and would have written past the planet array.

    It never loads, on any seed. Which error surfaces first depends on the
    roll -- packing that many worlds also exhausts zones -- so the test pins
    seeds and requires the limit to be the reported cause at least once."""
    reasons = set()
    for seed in range(1, 20):
        set_rand_seed(seed)
        with pytest.raises(ScenarioError) as caught:
            load_scenario(SCENARIO_DIR / "AWAKEN.SCN", FOUR_PLAYERS)
        reasons.add(str(caught.value))

    assert any("Too many worlds" in r for r in reasons), reasons


def test_princes_has_a_stray_token_in_its_starbase_block():
    """Its one CreateStarbase carries an extra `0 ; (reserved)` field that the
    directive takes no argument for. Every other scenario's starbase block has
    six fields; this one has seven, so the block runs one token long and the
    trailing cargo amount is read as the next command."""
    with pytest.raises(ScenarioError, match='Unknown command "3500"'):
        load_scenario(SCENARIO_DIR / "PRINCES.SCN", FOUR_PLAYERS)


# --- The introduction pass ---------------------------------------------------


def test_tokens_before_begintext_are_discarded():
    """Nebula.SCN carries a column ruler between the header and its intro. It
    is not a directive and never reaches the dispatch, because the intro scan
    swallows everything up to BEGINTEXT."""
    body = (
        'ANACREON 16 SCENARIO\n"T" 0 1 1 20 10 1 1 1 4021\n'
        "1234567890123456789012345678901234567890\n"
        "BeginText\nhello\nEndText\nEndScenario\n"
    )
    loader = ScenarioLoader(game=blank_game(size=20), reader=TokenReader(body))
    loader.read_header()
    pages = loader.read_introduction()
    loader.run()

    assert not loader.failed, loader.errors
    assert pages == ["hello"]


def test_newpage_splits_the_introduction():
    body = (
        'ANACREON 16 SCENARIO\n"T" 0 1 1 20 10 1 1 1 4021\n'
        "BeginText\none\nNewPage\ntwo\nEndText\nEndScenario\n"
    )
    loader = ScenarioLoader(game=blank_game(size=20), reader=TokenReader(body))
    loader.read_header()

    assert loader.read_introduction() == ["one", "two"]


def test_endtext_is_matched_anywhere_in_a_line():
    """Pos(), not a token comparison -- a line merely containing the word ends
    the page."""
    body = (
        'ANACREON 16 SCENARIO\n"T" 0 1 1 20 10 1 1 1 4021\n'
        "BeginText\nkeep\n   EndText   ; done\nEndScenario\n"
    )
    loader = ScenarioLoader(game=blank_game(size=20), reader=TokenReader(body))
    loader.read_header()

    assert loader.read_introduction() == ["keep"]


def test_a_scenario_with_no_introduction_is_an_error():
    body = 'ANACREON 16 SCENARIO\n"T" 0 1 1 20 10 1 1 1 4021\nEndScenario\n'
    loader = ScenarioLoader(game=blank_game(size=20), reader=TokenReader(body))
    loader.read_header()
    loader.read_introduction()

    assert loader.failed
    assert "BEGINTEXT" in loader.errors[0]


# --- Reproducibility ---------------------------------------------------------


def test_every_shipped_scenario_is_unseeded():
    """All 13 carry Seed 0, which means Randomize. Porting Turbo Pascal's
    generator therefore does *not* recover the galaxies players saw in 2004 --
    those were rolled fresh on every new game and never existed twice. What it
    buys is that our own seeded scenarios draw from the sequence the original
    would have drawn from."""
    for name in ORIGINAL_SCENARIOS:
        loader = ScenarioLoader(
            game=blank_game(size=20),
            reader=TokenReader.from_path(SCENARIO_DIR / f"{name}.SCN"),
        )
        loader.read_header()
        assert loader.header.seed == 0, name


def test_a_seeded_scenario_regenerates_the_same_galaxy():
    """The point of porting Turbo Pascal's generator: a fixed Seed gives the
    same galaxy every run. frontier.scn carries one; none of the originals do."""
    first = load_scenario(DEFAULT_SCENARIO, FOUR_PLAYERS)
    second = load_scenario(DEFAULT_SCENARIO, FOUR_PLAYERS)

    def fingerprint(game):
        return [
            (p.XY.x, p.XY.y, int(p.Cls), int(p.Tech), p.Pop, p.TriReserve)
            for p in game.Universe.Planet[1 : game.NoOfPlanets + 1]
        ]

    assert fingerprint(first) == fingerprint(second)
    assert len(fingerprint(first)) > 1


def test_a_seeded_galaxy_survives_an_intervening_draw():
    """Seeding happens inside the loader, so unrelated RNG use before the load
    cannot shift the galaxy."""
    baseline = load_scenario(DEFAULT_SCENARIO, FOUR_PLAYERS)
    set_rand_seed(999)
    rnd(1, 100)
    again = load_scenario(DEFAULT_SCENARIO, FOUR_PLAYERS)

    assert [p.XY.x for p in again.Universe.Planet[1:20]] == [
        p.XY.x for p in baseline.Universe.Planet[1:20]
    ]


def test_an_unseeded_scenario_still_loads():
    """INTRO.SCN carries Seed 0, which means Randomize -- a different galaxy
    every run, but a valid one."""
    game = load_scenario(SCENARIO_DIR / "INTRO.SCN", FOUR_PLAYERS)
    assert game.NoOfPlanets == 50
