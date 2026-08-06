"""The prologue: the menu you get before and between games.

Port of PROLOG.PAS, minus the parts that only DOS could do. It owns the game's
lifecycle -- start, load, save, quit -- and the handful of settings that live
outside a game: the turn time limit, autosave, pause, sequential play. Drawing
it is :mod:`recreon.ui.prologue`.

**Two flags drive everything.** ``GameLoaded`` says whether there is a game to
act on; almost every command refuses with "You must Load a game first" without
it. ``GameModified`` says whether it has changed since the last save, and is
what makes quitting or loading stop to ask. They are unit-level typed
constants in the original, which is to say globals with exactly this scope, so
they are a small object here rather than more state on
:class:`~recreon.environ.GameEnvironment`.

Deliberately not ported:

* ``MainTitle`` and the title-screen effects -- ``DisplayBitPicture``,
  the star field, ``LettersSFX``, ``ZoomOutSFX``. Direct video-memory work in
  the same family as FASTSCR.ASM, with no Python equivalent.
* ``DOSShell``, ``PrintGalacticMap`` (writes to ``LST:``), ``ToggleColorBW``.
* ``Directories`` and ``SaveConfiguration``, which read and write
  ANACREON.CNF. Configuration belongs with an options screen, and the file
  format is a DOS-era fixed-width blob worth replacing rather than porting.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .environ import DEFAULT_GAME_NAME, GameEnvironment
from .galaxy import Location, limbo
from .intrface import clear_known_set, destroy_empire, scout
from .loadsave import SaveFileError, clean_up_universe, load_game, save_game
from .news import NewsTypes, add_news
from .newgame import EmpireIdentity
from .primintr import (
    create_empire,
    empire_active,
    empire_name,
    empire_player,
    get_coord,
    get_empire_technology,
    get_population,
    get_status,
    get_tech,
    known,
    set_status,
    set_tech,
    set_type,
)
from .types import (
    PLAYER_EMPIRES,
    Empire,
    IDNumber,
    ObjectTypes,
    TechLevel,
    TechnologyTypes,
    WorldTypes,
    empty_quadrant,
)

#: Longest turn the time-limit prompt will accept, in minutes. "Please limit
#: yourself to 2 hours per turn!"
MAX_MINUTES_PER_TURN = 120

#: A world has to be at least this developed to seat a new empire's capital.
MIN_CAPITAL_TECH = TechLevel.BioTchLvl
MIN_CAPITAL_POP = 2000

#: Shown to a player joining a galaxy already carved up between eight empires.
DWARF_AMONG_GIANTS = (
    "You are a dwarf among giants. You have fewer ships, fewer people, and a "
    "smaller industrial capacity than any other empire in the galaxy. With one "
    "world and your Imperial Starfleet you must carve an empire out of the "
    "scraps and remnants of others. But that is your greatest strength: With "
    "luck, and a great deal of diplomatic skill, you'll perhaps be ignored for "
    "just long enough... By the time the giants realize their mistake, your "
    "flag will be flying over a dozen worlds."
)


class PrologueError(Exception):
    """A command that cannot run, carrying what the original's window said."""


@dataclass
class PrologueState:
    """``GameLoaded`` and ``GameModified``, the prologue's two globals."""

    game_loaded: bool = False
    game_modified: bool = False

    def require_game(self) -> None:
        if not self.game_loaded:
            raise PrologueError("You must Load a game first.")


def do_not_save_game(state: PrologueState) -> None:
    """Port of ``DoNotSaveGame``: PROLOG.PAS:392, one line.

    Clears the modified flag so the prologue does not offer to save. Called
    from ANACREON.PAS when the last player has been destroyed -- a finished
    game should not invite you back into it. It has nothing to do with the
    autosave, which keys on ``AutoSave``.
    """
    state.game_modified = False


# --- Menu labels -------------------------------------------------------------


