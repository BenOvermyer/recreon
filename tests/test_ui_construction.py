"""The construction and warp-link screens."""

from pathlib import Path

import pytest

from recreon.datacnst import TechDev
from recreon.galaxy import XYCoord
from recreon.intrface import create_stargate, next_stargate_slot
from recreon.main import new_game
from recreon.types import Empire, IDNumber, ObjectTypes, TechLevel, TechnologyTypes
from recreon.ui.app import RecreonApp
from recreon.ui.construction import ConstructionScreen, WarpLinkScreen
from recreon.ui.prologue import Attention, ChooseFrom, TextPrompt
from recreon.utils.pascal import set_rand_seed

T = TechnologyTypes


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


def app_with_tech(tmp_path, level=TechLevel.GteTchLvl):
    """A running game whose player can build everything."""
    game = new_game()
    data = game.Universe.EmpireData[Empire.Empire1]
    data.TechnologyLevel = level
    data.Technology = set(TechDev[level])
    return RecreonApp(game, save_dir=tmp_path)


async def open_construction(app, pilot):
    await pilot.press("b")
    await pilot.pause()
    return app.screen


# --- Status ------------------------------------------------------------------


async def test_the_build_key_opens_the_status_screen(tmp_path):
    app = app_with_tech(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await open_construction(app, pilot)

        assert isinstance(screen, ConstructionScreen)
        assert screen.rows == []


async def test_an_empty_table_says_there_are_no_sites(tmp_path):
    app = app_with_tech(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await open_construction(app, pilot)
        text = " ".join(
            str(w.content) for w in screen.query("#table Static")
        )

        assert "no active construction sites" in text


# --- Constructing ------------------------------------------------------------


async def build_at(app, pilot, screen, where: str):
    screen.action_construct()
    await pilot.pause()
    await pilot.press("enter")  # first buildable type
    await pilot.pause()
    app.screen.query_one("Input").value = where
    await pilot.press("enter")
    await pilot.pause()


async def test_constructing_adds_a_row(tmp_path):
    app = app_with_tech(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await open_construction(app, pilot)

        await build_at(app, pilot, screen, "3,3")

        assert isinstance(app.screen, Attention)
        assert "Starting construction" in app.screen.message

        await pilot.press("escape")
        await pilot.pause()
        assert len(screen.rows) == 1


async def test_the_type_chooser_offers_only_what_you_can_build(tmp_path):
    """Bio-tech grants the outpost and nothing else."""
    app = app_with_tech(tmp_path, TechLevel.BioTchLvl)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await open_construction(app, pilot)

        screen.action_construct()
        await pilot.pause()

        assert isinstance(app.screen, ChooseFrom)
        assert [label for _, label in app.screen.options] == ["Outpost"]


async def test_an_empire_with_no_construction_technology_is_told_so(tmp_path):
    app = app_with_tech(tmp_path, TechLevel.WrpTchLvl)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await open_construction(app, pilot)

        screen.action_construct()
        await pilot.pause()

        assert isinstance(app.screen, Attention)
        assert "technology to build anything" in app.screen.message


async def test_an_occupied_sector_is_refused(tmp_path):
    app = app_with_tech(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await open_construction(app, pilot)

        # 0,0 is the capital itself -- relative coordinates are capital-based.
        await build_at(app, pilot, screen, "0,0")

        assert isinstance(app.screen, Attention)
        assert "already occupied" in app.screen.message


async def test_a_malformed_coordinate_is_refused(tmp_path):
    app = app_with_tech(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await open_construction(app, pilot)

        await build_at(app, pilot, screen, "over there")

        assert isinstance(app.screen, Attention)
        assert "x,y" in app.screen.message


# --- Aborting ----------------------------------------------------------------


async def test_aborting_asks_first_and_then_removes_the_row(tmp_path):
    app = app_with_tech(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await open_construction(app, pilot)

        await build_at(app, pilot, screen, "3,3")
        await pilot.press("escape")
        await pilot.pause()
        assert len(screen.rows) == 1

        screen.action_abort()
        await pilot.pause()
        assert isinstance(app.screen, Attention)
        assert "abort" in app.screen.message

        await pilot.click("#yes")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        assert screen.rows == []


async def test_declining_the_abort_keeps_the_site(tmp_path):
    app = app_with_tech(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await open_construction(app, pilot)

        await build_at(app, pilot, screen, "3,3")
        await pilot.press("escape")
        await pilot.pause()

        screen.action_abort()
        await pilot.pause()
        await pilot.press("escape")  # Esc on a confirm is "no"
        await pilot.pause()

        assert len(screen.rows) == 1


# --- Warp links --------------------------------------------------------------


async def test_the_warp_key_opens_the_frequency_list(tmp_path):
    app = app_with_tech(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("w")
        await pilot.pause()

        assert isinstance(app.screen, WarpLinkScreen)


async def test_a_known_gate_can_be_retuned(tmp_path):
    app = app_with_tech(tmp_path)
    game = app.game
    slot = next_stargate_slot(game)
    gate = IDNumber(ObjectTypes.Gate, slot)
    create_stargate(game, gate, Empire.Empire1, T.gte, XYCoord(9, 9))
    game.Universe.Stargate[slot].KnownBy.add(Empire.Empire1)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("w")
        await pilot.pause()
        screen = app.screen
        assert len(screen.entries) == 1

        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, TextPrompt)

        app.screen.query_one("Input").value = "4321"
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, Attention)
        assert "4321" in app.screen.message
        # Your own gate: keep the code quiet.
        assert "divulge" in app.screen.detail

        await pilot.press("escape")
        await pilot.pause()
        assert app.screen.entries[0].frequency == 4321


async def test_a_frequency_out_of_range_is_refused(tmp_path):
    app = app_with_tech(tmp_path)
    game = app.game
    slot = next_stargate_slot(game)
    gate = IDNumber(ObjectTypes.Gate, slot)
    create_stargate(game, gate, Empire.Empire1, T.gte, XYCoord(9, 9))
    game.Universe.Stargate[slot].KnownBy.add(Empire.Empire1)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("w")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        app.screen.query_one("Input").value = "99999"
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, Attention)
        assert "between 0 and 9999" in app.screen.message


async def test_no_known_gates_says_so(tmp_path):
    app = app_with_tech(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("w")
        await pilot.pause()

        text = " ".join(str(w.content) for w in app.screen.query("#list Static"))
        assert "no known stargates" in text
