"""The scenario front end, ported from NEWGAME.PAS.

`GetScenarios`, `ScenarioIntroduction`, `InputEmpireName` and the flow
`StartNewGame` drives.
"""

from pathlib import Path

import pytest

from recreon.environ import GameEnvironment
from recreon.newgame import (
    DEMO_CHECKSUMS,
    MAX_NO_OF_SCENARIOS,
    RND_EMPIRE_NAMES,
    EmpireIdentity,
    ScenarioEntry,
    ScenarioFrontEnd,
    ScenarioHeader,
    check_sum,
    get_scenarios,
    load_scenario,
    read_scenario_intro,
    start_new_game,
)
from recreon.types import Empire
from recreon.utils.pascal import set_rand_seed

SHIPPED = Path(__file__).parent.parent / "original" / "scenarios"
AUTHORED = Path(__file__).parent.parent / "src" / "recreon" / "data" / "scenarios"


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


# --- The name table ----------------------------------------------------------


def test_the_random_name_table_is_the_original_one():
    """59 names, from `RndEmpireName` at NEWGAME.PAS:62.

    The count is load-bearing twice over: `GetRandomEmpireName` indexes with
    `Rnd(1, 59)`, so both the bound and the order decide which name comes out.
    Sixteen invented names stood here until the Pascal turned out to be
    readable after all.
    """
    assert len(RND_EMPIRE_NAMES) == 59
    assert len(set(RND_EMPIRE_NAMES)) == 59
    assert RND_EMPIRE_NAMES[0] == "Aaraavon"
    assert RND_EMPIRE_NAMES[6] == "Cal'Dulmas"
    assert RND_EMPIRE_NAMES[-1] == "Yolandis"


def test_a_random_name_is_never_one_already_taken():
    """`GetRandomEmpireName` rejects and re-rolls rather than filtering.

    Both matter. A filtered draw would call `Rnd` with a smaller bound and
    call it exactly once, so the value *and* the number of draws would differ
    from the original -- and every draw after it in the scenario would shift.
    """
    from recreon.ui.newgame import suggest_empire_name

    taken = set(RND_EMPIRE_NAMES[:50])
    for _ in range(40):
        name = suggest_empire_name(taken)
        assert name in RND_EMPIRE_NAMES
        assert name not in taken


# --- Listing scenarios -------------------------------------------------------


def test_the_shipped_scenarios_are_all_listed():
    """All 13, including the two that will not load.

    `GetScenarios` reads only the header, so a file that fails later still
    appears in the menu -- which is how a player could pick AWAKEN.SCN and
    watch it fail.
    """
    entries = get_scenarios(SHIPPED)
    assert len(entries) == 13
    assert {e.path.name.upper() for e in entries} >= {"AWAKEN.SCN", "PRINCES.SCN"}


def test_listing_skips_files_that_are_not_scenarios(tmp_path):
    (tmp_path / "notes.scn").write_text("just some text\n")
    (tmp_path / "readme.txt").write_text("ANACREON 10 SCENARIO\n")

    assert get_scenarios(tmp_path) == []


def test_listing_is_sorted_by_filename(tmp_path):
    """DOS gave the original directory order for free; this does not."""
    for name in ["zulu.scn", "alpha.scn", "mike.scn"]:
        (tmp_path / name).write_text(
            'ANACREON 16 SCENARIO\n"T"\n0 1 1 20 5 0 100 200 4021\n'
            "BEGINTEXT\nhi\nENDTEXT\nENDSCENARIO\n"
        )

    assert [e.path.name for e in get_scenarios(tmp_path)] == [
        "alpha.scn", "mike.scn", "zulu.scn",
    ]


def test_the_twenty_scenario_limit_is_recorded_not_enforced():
    """The original's menu is an `ARRAY [1..20]` filled without a check.

    Reproducing the overrun would corrupt the caller's stack and buy nothing;
    the constant records what the window was sized for.
    """
    assert MAX_NO_OF_SCENARIOS == 20


# --- Menu columns ------------------------------------------------------------


def entry(**kwargs) -> ScenarioEntry:
    header = ScenarioHeader(**{"title": "T", "difficulty": 0, **kwargs})
    return ScenarioEntry(path=Path("x.scn"), header=header)