def menu_labels(game: GameEnvironment) -> dict[str, str]:
    """The toggles' current settings. Port of ``UpdateMenuBar``.

    Note ``Sequential play`` reads **ON when ``AsyncTurns`` is false** -- the
    setting and the flag are inverses of each other, and the original's label
    is the one place that is stated.
    """
    return {
        "auto_backup": "ON" if game.AutoSave else "OFF",
        "pause": "Active" if game.PauseActive else "Inactive",
        "sequential_play": "OFF" if game.AsyncTurns else "ON",
    }


# --- Saving ------------------------------------------------------------------


def save_the_game(
    game: GameEnvironment, state: PrologueState, filename: str | Path
) -> Path:
    """Save under ``filename``, via a temporary. Port of ``SaveTheGame``.

    The original writes to ``<name>.BAK``, erases ``<name>``, then renames --
    so a failed write leaves the previous save intact. That much is worth
    keeping and is kept.

    **The temporary it picks is the autosave's own file** (#54). ``AutoBackup``
    writes ``<CurrentGame without extension>.BAK``, which is exactly the name
    this overwrites and then renames away, so saving by hand destroys the
    backup and leaves a window in which neither file is complete. Reproduced,
    because a player could have relied on either file being there; filed
    rather than fixed.
    """
    state.require_game()

    target = Path(game.SavDirect) / Path(filename).name
    temporary = target.with_suffix(".BAK")

    save_game(game, temporary)

    # Erase-then-rename, as the original does. The erase is allowed to fail --
    # `Null:=IOResult` discards its result -- because the first save of a game
    # has nothing to erase.
    target.unlink(missing_ok=True)
    try:
        temporary.rename(target)
    except OSError as exc:
        raise SaveFileError(f"cannot rename {temporary} to {target}: {exc}") from exc

    game.CurrentGame = target.name
    state.game_modified = False
    return target


def needs_saving(state: PrologueState) -> bool:
    """Whether to stop and ask before discarding. Port of ``GameNotSaved``.

    The original opens an ``AttentionWindow`` here; deciding is the caller's,
    so this is only the test it makes. Answering "no" is what ``Esc`` does in
    the original, and it clears the flag -- the changes are gone, so nothing
    is left to warn about.
    """
    return state.game_loaded and state.game_modified


# --- Loading and quitting ----------------------------------------------------


def continue_old_game(
    game: GameEnvironment, state: PrologueState, filename: str | Path
) -> list[str]:
    """Load a saved game over the current one. Port of ``ContinueOldGame``.

    Tears down whatever was loaded first, which the original does here and
    conspicuously *not* inside ``LoadGame`` -- see #46. Returns whatever
    warnings the save file provoked.

    The caller is expected to have dealt with :func:`needs_saving` already.
    """
    if state.game_loaded:
        clean_up_universe(game)
        state.game_loaded = False
        state.game_modified = False

    game.initialize_universe(0, 0, 0)

    warnings = load_game(game, filename)

    game.CurrentGame = Path(filename).name
    state.game_loaded = True
    state.game_modified = False
    return warnings


def quit_game(state: PrologueState) -> bool:
    """Whether the program may exit. Port of ``QuitGame``.

    False when there are unsaved changes still to resolve; the caller asks
    through :func:`needs_saving` and either saves or discards, after which
    this returns True.
    """
    if needs_saving(state):
        return False

    state.game_modified = False
    state.game_loaded = False
    return True


def start_a_new_game(game: GameEnvironment, state: PrologueState) -> None:
    """Book-keeping after the scenario front end built a galaxy.

    Port of the tail of ``StartANewGame``. A new game is modified from the
    moment it exists -- it has never been saved -- and turns start sequential
    whatever the previous game was set to.
    """
    game.reset_empires_to_move()
    game.AsyncTurns = False
    game.CurrentGame = DEFAULT_GAME_NAME

    state.game_loaded = True
    state.game_modified = True


def abandon_new_game(game: GameEnvironment, state: PrologueState) -> None:
    """The player escaped out of the scenario front end.

    ``StartANewGame`` has already called ``CleanUpUniverse`` by this point, so
    there is no game to go back to -- both flags come down.
    """
    state.game_loaded = False
    state.game_modified = False


# --- Settings ----------------------------------------------------------------


