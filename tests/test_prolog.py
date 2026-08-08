"""The prologue's commands, ported from PROLOG.PAS."""


import pytest
from conftest import blank_game

from recreon.environ import GameEnvironment
from recreon.loadsave import backup_path, load_game, save_game
from recreon.main import new_game, update_turn
from recreon.newgame import EmpireIdentity
from recreon.news import NewsTypes
from recreon.primintr import empire_active, get_status, get_tech
from recreon.prolog import (
    DEFAULT_GAME_NAME,
    MAX_MINUTES_PER_TURN,
    PrologueError,
    PrologueState,
    abandon_new_game,
    add_player_empire,
    change_time_limit,
    choose_player_options,
    continue_old_game,
    deletable_empires,
    delete_player_empire,
    do_not_save_game,
    find_new_capital,
    find_new_empire_slot,
    menu_labels,
    needs_saving,
    players_to_move,
    quit_game,
    save_the_game,
    start_a_new_game,
    toggle_auto_save,
    toggle_pause,
    toggle_turn_sync,
)
from recreon.types import (
    Empire,
    ObjectTypes,
    TechLevel,
    TechnologyTypes,
    WorldTypes,
)
from recreon.utils.pascal import set_rand_seed


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


@pytest.fixture
def state():
    return PrologueState(game_loaded=True)


@pytest.fixture
def game(tmp_path):
    g = new_game()
    g.SavDirect = str(tmp_path)
    return g


def mature(tmp_path, years: int = 200):
    """A galaxy old enough for independent worlds to be worth settling."""
    g = new_game()
    for _ in range(years):
        update_turn(g)
    g.SavDirect = str(tmp_path)
    return g


# --- The two flags -----------------------------------------------------------


def test_almost_every_command_needs_a_game(game):
    empty = PrologueState()

    with pytest.raises(PrologueError, match="must Load a game first"):
        change_time_limit(game, empty, 10)
    with pytest.raises(PrologueError, match="must Load a game first"):
        save_the_game(game, empty, "X.SAV")
    with pytest.raises(PrologueError, match="must Load a game first"):
        add_player_empire(game, empty, EmpireIdentity(name="X"))


def test_do_not_save_game_only_clears_the_modified_flag(state):
    """PROLOG.PAS:392 is one line: `GameModified:=False`.

    It suppresses the save-before-quit prompt for a game that has ended; it
    has nothing to do with the autosave, which keys on `AutoSave`.
    """
    state.game_modified = True
    do_not_save_game(state)

    assert not state.game_modified
    assert state.game_loaded


def test_needs_saving_only_when_loaded_and_modified():
    assert not needs_saving(PrologueState(False, False))
    assert not needs_saving(PrologueState(False, True))
    assert not needs_saving(PrologueState(True, False))
    assert needs_saving(PrologueState(True, True))


# --- Menu labels -------------------------------------------------------------


def test_sequential_play_reads_the_inverse_of_the_flag(game):
    """`AsyncTurns` off means sequential play is ON. The label is the one
    place the original states which way round they are."""
    game.AsyncTurns = False
    assert menu_labels(game)["sequential_play"] == "ON"

    game.AsyncTurns = True
    assert menu_labels(game)["sequential_play"] == "OFF"


def test_the_other_labels_track_their_flags(game):
    game.AutoSave = False
    game.PauseActive = True
    labels = menu_labels(game)

    assert labels["auto_backup"] == "OFF"
    assert labels["pause"] == "Active"


# --- Saving ------------------------------------------------------------------


def test_saving_writes_through_a_temporary(game, state, tmp_path):
    target = save_the_game(game, state, "MYGAME.SAV")

    assert target == tmp_path / "MYGAME.SAV"
    assert target.exists()
    assert game.CurrentGame == "MYGAME.SAV"
    assert not state.game_modified

    reloaded = GameEnvironment()
    load_game(reloaded, target)
    assert reloaded.NoOfPlanets == game.NoOfPlanets


def test_saving_by_hand_destroys_the_autosave(game, state, tmp_path):
    """Original bug #54, reproduced.

    `SaveTheGame`'s scratch file is `<name>.BAK` -- which is exactly the file
    `AutoBackup` writes. So a manual save overwrites the backup and then
    renames it away, leaving no backup at all.
    """
    game.CurrentGame = "ANACREON.SAV"
    backup = backup_path(game)
    save_game(game, backup)
    assert backup.exists()

    save_the_game(game, state, "ANACREON.SAV")

    assert (tmp_path / "ANACREON.SAV").exists()
    assert not backup.exists()


def test_saving_replaces_a_previous_save_of_the_same_name(game, state, tmp_path):
    save_the_game(game, state, "SLOT.SAV")
    first = (tmp_path / "SLOT.SAV").read_text()

    update_turn(game)
    save_the_game(game, state, "SLOT.SAV")

    assert (tmp_path / "SLOT.SAV").read_text() != first


# --- Loading and quitting ----------------------------------------------------


