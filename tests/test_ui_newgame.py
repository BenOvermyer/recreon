"""The new-game screens: scenario picker, introduction, naming."""

from pathlib import Path

import pytest

from recreon.ui.app import RecreonApp
from recreon.ui.newgame import NewGameScreen, SuggestionsScreen
from recreon.types import Empire
from recreon.utils.pascal import set_rand_seed

SCENARIOS = Path(__file__).parent.parent / "src" / "recreon" / "data" / "scenarios"


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


async def open_picker(app, pilot, directory=SCENARIOS):
    """Push the picker directly, as the prologue's 'New game' command does.

    Driving it through the prologue would test the menu rather than the
    picker; `test_ui_prologue.py` covers that path.
    """
    screen = NewGameScreen(directory)
    app.push_screen(screen, lambda game: game and app.adopt_game(game))
    await pilot.pause()
    return screen


async def walk_to_naming(pilot, screen, players: int | None = None):
    """Pick the first scenario, page past the intro, answer the count."""
    await pilot.press("enter")
    await pilot.pause()

    while screen.step == "intro":
        await pilot.press("enter")
        await pilot.pause()

    if screen.step == "count":
        for ch in str(players if players is not None else 1):
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()


async def test_the_picker_starts_on_the_scenario_list():
    app = RecreonApp(None, scenario_dir=SCENARIOS)
    async with app.run_test() as pilot:
        screen = await open_picker(app, pilot)
        assert screen.step == "scenario"
        assert not app.started


async def test_the_status_bar_says_so_before_a_game_exists():
    """A blank environment has an unallocated galaxy, and asking it for a
    sector raises rather than wrapping to the far edge."""
    app = RecreonApp(None)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert "No game loaded" in str(app.status_bar.content)


async def test_picking_a_scenario_shows_its_introduction():
    app = RecreonApp(None, scenario_dir=SCENARIOS)
    async with app.run_test() as pilot:
        screen = await open_picker(app, pilot)

        await pilot.press("enter")
        await pilot.pause()

        assert screen.step == "intro"
        assert screen.header.title == "The Kalgan Frontier"
        assert screen.pages


async def test_the_whole_flow_builds_a_galaxy():
    app = RecreonApp(None, scenario_dir=SCENARIOS)
    async with app.run_test() as pilot:
        screen = await open_picker(app, pilot)

        await walk_to_naming(pilot, screen, players=2)
        assert screen.step == "name"
        assert screen.count == 2

        for _ in range(2):
            await pilot.press("enter")
            await pilot.pause()

        assert app.started
        assert app.game.NoOfPlanets > 0
        players = [
            data.EmpireName
            for data in app.game.Universe.EmpireData.values()
            if data.InUse and data.IsAPlayer
        ]
        assert len(players) == 2


async def test_an_empty_name_takes_the_suggestion():
    """And the suggestion comes from the original's 59-name table."""
    from recreon.newgame import RND_EMPIRE_NAMES

    app = RecreonApp(None, scenario_dir=SCENARIOS)
    async with app.run_test() as pilot:
        screen = await open_picker(app, pilot)

        await walk_to_naming(pilot, screen, players=1)
        suggestion = screen.suggestion
        assert suggestion in RND_EMPIRE_NAMES

        await pilot.press("enter")
        await pilot.pause()

        assert app.game.Universe.EmpireData[Empire.Empire1].EmpireName == suggestion


async def test_a_typed_name_is_capitalised():
    """`Name[1]:=UpCase(Name[1])` runs whichever way the name arrived."""
    app = RecreonApp(None, scenario_dir=SCENARIOS)
    async with app.run_test() as pilot:
        screen = await open_picker(app, pilot)

        await walk_to_naming(pilot, screen, players=1)
        for ch in "sarkhon":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        assert app.game.Universe.EmpireData[Empire.Empire1].EmpireName == "Sarkhon"


async def test_a_bad_player_count_is_rejected_without_advancing():
    app = RecreonApp(None, scenario_dir=SCENARIOS)
    async with app.run_test() as pilot:
        screen = await open_picker(app, pilot)

        await pilot.press("enter")
        await pilot.pause()
        while screen.step == "intro":
            await pilot.press("enter")
            await pilot.pause()

        assert screen.step == "count"
        for ch in "99":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        assert screen.step == "count"
        assert "between 1 and 4" in str(screen.query_one("#hint").content)


async def test_a_non_numeric_player_count_is_rejected():
    app = RecreonApp(None, scenario_dir=SCENARIOS)
    async with app.run_test() as pilot:
        screen = await open_picker(app, pilot)

        await pilot.press("enter")
        await pilot.pause()
        while screen.step == "intro":
            await pilot.press("enter")
            await pilot.pause()

        await pilot.press("x")
        await pilot.press("enter")
        await pilot.pause()

        assert screen.step == "count"
        assert "valid number" in str(screen.query_one("#hint").content)


async def test_escape_at_the_name_prompt_opens_the_suggestions():
    """The help line reads '<Esc>:Suggestions', not '<Esc>:Exit'."""
    app = RecreonApp(None, scenario_dir=SCENARIOS)
    async with app.run_test() as pilot:
        screen = await open_picker(app, pilot)

        await walk_to_naming(pilot, screen, players=1)
        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, SuggestionsScreen)

        await pilot.press("enter")
        await pilot.pause()

        assert screen.query_one("#answer").value == "Aaraavon"


async def test_escape_during_the_intro_goes_back_to_the_list():
    app = RecreonApp(None, scenario_dir=SCENARIOS)
    async with app.run_test() as pilot:
        screen = await open_picker(app, pilot)

        await pilot.press("enter")
        await pilot.pause()
        assert screen.step == "intro"

        await pilot.press("escape")
        await pilot.pause()
        assert screen.step == "scenario"


async def test_an_empty_directory_says_so(tmp_path):
    """AttentionWindow('There are no Anacreon scenario', 'files in "…"')."""
    app = RecreonApp(None, scenario_dir=tmp_path)
    async with app.run_test() as pilot:
        screen = await open_picker(app, pilot, tmp_path)
        prompt = str(screen.query_one("#prompt").content)
        assert "no Anacreon scenario files" in prompt


async def test_backing_out_of_the_picker_leaves_the_app_running():
    """`StartNewGame`'s Exit flag returns to the prologue, it does not quit."""
    app = RecreonApp(None, scenario_dir=SCENARIOS)
    async with app.run_test() as pilot:
        await open_picker(app, pilot)
        await pilot.press("escape")
        await pilot.pause()

        assert not isinstance(app.screen, NewGameScreen)
        assert not app.started
        assert app.is_running
