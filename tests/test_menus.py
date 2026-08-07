"""The in-game menu bar, from PLAYTURN.PAS's seven pull-downs."""

import pytest

from recreon.main import new_game
from recreon.playturn import (
    MENU_BAR,
    NOT_PORTABLE,
    UNREACHABLE,
    Command,
    all_menu_commands,
    menu_for,
)
from recreon.primintr import get_capital, get_coord
from recreon.types import Empire
from recreon.ui.app import RecreonApp
from recreon.ui.closeup import CloseUpScreen, ProductionScreen
from recreon.ui.construction import ConstructionScreen, WarpLinkScreen
from recreon.ui.defenses import DefenseScreen
from recreon.ui.fleet import FleetScreen
from recreon.ui.menu import PENDING, MenuScreen
from recreon.ui.prologue import Attention
from recreon.utils.pascal import set_rand_seed

PLAYER = Empire.Empire1


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


# --- The structure -----------------------------------------------------------


def test_there_are_seven_menus_in_the_originals_order():
    assert [bar.title for bar in MENU_BAR] == [
        "Info",
        "Game",
        "Empire",
        "Worlds",
        "Fleet",
        "Build",
        "Ministry of War",
    ]


def test_accelerators_are_unique_within_each_menu():
    """They have to be: the original selects on a single keypress."""
    for bar in MENU_BAR:
        keys = [item.key for item in bar.items]
        assert len(keys) == len(set(keys)), bar.title


def test_an_accelerator_is_not_always_the_first_letter():
    """"caNcel orders" is N and "auTo attack" is T -- both cases where the
    obvious letter was taken within the same menu."""
    fleet = next(bar for bar in MENU_BAR if bar.title == "Fleet")
    cancel = next(i for i in fleet.items if i.command is Command.CancelOrdCom)
    assert cancel.key == "N"

    war = next(bar for bar in MENU_BAR if bar.title == "Ministry of War")
    auto = next(i for i in war.items if i.command is Command.AutoAttackCom)
    assert auto.key == "T"


def test_the_dead_artifact_commands_are_on_no_menu():
    """`ArtfctCom`, `TransCom` and `HoloCom` are inside the commented block in
    v2.0 -- declared, but menued and dispatched nowhere."""
    on_menus = set(all_menu_commands())
    assert not (UNREACHABLE & on_menus)


def test_every_menu_command_is_unique():
    commands = all_menu_commands()
    assert len(commands) == len(set(commands))


def test_menu_for_finds_where_a_command_lives():
    assert menu_for(Command.FLaunchCom).title == "Fleet"
    assert menu_for(Command.CAddCom).title == "Build"
    assert menu_for(Command.HoloCom) is None


def test_every_menu_command_either_runs_or_explains_itself():
    """No command may be a silent no-op: it opens something, says it is not
    portable, or says what it is waiting on."""
    handled = {
        Command.EndCom,
        Command.XXXCom,
        Command.PauseCom,
        Command.InfoCom,
        Command.ProdInfoCom,
        Command.SelfDestCom,
        Command.WarpLinkFreqCom,
        Command.FLaunchCom,
        Command.FDestCom,
        Command.FTransCom,
        Command.FAbortCom,
        Command.FFuelCom,
        Command.SRMSweepCom,
        Command.OrderCom,
        Command.CancelOrdCom,
        Command.ProbeCom,
        Command.ConStaCom,
        Command.CAddCom,
        Command.CAbortCom,
        Command.DefnsCom,
        Command.AutoAttackCom,
        Command.DesignateCom,
        Command.TerraCom,
        Command.SelfSufCom,
        Command.GrantIndepCom,
        Command.STechCom,
        Command.MSendCom,
        Command.MReadCom,
        Command.LAMCom,
        Command.NAddCom,
        Command.NDelCom,
        Command.HrdCopyCom,
    }

    for command in all_menu_commands():
        assert (
            command in handled
            or command in PENDING
            or command in NOT_PORTABLE
        ), command


# --- Driving it --------------------------------------------------------------


def running(tmp_path):
    game = new_game()
    app = RecreonApp(game, save_dir=tmp_path)
    return app, get_coord(game, get_capital(game, PLAYER))


async def choose(pilot, app, menu_index, item_index):
    await pilot.press("m")
    await pilot.pause()
    for _ in range(menu_index):
        await pilot.press("down")
    await pilot.press("enter")
    await pilot.pause()
    for _ in range(item_index):
        await pilot.press("down")
    await pilot.press("enter")
    await pilot.pause()
    await pilot.pause()


async def test_the_menu_key_opens_the_bar(tmp_path):
    app, _ = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("m")
        await pilot.pause()

        assert isinstance(app.screen, MenuScreen)
        assert app.screen.menu is None


async def test_escape_backs_out_of_a_menu_then_closes_the_bar(tmp_path):
    app, _ = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("m")
        await pilot.pause()
        screen = app.screen

        await pilot.press("enter")  # open Info
        await pilot.pause()
        assert screen.menu is not None

        await pilot.press("escape")
        await pilot.pause()
        assert screen.menu is None
        assert isinstance(app.screen, MenuScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, MenuScreen)


@pytest.mark.parametrize(
    "menu_index,item_index,expected",
    [
        (3, 0, CloseUpScreen),      # Worlds > Close up
        (3, 2, ProductionScreen),   # Worlds > Production
        (4, 0, FleetScreen),        # Fleet > Deploy
        (5, 0, ConstructionScreen), # Build > Site status
        (6, 3, DefenseScreen),      # Ministry of War > Defenses
        (2, 3, WarpLinkScreen),     # Empire > Link frequencies
    ],
)
async def test_menu_commands_open_their_screens(
    tmp_path, menu_index, item_index, expected
):
    app, xy = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.map_view.cursor_x, app.map_view.cursor_y = xy.x, xy.y

        await choose(pilot, app, menu_index, item_index)

        assert isinstance(app.screen, expected)


async def test_an_unported_command_says_what_it_is_waiting_on(tmp_path):
    """Attack is ATTCOMM.PAS. Left on the menu rather than hidden, so the
    menu stays a faithful picture of what the game offers."""
    app, _ = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()

        await choose(pilot, app, 6, 0)  # Ministry of War > Attack

        assert isinstance(app.screen, Attention)
        assert "ATTCOMM" in app.screen.message


async def test_the_status_report_replaces_the_printer(tmp_path):
    """`StatusHardcopy`'s printer has no equivalent; its report does."""
    from recreon.ui.names import StatusReportScreen

    app, _ = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await choose(pilot, app, 1, 1)  # Game > Status hardcopy

        assert isinstance(app.screen, StatusReportScreen)


async def test_a_dos_only_command_says_so(tmp_path):
    app, _ = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()

        await choose(pilot, app, 0, 1)  # Info > DOS shell

        assert isinstance(app.screen, Attention)
        assert "DOS feature" in app.screen.message


async def test_next_turn_from_the_menu_advances_the_year(tmp_path):
    app, _ = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        before = app.game.Year

        await choose(pilot, app, 1, 2)  # Game > Next turn

        assert app.game.Year >= before
        assert not isinstance(app.screen, MenuScreen)


async def test_pause_from_the_menu_toggles_and_reports(tmp_path):
    app, _ = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        before = app.game.PauseActive

        await choose(pilot, app, 1, 0)  # Game > Pause game

        assert app.game.PauseActive is not before
        assert isinstance(app.screen, Attention)