def test_loading_replaces_the_running_game(game, state, tmp_path):
    for _ in range(20):
        update_turn(game)
    save_game(game, tmp_path / "MID.SAV")
    saved_year = game.Year

    fresh = new_game()
    fresh.SavDirect = str(tmp_path)
    continue_old_game(fresh, state, tmp_path / "MID.SAV")

    assert fresh.Year == saved_year
    assert fresh.CurrentGame == "MID.SAV"
    assert state.game_loaded
    assert not state.game_modified


def test_loading_tears_the_old_universe_down_first(game, state, tmp_path):
    """`ContinueOldGame` calls `CleanUpUniverse`, which `LoadGame` does not.

    See #46: the original's load leaks everything the outgoing game held, and
    this is the call site that stops it happening from the menu.
    """
    for _ in range(120):
        update_turn(game)
    save_game(game, tmp_path / "A.SAV")

    other = new_game()
    other.SavDirect = str(tmp_path)
    for _ in range(40):
        update_turn(other)

    continue_old_game(other, state, tmp_path / "A.SAV")

    # Nothing of the outgoing galaxy survives into the incoming one.
    assert other.Year == game.Year
    assert other.GlobalSets.SetOfActivePlanets == game.GlobalSets.SetOfActivePlanets


def test_quitting_waits_for_unsaved_changes(state):
    state.game_modified = True
    assert not quit_game(state)

    state.game_modified = False
    assert quit_game(state)
    assert not state.game_loaded


def test_a_new_game_counts_as_modified(game):
    """It has never been saved, so quitting should stop to ask."""
    state = PrologueState()
    start_a_new_game(game, state)

    assert state.game_loaded and state.game_modified
    assert game.CurrentGame == DEFAULT_GAME_NAME
    assert not game.AsyncTurns
    assert game.EmpiresToMove


def test_abandoning_a_new_game_leaves_nothing_loaded(game):
    state = PrologueState(game_loaded=True, game_modified=True)
    abandon_new_game(game, state)

    assert not state.game_loaded
    assert not state.game_modified


# --- Settings ----------------------------------------------------------------


def test_the_toggles_flip_and_announce(game, state):
    assert "OFF" in toggle_auto_save(game, state)
    assert not game.AutoSave
    assert state.game_modified

    assert "INACTIVE" in toggle_pause(game, state)
    assert not game.PauseActive


def test_returning_to_sequential_play_rewinds_the_rotation(game, state):
    """Going non-sequential does neither of these; coming back does both."""
    game.Player = Empire.Empire3
    game.EmpiresToMove = set()

    assert "NON-SEQUENTIAL" in toggle_turn_sync(game, state)
    assert game.Player is Empire.Empire3
    assert game.EmpiresToMove == set()

    assert "SEQUENTIAL" in toggle_turn_sync(game, state)
    assert game.Player is Empire.Empire1
    assert game.EmpiresToMove


def test_the_time_limit_is_stored_in_seconds(game, state):
    change_time_limit(game, state, 7)
    assert game.TimePerTurn == 420
    assert state.game_modified


@pytest.mark.parametrize("minutes", [0, -5])
def test_a_non_positive_time_limit_is_refused(game, state, minutes):
    with pytest.raises(PrologueError, match="positive integer"):
        change_time_limit(game, state, minutes)


def test_more_than_two_hours_per_turn_is_refused(game, state):
    with pytest.raises(PrologueError, match="2 hours"):
        change_time_limit(game, state, MAX_MINUTES_PER_TURN + 1)

    change_time_limit(game, state, MAX_MINUTES_PER_TURN)
    assert game.TimePerTurn == MAX_MINUTES_PER_TURN * 60


# --- Choosing a player -------------------------------------------------------


def test_players_are_offered_in_slot_order():
    g = blank_game(empires=3)
    options = choose_player_options(g, {Empire.Empire3, Empire.Empire1})

    assert [emp for emp, _ in options] == [Empire.Empire1, Empire.Empire3]
    assert [name for _, name in options] == ["Empire 1", "Empire 3"]


def test_only_active_human_empires_can_be_deleted(game):
    names = dict(deletable_empires(game))

    assert all(empire_active(game, emp) for emp in names)
    assert Empire.Empire6 not in names  # an NPE in frontier.scn


def test_players_to_move_follows_the_pending_set(game):
    game.EmpiresToMove = {Empire.Empire1}
    assert [emp for emp, _ in players_to_move(game)] == [Empire.Empire1]


# --- Adding an empire --------------------------------------------------------


def test_a_capital_needs_a_developed_independent_world(game):
    """Bio-tech and over two thousand people. A fresh galaxy has neither."""
    assert find_new_capital(game).ObjTyp is ObjectTypes.Void


def test_a_mature_galaxy_has_somewhere_to_put_a_newcomer(tmp_path):
    g = mature(tmp_path)
    world = find_new_capital(g)

    assert world.ObjTyp is ObjectTypes.Pln
    assert get_status(g, world) is Empire.Indep
    assert get_tech(g, world) >= TechLevel.BioTchLvl


