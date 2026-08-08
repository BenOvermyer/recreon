"""The fleet screen, the distribution grid and the order editor."""

import pytest

from recreon.fleet import get_next_fleet, move_fleet
from recreon.main import new_game
from recreon.orders import fleet_next_statement, get_fleet_code
from recreon.primintr import get_capital, get_coord, get_ships, put_ships
from recreon.types import Empire, TechnologyTypes, ship_array
from recreon.ui.app import RecreonApp
from recreon.ui.fleet import DistributionScreen, FleetScreen, OrdersScreen
from recreon.ui.prologue import Attention, ChooseFrom, TextPrompt
from recreon.utils.pascal import set_rand_seed

T = TechnologyTypes
PLAYER = Empire.Empire1


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


def running(tmp_path, with_fleet=True):
    game = new_game()
    app = RecreonApp(game, save_dir=tmp_path)
    if with_fleet:
        home = get_capital(game, PLAYER)
        flt = get_next_fleet(game, PLAYER)
        move_fleet(game, flt, get_coord(game, home))
        # Scouted, because GetGround filters on it even for your own fleets.
        game.Universe.Fleet[flt.Index].ScoutedBy.add(PLAYER)
        ships = ship_array()
        ships[T.fgt] = 120
        ships[T.trn] = 40
        put_ships(game, flt, ships)
    return app


async def open_fleets(app, pilot):
    await pilot.press("f")
    await pilot.pause()
    return app.screen


# --- The list ----------------------------------------------------------------


