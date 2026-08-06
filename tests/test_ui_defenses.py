"""The defense grid and self-destruct screens."""

import pytest

from recreon.galaxy import XYCoord
from recreon.intrface import create_starbase
from recreon.main import new_game
from recreon.msccomm import TOTAL_MUST_BE_100
from recreon.primintr import get_defense_settings, get_object
from recreon.types import (
    SHIP_TYPES,
    Empire,
    IDNumber,
    ObjectTypes,
    ShellPos,
    TechnologyTypes,
    empty_quadrant,
)
from recreon.ui.app import RecreonApp
from recreon.ui.defenses import DefenseScreen, SelfDestructScreen
from recreon.ui.prologue import Attention, ChooseFrom, TextPrompt
from recreon.utils.pascal import set_rand_seed

T = TechnologyTypes
PLAYER = Empire.Empire1


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


def running(tmp_path):
    return RecreonApp(new_game(), save_dir=tmp_path)


# --- The grid ----------------------------------------------------------------


async def test_the_defense_key_opens_the_grid(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()

        assert isinstance(app.screen, DefenseScreen)


async def test_the_grid_shows_a_row_per_ship_type_with_its_total(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()

        rows = app.screen.query("#grid Static")
        # One heading plus one row per ship type.
        assert len(rows) == len(SHIP_TYPES) + 1
        assert "DeepSp" in str(rows[0].content)
        assert str(rows[1].content).rstrip().endswith("100")


async def test_the_cursor_moves_and_wraps(tmp_path):
    """Up from the first ship goes to the last, as the original's Up/Down
    explicitly do."""
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        screen = app.screen

        assert (screen.ship_index, screen.shell_index) == (0, 0)

        await pilot.press("up")
        await pilot.pause()
        assert screen.ship_index == len(SHIP_TYPES) - 1

        await pilot.press("left")
        await pilot.pause()
        assert screen.shell_index == len(ShellPos) - 1


async def test_typing_a_digit_opens_the_entry_prompt(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()

        await pilot.press("5")
        await pilot.pause()

        assert isinstance(app.screen, TextPrompt)
        assert app.screen.value == "5"


async def test_an_out_of_range_entry_empties_the_shell(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        screen = app.screen

        await pilot.press("1")
        await pilot.pause()
        app.screen.query_one("Input").value = "150"
        await pilot.press("enter")
        await pilot.pause()

        assert screen.dist[ShellPos.DpSpc][SHIP_TYPES[0]] == 0


# --- Leaving -----------------------------------------------------------------


async def test_the_first_escape_normalises_and_explains(tmp_path):
    """Esc runs the legality check, reports it, normalises, and stays. Only a
    second Esc leaves -- the original's `UNTIL (Ch=EscKey) AND NOT (Error)`."""
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        screen = app.screen

        # Break the fighter row.
        await pilot.press("1")
        await pilot.pause()
        app.screen.query_one("Input").value = "150"
        await pilot.press("enter")
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, DefenseScreen)
        assert screen.note == TOTAL_MUST_BE_100

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, DefenseScreen)


async def test_leaving_a_legal_grid_saves_it(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        screen = app.screen

        # Move everything into deep space for fighters, legally.
        ship = SHIP_TYPES[0]
        for shell in ShellPos:
            screen.dist[shell][ship] = 0
        screen.dist[ShellPos.DpSpc][ship] = 100

        await pilot.press("escape")
        await pilot.pause()

        saved = get_defense_settings(app.game, PLAYER).ShellDefDist
        assert saved[ShellPos.DpSpc][ship] == 100


# --- Self-destruct -----------------------------------------------------------


async def test_with_nothing_to_scuttle_it_says_so(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, SelfDestructScreen)
        text = " ".join(str(w.content) for w in screen.query("#body Static"))
        assert "nothing that can be destroyed" in text


async def test_scuttling_a_base_asks_first_and_then_removes_it(tmp_path):
    app = running(tmp_path)
    game = app.game
    base = IDNumber(ObjectTypes.Base, 1)
    create_starbase(game, base, PLAYER, XYCoord(8, 8), T.cmm)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()

        assert isinstance(app.screen, ChooseFrom)
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, Attention)
        assert "Destruct sequence" in app.screen.message

        await pilot.click("#yes")
        await pilot.pause()

        assert get_object(game, XYCoord(8, 8)) == empty_quadrant()


async def test_declining_leaves_the_base_standing(tmp_path):
    app = running(tmp_path)
    game = app.game
    base = IDNumber(ObjectTypes.Base, 1)
    create_starbase(game, base, PLAYER, XYCoord(8, 8), T.cmm)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        await pilot.click("#no")
        await pilot.pause()

        assert isinstance(app.screen, Attention)
        assert "aborted" in app.screen.message
        assert get_object(game, XYCoord(8, 8)) == base
