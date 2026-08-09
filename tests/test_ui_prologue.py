"""The prologue menu screen."""

from pathlib import Path

import pytest
from textual.widgets import ListView

from recreon.loadsave import save_game
from recreon.main import new_game, update_turn
from recreon.ui.app import RecreonApp
from recreon.ui.newgame import NewGameScreen
from recreon.ui.prologue import (
    LOGO,
    Attention,
    ChooseFrom,
    PrologueScreen,
    TextPrompt,
)
from recreon.utils.pascal import set_rand_seed

SCENARIOS = Path(__file__).parent.parent / "src" / "recreon" / "data" / "scenarios"


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


def app_for(tmp_path, game=None):
    return RecreonApp(game, scenario_dir=SCENARIOS, save_dir=tmp_path)


async def finish_new_game(pilot, screen, players: int = 1, scenario="frontier.scn"):
    """Drive the picker that the prologue's 'New game' command pushed.

    Selects by name rather than taking whichever sorts first: most of the
    bundled scenarios set a minimum player count above 1, and frontier.scn is
    the one that accepts a single player.
    """
    listing = screen.query_one(ListView)
    listing.index = next(
        i for i, entry in enumerate(screen.entries) if entry.path.name == scenario
    )
    await pilot.pause()

    await pilot.press("enter")
    await pilot.pause()
    while screen.step == "intro":
        await pilot.press("enter")
        await pilot.pause()
    if screen.step == "count":
        await pilot.press(str(players))
        await pilot.press("enter")
        await pilot.pause()
    for _ in range(players):
        await pilot.press("enter")
        await pilot.pause()


# --- Where the app starts ----------------------------------------------------


async def test_the_app_opens_on_the_prologue(tmp_path):
    """ANACREON.PAS runs `Prologue` before anything else."""
    app = app_for(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, PrologueScreen)
        assert not app.prologue.game_loaded