async def test_the_fleet_key_lists_your_fleets(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await open_fleets(app, pilot)

        assert isinstance(screen, FleetScreen)
        assert len(screen.fleets) == 1


async def test_with_no_fleets_it_says_so(tmp_path):
    app = running(tmp_path, with_fleet=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await open_fleets(app, pilot)

        text = " ".join(str(w.content) for w in screen.query("#list Static"))
        assert "no fleets deployed" in text


# --- Destination -------------------------------------------------------------


async def test_setting_a_destination(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await open_fleets(app, pilot)
        flt = screen.selected

        screen.action_destination()
        await pilot.pause()
        app.screen.query_one("Input").value = "2,2"
        await pilot.press("enter")
        await pilot.pause()

        assert app.game.Universe.Fleet[flt.Index].Dest != get_coord(
            app.game, get_capital(app.game, PLAYER)
        )


async def test_a_malformed_destination_is_refused(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await open_fleets(app, pilot)

        screen.action_destination()
        await pilot.pause()
        app.screen.query_one("Input").value = "somewhere"
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, Attention)
        assert "x,y" in app.screen.message


# --- Orders ------------------------------------------------------------------


async def test_writing_orders_compiles_and_installs_them(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await open_fleets(app, pilot)
        flt = screen.selected

        screen.action_orders()
        await pilot.pause()
        assert isinstance(app.screen, OrdersScreen)

        app.screen.query_one("TextArea").text = "WAIT\nREPE"
        app.screen.action_accept()
        await pilot.pause()

        assert isinstance(app.screen, Attention)
        assert "completed" in app.screen.message
        assert len(get_fleet_code(app.game, flt)) == 2
        assert fleet_next_statement(app.game, flt) == 1


async def test_a_bad_order_line_is_reported_with_its_number(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await open_fleets(app, pilot)

        screen.action_orders()
        await pilot.pause()
        app.screen.query_one("TextArea").text = "WAIT\nBOGUS"
        app.screen.action_accept()
        await pilot.pause()

        assert isinstance(app.screen, Attention)
        assert "line 2" in app.screen.message


async def test_cancelling_orders_clears_them(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await open_fleets(app, pilot)
        flt = screen.selected

        screen.action_orders()
        await pilot.pause()
        app.screen.query_one("TextArea").text = "WAIT"
        app.screen.action_accept()
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        screen.action_cancel_orders()
        await pilot.pause()

        assert fleet_next_statement(app.game, flt) == 0
        assert get_fleet_code(app.game, flt) == []


# --- Transfer ----------------------------------------------------------------


async def test_transferring_moves_ships_between_fleet_and_world(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await open_fleets(app, pilot)
        flt = screen.selected
        home = get_capital(app.game, PLAYER)

        screen.action_transfer()
        await pilot.pause()
        assert isinstance(app.screen, ChooseFrom)

        await pilot.press("enter")
        await pilot.pause()
        grid = app.screen
        assert isinstance(grid, DistributionScreen)

        total = grid.fleet_ships[T.fgt] + grid.ground_ships[T.fgt]
        grid.fleet_ships[T.fgt] = 20
        grid.ground_ships[T.fgt] = total - 20
        grid.action_accept()
        await pilot.pause()

        assert get_ships(app.game, flt)[T.fgt] == 20
        assert get_ships(app.game, home)[T.fgt] == total - 20


async def test_the_grid_refuses_to_close_while_the_fleet_is_overloaded(tmp_path):
    """Cargo needs transports to lift it, so a fleet can be loaded past its
    capacity -- and has to be fixed before leaving."""
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await open_fleets(app, pilot)

        screen.action_transfer()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        grid = app.screen

        grid.fleet_ships[T.trn] = 0
        grid.fleet_cargo[T.met] = 99999
        grid.action_accept()
        await pilot.pause()

        assert isinstance(app.screen, DistributionScreen)
        assert "transports" in grid.note


async def test_backing_out_of_the_grid_changes_nothing(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await open_fleets(app, pilot)
        flt = screen.selected
        before = dict(get_ships(app.game, flt))

        screen.action_transfer()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        app.screen.fleet_ships[T.fgt] = 1
        await pilot.press("escape")
        await pilot.pause()

        assert get_ships(app.game, flt) == before


# --- Other commands ----------------------------------------------------------


async def test_sweeping_an_empty_sector_reports_nothing_found(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await open_fleets(app, pilot)

        screen.action_sweep()
        await pilot.pause()

        assert isinstance(app.screen, Attention)
        assert "No SRMs found" in app.screen.message


async def test_launching_a_probe(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await open_fleets(app, pilot)

        screen.action_probe()
        await pilot.pause()
        app.screen.query_one("Input").value = "3,3"
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, Attention)
        assert "Probe #1" in app.screen.message


async def test_aborting_a_fleet_onto_your_own_world_needs_no_confirmation(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await open_fleets(app, pilot)
        flt = screen.selected
        home = get_capital(app.game, PLAYER)
        before = get_ships(app.game, home)[T.fgt]

        screen.action_abort()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert flt.Index not in app.game.GlobalSets.SetOfActiveFleets
        assert get_ships(app.game, home)[T.fgt] == before + 120


# --- Deploy ------------------------------------------------------------------
#
# The one command driven by PLAYTURN.PAS's parameter table rather than by
# parameters the screen picks itself, so these also exercise `ParameterSession`
# against a real app.


async def answer(app, pilot, text):
    """Type one parameter into whatever prompt is up."""
    app.screen.query_one("Input").value = text
    await pilot.press("enter")
    await pilot.pause()


async def test_deploying_a_fleet_asks_the_originals_three_questions(tmp_path):
    app = running(tmp_path, with_fleet=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await open_fleets(app, pilot)
        home = get_capital(app.game, PLAYER)
        put_ships(app.game, home, {**ship_array(), T.fgt: 500})

        screen.action_deploy()
        await pilot.pause()
        assert app.screen.prompt == "What name shall we use for this fleet? "

        await answer(app, pilot, "Vanguard")
        assert app.screen.prompt == "Where shall we deploy the fleet from? "

        await answer(app, pilot, "0,0")
        assert app.screen.prompt == "What shall its destination be? "

        await answer(app, pilot, "2,2")
        assert isinstance(app.screen, DistributionScreen)
        assert "Vanguard ready to be deployed from" in app.screen.heading


async def test_a_deployed_fleet_carries_its_name_and_its_ships(tmp_path):
    app = running(tmp_path, with_fleet=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await open_fleets(app, pilot)
        home = get_capital(app.game, PLAYER)
        put_ships(app.game, home, {**ship_array(), T.fgt: 500})

        screen.action_deploy()
        await pilot.pause()
        for text in ("Vanguard", "0,0", "2,2"):
            await answer(app, pilot, text)

        grid = app.screen
        grid.fleet_ships[T.fgt] = 300
        grid.ground_ships[T.fgt] = 200
        grid.action_accept()
        await pilot.pause()

        assert len(app.game.GlobalSets.SetOfActiveFleets) == 1
        (index,) = app.game.GlobalSets.SetOfActiveFleets
        assert app.game.Universe.Fleet[index].Ships[T.fgt] == 300
        assert get_ships(app.game, home)[T.fgt] == 200


async def test_a_bad_answer_re_asks_with_the_originals_message(tmp_path):
    app = running(tmp_path, with_fleet=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await open_fleets(app, pilot)

        screen.action_deploy()
        await pilot.pause()
        await answer(app, pilot, "Muchtoolonganame")

        assert app.screen.prompt == "What name shall we use for this fleet? "
        assert "restrict yourself to 8 characters" in app.screen.detail


async def test_escaping_a_prompt_abandons_the_whole_command(tmp_path):
    """The original sets `Comm := NullCom` and jumps clear of the loop -- the
    answers already given go with it, and there is no going back one step."""
    app = running(tmp_path, with_fleet=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await open_fleets(app, pilot)

        screen.action_deploy()
        await pilot.pause()
        await answer(app, pilot, "Vanguard")
        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, FleetScreen)
        assert not app.game.GlobalSets.SetOfActiveFleets


async def test_deploying_is_refused_once_thirty_fleets_are_in_space(tmp_path):
    """`TrapCommandErrors`, which fires before the first question is asked."""
    from recreon.types import NO_OF_FLEETS_PER_EMPIRE

    app = running(tmp_path, with_fleet=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await open_fleets(app, pilot)

        full = set(range(1, NO_OF_FLEETS_PER_EMPIRE + 1))
        app.game.GlobalSets.SetOfFleetsOf[PLAYER] |= full
        app.game.GlobalSets.SetOfActiveFleets |= full

        screen.action_deploy()
        await pilot.pause()

        assert isinstance(app.screen, Attention)
        assert "too many fleets in space already" in app.screen.message
