"""Milestone 2: the map renders and turns advance from the UI."""


from conftest import blank_game

from recreon.galaxy import XYCoord
from recreon.primintr import put_object
from recreon.types import Empire, IDNumber, ObjectTypes, WorldClass
from recreon.ui.app import RecreonApp
from recreon.ui.map_view import BLANK_CHAR, MapView, cp437


def test_cp437_decodes_dos_glyphs():
    # The starbase and stargate glyph tables hold raw CP437 bytes.
    assert cp437(0xFE) == "■"  # cmm
    assert cp437(0xF0) == "≡"  # frt
    assert cp437(0xE3) == "π"  # cmp
    assert cp437(0x40) == "@"  # dis


def test_cp437_handles_the_control_range():
    # Python's cp437 codec maps 0x00-0x1F to C0 control characters, but the
    # IBM PC font drew symbols there -- and both stargate glyphs live in that
    # range, so decoding via the codec alone renders them blank.
    assert cp437(0x12) == "↕"  # gte
    assert cp437(0x18) == "↑"  # lnk


def test_stargate_glyphs_are_visible():
    from recreon.datacnst import GateTypeData
    from recreon.types import STARGATE_TYPES

    for gate in STARGATE_TYPES:
        glyph = cp437(GateTypeData[gate])
        assert glyph.isprintable() and glyph.strip()


def test_map_glyphs_reflect_sector_contents():
    """Empty space is blank, and a known world shows its designation glyph.

    The map draws `TypeStr[Typ]` -- what the world is *for* -- not `ClassStr`,
    which is its terrain. An earlier version of this widget drew the latter.
    """
    from recreon.types import WorldTypes

    game = blank_game(size=10)
    view = MapView(game)

    # (2,2) is off the capital-relative grid rules for this fixture.
    assert view.glyph_at(XYCoord(2, 2)) == BLANK_CHAR

    planet_pos = XYCoord(3, 4)
    game.NoOfPlanets = 1
    game.Universe.Planet[1].XY = planet_pos
    game.Universe.Planet[1].Cls = WorldClass.EthCls
    game.Universe.Planet[1].Typ = WorldTypes.CapTyp
    game.Universe.Planet[1].KnownBy.add(Empire.Empire1)
    put_object(game, planet_pos, IDNumber(ObjectTypes.Pln, 1))

    # TypeStr maps CapTyp to 'C'.
    assert view.glyph_at(planet_pos) == "C"


def test_cursor_clamps_to_the_galaxy_edge():
    game = blank_game(size=5)
    view = MapView(game)

    view.move_cursor(-10, -10)
    assert (view.cursor_x, view.cursor_y) == (1, 1)

    view.move_cursor(100, 100)
    assert (view.cursor_x, view.cursor_y) == (5, 5)


async def test_app_starts_and_renders_a_map():
    game = blank_game(size=20, empires=1)
    app = RecreonApp(game)

    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.map_view.render()
        assert f"Year {game.Year}" in str(app.status_bar.content)


async def test_next_turn_binding_advances_the_year():
    game = blank_game(size=20, empires=1)
    app = RecreonApp(game)
    start = game.Year

    async with app.run_test() as pilot:
        await pilot.press("n")
        await pilot.pause()
        assert game.Year == start + 1
        assert f"Year {start + 1}" in str(app.status_bar.content)


async def test_arrow_keys_move_the_cursor_and_update_the_status():
    game = blank_game(size=20, empires=1)
    app = RecreonApp(game)

    async with app.run_test() as pilot:
        await pilot.press("right", "right", "down")
        await pilot.pause()
        assert (app.map_view.cursor_x, app.map_view.cursor_y) == (3, 2)
        assert "[3,2]" in str(app.status_bar.content)


async def test_status_bar_names_what_is_under_the_cursor():
    game = blank_game(size=20, empires=1)
    game.Universe.EmpireData[Empire.Empire1].EmpireName = "Sarkhon"
    put_object(game, XYCoord(1, 1), IDNumber(ObjectTypes.Pln, 1))

    app = RecreonApp(game)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert "Sarkhon" in str(app.status_bar.content)
        assert "Pln" in str(app.status_bar.content)


async def test_the_news_panel_shows_headlines_as_prose():
    """The panel renders whatever is in the player's feed, not raw enum names."""
    from recreon.galaxy import Location
    from recreon.galaxy import XYCoord as XY
    from recreon.news import NewsTypes, add_news

    game = blank_game(size=20, empires=2)
    game.Universe.EmpireData[Empire.Empire2].EmpireName = "Kaldor"
    world = IDNumber(ObjectTypes.Pln, 1)
    game.NoOfPlanets = 1
    put_object(game, XY(3, 3), world)
    game.Universe.Planet[1].XY = XY(3, 3)

    add_news(
        game,
        Empire.Empire1,
        NewsTypes.BattleL,
        Location(XY(0, 0), world),
        int(Empire.Empire2),
    )

    app = RecreonApp(game)
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = str(app.news_panel.render())
        assert "conquered by the empire of Kaldor" in panel
        assert "BattleL" not in panel


async def test_the_news_panel_says_so_when_nothing_happened():
    game = blank_game(size=20, empires=1)
    app = RecreonApp(game)

    async with app.run_test() as pilot:
        await pilot.pause()
        assert "no news" in str(app.news_panel.render())