def test_a_newcomer_lands_at_the_best_technology_in_the_galaxy(tmp_path, state):
    """One world against established empires, but not a primitive one."""
    g = mature(tmp_path)
    best = max(
        g.Universe.EmpireData[emp].TechnologyLevel
        for emp in g.NPEData
        if empire_active(g, emp)
    )

    emp = add_player_empire(g, state, EmpireIdentity(name="Newcomer"))
    data = g.Universe.EmpireData[emp]

    assert data.InUse and data.IsAPlayer
    assert data.EmpireName == "Newcomer"
    assert data.TechnologyLevel == best
    assert get_status(g, data.Capital) is emp
    assert g.Universe.Planet[data.Capital.Index].Typ is WorldTypes.CapTyp


def test_a_newcomer_inherits_no_charts(tmp_path, state):
    """`ClearKnownSet` runs before the capital is handed over, so the only
    thing on the new empire's map is what it can see from home."""
    g = mature(tmp_path)
    emp = add_player_empire(g, state, EmpireIdentity(name="Newcomer"))

    known = [
        i
        for i in range(1, g.NoOfPlanets + 1)
        if emp in g.Universe.Planet[i].KnownBy
    ]
    capital = g.Universe.EmpireData[emp].Capital.Index

    assert capital in known
    assert len(known) < g.NoOfPlanets // 2


def test_the_galaxy_hears_about_a_new_empire(tmp_path, state):
    """Every empire that already knew the world gets a NewPlEmp headline."""
    g = mature(tmp_path)
    world = find_new_capital(g)
    watcher = Empire.Empire1
    g.Universe.Planet[world.Index].KnownBy.add(watcher)

    add_player_empire(g, state, EmpireIdentity(name="Newcomer"))

    assert any(
        item.Headline is NewsTypes.NewPlEmp for item in g.News[watcher]
    )


def test_a_ninth_empire_is_refused(tmp_path, state):
    g = mature(tmp_path)
    for i in range(8):
        emp = Empire(i)
        g.Universe.EmpireData[emp].InUse = True

    assert find_new_empire_slot(g) is Empire.Indep
    with pytest.raises(PrologueError, match="already eight empires"):
        add_player_empire(g, state, EmpireIdentity(name="Ninth"))


def test_the_technology_union_is_order_dependent(tmp_path, state):
    """Original bug #55, reproduced.

    A new high-water mark *replaces* the accumulated technology set instead of
    merging into it, so anything gathered from empires examined earlier is
    discarded. The newcomer ends up with the best empire's technologies plus
    those of empires after it in slot order, and nothing from before.
    """
    g = mature(tmp_path)

    early, late = Empire.Empire1, Empire.Empire7
    for emp in (early, late):
        g.Universe.EmpireData[emp].InUse = True
        g.Universe.EmpireData[emp].IsAPlayer = True

    # A distinctive technology on a *low*-tech empire early in slot order.
    g.Universe.EmpireData[early].TechnologyLevel = TechLevel.PrimitLvl
    g.Universe.EmpireData[early].Technology = {TechnologyTypes.gte}
    # ...and the highest level late in slot order, which resets the union.
    g.Universe.EmpireData[late].TechnologyLevel = TechLevel.GteTchLvl
    g.Universe.EmpireData[late].Technology = {TechnologyTypes.ssp}

    emp = add_player_empire(g, state, EmpireIdentity(name="Newcomer"))
    gathered = g.Universe.EmpireData[emp].Technology

    # The early empire's contribution was thrown away when Empire7 raised the
    # maximum. Fixing #55 would put `gte` back.
    assert TechnologyTypes.gte not in gathered


# --- Deleting an empire ------------------------------------------------------


def test_the_last_empire_cannot_be_deleted(game, state):
    with pytest.raises(PrologueError, match="last empire"):
        delete_player_empire(game, state, Empire.Empire1)


def test_deleting_the_empire_whose_turn_it_is_ends_the_turn(tmp_path, state):
    g = mature(tmp_path)
    newcomer = add_player_empire(g, state, EmpireIdentity(name="Newcomer"))

    g.Player = newcomer
    assert delete_player_empire(g, state, newcomer) is True
    assert not empire_active(g, newcomer)
    assert newcomer not in g.EmpiresToMove


def test_deleting_another_empire_does_not(tmp_path, state):
    g = mature(tmp_path)
    newcomer = add_player_empire(g, state, EmpireIdentity(name="Newcomer"))

    g.Player = Empire.Empire1
    assert delete_player_empire(g, state, newcomer) is False


def test_under_non_sequential_turns_any_deletion_ends_the_turn(tmp_path, state):
    """The prologue has to go back and ask who is moving."""
    g = mature(tmp_path)
    newcomer = add_player_empire(g, state, EmpireIdentity(name="Newcomer"))
    g.AsyncTurns = True
    g.Player = Empire.Empire1

    assert delete_player_empire(g, state, newcomer) is True
    assert g.Player is newcomer