def test_the_menu_line_uses_the_originals_column_widths():
    line = entry(
        title="The Kalgan Frontier", difficulty=2,
        min_players=1, max_players=4, min_length=50, max_length=200,
    ).menu_line()

    assert line == (
        "The Kalgan Frontier     " "Advanced      " "1-4 Players " "50-200 years"
    )
    # AdjustString pads to exactly 23, 14 and 11.
    assert line[:23] == "The Kalgan Frontier    "


def test_a_long_title_is_truncated_rather_than_pushing_the_columns():
    line = entry(title="A" * 40, min_players=1, max_players=1).menu_line()
    assert line.startswith("A" * 23 + " ")


@pytest.mark.parametrize(
    "low,high,expected",
    [(1, 1, "1 Player"), (2, 2, "2 Players"), (1, 4, "1-4 Players")],
)
def test_the_player_column_pluralises_on_the_maximum(low, high, expected):
    """`IF MaxPlay>1` -- so a solo scenario reads "1 Player"."""
    assert entry(min_players=low, max_players=high).players == expected


@pytest.mark.parametrize(
    "low,high,expected",
    [(50, 200, "50-200 years"), (200, 0, "200+ years")],
)
def test_the_duration_column_handles_an_open_upper_bound(low, high, expected):
    assert entry(min_length=low, max_length=high).duration == expected


def test_an_unknown_difficulty_falls_back_to_its_number():
    assert entry(difficulty=9).difficulty == "9"


# --- Reading a scenario ahead of loading it ----------------------------------


def test_the_intro_can_be_read_without_running_any_directive():
    header, pages = read_scenario_intro(AUTHORED / "frontier.scn")

    assert header.title == "The Kalgan Frontier"
    assert header.min_players == 1 and header.max_players == 4
    assert pages and any(page.strip() for page in pages)


def test_reading_the_intro_first_does_not_change_the_galaxy():
    """Two passes are safe because neither the header nor the intro draws.

    `run` is what seeds the generator, from the scenario's own Seed, so a
    galaxy built after a peek is the galaxy a single pass would have built.
    """
    first = load_scenario(AUTHORED / "frontier.scn")

    read_scenario_intro(AUTHORED / "frontier.scn")
    second = load_scenario(AUTHORED / "frontier.scn")

    assert first.NoOfPlanets == second.NoOfPlanets
    assert [
        (p.XY.x, p.XY.y, p.Emp, p.Cls) for p in first.Universe.Planet[1:20] if p
    ] == [
        (p.XY.x, p.XY.y, p.Emp, p.Cls) for p in second.Universe.Planet[1:20] if p
    ]


# --- The front end drives loading --------------------------------------------


class RecordingFrontEnd(ScenarioFrontEnd):
    """A front end that answers from a script and remembers what it was asked."""

    def __init__(self, count, names):
        super().__init__()
        self.count = count
        self.names = names
        self.pages_shown = None
        self.asked = []

    def introduction(self, header, pages):
        self.pages_shown = pages

    def no_of_players(self, header):
        return self.count

    def empire_identity(self, emp, taken):
        self.asked.append((emp, frozenset(taken)))
        return EmpireIdentity(name=self.names[len(self.asked) - 1])


def test_the_front_end_is_asked_in_the_originals_order():
    """Intro, then the count, then one name per player -- before any directive."""
    front_end = RecordingFrontEnd(3, ["Aster", "Belisar", "Corvin"])
    game = load_scenario(AUTHORED / "frontier.scn", front_end=front_end)

    assert front_end.pages_shown
    assert [emp for emp, _ in front_end.asked] == [
        Empire.Empire1, Empire.Empire2, Empire.Empire3
    ]
    # `taken` accumulates, which is what keeps a suggestion distinct.
    assert front_end.asked[0][1] == frozenset()
    assert front_end.asked[2][1] == frozenset({"Aster", "Belisar"})

    named = {
        data.EmpireName
        for data in game.Universe.EmpireData.values()
        if data.InUse and data.IsAPlayer
    }
    assert named == {"Aster", "Belisar", "Corvin"}