def toggle_auto_save(game: GameEnvironment, state: PrologueState) -> str:
    """Port of ``ToggleAutoSave``. Returns the line the original announced."""
    game.AutoSave = not game.AutoSave
    state.game_modified = True
    return f"Auto Backup is now {'ON' if game.AutoSave else 'OFF'}."


def toggle_pause(game: GameEnvironment, state: PrologueState) -> str:
    """Port of ``TogglePause``."""
    game.PauseActive = not game.PauseActive
    state.game_modified = True
    return f"Pause feature is now {'ACTIVE' if game.PauseActive else 'INACTIVE'}."


def toggle_turn_sync(game: GameEnvironment, state: PrologueState) -> str:
    """Port of ``ToggleTurnSync``.

    Turning sequential play back *on* rewinds the rotation: the pending-move
    set is refilled and play returns to Empire1. Going the other way does
    neither, so a game switched to non-sequential mid-round keeps whatever
    was outstanding.
    """
    game.AsyncTurns = not game.AsyncTurns
    state.game_modified = True

    if game.AsyncTurns:
        return "Player turns are now NON-SEQUENTIAL"

    game.reset_empires_to_move()
    game.Player = Empire.Empire1
    return "Player turns are now SEQUENTIAL"


def change_time_limit(
    game: GameEnvironment, state: PrologueState, minutes: int
) -> None:
    """Set the time added to a player's turn each year. ``ChangeTimeLimit``.

    Stored in seconds, prompted for in minutes.
    """
    state.require_game()

    if minutes <= 0:
        raise PrologueError("Please enter a positive integer.")
    if minutes > MAX_MINUTES_PER_TURN:
        raise PrologueError("Please limit yourself to 2 hours per turn!")

    game.TimePerTurn = minutes * 60
    state.game_modified = True


# --- Choosing a player -------------------------------------------------------


def choose_player_options(
    game: GameEnvironment, empires: set[Empire]
) -> list[tuple[Empire, str]]:
    """The menu ``ChoosePlayer`` builds: each empire in ``empires``, by name.

    In slot order, which is the order the original's ``FOR`` loop adds them.
    """
    return [
        (emp, empire_name(game, emp) or emp.name)
        for emp in PLAYER_EMPIRES
        if emp in empires
    ]


def players_to_move(game: GameEnvironment) -> list[tuple[Empire, str]]:
    """Who may take a turn. ``GetPlayerToMove`` asks over ``EmpiresToMove``."""
    return choose_player_options(game, game.EmpiresToMove)


def deletable_empires(game: GameEnvironment) -> list[tuple[Empire, str]]:
    """Player empires that could be removed. Active and human-controlled."""
    return choose_player_options(
        game,
        {
            emp
            for emp in PLAYER_EMPIRES
            if empire_active(game, emp) and empire_player(game, emp)
        },
    )


# --- Adding and removing empires ---------------------------------------------


def delete_player_empire(
    game: GameEnvironment, state: PrologueState, emp: Empire
) -> bool:
    """Remove a player empire. Port of ``DeletePlayerEmpire``.

    Returns whether the deletion ended the *current* player's turn, which is
    the original's ``Continue`` flag: true when the deleted empire was the one
    playing, or always under non-sequential turns, where the prologue has to
    go back and ask who is moving.

    Refuses to delete the last player empire -- "But that's the last empire!
    How can you play with no empires?"
    """
    state.require_game()

    remaining = deletable_empires(game)
    if len(remaining) <= 1:
        raise PrologueError(
            "But that's the last empire! How can you play with no empires?"
        )

    game.EmpiresToMove.discard(emp)
    destroy_empire(game, emp)
    state.game_modified = True

    if game.AsyncTurns:
        game.Player = emp
        return True
    return game.Player == emp


def find_new_empire_slot(game: GameEnvironment) -> Empire:
    """The first unused empire slot, or ``Indep`` when all eight are taken."""
    for emp in PLAYER_EMPIRES:
        if not empire_active(game, emp):
            return emp
    return Empire.Indep


