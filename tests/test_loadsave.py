"""Saving and loading a game, ported from LOADSAVE.PAS."""

import json

import pytest
from conftest import blank_game, place_world

from recreon.datastrc import NameRecord
from recreon.environ import GameEnvironment
from recreon.fleet import get_next_fleet, move_fleet
from recreon.galaxy import Location, XYCoord
from recreon.loadsave import (
    CURRENT_SF_VERSION,
    SF_SIGNATURE,
    SaveFileError,
    auto_backup,
    backup_path,
    clean_up_universe,
    load_game,
    save_game,
)
from recreon.main import new_game, update_turn
from recreon.news import NewsRecord, NewsTypes, add_news
from recreon.npe.types import NPEmpireTypes
from recreon.orders import CommandRecord, CommandTypes, get_fleet_code
from recreon.types import (
    Empire,
    IDNumber,
    ObjectTypes,
    SpecialConditions,
    TechLevel,
    TechnologyTypes,
)
from recreon.utils.pascal import set_rand_seed

T = TechnologyTypes


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


@pytest.fixture
def saved(tmp_path):
    return tmp_path / "game.sav"


# --- Round-tripping ----------------------------------------------------------


def test_header_names_the_format(saved):
    """A save is identifiable before any of it is decoded."""
    save_game(blank_game(), saved)
    document = json.loads(saved.read_text())

    assert document["signature"] == SF_SIGNATURE
    assert document["version"] == CURRENT_SF_VERSION


def test_a_scenario_survives_a_round_trip(saved, scenario_path):
    game = new_game(scenario_path)
    save_game(game, saved)

    loaded = GameEnvironment()
    assert load_game(loaded, saved) == []

    assert loaded.Year == game.Year
    assert loaded.NoOfPlanets == game.NoOfPlanets
    assert loaded.Galaxy.size == game.Galaxy.size
    assert loaded.ScenaFilename == str(scenario_path)


def played_out(scenario_path, turns: int = 120):
    """A game with every save section carrying something.

    Playing alone is not enough. A hundred and twenty turns reliably grows the
    economy, the news and the AI's state, but whether any *fleet* is in the
    air at the moment you stop is down to the roll -- frontier.scn's empires
    launch rarely and abort quickly, so the count is 0 most turns. Waiting for
    one would make the test a hostage to the RNG trajectory, and any change to
    a draw anywhere in the game would move it.

    So the fleet is placed deliberately, with cargo and compiled orders, and
    the played-out galaxy supplies the rest.
    """
    game = new_game(scenario_path)
    for _ in range(turns):
        update_turn(game)

    flt_id = get_next_fleet(game, game.Player)
    fleet = game.Universe.Fleet[flt_id.Index]
    fleet.Ships[T.fgt] = 120
    fleet.Cargo[T.tri] = 40
    fleet.Dest = XYCoord(6, 6)
    fleet.NextOrder = 1
    move_fleet(game, flt_id, XYCoord(4, 4))
    get_fleet_code(game, flt_id).append(
        CommandRecord(CommandTypes.DestCOM, Location(XYCoord(6, 6), IDNumber()))
    )

    return game


def test_resaving_a_loaded_game_is_byte_identical(tmp_path, scenario_path):
    """The strongest statement the format can make about itself.

    If any field were dropped, coerced to a different type, or restored in a
    different order, the second save would differ from the first.
    """
    game = played_out(scenario_path)

    # Every section this is meant to cover actually has content.
    assert game.GlobalSets.SetOfActiveFleets
    assert game.GlobalSets.SetOfActiveStarbases
    assert game.GlobalSets.SetOfActivePlanets
    assert any(game.News.values())
    assert any(data.Data is not None for data in game.NPEData.values())

    first, second = tmp_path / "a.sav", tmp_path / "b.sav"
    save_game(game, first)

    loaded = GameEnvironment()
    load_game(loaded, first)
    save_game(loaded, second)

    assert first.read_text() == second.read_text()


