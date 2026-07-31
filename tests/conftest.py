"""Shared test helpers.

``place_world`` used to live in ``main.py`` as a stopgap while NEWGAME.PAS was
unported. Real games now come from scenario files, so it lives here instead:
it is not a port of anything and has no place in the shipped package, but unit
tests still want one world with exactly known attributes rather than a whole
generated galaxy.
"""

from __future__ import annotations

import pytest

from recreon.datacnst import TechDev, TriResByClass
from recreon.environ import GameEnvironment
from recreon.galaxy import XYCoord
from recreon.intrface import create_planet, get_optimum_indus
from recreon.primintr import put_indus
from recreon.types import (
    PLAYER_EMPIRES,
    Empire,
    IDNumber,
    ObjectTypes,
    TechLevel,
    TechnologyTypes,
    WorldClass,
    WorldTypes,
)


def blank_game(size: int = 20, empires: int = 1) -> GameEnvironment:
    """An empty galaxy with ``empires`` active human empires."""
    game = GameEnvironment()
    game.initialize_universe(size=size)

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
    """One world with known attributes, developed enough to have an economy."""
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

    # Enough raw material to get the first year's production moving.
    planet.Cargo[TechnologyTypes.met] = 500
    planet.Cargo[TechnologyTypes.che] = 500
    planet.Cargo[TechnologyTypes.sup] = 500

    put_indus(game, world, get_optimum_indus(game, world))
    return world


@pytest.fixture
def scenario_path():
    from recreon.main import DEFAULT_SCENARIO

    return DEFAULT_SCENARIO
