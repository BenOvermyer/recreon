"""Scenario background text, SCENA.PAS.

Half of these run against the real shipped `.SCN` files rather than fixtures.
That is deliberate: the index format is only documented by the seven scenarios
that use it, and a parser that agrees with a fixture I wrote proves nothing
about a file the original's authors wrote.
"""

from pathlib import Path

import pytest
from conftest import load_scenario_placed

from recreon.clscomm import close_up
from recreon.environ import GameEnvironment
from recreon.newgame import load_scenario
from recreon.primintr import set_status
from recreon.scena import (
    build_empire_set,
    display_background,
    display_text,
    find_line,
    id_match,
    interpret_set,
    load_scena_text,
    parse_line,
    satisfies_conditions,
    scenario_path,
    split_line,
)
from recreon.types import Empire, IDNumber, ObjectTypes, empty_quadrant
from recreon.utils.pascal import set_rand_seed

SHIPPED = Path(__file__).resolve().parents[1] / "original" / "scenarios"
PLAYER = Empire.Empire1


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


@pytest.fixture
def jakarta():
    """JAKARTA.SCN: the only shipped scenario with both `E:` and `A:` entries."""
    return load_scenario(
        SHIPPED / "JAKARTA.SCN", {Empire.Empire1: "A", Empire.Empire2: "B"}
    )


# --- Splitting a line --------------------------------------------------------


def test_a_normal_index_entry_splits_into_its_fields():
    assert split_line("2:6 E:0,1,8      3      ; CloseUp: Old empire capital") == [
        "2:6",
        "E:0,1,8",
        "3",
    ]


def test_tabs_count_as_whitespace():
    """`AWAKEN.SCN` and `Nebula.SCN` both align their index columns with tabs."""
    assert split_line("2:5   E:6\t\t\t2\t; CloseUp") == ["2:5", "E:6", "2"]


def test_a_comment_only_line_yields_one_empty_field():
    """`Nebula.SCN` opens its index with a `;ID Criteria Text` ruler, which has
    to fall through the ID match rather than blow up."""
    assert split_line(";ID  Criteria   Text") == [""]
    assert id_match(split_line(";ID  Criteria   Text")[0]) == empty_quadrant()


def test_a_blank_line_yields_one_empty_field():
    assert split_line("") == [""]
    assert split_line("   \t ") == [""]


# --- Reading an ID -----------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("2:6", IDNumber(ObjectTypes.Pln, 6)),
        ("3:1", IDNumber(ObjectTypes.Base, 1)),
        ("4:33", IDNumber(ObjectTypes.Gate, 33)),
        ("1:27", IDNumber(ObjectTypes.Con, 27)),
    ],
)
def test_an_id_is_an_object_type_ordinal_and_an_index(text, expected):
    """The index is written against `ObjectTypes` ordinals, not names --
    `Nebula.SCN` references construction sites, bases and gates as well as
    worlds."""
    assert id_match(text) == expected


@pytest.mark.parametrize("text", ["", "nonsense", "2:", ":6", "x:y", "99:1"])
def test_an_unreadable_id_is_the_empty_quadrant(text):
    assert id_match(text) == empty_quadrant()


# --- Conditions --------------------------------------------------------------


def test_an_empire_set_is_read_as_zero_based_ordinals():
    """`E:0` is Empire1 and `E:8` is Indep -- the index uses `Empire`'s own
    numbering, so 8 means "while nobody owns it"."""
    assert build_empire_set("E:0") == {Empire.Empire1}
    assert build_empire_set("A:8") == {Empire.Indep}
    assert build_empire_set("E:0,1,8") == {
        Empire.Empire1,
        Empire.Empire2,
        Empire.Indep,
    }


def test_all_means_every_empire_including_indep():
    """`Nebula.SCN` uses `E:ALL` for its teaser text. It reaches the special
    case with an empty numeric set, because `ALL` parses as no number."""
    assert interpret_set("ALL") == set()
    assert build_empire_set("E:ALL") == set(Empire)


