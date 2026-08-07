"""The interactive attack screens.

`tests/test_ui_attack.py` drives the auto-attack. This file drives
``AttackCommand``: the standard-vs-custom question, the group splitter, and the
round-by-round battle screen with its move, target and retreat decisions.
"""

import pytest

from recreon.attack import GroupStatus
from recreon.fleet import get_next_fleet, move_fleet
from recreon.main import new_game
from recreon.primintr import get_capital, get_coord, put_cargo, put_ships
from recreon.types import (
    Empire,
    ShellPos,
    TechnologyTypes,
    cargo_array,
    ship_array,
)
from recreon.ui.app import RecreonApp
from recreon.ui.attack import (
    AttackScreen,
    BattleScreen,
    GroupSplitterScreen,
    MoveScreen,
    TargetScreen,
)
from recreon.ui.prologue import Attention, ChooseFrom
from recreon.utils.pascal import set_rand_seed

T = TechnologyTypes
PLAYER = Empire.Empire1


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


def running(tmp_path, enemy_fgt=1, transports=0):
    """An app with the player's fleet and an enemy fleet in the same sector."""
    game = new_game()
    app = RecreonApp(game, save_dir=tmp_path)

    xy = get_coord(game, get_capital(game, PLAYER))
    flt = get_next_fleet(game, PLAYER)
    move_fleet(game, flt, xy)
    game.Universe.Fleet[flt.Index].ScoutedBy.add(PLAYER)
    ships = ship_array()
    ships[T.fgt] = 3000
    ships[T.ssp] = 300
    ships[T.trn] = transports
    put_ships(game, flt, ships)
    if transports:
        hold = cargo_array()
        hold[T.men] = 1000
        put_cargo(game, flt, hold)

    enemy = get_next_fleet(game, Empire.Empire2)
    move_fleet(game, enemy, xy)
    game.Universe.Fleet[enemy.Index].ScoutedBy.add(PLAYER)
    weak = ship_array()
    weak[T.fgt] = enemy_fgt
    put_ships(game, enemy, weak)
    return app


async def reach_the_question(pilot, app):
    """Fleet, then target, leaving the standard-configuration question up."""
    app.action_attack()
    await pilot.pause()
    await pilot.press("enter")  # the fleet
    await pilot.pause()
    assert isinstance(app.screen, ChooseFrom)
    await pilot.press("enter")  # the target
    await pilot.pause()
    assert isinstance(app.screen, Attention)


async def reach_the_battle(pilot, app):
    await reach_the_question(pilot, app)
    await pilot.click("#yes")  # standard configuration
    await pilot.pause()
    await pilot.pause()
    assert isinstance(app.screen, BattleScreen)


# --- Getting there -----------------------------------------------------------