async def test_the_logo_is_laid_out_without_wrapping(tmp_path):
    """Block art survives only if the widget is exactly the size of the art.

    A wrap or an ellipsis shears the letters apart, and nothing else in the
    suite would notice -- the screen still works, it just looks broken. So
    pin the rendered size against the art's own dimensions.
    """
    lines = LOGO.splitlines()
    art = (max(len(line) for line in lines), len(lines))

    app = app_for(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        logo = app.screen.get_widget_by_id("logo")

        assert (logo.size.width, logo.size.height) == art
        # Centred as a block rather than left against the edge.
        assert logo.region.x > 0


async def test_the_logo_fits_an_eighty_column_terminal(tmp_path):
    """The width the DOS build assumed, and the floor this UI is drawn for."""
    assert max(len(line) for line in LOGO.splitlines()) <= 80

    app = app_for(tmp_path)
    async with app.run_test(size=(80, 30)) as pilot:
        await pilot.pause()
        assert app.screen.get_widget_by_id("logo").size.height == len(LOGO.splitlines())


async def test_a_game_on_the_command_line_skips_the_prologue(tmp_path):
    app = app_for(tmp_path, new_game())
    async with app.run_test() as pilot:
        await pilot.pause()
        assert not isinstance(app.screen, PrologueScreen)
        assert app.prologue.game_loaded
        assert not app.prologue.game_modified


async def test_the_menu_offers_the_originals_commands(tmp_path):
    app = app_for(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        keys = [key for key, _ in app.screen._commands()]

    assert keys == [
        "begin", "new", "load", "save", "quit",
        "time", "add", "delete", "autosave", "pause", "sync",
    ]


# --- Starting and playing ----------------------------------------------------


async def test_new_game_builds_a_galaxy_and_returns_to_the_menu(tmp_path):
    app = app_for(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        prologue = app.screen

        prologue.run_command("new")
        await pilot.pause()
        assert isinstance(app.screen, NewGameScreen)

        await finish_new_game(pilot, app.screen)

        assert isinstance(app.screen, PrologueScreen)
        assert app.prologue.game_loaded
        # Never saved, so quitting should stop to ask.
        assert app.prologue.game_modified
        assert app.game.NoOfPlanets > 0


async def test_begin_leaves_the_menu_for_the_map(tmp_path):
    app = app_for(tmp_path, new_game())
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_prologue()
        await pilot.pause()

        app.screen.run_command("begin")
        await pilot.pause()

        assert not isinstance(app.screen, PrologueScreen)
        assert app.started


async def test_begin_with_no_game_offers_to_load_one(tmp_path):
    """Command 5 loads first when nothing is up, as the original does."""
    app = app_for(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.screen.run_command("begin")
        await pilot.pause()

        # No saves in the directory, so it says so rather than opening a picker.
        assert isinstance(app.screen, Attention)


# --- Saving and loading ------------------------------------------------------


async def test_saving_from_the_menu_writes_a_file(tmp_path):
    app = app_for(tmp_path, new_game())
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_prologue()
        await pilot.pause()
        app.prologue.game_modified = True

        app.screen.run_command("save")
        await pilot.pause()
        assert isinstance(app.screen, TextPrompt)

        await pilot.press("enter")
        await pilot.pause()

        assert (tmp_path / "ANACREON.SAV").exists()
        assert not app.prologue.game_modified


async def test_loading_repoints_every_widget(tmp_path):
    """Loading builds a fresh environment, so a widget still holding the old
    one would keep rendering the previous galaxy."""
    played = new_game()
    for _ in range(20):
        update_turn(played)
    save_game(played, tmp_path / "MID.SAV")

    app = app_for(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.screen.run_command("load")
        await pilot.pause()
        assert isinstance(app.screen, ChooseFrom)

        await pilot.press("enter")
        await pilot.pause()

        assert app.prologue.game_loaded
        assert app.game.Year == played.Year
        assert app.game.CurrentGame == "MID.SAV"
        assert app.map_view.game is app.game
        assert app.status_bar.game is app.game


async def test_loading_with_no_saves_says_so(tmp_path):
    app = app_for(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.screen.run_command("load")
        await pilot.pause()

        assert isinstance(app.screen, Attention)
        assert "no saved games" in app.screen.message


# --- Unsaved changes ---------------------------------------------------------


async def test_quitting_with_unsaved_changes_asks_first(tmp_path):
    app = app_for(tmp_path, new_game())
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_prologue()
        await pilot.pause()
        app.prologue.game_modified = True

        app.screen.run_command("quit")
        await pilot.pause()

        assert isinstance(app.screen, Attention)
        assert "not saved" in app.screen.message
        assert app.is_running


async def test_escaping_that_prompt_loses_the_changes_and_quits(tmp_path):
    """"Press <Esc> to lose changes." -- the original clears the flag."""
    app = app_for(tmp_path, new_game())
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_prologue()
        await pilot.pause()
        app.prologue.game_modified = True

        app.screen.run_command("quit")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        assert not app.prologue.game_modified
        assert not app.is_running


async def test_choosing_to_save_on_the_way_out_saves_and_then_quits(tmp_path):
    """`GameNotSaved` calls `SaveTheGame` and control falls back into
    `QuitGame`, so answering yes does both. Without the continuation the
    player would have to ask to quit twice."""
    app = app_for(tmp_path, new_game())
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_prologue()
        await pilot.pause()
        app.prologue.game_modified = True

        app.screen.run_command("quit")
        await pilot.pause()
        await pilot.click("#yes")
        await pilot.pause()

        assert isinstance(app.screen, TextPrompt)
        await pilot.press("enter")
        await pilot.pause()

        assert (tmp_path / "ANACREON.SAV").exists()
        assert not app.is_running


async def test_quitting_a_saved_game_goes_straight_out(tmp_path):
    app = app_for(tmp_path, new_game())
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_prologue()
        await pilot.pause()
        app.prologue.game_modified = False

        app.screen.run_command("quit")
        await pilot.pause()

        assert not app.is_running


# --- Settings ----------------------------------------------------------------


async def test_a_toggle_updates_its_own_menu_line(tmp_path):
    app = app_for(tmp_path, new_game())
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_prologue()
        await pilot.pause()
        prologue = app.screen

        before = dict(prologue._commands())["autosave"]
        prologue.run_command("autosave")
        await pilot.pause()

        assert "ON" in before
        assert "OFF" in dict(prologue._commands())["autosave"]
        assert isinstance(app.screen, Attention)


async def test_the_time_limit_prompt_rejects_nonsense(tmp_path):
    app = app_for(tmp_path, new_game())
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_prologue()
        await pilot.pause()

        app.screen.run_command("time")
        await pilot.pause()
        assert isinstance(app.screen, TextPrompt)

        prompt = app.screen
        prompt.query_one("Input").value = "nonsense"
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, Attention)
        assert "positive integer" in app.screen.message


async def test_the_time_limit_prompt_accepts_a_number(tmp_path):
    app = app_for(tmp_path, new_game())
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_prologue()
        await pilot.pause()

        app.screen.run_command("time")
        await pilot.pause()
        app.screen.query_one("Input").value = "12"
        await pilot.press("enter")
        await pilot.pause()

        assert app.game.TimePerTurn == 720


# --- Turns -------------------------------------------------------------------


async def test_taking_a_turn_marks_the_game_modified(tmp_path):
    app = app_for(tmp_path, new_game())
    async with app.run_test() as pilot:
        await pilot.pause()
        assert not app.prologue.game_modified

        year = app.game.Year
        await pilot.press("n")
        await pilot.pause()

        assert app.prologue.game_modified
        assert app.game.Year >= year


async def test_taking_a_turn_writes_the_autosave(tmp_path):
    """ANACREON.PAS runs `AutoBackup` after every completed turn."""
    app = app_for(tmp_path, new_game())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()

        assert (tmp_path / "ANACREON.BAK").exists()