def test_e_fires_on_a_close_up_and_a_on_a_conquest(jakarta):
    """The two tags are what let one index serve both callers."""
    world = IDNumber(ObjectTypes.Pln, 3)
    set_status(jakarta, world, Empire.Empire3)
    parms = ["2:3", "E:2", "5"]

    assert satisfies_conditions(jakarta, PLAYER, False, world, parms, 2, 2)
    assert not satisfies_conditions(jakarta, PLAYER, True, world, parms, 2, 2)

    parms = ["2:3", "A:2", "8"]
    assert satisfies_conditions(jakarta, PLAYER, True, world, parms, 2, 2)
    assert not satisfies_conditions(jakarta, PLAYER, False, world, parms, 2, 2)


def test_o_asks_whether_the_viewer_owns_it(jakarta):
    """`Nebula.SCN`'s "for the owner's eyes only" condition."""
    world = IDNumber(ObjectTypes.Pln, 3)
    parms = ["2:3", "O", "1"]

    set_status(jakarta, world, PLAYER)
    assert satisfies_conditions(jakarta, PLAYER, False, world, parms, 2, 2)

    set_status(jakarta, world, Empire.Empire2)
    assert not satisfies_conditions(jakarta, PLAYER, False, world, parms, 2, 2)


def test_conditions_are_anded(jakarta):
    """`Nebula.SCN` writes `2:1  O E:0  8` -- owned by the viewer *and* by
    empire 1. Both have to hold."""
    world = IDNumber(ObjectTypes.Pln, 1)
    parms = ["2:1", "O", "E:0", "8"]

    set_status(jakarta, world, PLAYER)
    assert satisfies_conditions(jakarta, PLAYER, False, world, parms, 2, 3)

    # Owned by the viewer, but the viewer is not empire 1.
    set_status(jakarta, world, Empire.Empire2)
    assert not satisfies_conditions(
        jakarta, Empire.Empire2, False, world, parms, 2, 3
    )


def test_an_unrecognised_condition_is_ignored(jakarta):
    """The original's `CASE` has no `ELSE`, so a typo silently matches
    everything rather than nothing."""
    world = IDNumber(ObjectTypes.Pln, 1)
    assert satisfies_conditions(
        jakarta, PLAYER, False, world, ["2:1", "Z:9", "1"], 2, 2
    )


# --- Substitution ------------------------------------------------------------


def test_a_coordinate_substitution_expands(jakarta):
    """`[C2:1]` becomes planet 1's coordinates, relative to the capital."""
    out = parse_line(jakarta, PLAYER, "The world at [C2:1] is yours.")

    assert "[C2:1]" not in out
    assert out.startswith("The world at ") and out.endswith(" is yours.")


def test_a_name_substitution_expands(jakarta):
    out = parse_line(jakarta, PLAYER, "Take [N2:1] first.")

    assert "[N2:1]" not in out
    assert out.startswith("Take ") and out.endswith(" first.")


def test_an_object_that_is_nowhere_becomes_five_spaces(jakarta):
    """`Nebula.SCN` names twenty starbases and eighteen gates that a given game
    may not have, and relies on this to degrade instead of breaking."""
    assert parse_line(jakarta, PLAYER, "[C3:99]") == "     "


def test_several_substitutions_on_one_line(jakarta):
    out = parse_line(jakarta, PLAYER, "[C2:1] and [C2:2] and [C2:3].")

    assert "[" not in out and "]" not in out
    assert out.count(" and ") == 2


def test_a_line_with_no_brackets_is_untouched(jakarta):
    line = "Description: Jakarta is a world of stark contrasts."
    assert parse_line(jakarta, PLAYER, line) == line


def test_an_unmatched_bracket_stops_instead_of_hanging(jakarta):
    """Original bug #77, and the one place this port deviates on purpose.

    `WHILE OpenB+CloseB>0` tests the *sum*, so a `[` with no `]` -- or a `]`
    before its `[` -- leaves the line unchanged and loops forever. There is no
    way to tell a hang from a crash, and reproducing it would make the port
    unusable on exactly the scenario the original was unusable on, so this
    stops and leaves the text as written.

    No shipped scenario trips it; every bracket in all thirteen is matched.
    """
    assert parse_line(jakarta, PLAYER, "gate at [C4:33 is key") == (
        "gate at [C4:33 is key"
    )
    assert parse_line(jakarta, PLAYER, "a] b") == "a] b"


