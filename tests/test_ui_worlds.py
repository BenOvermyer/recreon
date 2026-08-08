"""The world and empire command screens."""

import pytest

from recreon.designcom import inbox
from recreon.main import new_game
from recreon.primintr import get_capital, get_coord, get_status, get_type
from recreon.types import Empire, IndusTypes
from recreon.ui.app import RecreonApp
from recreon.ui.prologue import Attention, ChooseFrom
from recreon.ui.worlds import (
    ISSPScreen,
    ReadMessagesScreen,
    SendMessageScreen,
    TerraformScreen,
    TradeTechnologyScreen,
)
from recreon.utils.pascal import set_rand_seed

PLAYER = Empire.Empire1


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


def on_capital(tmp_path):
    game = new_game()
    app = RecreonApp(game, save_dir=tmp_path)
    return app, get_coord(game, get_capital(game, PLAYER))


async def at_cursor(app, pilot, xy, action):
    app.map_view.cursor_x, app.map_view.cursor_y = xy.x, xy.y
    getattr(app, action)()
    await pilot.pause()
    await pilot.pause()


# --- Designate ---------------------------------------------------------------


async def test_designating_offers_types_and_applies_one(tmp_path):
    app, xy = on_capital(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await at_cursor(app, pilot, xy, "action_designate")

        assert isinstance(app.screen, ChooseFrom)
        assert app.screen.options

        world = app.game.Galaxy.sector(xy).Obj
        chosen = app.screen.options[0][0]
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        # The capital designation warns; anything else applies straight away.
        if isinstance(app.screen, Attention):
            await pilot.click("#yes")
            await pilot.pause()

        assert get_type(app.game, world) is chosen


# --- ISSP --------------------------------------------------------------------


async def test_issp_settings_are_saved_on_the_way_out(tmp_path):
    app, xy = on_capital(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await at_cursor(app, pilot, xy, "action_issp")

        screen = app.screen
        assert isinstance(screen, ISSPScreen)
        screen.settings[IndusTypes.CheInd] = 9

        await pilot.press("escape")
        await pilot.pause()

        from recreon.designcom import issp_settings

        world = app.game.Galaxy.sector(xy).Obj
        assert issp_settings(app.game, world)[IndusTypes.CheInd] == 9


# --- Liberate ----------------------------------------------------------------


async def test_liberating_needs_confirmation(tmp_path):
    app, xy = on_capital(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await at_cursor(app, pilot, xy, "action_liberate")

        assert isinstance(app.screen, ChooseFrom)
        world = app.game.Galaxy.sector(xy).Obj

        await pilot.press("enter")  # Independent
        await pilot.pause()
        assert isinstance(app.screen, Attention)

        await pilot.click("#no")
        await pilot.pause()
        assert get_status(app.game, world) is PLAYER

        # And yes actually does it.
        await pilot.press("escape")
        await pilot.pause()
        await at_cursor(app, pilot, xy, "action_liberate")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.click("#yes")
        await pilot.pause()

        assert get_status(app.game, world) is Empire.Indep


# --- Terraform ---------------------------------------------------------------


async def test_terraforming_offers_classes(tmp_path):
    app, xy = on_capital(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await at_cursor(app, pilot, xy, "action_terraform")

        # Either a class chooser, or the screen saying it cannot be done.
        assert isinstance(app.screen, (ChooseFrom, TerraformScreen))


# --- Messages ----------------------------------------------------------------


async def test_sending_a_message_puts_it_in_the_inbox(tmp_path):
    app, _ = on_capital(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_send_message()
        await pilot.pause()

        assert isinstance(app.screen, ChooseFrom)
        recipients = [emp for emp, _ in app.screen.options]
        await pilot.press("enter")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, SendMessageScreen)
        screen.query_one("TextArea").text = "Header\nBody"
        screen.action_send()
        await pilot.pause()

        assert inbox(app.game, recipients[0])


async def test_the_inbox_lists_what_arrived(tmp_path):
    app, _ = on_capital(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()

        from recreon.designcom import send_message_command

        send_message_command(app.game, PLAYER, {PLAYER}, ["Header", "Note"])

        app.action_read_messages()
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, ReadMessagesScreen)
        assert len(screen.messages) == 1


async def test_an_empty_inbox_says_so(tmp_path):
    app, _ = on_capital(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_read_messages()
        await pilot.pause()

        text = " ".join(str(w.content) for w in app.screen.query("#body Static"))
        assert "no messages" in text


# --- Trade technology --------------------------------------------------------


async def test_trading_technology_offers_recipients(tmp_path):
    app, _ = on_capital(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_trade_technology()
        await pilot.pause()

        assert isinstance(app.screen, (ChooseFrom, TradeTechnologyScreen))


# --- LAMs --------------------------------------------------------------------


async def test_launching_lams_needs_a_base_under_the_cursor(tmp_path):
    app, xy = on_capital(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await at_cursor(app, pilot, xy, "action_launch_lams")

        assert isinstance(app.screen, Attention)
        assert "starbases" in app.screen.message
