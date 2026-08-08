"""World designation and industrial self-sufficiency.

Ports the world-designation half of DESIGN.PAS, with ``DesignateWorld`` and
``TerraformWorld`` from INTRFACE.PAS, which is where the original actually
keeps them. The command-loop and window code around them is Phase 8.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .datacnst import MAX_ISSP, MinTechForType, TechDev
from .primintr import (
    change_total_rev_index,
    get_capital,
    get_efficiency,
    get_indus,
    get_status,
    get_tech,
    put_indus,
    set_capital,
    set_class,
    set_efficiency,
    set_empire_technology,
    set_issp,
    set_terraform_target,
    set_type,
)
from .types import IDNumber, IndusTypes, TechLevel, WorldClass, WorldTypes
from .utils.int_utils import rnd
from .utils.pascal import pascal_random_real, pascal_round

if TYPE_CHECKING:
    from .environ import GameEnvironment


def can_designate(game: GameEnvironment, world: IDNumber, new_type: WorldTypes) -> bool:
    """Whether the world is advanced enough for this designation."""
    return get_tech(game, world) >= MinTechForType[new_type]


def designate_world(
    game: GameEnvironment, world: IDNumber, new_type: WorldTypes
) -> None:
    """Redesignate a world, which always costs efficiency.

    Naming a new capital moves the empire's tech level with it and demotes
    the old capital to a base world -- an expensive move, reflected in the
    revolution-index hit.
    """
    if new_type == WorldTypes.CapTyp:
        emp = get_status(game, world)
        cap_id = get_capital(game, emp)
        old_tech = get_tech(game, cap_id)
        new_tech = get_tech(game, world)

        if old_tech > new_tech:
            set_empire_technology(game, emp, new_tech, TechDev[new_tech])
        elif old_tech < new_tech:
            # A capital promoted upward keeps only the level below its own.
            below = TechLevel(max(0, int(new_tech) - 1))
            set_empire_technology(game, emp, new_tech, TechDev[below])

        set_capital(game, emp, world)
        set_type(game, cap_id, WorldTypes.BseTyp)

        eff = get_efficiency(game, cap_id)
        set_efficiency(game, cap_id, eff - pascal_round(eff / (1.5 + pascal_random_real())))

        change_total_rev_index(game, emp, rnd(35, 45))

    eff = get_efficiency(game, world)
    set_efficiency(game, world, eff - pascal_round(eff / (1.5 + pascal_random_real())))

    set_type(game, world, new_type)


def terraform_world(
    game: GameEnvironment, world: IDNumber, new_class: WorldClass
) -> None:
    """Begin terraforming, which halves industry and guts efficiency."""
    old_industry = get_indus(game, world)

    set_class(game, world, WorldClass.TerCls)
    set_type(game, world, WorldTypes.TerTyp)
    set_terraform_target(game, world, new_class)

    put_indus(
        game,
        world,
        {ind: pascal_round(old_industry[ind] / 2) for ind in IndusTypes},
    )
    set_efficiency(
        game, world, pascal_round(get_efficiency(game, world) / 100 * rnd(30, 60))
    )


def change_issp(
    game: GameEnvironment, world: IDNumber, ind: IndusTypes, issp_ind: int
) -> None:
    """Set one industry's self-sufficiency index, clamped to the ISSP table.

    The index selects a multiplier from :data:`~recreon.datacnst.ISSP`;
    NORMAL_ISSP (5) is exactly self-sufficient, lower imports, higher exports.
    """
    set_issp(game, world, ind, max(0, min(MAX_ISSP, issp_ind)))
