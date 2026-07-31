"""Entry point and turn loop.

Port of the ANACREON.PAS main program, reduced to the parts whose
dependencies exist. The turn rotation and the point at which the year
advances are faithful; the work done inside a turn is not yet there.
"""

from __future__ import annotations

import argparse

from . import __version__
from .environ import GameEnvironment
from .primintr import empire_active, empire_player, no_more_players
from .types import PLAYER_EMPIRES, Empire


def update_universe(game: GameEnvironment) -> None:
    """Advance the world by one year.

    Port of UPDATE.PAS ``UpdateUniverse``, of which only the year increment
    is implemented. Planet production, starbase updates, construction
    progress and empire research are Phase 3 onward.
    """
    game.Year += 1


def update_turn(game: GameEnvironment) -> None:
    """End the active empire's turn and hand off to the next one.

    Port of the synchronous branch of ANACREON.PAS ``UpdateTurn``. The year
    advances when the rotation wraps past Empire8 -- not once per player
    turn -- so a full round of empires is one game year.

    The asynchronous (play-by-mail) branch is not ported; ``AsyncTurns`` is
    always False for now.
    """
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
            # and the fleet updates land in Phase 7.

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


def new_game(size: int = 50, planets: int = 0, empires: int = 1) -> GameEnvironment:
    """A blank game with ``empires`` human empires and an empty galaxy.

    Real setup -- naming empires, placing worlds, seeding fleets -- is
    NEWGAME.PAS, in Phase 3. This is just enough to have something to look
    at and advance.
    """
    game = GameEnvironment()
    game.initialize_universe(size=size, planets=planets)

    for i in range(empires):
        emp = PLAYER_EMPIRES[i]
        data = game.Universe.EmpireData[emp]
        data.InUse = True
        data.IsAPlayer = True
        data.EmpireName = f"Empire {i + 1}"
        data.Founding = game.Year

    game.reset_empires_to_move()
    return game


def main() -> None:
    parser = argparse.ArgumentParser(prog="recreon", description="Re:creon")
    parser.add_argument("--version", action="version", version=f"Re:creon {__version__}")
    parser.add_argument(
        "--size", type=int, default=50, help="galaxy size in sectors (default: 50)"
    )
    parser.add_argument(
        "--no-ui", action="store_true", help="advance one turn and exit, without the UI"
    )
    args = parser.parse_args()

    game = new_game(size=args.size)

    if args.no_ui:
        update_turn(game)
        print(f"Re:creon {__version__} -- year {game.Year}, galaxy {game.Galaxy.size}^2")
        return

    from .ui.app import RecreonApp

    RecreonApp(game).run()


if __name__ == "__main__":
    main()