# --- Finding a block ---------------------------------------------------------


def test_find_line_returns_the_line_after_the_match():
    lines = ["one", "WorldBackgroundIndex", "2:1 E:0 4", "EndIndex"]
    assert find_line(lines, 0, "WORLDBACKGROUNDINDEX") == 2
    assert find_line(lines, 0, "nothing here") == -1


def test_find_line_matches_a_substring_case_insensitively():
    """Which is why a scenario can write `WorldBackgroundIndex` and the code
    can look for `WORLDBACKGROUNDINDEX`."""
    assert find_line(["  EndIndex  ; done"], 0, "ENDINDEX") == 1


def test_a_text_block_stops_at_endtext(jakarta):
    lines = ["TEXT 1", "first", "second", "ENDTEXT", "TEXT 2", "other"]
    assert display_text(jakarta, PLAYER, lines, 0, 1) == ["first", "second"]


# --- The whole thing, against real scenarios ---------------------------------


def test_the_close_up_text_for_a_real_world(jakarta):
    """`2:3 E:2  5` -- Jakarta, seen by anyone, while empire 3 holds it."""
    world = IDNumber(ObjectTypes.Pln, 3)
    set_status(jakarta, world, Empire.Empire3)

    text = display_background(jakarta, PLAYER, world, conquer=False)

    assert text
    assert text[0].startswith("Description: Jakarta is a world of stark contrasts")


def test_the_conquest_text_for_the_same_world(jakarta):
    """`2:3 A:2  8` -- the same world, taken rather than looked at, gives
    different text entirely."""
    world = IDNumber(ObjectTypes.Pln, 3)
    set_status(jakarta, world, Empire.Empire3)

    text = display_background(jakarta, PLAYER, world, conquer=True)

    assert text
    assert "you have conquered Jakarta" in text[0]


def test_the_owner_decides_which_text_a_world_gets(jakarta):
    """`2:3 E:2` wants empire 3. Hand it to empire 5 and the entry no longer
    applies, so nothing comes back."""
    world = IDNumber(ObjectTypes.Pln, 3)

    set_status(jakarta, world, Empire.Empire5)
    assert display_background(jakarta, PLAYER, world, conquer=False) is None


def test_a_world_with_no_entry_gets_nothing(jakarta):
    world = IDNumber(ObjectTypes.Pln, 20)
    assert display_background(jakarta, PLAYER, world, conquer=False) is None


def test_a_scenario_with_no_index_gets_nothing():
    """Six of the thirteen have no `WORLDBACKGROUNDINDEX` at all, and that is
    not an error."""
    game = load_scenario(SHIPPED / "INTRO.SCN", {Empire.Empire1: "A"})

    assert display_background(
        game, PLAYER, IDNumber(ObjectTypes.Pln, 1), conquer=False
    ) is None


def test_a_game_with_no_scenario_file_gets_nothing():
    game = GameEnvironment()
    game.initialize_universe(size=20)

    assert scenario_path(game) is None
    assert display_background(
        game, PLAYER, IDNumber(ObjectTypes.Pln, 1), conquer=False
    ) is None
    # #78: the original crashes here rather than returning empty-handed.
    assert load_scena_text(game, 1) == []


def test_a_scenario_file_that_has_gone_missing(jakarta, tmp_path):
    """`ScenaFilename` rides along in the save, so a game reloaded after the
    scenario moved has a path that no longer resolves."""
    jakarta.ScenaFilename = str(tmp_path / "GONE.SCN")

    assert scenario_path(jakarta) is None
    assert display_background(
        jakarta, PLAYER, IDNumber(ObjectTypes.Pln, 3), conquer=False
    ) is None