def find_new_capital(game: GameEnvironment) -> IDNumber:
    """The first independent world fit to seat a new empire.

    ``GetNewCapital``: independent, at least bio-tech, and over two thousand
    population. First in index order rather than best -- so a new empire lands
    on whichever qualifying world the scenario happened to place earliest, not
    on the strongest one available.
    """
    for i in range(1, game.NoOfPlanets + 1):
        world = IDNumber(ObjectTypes.Pln, i)
        if (
            get_status(game, world) == Empire.Indep
            and get_tech(game, world) >= MIN_CAPITAL_TECH
            and get_population(game, world) > MIN_CAPITAL_POP
        ):
            return world
    return empty_quadrant()


def add_player_empire(
    game: GameEnvironment, state: PrologueState, identity: EmpireIdentity
) -> Empire:
    """Seat a new player empire on an independent world. ``AddPlayerEmpire``.

    The newcomer starts at the *highest* technology level any active empire
    has reached, which is what makes joining a game in progress survivable at
    all -- one world against eight established empires, but not a primitive
    one. Every empire that already knows the world gets a ``NewPlEmp``
    headline, so the galaxy notices.

    **Original bug (#55).** The technology *set* is gathered wrongly:

    ```pascal
    IF Tech>MaxTech THEN
       BEGIN MaxTech:=Tech; MaxTechnology:=Technology; END
    ELSE
       MaxTechnology:=MaxTechnology+Technology;
    ```

    A new high-water mark **replaces** the accumulated set instead of merging
    into it, so everything gathered from empires examined earlier is thrown
    away. The result depends on the order the empires happen to sit in: the
    newcomer gets the best empire's technologies plus those of any empire
    *after* it in slot order, and nothing from before. Reproduced.
    """
    state.require_game()

    new_emp = find_new_empire_slot(game)
    if new_emp == Empire.Indep:
        raise PrologueError("There are already eight empires in the galaxy.")

    world_id = find_new_capital(game)
    if world_id.ObjTyp == ObjectTypes.Void:
        raise PrologueError("A suitable world cannot be found for a capital.")

    state.game_modified = True

    max_tech = TechLevel.PrimitLvl
    max_technology: set[TechnologyTypes] = set()

    for emp in PLAYER_EMPIRES:
        if not empire_active(game, emp):
            continue

        if known(game, emp, world_id):
            add_news(
                game,
                emp,
                NewsTypes.NewPlEmp,
                Location(XY=limbo(), ID=world_id),
                int(new_emp),
            )

        tech, technology = get_empire_technology(game, emp)
        if tech > max_tech:
            max_tech = tech
            # Replaces rather than merges -- see #55 above.
            max_technology = set(technology)
        else:
            max_technology |= technology

    create_empire(
        game,
        new_emp,
        is_player=True,
        is_empress=identity.is_empress,
        name=identity.name,
        password=identity.password,
        tech=max_tech,
        tech_set=max_technology,
        rev_factor=0,
        modifiers=set(),
        year_founded=game.Year,
        capital=world_id,
    )

    # A newcomer inherits no charts: KnownBy is wiped before the capital is
    # handed over, so the only thing on its map is what it can see from home.
    clear_known_set(game, new_emp)
    set_status(game, world_id, new_emp)
    set_type(game, world_id, WorldTypes.CapTyp)
    set_tech(game, world_id, max_tech)
    scout(game, new_emp, get_coord(game, world_id))

    return new_emp


__all__ = [
    "DEFAULT_GAME_NAME",
    "DWARF_AMONG_GIANTS",
    "MAX_MINUTES_PER_TURN",
    "PrologueError",
    "PrologueState",
    "abandon_new_game",
    "add_player_empire",
    "change_time_limit",
    "choose_player_options",
    "continue_old_game",
    "delete_player_empire",
    "deletable_empires",
    "do_not_save_game",
    "find_new_capital",
    "find_new_empire_slot",
    "menu_labels",
    "needs_saving",
    "players_to_move",
    "quit_game",
    "save_the_game",
    "start_a_new_game",
    "toggle_auto_save",
    "toggle_pause",
    "toggle_turn_sync",
]