def test_a_loaded_game_plays_on_identically(tmp_path, scenario_path):
    """Loading is not merely lossless, it is behaviourally invisible.

    Two copies of the same game, one of which has been through the file,
    advance through sixty turns of economy, fleet movement and AI to the same
    state. RandSeed is not saved -- the original does not save it either -- so
    both runs are re-seeded to the same value first.
    """
    game = new_game(scenario_path)
    for _ in range(80):
        update_turn(game)

    midpoint = tmp_path / "mid.sav"
    save_game(game, midpoint)
    loaded = GameEnvironment()
    load_game(loaded, midpoint)

    in_memory, from_disk = tmp_path / "x.sav", tmp_path / "y.sav"

    set_rand_seed(1234)
    for _ in range(60):
        update_turn(game)
    save_game(game, in_memory)

    set_rand_seed(1234)
    for _ in range(60):
        update_turn(loaded)
    save_game(loaded, from_disk)

    assert in_memory.read_text() == from_disk.read_text()


# --- Types survive the file --------------------------------------------------


def test_enums_and_sets_come_back_as_themselves(saved):
    """JSON stores an Empire as an int; the codec has to undo that.

    Nearly every ported routine compares enum members and indexes dicts keyed
    by them, so a save that round-tripped ``Empire.Empire3`` as a bare ``2``
    would look right in a diff and fail at the first lookup.
    """
    game = blank_game(size=20, empires=2)
    world = place_world(game, 1, XYCoord(5, 5), emp=Empire.Empire1)
    planet = game.Universe.Planet[world.Index]
    planet.ScoutedBy = {Empire.Empire2}
    planet.KnownBy = {Empire.Empire1, Empire.Empire2}
    planet.Special = {SpecialConditions.AmbAddict}
    planet.Tech = TechLevel.StrTchLvl

    save_game(game, saved)
    loaded = GameEnvironment()
    load_game(loaded, saved)

    restored = loaded.Universe.Planet[1]
    assert restored.Emp is Empire.Empire1
    assert restored.Tech is TechLevel.StrTchLvl
    assert restored.ScoutedBy == {Empire.Empire2}
    assert restored.Special == {SpecialConditions.AmbAddict}
    assert all(isinstance(emp, Empire) for emp in restored.KnownBy)
    assert all(isinstance(key, TechnologyTypes) for key in restored.Cargo)


def test_empire_names_and_place_names_survive(saved):
    game = blank_game(empires=2)
    data = game.Universe.EmpireData[Empire.Empire1]
    data.EmpireName = "Sarkhon"
    data.Names.append(NameRecord("The Deeps", Location(XYCoord(3, 4), IDNumber())))

    save_game(game, saved)
    loaded = GameEnvironment()
    load_game(loaded, saved)

    restored = loaded.Universe.EmpireData[Empire.Empire1]
    assert restored.EmpireName == "Sarkhon"
    assert [name.Name for name in restored.Names] == ["The Deeps"]
    assert restored.Names[0].Coord.XY.x == 3


def test_the_sector_grid_survives_including_row_zero(saved):
    """Row and column 0 are outside the galaxy but are still allocated.

    They carry ``NO_SRM_FIELD`` in ``Special`` rather than 0, so a save that
    dropped them would come back differing from a fresh grid at the edges.
    """
    game = blank_game(size=12)
    game.Galaxy.sector(XYCoord(4, 7)).Special = 0x25
    game.Galaxy.set_mine_scout(Empire.Empire1, XYCoord(4, 7))

    save_game(game, saved)
    loaded = GameEnvironment()
    load_game(loaded, saved)

    assert loaded.Galaxy.size == 12
    assert loaded.Galaxy.sector(XYCoord(4, 7)).Special == 0x25
    assert loaded.Galaxy.sector(XYCoord(4, 7)).MineScout == {Empire.Empire1}
    fresh = blank_game(size=12)
    assert loaded.Galaxy.sector(XYCoord(0, 0)).Special == (
        fresh.Galaxy.sector(XYCoord(0, 0)).Special
    )


def test_news_survives_per_empire(saved):
    game = blank_game(empires=2)
    place_world(game, 1, XYCoord(5, 5), emp=Empire.Empire1)
    loc = Location(XYCoord(0, 0), IDNumber(ObjectTypes.Pln, 1))
    add_news(game, Empire.Empire1, NewsTypes.Starv, loc, 3)

    save_game(game, saved)
    loaded = GameEnvironment()
    load_game(loaded, saved)

    assert loaded.News[Empire.Empire1] == [
        NewsRecord(NewsTypes.Starv, loc, 3, 0, 0)
    ]
    assert loaded.News[Empire.Empire2] == []


# --- Sets are rebuilt, not saved ---------------------------------------------


