"""Entry point and turn loop.

Port of the ANACREON.PAS main program, reduced to the parts whose
dependencies exist. The turn rotation and the point at which the year
advances are faithful; the work done inside a turn is not yet there.
"""

from __future__ import annotations

import argparse

from . import __version__
from .datacnst import TechDev, TriResByClass
from .environ import GameEnvironment
from .galaxy import XYCoord
from .intrface import create_planet, get_optimum_indus
from .primintr import empire_active, empire_player, no_more_players, put_indus
from .types import (
    PLAYER_EMPIRES,
    Empire,
    IDNumber,
    ObjectTypes,
    TechLevel,
    TechnologyTypes,
    WorldClass,
    WorldTypes,
)
from .update import update_universe


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
    NEWGAME.PAS, which the implementation plan never schedules. See
    :func:`place_world` for the stopgap.
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
        data.TechnologyLevel = TechLevel.WrpTchLvl
        data.Technology = set(TechDev[TechLevel.WrpTchLvl])

    game.reset_empires_to_move()
    return game


def place_world(
    game: GameEnvironment,
    index: int,
    xy: XYCoord,
    emp: Empire = Empire.Indep,
    cls: WorldClass = WorldClass.EthCls,
    typ: WorldTypes = WorldTypes.IndTyp,
    tech: TechLevel = TechLevel.WrpTchLvl,
    pop: int = 500,
    eff: int = 50,
) -> IDNumber:
    """Put one world on the map, developed enough to have an economy.

    A stopgap for NEWGAME.PAS, which generates a whole galaxy -- star
    placement, empire homeworlds, naming, starting fleets -- and is not
    scheduled anywhere in the implementation plan. This creates a single
    world with plausible defaults so the update loop has something to run
    on; it is not a port of anything.
    """
    world = IDNumber(ObjectTypes.Pln, index)
    planet = game.Universe.Planet[index]

    planet.Emp = emp
    planet.Cls = cls
    planet.Typ = typ
    planet.Tech = tech
    planet.Pop = pop
    planet.Eff = eff
    planet.TriReserve = TriResByClass[cls]

    create_planet(game, world, xy)
    game.NoOfPlanets = max(game.NoOfPlanets, index)

    # Seed enough raw material to get the first year's production moving.
    planet.Cargo[TechnologyTypes.met] = 500
    planet.Cargo[TechnologyTypes.che] = 500
    planet.Cargo[TechnologyTypes.sup] = 500

    put_indus(game, world, get_optimum_indus(game, world))
    return world


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