def test_the_player_count_is_clamped_to_what_the_scenario_allows():
    front_end = RecordingFrontEnd(99, [f"E{i}" for i in range(10)])
    load_scenario(AUTHORED / "frontier.scn", front_end=front_end)

    assert len(front_end.asked) == 4  # frontier.scn tops out at 4


def test_an_identity_carries_the_password_and_the_sex():
    """CreatePlayerEmpire passes Sex[Emp] and Password[Emp], not defaults."""
    front_end = ScenarioFrontEnd(
        {Empire.Empire1: EmpireIdentity("Sarkhon", "hunter2", is_empress=True)}
    )
    game = load_scenario(AUTHORED / "frontier.scn", front_end=front_end)

    data = game.Universe.EmpireData[Empire.Empire1]
    assert data.EmpireName == "Sarkhon"
    assert data.Pass == "hunter2"
    assert data.IsAnEmpress is True


def test_creating_a_player_empire_makes_no_random_draw():
    """CreateNPEmpire rolls `Rnd(0,1)` for sex; CreatePlayerEmpire does not.

    A spurious draw would consume a step of the LCG the original never
    consumes and shift every draw in the rest of the scenario -- so this pins
    it by checking the galaxy is identical whichever sex is supplied.
    """
    def galaxy_with(is_empress):
        set_rand_seed(4021)
        front_end = ScenarioFrontEnd(
            {Empire.Empire1: EmpireIdentity("Sarkhon", is_empress=is_empress)}
        )
        game = load_scenario(AUTHORED / "frontier.scn", front_end=front_end)
        return [
            (p.XY.x, p.XY.y, p.Emp, p.Cls, p.Pop)
            for p in game.Universe.Planet[1 : game.NoOfPlanets + 1]
            if p
        ]

    assert galaxy_with(True) == galaxy_with(False)


def test_names_passed_directly_still_work():
    """The old `player_names` argument keeps working, seeding the default."""
    game = load_scenario(
        AUTHORED / "frontier.scn",
        player_names={Empire.Empire1: "Solo"},
    )
    assert game.Universe.EmpireData[Empire.Empire1].EmpireName == "Solo"


def test_start_new_game_records_where_the_scenario_came_from():
    """`StartNewGame` stores the bare filename, not the full path."""
    scenario = next(
        e for e in get_scenarios(AUTHORED) if e.path.name == "frontier.scn"
    )
    game = start_new_game(AUTHORED, scenario)

    assert game.ScenaFilename == "frontier.scn"
    assert game.SceDirect == str(AUTHORED)
    assert game.NoOfPlanets > 0


# --- The demo's anti-tamper check --------------------------------------------


def test_check_sum_totals_the_bytes(tmp_path):
    path = tmp_path / "tiny.scn"
    path.write_bytes(b"ABC")
    assert check_sum(path) == 65 + 66 + 67


def test_the_demo_checksums_are_recorded_but_unmatched():
    """Its only call site is inside `{$IFDEF Demo}`, so nothing calls this.

    Which three scenarios the sums identify is not recorded, and none of the
    shipped files matches -- consistent with the demo having shipped its own.
    """
    assert DEMO_CHECKSUMS == (43171, 6792, 44304)
    assert not any(
        check_sum(path) in DEMO_CHECKSUMS for path in SHIPPED.glob("*.SCN")
    )


# --- Defaults ----------------------------------------------------------------


def test_the_default_front_end_takes_a_fixed_scenarios_player_count():
    """`NoChoice`: when min equals max there is nothing to ask."""
    front_end = ScenarioFrontEnd()
    header = ScenarioHeader(min_players=3, max_players=3)
    assert front_end.no_of_players(header) == 3


def test_the_default_front_end_names_unclaimed_slots():
    front_end = ScenarioFrontEnd({Empire.Empire1: EmpireIdentity("Sarkhon")})

    assert front_end.empire_identity(Empire.Empire1, set()).name == "Sarkhon"
    assert front_end.empire_identity(Empire.Empire2, set()).name == "Empire 2"


def test_a_game_still_loads_with_no_front_end_at_all():
    game = load_scenario(AUTHORED / "frontier.scn", game=GameEnvironment())
    assert game.NoOfPlanets > 0
    assert game.Universe.EmpireData[Empire.Empire1].InUse