async def test_it_asks_about_the_battle_configuration(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await reach_the_question(pilot, app)

        assert "ready to attack" in app.screen.message
        assert "Standard battle configuration" in app.screen.detail


async def test_saying_yes_opens_the_battle_on_the_default_distribution(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await reach_the_battle(pilot, app)

        # fgt and ssp are two ship types, so two groups.
        assert app.screen.session.no_of_groups == 2


async def test_saying_no_opens_the_splitter(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await reach_the_question(pilot, app)

        await pilot.click("#no")
        await pilot.pause()

        assert isinstance(app.screen, GroupSplitterScreen)


async def test_with_no_fleets_it_says_so(tmp_path):
    game = new_game()
    app = RecreonApp(game, save_dir=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_attack()
        await pilot.pause()

        text = " ".join(str(w.content) for w in app.screen.query("#body Static"))
        assert "no fleets deployed" in text


# --- The splitter ------------------------------------------------------------


async def test_the_splitter_loads_a_slot_with_the_space_bar(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await reach_the_question(pilot, app)
        await pilot.click("#no")
        await pilot.pause()

        await pilot.press("space")  # every fighter into slot 1
        await pilot.pause()

        assert app.screen.splitter.gp[1].Num == 3000
        assert app.screen.splitter.sh[T.fgt] == 0


async def test_the_splitters_choice_reaches_the_battle(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await reach_the_question(pilot, app)
        await pilot.click("#no")
        await pilot.pause()

        await pilot.press("space")  # slot 1: all 3000 fighters
        await pilot.press("escape")  # commit -- Escape does not cancel
        await pilot.pause()
        await pilot.pause()

        assert isinstance(app.screen, BattleScreen)
        session = app.screen.session
        assert session.no_of_groups == 1  # the starships were left behind
        assert session.gp[1].Num == 3000


async def test_committing_an_empty_configuration_does_not_attack(tmp_path):
    """`GetGroups` can return nothing, and `IF NoOfGroups>0` then quietly skips
    the whole engagement."""
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await reach_the_question(pilot, app)
        await pilot.click("#no")
        await pilot.pause()

        await pilot.press("escape")  # nothing loaded
        await pilot.pause()
        await pilot.pause()

        assert isinstance(app.screen, AttackScreen)
        text = " ".join(str(w.content) for w in app.screen.query("#body Static"))
        assert "nothing aboard" in text


# --- The battle screen -------------------------------------------------------


async def test_the_battle_screen_shows_both_sides(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await reach_the_battle(pilot, app)

        groups = str(app.screen.query_one("#groups-sheet").content)
        enemy = str(app.screen.query_one("#enemy-sheet").content)

        assert "fgt sq" in groups
        assert "O:DSp" in groups  # both groups start in deep space
        assert "fighter squadrons" in enemy


async def test_engaging_at_range_changes_nothing(tmp_path):
    """No auto-advance and no auto-targeting: a fleet left in deep space with
    no orders trades no fire at all."""
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await reach_the_battle(pilot, app)
        session = app.screen.session

        for _ in range(5):
            await pilot.press("e")
            await pilot.pause()

        assert not session.end_battle
        assert sum(session.casualties.values()) == 0
        assert session.gp[1].Pos is ShellPos.DpSpc


async def test_moving_opens_the_manoeuvre_screen(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await reach_the_battle(pilot, app)

        await pilot.press("m")
        await pilot.pause()

        assert isinstance(app.screen, MoveScreen)


async def test_an_ordered_advance_closes_a_shell(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await reach_the_battle(pilot, app)
        session = app.screen.session

        await pilot.press("m")
        await pilot.pause()
        await pilot.press("a")  # the highlighted group advances
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        assert session.gp[1].Pos is ShellPos.HiOrb


async def test_cancelling_the_manoeuvre_leaves_everyone_put(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await reach_the_battle(pilot, app)
        session = app.screen.session

        await pilot.press("m")
        await pilot.pause()
        await pilot.press("a")
        await pilot.press("escape")
        await pilot.pause()
        await pilot.pause()

        assert session.gp[1].Pos is ShellPos.DpSpc
        assert session.gp[1].Sta is GroupStatus.GReady


async def test_targeting_opens_the_target_screen_and_sticks(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await reach_the_battle(pilot, app)
        session = app.screen.session

        await pilot.press("t")
        await pilot.pause()
        assert isinstance(app.screen, TargetScreen)

        await pilot.press("f")  # ATSymb[fgt]
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        assert session.gp[1].Trg is T.fgt


async def test_the_details_screen_toggles(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await reach_the_battle(pilot, app)

        await pilot.press("d")
        await pilot.pause()
        assert "destroyed by enemy" in str(app.screen.query_one("#groups-sheet").content)

        await pilot.press("d")
        await pilot.pause()
        assert "Your groups" in str(app.screen.query_one("#groups-sheet").content)


async def test_retreating_asks_first_then_ends_the_battle(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await reach_the_battle(pilot, app)
        session = app.screen.session

        await pilot.press("r")
        await pilot.pause()
        assert isinstance(app.screen, Attention)
        assert "Break off" in app.screen.message

        await pilot.click("#yes")
        for _ in range(6):
            await pilot.pause()

        assert session.end_battle
        assert isinstance(app.screen, AttackScreen)
        text = " ".join(str(w.content) for w in app.screen.query("#body Static"))
        assert "retreated" in text


async def test_declining_the_retreat_keeps_fighting(tmp_path):
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await reach_the_battle(pilot, app)
        session = app.screen.session

        await pilot.press("r")
        await pilot.pause()
        await pilot.click("#no")
        await pilot.pause()
        await pilot.pause()

        assert not session.end_battle
        assert isinstance(app.screen, BattleScreen)


async def test_a_fight_pressed_home_ends_and_reports(tmp_path):
    """Aim, close, keep firing -- the whole loop through the real screens."""
    app = running(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await reach_the_battle(pilot, app)
        session = app.screen.session

        # Point both groups at the enemy's fighters.
        session.set_targets(dict.fromkeys(session.target_options(), T.fgt))

        for _ in range(30):
            if session.end_battle:
                break
            if not isinstance(app.screen, BattleScreen):
                break
            await pilot.press("m")
            await pilot.pause()
            if isinstance(app.screen, MoveScreen):
                await pilot.press("a")
                await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()

        assert session.end_battle
        for _ in range(6):
            await pilot.pause()

        assert isinstance(app.screen, AttackScreen)
        text = " ".join(str(w.content) for w in app.screen.query("#body Static"))
        assert text.strip()
