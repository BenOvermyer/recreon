"""Where Python is more permissive than Turbo Pascal, and must not be.

Every silent bug found in this port so far came from the same shape: a Python
builtin quietly accepting something Pascal rejects, or computing something
Pascal computes differently. Six categories are known --

1. banker's rounding vs round-half-away (``pascal_round``)
2. ``int()`` accepting whitespace/underscores where ``Val`` errors (``pascal_val``)
3. an ordinal ``FOR`` range read as a semantic grouping
4. a CP437 codec mapping the control range to control characters
5. ``//`` flooring where ``DIV`` truncates toward zero (``pascal_div``)
6. unbounded ints where a ``Word`` or ``Index`` wraps

-- and three of the six passed every unit test at the time, surfacing only by
running the game or by reasoning about operand ranges. So the tests here are
deliberately about the *convention* rather than about any one caller: they pin
that the strict helpers are used at the parse sites that port a Pascal ``Val``,
and they scan the source for the shapes that should never reappear.
"""

import ast
import pathlib

import pytest

from recreon.newgame import ScenarioError, read_scenario_intro
from recreon.primintr import name2coord, name2fleet
from recreon.types import Empire, ObjectTypes, empty_quadrant
from recreon.utils.dfa import TokenError, TokenReader
from recreon.utils.pascal import pascal_round, pascal_val, trunc

SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "recreon"
PLAYER = Empire.Empire1


@pytest.fixture
def game_with_capital():
    """A real game, because `name2coord` reads the capital to go relative."""
    from recreon.main import new_game
    from recreon.utils.pascal import set_rand_seed

    set_rand_seed(4021)
    return new_game()


# --- The helpers themselves --------------------------------------------------


@pytest.mark.parametrize("text", [" 5", "5 ", " 5 ", "5_0", "\t5", "5\n"])
def test_pascal_val_rejects_what_python_would_accept(text):
    """`int()` takes all of these. `Val` reports an error at the first
    offending character, and every caller in the port checks that error."""
    assert int(text.replace("_", "")) or True  # int() is happy
    with pytest.raises(ValueError):
        pascal_val(text)


@pytest.mark.parametrize("text,expected", [("5", 5), ("-5", -5), ("+5", 5), ("0", 0)])
def test_pascal_val_accepts_what_val_accepts(text, expected):
    assert pascal_val(text) == expected


def test_pascal_round_breaks_ties_away_from_zero():
    """Python's `round` is banker's rounding: `round(2.5)` is 2."""
    assert pascal_round(2.5) == 3
    assert round(2.5) == 2
    assert pascal_round(-2.5) == -3
    assert pascal_round(3.5) == 4 == round(3.5)


def test_trunc_goes_toward_zero():
    assert trunc(2.9) == 2
    assert trunc(-2.9) == -2


# --- The parse sites that port a Val ------------------------------------------


def test_the_scenario_tokeniser_is_strict():
    """`NextInteger` is `Val(Token,Temp,Error)` with the failure turned into
    `ERROR: Illegal number format`. This is the highest-traffic parse in the
    codebase -- every numeric field of every scenario file."""
    reader = TokenReader("12 1_2")

    assert reader.next_integer() == 12
    with pytest.raises(TokenError):
        reader.next_integer()


@pytest.mark.parametrize("text", ["FLEET 12", "FLEET1_2", "FLEET 1 2"])
def test_a_fleet_name_with_junk_in_it_resolves_to_nothing(game_with_capital, text):
    """`Name2Fleet` is `Val(Copy(Strg,6,16),FltIndex,Error)`. With a bare
    `int()` the port accepted `FLEET 12`, and this is on the path of every
    typed name in the game through `get_location`."""
    assert name2fleet(game_with_capital, PLAYER, text) == empty_quadrant()


def test_a_well_formed_fleet_name_still_resolves(game_with_capital):
    flt = name2fleet(game_with_capital, PLAYER, "FLEET12")
    assert flt.ObjTyp == ObjectTypes.Flt and flt.Index == 12


@pytest.mark.parametrize("text", [" 1, 1", "1_0,1", "1,1_0"])
def test_a_coordinate_with_junk_in_it_resolves_to_limbo(game_with_capital, text):
    """`name2coord` already used `pascal_val`; this pins that it keeps doing so,
    since it is the sibling `name2fleet` should have matched all along. Limbo
    is (0,0), which `in_galaxy` excludes."""
    xy = name2coord(game_with_capital, text)
    assert (xy.x, xy.y) == (0, 0)


def test_a_well_formed_coordinate_still_resolves(game_with_capital):
    xy = name2coord(game_with_capital, "0,0")
    assert (xy.x, xy.y) != (0, 0), "0,0 is the capital, not Limbo"


def test_a_scenario_header_version_must_be_digits(tmp_path):
    """Fixed columns 10-11, parsed strictly: `int()` strips whitespace where
    `Val` errors, so a header off by one column would otherwise read as some
    low version and silently enable the old-format shims."""
    scn = tmp_path / "BAD.SCN"
    scn.write_text("SCENARIO 1 0\nTitle\n0 1 1 20 10 1 10 20 4000\n")

    with pytest.raises(ScenarioError):
        read_scenario_intro(scn)


# --- Source-level guards ------------------------------------------------------
#
# These scan `src/` rather than exercising behaviour. They exist because the
# categories above are invisible to ordinary tests -- the code runs, it just
# gives a slightly different answer than the Pascal would.


def _calls_named(name: str) -> list[str]:
    """Every `<name>(...)` call site under src/recreon, as 'path:line'."""
    hits = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == name
            ):
                hits.append(f"{path.relative_to(SRC)}:{node.lineno}")
    return hits


def test_nothing_calls_pythons_round():
    """Pascal's `Round` breaks ties away from zero and Python's does not, so
    every `Round` in the original goes through `pascal_round`. There is no
    legitimate bare `round` in a ported module -- if one appears, it is either
    a missed conversion or wants a comment saying why it is not one."""
    assert _calls_named("round") == []


def test_the_scenario_parser_does_not_use_bare_int():
    """NEWGAME.PAS parses every scalar with `Val` and checks the error. The
    parser had six bare `int()` calls; they are the reason this test exists."""
    tree = ast.parse((SRC / "newgame.py").read_text())
    bare = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "int"
        # int(<enum>) is fine; int(<string expression>) is the risk. Slices and
        # names that are not obviously enums get flagged.
        and node.args
        and isinstance(node.args[0], (ast.Subscript, ast.Constant))
    ]
    assert bare == []


def test_utils_pascal_is_the_only_place_that_touches_the_lcg():
    """`Never call Python's random module` -- a draw that bypasses the ported
    LCG desynchronises every draw after it."""
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "random":
                        offenders.append(str(path.relative_to(SRC)))
            elif isinstance(node, ast.ImportFrom) and node.module == "random":
                offenders.append(str(path.relative_to(SRC)))
    assert offenders == []
