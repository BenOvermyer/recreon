"""The close-up and production screens."""

import pytest

from recreon.main import new_game
from recreon.primintr import get_capital, get_coord
from recreon.types import Empire
from recreon.ui.app import RecreonApp
from recreon.ui.closeup import CloseUpScreen, ProductionScreen
from recreon.utils.pascal import set_rand_seed

PLAYER = Empire.Empire1


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


def at_capital(tmp_path):
    """An app with the map cursor parked on the player's capital."""
    game = new_game()
    app = RecreonApp(game, save_dir=tmp_path)
    xy = get_coord(game, get_capital(game, PLAYER))
    return app, xy


def body_text(screen) -> str:
    return " ".join(str(w.content) for w in screen.query("#body Static"))


async def test_the_production_key_opens_the_screen_for_the_world_under_the_cursor(
    tmp_path,
):
    app, xy = at_capital(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.map_view.cursor_x, app.map_view.cursor_y = xy.x, xy.y

        await pilot.press("i")
        await pilot.pause()

        assert isinstance(app.screen, ProductionScreen)
        text = body_text(app.screen)
        assert "Available industry" in text
        assert "Projected production" in text


async def test_the_close_up_key_opens_the_screen(tmp_path):
    app, xy = at_capital(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.map_view.cursor_x, app.map_view.cursor_y = xy.x, xy.y

        await pilot.press("z")
        await pilot.pause()

        assert isinstance(app.screen, CloseUpScreen)
        assert "Efficiency" in body_text(app.screen)


async def test_empty_space_opens_nothing(tmp_path):
    """Both screens need a world or a base; the cursor is usually on neither."""
    app, _ = at_capital(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Find a sector with nothing in it.
        from recreon.primintr import get_object
        from recreon.types import ObjectTypes

        for xy in app.game.Galaxy.coordinates():
            if get_object(app.game, xy).ObjTyp is ObjectTypes.Void:
                app.map_view.cursor_x, app.map_view.cursor_y = xy.x, xy.y
                break

        await pilot.press("i")
        await pilot.pause()
        assert not isinstance(app.screen, ProductionScreen)

        await pilot.press("z")
        await pilot.pause()
        assert not isinstance(app.screen, CloseUpScreen)


async def test_the_production_screen_shows_the_trillum_reserves(tmp_path):
    """The reserve figure is the only way a player can tell the trillum
    forecast is lying to them -- see #62."""
    app, xy = at_capital(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.map_view.cursor_x, app.map_view.cursor_y = xy.x, xy.y

        await pilot.press("i")
        await pilot.pause()

        assert "Trillum reserves" in body_text(app.screen)