@pytest.mark.parametrize(
    "name", ["JAKARTA.SCN", "ARRONAX.SCN", "EASTWEST.SCN", "GAUNTLET.SCN"]
)
def test_every_loadable_scenario_with_an_index_yields_some_text(name):
    """A sweep over each scenario's worlds under three different owners. The
    point is that the parser agrees with files it did not write -- `AWAKEN.SCN`
    and `PRINCES.SCN` also have indexes but are defective as shipped and do not
    load, and `Nebula.SCN` is covered separately below.

    Loaded through `load_scenario_placed` because GAUNTLET is in the list: it
    packs 172 worlds tightly enough to fail placement on roughly 8% of rolls,
    and no seed set here survives the scenario's own `Randomize`."""
    game = load_scenario_placed(
        SHIPPED / name, {Empire.Empire1: "A", Empire.Empire2: "B"}
    )

    found = 0
    for i in range(1, min(game.NoOfPlanets, 50) + 1):
        world = IDNumber(ObjectTypes.Pln, i)
        for emp in (Empire.Empire1, Empire.Empire2, Empire.Indep):
            if display_background(game, emp, world, conquer=False):
                found += 1

    assert found > 0


def test_nebula_expands_a_gate_coordinate_into_its_text():
    """`Nebula.SCN`'s player-1 instructions open by naming a stargate through
    a `[C4:…]` substitution, so this exercises the index and the substitution
    together against a real file."""
    game = load_scenario(SHIPPED / "Nebula.SCN", {Empire.Empire1: "A"})
    world = IDNumber(ObjectTypes.Pln, 1)
    set_status(game, world, Empire.Empire1)

    text = display_background(game, Empire.Empire1, world, conquer=False)

    assert text
    joined = "\n".join(text)
    assert "[" not in joined and "]" not in joined
    assert "gate at" in joined


# --- The two callers ---------------------------------------------------------


def test_the_close_up_screen_carries_the_background(jakarta):
    world = IDNumber(ObjectTypes.Pln, 3)
    set_status(jakarta, world, Empire.Empire3)
    jakarta.Universe.Planet[3].ScoutedBy.add(PLAYER)

    report = close_up(jakarta, PLAYER, world)

    assert report.background
    assert "Jakarta" in report.background[0]


def test_the_close_up_withholds_it_until_the_world_is_scouted(jakarta):
    """`CloseUpCommand`'s call is inside an `IF Scouted(Player,Obj)`. Authored
    prose says what a world *is*, which is what scouting is for."""
    world = IDNumber(ObjectTypes.Pln, 3)
    set_status(jakarta, world, Empire.Empire3)
    jakarta.Universe.Planet[3].ScoutedBy.discard(PLAYER)

    assert close_up(jakarta, PLAYER, world).background == []


def test_the_conquest_message_prefers_the_scenarios_words(jakarta):
    """`EnemyConquered` calls `DisplayBackground` first and only falls back to
    the generic speech when nothing comes back."""
    from recreon.attcomm import _enemy_conquered

    world = IDNumber(ObjectTypes.Pln, 3)
    set_status(jakarta, world, Empire.Empire3)
    flt = IDNumber(ObjectTypes.Flt, 1)

    lines = _enemy_conquered(jakarta, PLAYER, flt, world)

    assert "you have conquered Jakarta" in lines[0]


def test_the_generic_speech_survives_where_there_is_no_entry(jakarta):
    from recreon.attcomm import _enemy_conquered

    world = IDNumber(ObjectTypes.Pln, 20)
    flt = IDNumber(ObjectTypes.Flt, 1)

    lines = _enemy_conquered(jakarta, PLAYER, flt, world)

    assert lines
    assert "conquered Jakarta" not in "\n".join(lines)


def test_authored_text_spends_no_randomness(jakarta):
    """The original's `Rnd(1,3)` sits inside `IF NOT Message`, so a scenario
    that supplies text also leaves the generator where it found it. Keeping
    that shape is what keeps the stream in step."""
    from recreon.attcomm import _enemy_conquered
    from recreon.utils import pascal

    world = IDNumber(ObjectTypes.Pln, 3)
    set_status(jakarta, world, Empire.Empire3)
    flt = IDNumber(ObjectTypes.Flt, 1)

    before = pascal._rand_seed
    _enemy_conquered(jakarta, PLAYER, flt, world)

    assert pascal._rand_seed == before
