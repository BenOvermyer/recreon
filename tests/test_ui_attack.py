"""The auto-attack screen."""

import pytest

from recreon.fleet import get_next_fleet, move_fleet
from recreon.main import new_game
from recreon.primintr import get_capital, get_coord, put_ships
from recreon.types import Empire, TechnologyTypes, ship_array
from recreon.ui.app import RecreonApp
from recreon.ui.attack import AutoAttackScreen
from recreon.ui.prologue import Attention, ChooseFrom
from recreon.utils.pascal import set_rand_seed

T = TechnologyTypes
PLAYER = Empire.Empire1


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


def running(tmp_path, with_fleet=True, with_enemy=False):
    game = new_game()
    app = RecreonApp(game, save_dir=tmp_path)
    if not with_fleet:
        return app

    xy = get_coord(game, get_capital(game, PLAYER))
    flt = get_next_fleet(game, PLAYER)
    move_fleet(game, flt, xy)
    game.Universe.Fleet[flt.Index].ScoutedBy.add(PLAYER)
    ships = ship_array()
    ships[T.fgt] = 3000
    ships[T.ssp] = 300
    put_ships(game, flt, ships)

    if with_enemy:
        enemy = get_next_fleet(game, Empire.Empire2)
        move_fleet(game, enemy, xy)
        game.Universe.Fleet[enemy.Index].ScoutedBy.add(PLAYER)
        weak = ship_array()
        weak[T.fgt] = 1
        put_ships(game, enemy, weak)
    return app


async def test_with_no_fleets_it_says_so(tmp_path):
    app = running(tmp_path, with_fleet=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_auto_attack()
        await pilot.pause()

        text = " ".join(
            str(w.content) for w in app.screen.query("#body Static")
        )
        assert "no fleets deployed" in text


async def test_a_fleet_with_nothing_to_attack_says_so(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_auto_attack()
        await pilot.pause()

        assert isinstance(app.screen, ChooseFrom)
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        assert isinstance(app.screen, Attention)
        assert "nothing here to attack" in app.screen.message


async def test_attacking_asks_to_confirm_then_resolves(tmp_path):
    app = running(tmp_path, with_enemy=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_auto_attack()
        await pilot.pause()

        await pilot.press("enter")  # the fleet
        await pilot.pause()
        assert isinstance(app.screen, ChooseFrom)

        await pilot.press("enter")  # the target
        await pilot.pause()
        assert isinstance(app.screen, Attention)
        assert "ready to attack" in app.screen.message

        await pilot.click("#yes")
        await pilot.pause()
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, AutoAttackScreen)
        text = " ".join(str(w.content) for w in screen.query("#body Static"))
        assert text.strip()


async def test_declining_resolves_nothing(tmp_path):
    app = running(tmp_path, with_enemy=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        before = len(app.game.GlobalSets.SetOfActiveFleets)

        app.action_auto_attack()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.click("#no")
        await pilot.pause()

        assert len(app.game.GlobalSets.SetOfActiveFleets) == before
