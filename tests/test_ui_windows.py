"""The status-window screens, driven through the real app by their F-keys."""

import pytest

from recreon.fleet import get_next_fleet, move_fleet
from recreon.main import new_game
from recreon.primintr import get_capital, get_coord, put_ships
from recreon.types import Empire, TechnologyTypes, ship_array
from recreon.ui.app import RecreonApp
from recreon.ui.menu import MenuScreen
from recreon.ui.windows import (
    EmpireWindowScreen,
    FleetWindowScreen,
    HelpWindowScreen,
    NamesWindowScreen,
    NewsWindowScreen,
    StatusWindowScreen,
)
from recreon.utils.pascal import set_rand_seed

T = TechnologyTypes
PLAYER = Empire.Empire1


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


def running(tmp_path, with_fleet=False):
    game = new_game()
    app = RecreonApp(game, save_dir=tmp_path)
    if with_fleet:
        xy = get_coord(game, get_capital(game, PLAYER))
        flt = get_next_fleet(game, PLAYER)
        move_fleet(game, flt, xy)
        game.Universe.Fleet[flt.Index].ScoutedBy.add(PLAYER)
        ships = ship_array()
        ships[T.fgt] = 300
        put_ships(game, flt, ships)
    return app


def sheet(app) -> str:
    return str(app.screen.query_one("#sheet").content)


# --- The keys ----------------------------------------------------------------


@pytest.mark.parametrize(
    "key,expected",
    [
        ("f1", HelpWindowScreen),
        ("f3", StatusWindowScreen),
        ("f4", StatusWindowScreen),
        ("f5", FleetWindowScreen),
        ("f6", FleetWindowScreen),
        ("f7", NewsWindowScreen),
        ("f8", EmpireWindowScreen),
        ("f9", NamesWindowScreen),
    ],
)
async def test_each_function_key_opens_its_window(tmp_path, key, expected):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()

        await pilot.press(key)
        await pilot.pause()

        assert isinstance(app.screen, expected)


async def test_f2_opens_the_menu_bar_not_a_window(tmp_path):
    """The original's own help text says "<F2> Return to Menu" and "<F10> Map
    Window". F10 was bound to the menu before HLPWIND.PAS was read."""
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()

        await pilot.press("f2")
        await pilot.pause()

        assert isinstance(app.screen, MenuScreen)


async def test_f10_closes_a_window_and_returns_to_the_map(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("f8")
        await pilot.pause()
        assert isinstance(app.screen, EmpireWindowScreen)

        await pilot.press("f10")
        await pilot.pause()

        assert not isinstance(app.screen, EmpireWindowScreen)


async def test_escape_closes_a_window(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("f7")
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()

        assert not isinstance(app.screen, NewsWindowScreen)


# --- What they show ----------------------------------------------------------


async def test_the_status_window_shows_both_tables(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("f3")
        await pilot.pause()

        text = sheet(app)
        assert "World status" in text
        assert "Military status" in text
        assert "PlntName" in text


async def test_the_fleet_window_says_when_there_are_none(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("f5")
        await pilot.pause()

        assert "No fleets have been deployed." in sheet(app)


async def test_the_fleet_window_shows_both_tables(tmp_path):
    app = running(tmp_path, with_fleet=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("f5")
        await pilot.pause()

        text = sheet(app)
        assert "Fleet position" in text
        assert "Fleet contents" in text
        assert "at destination" in text


async def test_the_empire_window_lists_the_player(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("f8")
        await pilot.pause()

        text = sheet(app)
        assert "Empire" in text
        assert "Player" in text or "Empire 1" in text


async def test_the_names_window_says_when_there_are_none(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("f9")
        await pilot.pause()

        assert "No names have been defined." in sheet(app)


async def test_the_help_window_falls_back_to_the_key_list(tmp_path):
    """`ANACREON.HLP` does not ship, so this is what a player got -- and the
    index is shown alongside as a record of what the manual covered."""
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("f1")
        await pilot.pause()

        text = sheet(app)
        assert "Help file not available" in text
        assert "<F10>   Map Window" in text
        assert "Combat" in text  # the index


async def test_the_help_window_pages_a_real_help_file(tmp_path):
    from recreon.hlpwind import LINES_PER_PAGE

    hlp = tmp_path / "ANACREON.HLP"
    buf = bytearray()
    for page in range(3):
        for line in range(LINES_PER_PAGE):
            text = f"P{page}L{line}".encode("cp437")
            buf.append(len(text))
            buf += text.ljust(80, b"\x00")
    hlp.write_bytes(bytes(buf))

    app = running(tmp_path)
    app.game.HlpDirect = str(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("f1")
        await pilot.pause()
        assert "P1L0" in sheet(app)

        await pilot.press("pagedown")
        await pilot.pause()
        assert "P2L0" in sheet(app)

        # Page 2 is the last valid record of three, so this goes no further.
        await pilot.press("pagedown")
        await pilot.pause()
        assert "P2L0" in sheet(app)

        await pilot.press("pageup")
        await pilot.pause()
        assert "P1L0" in sheet(app)


async def test_windows_do_nothing_before_a_game_is_started(tmp_path):
    app = RecreonApp(save_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        # The prologue is up; the F-keys must not push a window behind it.
        await pilot.press("f8")
        await pilot.pause()

        assert not isinstance(app.screen, EmpireWindowScreen)
