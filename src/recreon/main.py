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
from .newgame import load_scenario
from .news import erase_news
from .primintr import empire_active, empire_player, next_empire, no_more_players
from .types import PLAYER_EMPIRES, Empire
from .update import update_universe


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
        # MovePlayerStarbases is Phase 6, with construction.

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
                return
            # An NPE's turn resolves without stopping the loop. ImplementNPE
            # is Phase 7, but its fleets still move on schedule.
            erase_news(game, game.Player)
            update_all_fleets(game, game.Player, next_empire(game, game.Player))

        if not any(empire_active(game, emp) for emp in PLAYER_EMPIRES):
            # Nothing left to rotate to; bail rather than spin forever.
            return


def play(game: GameEnvironment) -> None:
    """The main turn loop, with the player's turn itself still missing."""
    while not game.ExitProgram:
        if no_more_players(game):
            game.ExitProgram = True
            break

        # PlayerTakesTurn(Player) goes here -- Phase 4 onward.
        update_turn(game)


#: Shipped with the package; the only scenario that exists (see
#: IMPLEMENTATION_PLAN.md §3.5 for why the originals are not available).
DEFAULT_SCENARIO = Path(__file__).parent / "data" / "scenarios" / "frontier.scn"


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
        default=DEFAULT_SCENARIO,
        help=f"scenario file to load (default: {DEFAULT_SCENARIO.name})",
    )
    parser.add_argument("--name", default="Player", help="your empire's name")
    parser.add_argument(
        "--no-ui", action="store_true", help="advance one turn and exit, without the UI"
    )
    args = parser.parse_args()

    game = new_game(args.scenario, {Empire.Empire1: args.name})

    if args.no_ui:
        update_turn(game)
        print(
            f"Re:creon {__version__} -- year {game.Year}, "
            f"galaxy {game.Galaxy.size}^2, {game.NoOfPlanets} worlds"
        )
        return

    from .ui.app import RecreonApp

    RecreonApp(game).run()


if __name__ == "__main__":
    main()