def test_per_empire_sets_are_rebuilt_from_the_records(saved):
    """LoadPlanets rebuilds ``SetOfPlanetsOf`` from each record's own ``Emp``.

    Nothing writes the sets to the file, so they cannot disagree with the
    worlds they index -- which is exactly the class of bug that made every
    empire read as owning nothing before ``set_status`` was fixed.
    """
    game = blank_game(empires=2)
    place_world(game, 1, XYCoord(5, 5), emp=Empire.Empire1)
    place_world(game, 2, XYCoord(7, 7), emp=Empire.Empire2)

    save_game(game, saved)
    assert "SetOfPlanetsOf" not in saved.read_text()

    loaded = GameEnvironment()
    load_game(loaded, saved)

    assert loaded.GlobalSets.SetOfPlanetsOf[Empire.Empire1] == {1}
    assert loaded.GlobalSets.SetOfPlanetsOf[Empire.Empire2] == {2}
    assert loaded.GlobalSets.SetOfActivePlanets == {1, 2}


def test_the_world_count_is_recounted_on_load(saved):
    """``NoOfPlanets`` comes from the records, not from a stored number."""
    game = blank_game()
    place_world(game, 1, XYCoord(5, 5))
    place_world(game, 2, XYCoord(6, 6))
    place_world(game, 3, XYCoord(7, 7))

    save_game(game, saved)
    loaded = GameEnvironment()
    load_game(loaded, saved)

    assert loaded.NoOfPlanets == 3


# --- Fleets ------------------------------------------------------------------


def test_fleet_orders_ride_along_with_the_fleet(saved):
    game = blank_game()
    place_world(game, 1, XYCoord(5, 5), emp=Empire.Empire1)
    flt_id = get_next_fleet(game, Empire.Empire1)
    fleet = game.Universe.Fleet[flt_id.Index]
    fleet.XY = XYCoord(5, 5)
    fleet.Dest = XYCoord(8, 8)
    fleet.Ships[T.fgt] = 40
    fleet.NextOrder = 1
    get_fleet_code(game, flt_id).append(
        CommandRecord(CommandTypes.DestCOM, Location(XYCoord(8, 8), IDNumber()))
    )

    save_game(game, saved)
    loaded = GameEnvironment()
    load_game(loaded, saved)

    restored = loaded.Universe.Fleet[flt_id.Index]
    assert restored.Ships[T.fgt] == 40
    assert restored.Dest == XYCoord(8, 8)
    assert restored.NextOrder == 1

    code = get_fleet_code(loaded, flt_id)
    assert len(code) == 1
    assert code[0].Typ is CommandTypes.DestCOM
    assert code[0].Loc.XY == XYCoord(8, 8)


def test_a_fleet_saved_nowhere_is_moved_to_the_corner(saved):
    """LoadFleets' coordinate repair, reproduced.

    A zero component means Limbo, and a fleet at Limbo would crash the sector
    lookups. The original's fix is blunt -- (1, 1) regardless of whose fleet
    it is or where it was going -- and is kept.
    """
    game = blank_game()
    flt_id = get_next_fleet(game, Empire.Empire1)
    fleet = game.Universe.Fleet[flt_id.Index]
    fleet.XY = XYCoord(0, 0)
    fleet.Dest = XYCoord(6, 6)

    save_game(game, saved)
    loaded = GameEnvironment()
    load_game(loaded, saved)

    restored = loaded.Universe.Fleet[flt_id.Index]
    assert restored.XY == XYCoord(1, 1)
    assert restored.Dest == XYCoord(1, 1)


def test_orders_of_a_fleet_that_finished_them_are_dropped(saved):
    """SaveFleets only writes orders when ``NextOrder > 0``.

    A fleet that has run off the end of its order list has nothing left to
    execute, so the loss is not observable in play -- but the check is on
    ``NextOrder``, not on whether the list is empty, and this pins that.
    """
    game = blank_game()
    flt_id = get_next_fleet(game, Empire.Empire1)
    fleet = game.Universe.Fleet[flt_id.Index]
    fleet.XY = XYCoord(3, 3)
    fleet.Dest = XYCoord(3, 3)
    fleet.NextOrder = 0
    get_fleet_code(game, flt_id).append(CommandRecord(CommandTypes.AbortCOM))

    save_game(game, saved)
    loaded = GameEnvironment()
    load_game(loaded, saved)

    assert get_fleet_code(loaded, flt_id) == []


# --- AI state ----------------------------------------------------------------


