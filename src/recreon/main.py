"""Entry point and turn loop.

Port of the ANACREON.PAS main program, reduced to the parts whose
dependencies exist. The turn rotation and the point at which the year
advances are faithful; the work done inside a turn is not yet there.
"""

from __future__ import annotations

import argparse

from . import __version__
from pathlib import Path

from .environ import GameEnvironment
from .fleet import update_all_fleets
from .intrface import scout_fleets, scout_objects, update_probes
from .loadsave import auto_backup
from .newgame import load_scenario
from .news import erase_news
from .npe.dispatch import implement_npe
from .primintr import (
    clear_scout_set,
    empire_active,
    empire_player,
    next_empire,
    no_more_players,
)
from .sbase import move_player_starbases
from .types import PLAYER_EMPIRES, Empire
from .update import update_universe


def set_up_turn(game: GameEnvironment, player: Empire) -> None:
    """Refresh what ``player`` can see, at the start of its turn.

    Port of ANACREON.PAS ``SetUpTurn``. Scouting is recomputed from scratch
    every turn rather than accumulated: ``clear_scout_set`` drops everything
    the empire had *observed* (``KnownBy`` persists), then the two sweeps
    rebuild it from where its worlds and fleets actually are. So an empire that
    pulls back genuinely loses sight of what it was watching.

    Order matters. ``scout_objects`` runs the ring sweep from every world and
    fleet before rescanning the galaxy, and ``update_probes`` lands last
    because a probe reveals what it flew over regardless of the rest.
    """
    clear_scout_set(game, player)
    scout_fleets(game, player)
    scout_objects(game, player)
    update_probes(game, player)


def update_turn(game: GameEnvironment) -> None:
    """End the active empire's turn and hand off to the next one.

    Port of the synchronous branch of ANACREON.PAS ``UpdateTurn``. The year
    advances when the rotation wraps past Empire8 -- not once per player
    turn -- so a full round of empires is one game year.

    Fleets move here rather than in ``update_universe``, and they move twice
    per handoff: once for the outgoing empire's jump fleets and once for the
    incoming empire's warp fleets. ``update_all_fleets`` decides which is
    which.

    The asynchronous (play-by-mail) branch is not ported; ``AsyncTurns`` is
    always False for now.
    """
    if empire_active(game, game.Player):
        erase_news(game, game.Player)
        update_all_fleets(game, game.Player, next_empire(game, game.Player))
        move_player_starbases(game, next_empire(game, game.Player))

    game.EmpiresToMove.discard(game.Player)

    while True:
        if game.Player == Empire.Empire8:
            game.Player = Empire.Empire1
            game.reset_empires_to_move()
            update_universe(game)
        else:
            game.Player = Empire(int(game.Player) + 1)

        if empire_active(game, game.Player):
            if empire_player(game, game.Player):
                # ANACREON.PAS runs SetUpTurn before PlayerTakesTurn; the port
                # returns control here instead, so this is the same point.
                set_up_turn(game, game.Player)
                return
            # An NPE's turn resolves without stopping the loop, in the order
            # ANACREON.PAS:240-251 runs it: refresh what the empire can see,
            # let the AI act on it, then clear the news and move.
            set_up_turn(game, game.Player)
            implement_npe(game, game.Player)

            erase_news(game, game.Player)
            update_all_fleets(game, game.Player, next_empire(game, game.Player))
            move_player_starbases(game, next_empire(game, game.Player))

        if not any(empire_active(game, emp) for emp in PLAYER_EMPIRES):
            # Nothing left to rotate to; bail rather than spin forever.
            return


def play(game: GameEnvironment) -> list[str]:
    """The main turn loop, with the player's turn itself still missing.

    Returns whatever autosave had to say. ANACREON.PAS calls ``AutoBackup``
    after each completed turn, and the branch where the last player has been
    destroyed does not reach it -- so a finished game leaves no backup
    inviting the player back into it.

    That branch also calls ``DoNotSaveGame`` (PROLOG.PAS:392), whose whole
    body is ``GameModified := False``. It suppresses the prologue's
    save-before-you-quit prompt, not the backup; the two are independent, and
    the backup is skipped here purely by where it sits in the ``IF``. There is
    nothing to port until the prologue exists (§8.5).
    """
    warnings: list[str] = []

    while not game.ExitProgram:
        if no_more_players(game):
            game.ExitProgram = True
            break

        # PlayerTakesTurn(Player) goes here -- Phase 4 onward.
        update_turn(game)
        warnings.extend(auto_backup(game))

    return warnings


#: Where the scenario picker looks, and where the shipped scenario lives.
#: The 13 originals are in ``original/scenarios`` and are not installed with
#: the package; point ``--scenario-dir`` at them to play those.
SCENARIO_DIR = Path(__file__).parent / "data" / "scenarios"

#: Loaded when no scenario is chosen. Authored content, not a port -- it
#: reproduces no galaxy the original shipped. See IMPLEMENTATION_PLAN.md §3.5.
DEFAULT_SCENARIO = SCENARIO_DIR / "frontier.scn"


def new_game(
    scenario: str | Path = DEFAULT_SCENARIO,
    player_names: dict[Empire, str] | None = None,
) -> GameEnvironment:
    """Start a game from a scenario file.

    Empire slots with no name are skipped, so passing one name gives a
    single-player game against the scenario's NPEs.
    """
    return load_scenario(scenario, player_names or {Empire.Empire1: "Player"})


def main() -> None:
    parser = argparse.ArgumentParser(prog="recreon", description="Re:creon")
    parser.add_argument("--version", action="version", version=f"Re:creon {__version__}")
    parser.add_argument(
        "--scenario",
        help="scenario file to load, skipping the picker",
    )
    parser.add_argument(
        "--scenario-dir",
        default=SCENARIO_DIR,
        help=f"directory the picker scans for *.SCN (default: {SCENARIO_DIR})",
    )
    parser.add_argument(
        "--save-dir",
        default=Path.cwd(),
        help="directory saved games are written to and read from (default: .)",
    )
    parser.add_argument("--name", default="Player", help="your empire's name")
    parser.add_argument(
        "--no-ui", action="store_true", help="advance one turn and exit, without the UI"
    )
    args = parser.parse_args()

    if args.no_ui:
        game = new_game(args.scenario or DEFAULT_SCENARIO, {Empire.Empire1: args.name})
        update_turn(game)
        print(
            f"Re:creon {__version__} -- year {game.Year}, "
            f"galaxy {game.Galaxy.size}^2, {game.NoOfPlanets} worlds"
        )
        return

    from .ui.app import RecreonApp

    # With no --scenario the app opens on the prologue menu, which is where
    # the original starts: ANACREON.PAS runs Prologue before anything else.
    game = None
    if args.scenario:
        game = new_game(args.scenario, {Empire.Empire1: args.name})

    RecreonApp(
        game, scenario_dir=args.scenario_dir, save_dir=args.save_dir
    ).run()


if __name__ == "__main__":
    main()