def test_npe_personas_reload_as_their_own_type(saved, scenario_path):
    """The record class is chosen from the empire's ``Typ``, as NPE.PAS does."""
    game = new_game(scenario_path)
    npes = [
        emp
        for emp in game.NPEData
        if game.NPEData[emp].Typ is not NPEmpireTypes.NoNPE
        and game.NPEData[emp].Data is not None
    ]
    assert npes, "the scenario should create at least one NPE"

    save_game(game, saved)
    loaded = GameEnvironment()
    load_game(loaded, saved)

    for emp in npes:
        assert loaded.NPEData[emp].Typ is game.NPEData[emp].Typ
        assert type(loaded.NPEData[emp].Data) is type(game.NPEData[emp].Data)


# --- Errors ------------------------------------------------------------------


def test_a_file_that_is_not_a_save_is_refused(tmp_path):
    stray = tmp_path / "notes.txt"
    stray.write_text("this is not a save file")

    with pytest.raises(SaveFileError, match="not a save file"):
        load_game(GameEnvironment(), stray)


def test_a_json_file_without_the_signature_is_refused(tmp_path):
    impostor = tmp_path / "other.sav"
    impostor.write_text(json.dumps({"version": 1, "environment": {}}))

    with pytest.raises(SaveFileError, match="not a Re:creon save file"):
        load_game(GameEnvironment(), impostor)


def test_a_missing_file_is_refused(tmp_path):
    with pytest.raises(SaveFileError, match="cannot read"):
        load_game(GameEnvironment(), tmp_path / "nothing.sav")


def test_a_truncated_save_is_refused(saved):
    save_game(blank_game(), saved)
    document = json.loads(saved.read_text())
    del document["planets"]
    saved.write_text(json.dumps(document))

    with pytest.raises(SaveFileError, match="damaged"):
        load_game(GameEnvironment(), saved)


def test_an_older_save_warns_about_the_format(saved):
    save_game(blank_game(), saved)
    document = json.loads(saved.read_text())
    document["version"] = CURRENT_SF_VERSION - 1
    saved.write_text(json.dumps(document))

    warnings = load_game(GameEnvironment(), saved)
    assert len(warnings) == 1
    assert "format has changed" in warnings[0]


def test_a_newer_save_warns_about_the_version(saved):
    save_game(blank_game(), saved)
    document = json.loads(saved.read_text())
    document["version"] = CURRENT_SF_VERSION + 1
    saved.write_text(json.dumps(document))

    warnings = load_game(GameEnvironment(), saved)
    assert len(warnings) == 1
    assert "newer than this version" in warnings[0]


# --- Autosave and teardown ---------------------------------------------------


def test_autosave_writes_a_bak_beside_the_save(tmp_path):
    game = blank_game()
    game.SavDirect = str(tmp_path)
    game.CurrentGame = "campaign.sav"

    assert auto_backup(game) == []
    assert backup_path(game) == tmp_path / "campaign.BAK"
    assert (tmp_path / "campaign.BAK").exists()
    assert not (tmp_path / "campaign.sav").exists()


def test_autosave_does_nothing_when_it_is_off(tmp_path):
    game = blank_game()
    game.SavDirect = str(tmp_path)
    game.AutoSave = False

    assert auto_backup(game) == []
    assert list(tmp_path.iterdir()) == []


def test_a_failed_autosave_warns_rather_than_raising(tmp_path):
    """A backup that fails must not take the turn down with it."""
    game = blank_game()
    game.SavDirect = str(tmp_path / "no" / "such" / "directory")

    warnings = auto_backup(game)
    assert len(warnings) == 1
    assert "save the game manually" in warnings[0]


def test_clean_up_universe_clears_the_fleets_out_of_their_sectors(scenario_path):
    """Most arms of CleanUpUniverse are heap frees with no Python meaning.

    ``DestroyFleet`` is not: it clears the fleet's empire out of its sector's
    ``Flts`` set, which is state a reused GameEnvironment would otherwise
    carry into the next game.
    """
    game = played_out(scenario_path)
    assert game.GlobalSets.SetOfActiveFleets

    # Held by reference, because CleanUpSector drops the grid itself and the
    # coordinates would have nothing left to index.
    occupied = [
        game.Galaxy.sector(xy)
        for xy in game.Galaxy.coordinates()
        if game.Galaxy.sector(xy).Flts
    ]
    assert occupied

    clean_up_universe(game)

    assert game.GlobalSets.SetOfActiveFleets == set()
    assert not any(sector.Flts for sector in occupied)
    assert game.Galaxy.size == 0
