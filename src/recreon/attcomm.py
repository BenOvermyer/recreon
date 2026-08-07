"""Attack commands.

Port of ATTCOMM.PAS's target selection and the auto-attack command. The
mechanics are `attnpe.npe_attack` -- despite the name it consults no AI
persona, so it resolves a player's attack too.

**The round-by-round interactive attack is not ported yet.**
``AttackCommand`` is the larger half of this unit: it splits the fleet into
groups, then each round lets the player move groups between orbital shells,
retarget them and retreat, where ``npe_attack`` decides all of that
automatically. `GetGroups`, `WarpIn`, `WarpOut`, `GroupTarget`,
`GroupRetreat`, `GroupMove` and `Engage` are that loop and remain to do; the
Ministry of War menu says so rather than hiding the command.

What is here is enough to fight: pick a target, confirm, and let it resolve.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .attack import AttackIntentionTypes, AttackResultTypes
from .attnpe import npe_attack
from .datacnst import ObjName, ThingNames
from .environ import GameEnvironment
from .galaxy import XYCoord
from .primintr import (
    empire_name,
    empress,
    get_coord,
    get_fleets,
    get_object,
    get_ships,
    get_status,
    my_lord,
    object_name,
    scouted,
)
from .types import SHIP_TYPES, Empire, IDNumber, ObjectTypes, TechnologyTypes
from .utils.int_utils import rnd

T = TechnologyTypes

#: What can be attacked at all. Worlds, bases and fleets fight back; sites and
#: gates are simply razed by `npe_attack`.
TARGETABLE = (
    ObjectTypes.Pln,
    ObjectTypes.Base,
    ObjectTypes.Flt,
    ObjectTypes.Con,
    ObjectTypes.Gate,
)

#: Fights that resolve as a battle rather than a demolition.
FIGHTS_BACK = (ObjectTypes.Pln, ObjectTypes.Base, ObjectTypes.Flt)


def attack_targets(
    game: GameEnvironment, player: Empire, flt_id: IDNumber
) -> list[tuple[IDNumber, str]]:
    """What the fleet may attack in its own sector. Port of ``GetTarget``.

    **A world cannot be targeted while an enemy fleet is in the sector.** The
    original adds the object under the fleet only ``IF ListSize=0`` -- after
    finding no enemy fleets -- so a fleet in orbit screens the world beneath
    it, and has to be destroyed first. That is a real mechanic and not a
    display quirk.

    Enemy fleets must have been **scouted** to be offered; the object beneath
    gets no such test, because you can see what a world is without scouting
    what is on it.
    """
    xy = get_coord(game, flt_id)
    found: list[tuple[IDNumber, str]] = []

    for index in sorted(get_fleets(game, xy)):
        other = IDNumber(ObjectTypes.Flt, index)
        status = get_status(game, other)
        if status != player and scouted(game, player, other):
            found.append((other, _label(game, player, other, status)))

    if not found:
        obj = get_object(game, xy)
        status = get_status(game, obj)
        if obj.ObjTyp in TARGETABLE and status != player:
            found.append((obj, _label(game, player, obj, status)))

    return found


def _label(
    game: GameEnvironment, player: Empire, obj: IDNumber, emp: Empire
) -> str:
    name = object_name(game, player, obj, long_format=True)
    return f"{name}  ({empire_name(game, emp) or emp.name})"


@dataclass(slots=True)
class AttackOutcome:
    """What the auto-attack has to report afterwards."""

    result: AttackResultTypes
    #: Ships lost, by type -- only the types that took losses.
    casualties: dict[T, int] = field(default_factory=dict)
    #: Worlds taken as spoils, by planet index.
    spoils: set[int] = field(default_factory=set)
    lines: list[str] = field(default_factory=list)


def result_message(
    game: GameEnvironment,
    player: Empire,
    target: IDNumber,
    result: AttackResultTypes,
) -> list[str]:
    """What the staff say about the outcome. Port of ``ResultMessage``.

    A destroyed attack force draws one of two consolations at random, which is
    a draw from the generator in a message -- the same class of thing as
    ``my_lord``. A conquest is announced in the ruler's name, and the wording
    differs for an empress.
    """
    lord = my_lord(game, player)

    if result == AttackResultTypes.AttDestroyedART:
        excuse = (
            "Perhaps if you had been there to direct the attack..."
            if rnd(1, 2) == 1
            else "The fleet commander fought bravely and did not surrender."
        )
        return [
            f"I'm sorry, {lord}, the entire attack force has been destroyed.",
            excuse,
        ]

    if result == AttackResultTypes.AttRetreatsART:
        return [f"I'm sorry, {lord}, the fleet was forced to retreat."]

    if result == AttackResultTypes.DefConqueredART:
        if target.ObjTyp == ObjectTypes.Flt:
            return [f"The enemy fleet has been destroyed, {lord}."]

        name = empire_name(game, player) or player.name
        style = (
            f"In the name of Her Imperial Majesty, Lady of {name}, I hereby declare"
            if empress(game, player)
            else f"In the name of His Imperial Majesty, Lord of {name}, I hereby declare"
        )
        return [
            style,
            f"this {ObjName[target.ObjTyp]} to be under the sovereign "
            "jurisdiction of the",
            f"{name} Empire.",
        ]

    return []


def casualty_report(
    before: dict[T, int], after: dict[T, int]
) -> dict[T, int]:
    """Ships lost, by type. Port of ``CasualtyReport``.

    Only losses: a fight that *captured* transports leaves a negative
    difference, and the original's report has no column for it.
    """
    return {
        ship: before[ship] - after[ship]
        for ship in SHIP_TYPES
        if before[ship] > after[ship]
    }


def auto_attack_command(
    game: GameEnvironment, player: Empire, flt_id: IDNumber, target: IDNumber
) -> AttackOutcome:
    """Resolve an attack without the player directing it. ``AutoAttackCommand``.

    Construction sites and stargates are razed rather than fought -- they have
    nothing to fight with -- and the original reports that separately, without
    a casualty list.

    The intent is always ``ConquerAIT``: a player attacking by hand is trying
    to take the thing, not to deny its cargo.

    **Original bug (#65).** The original reads the fleet's ships again after
    the fight -- ``GetShips(FltID, NewShips)`` -- without checking whether the
    fleet still exists, and then subtracts to get the casualty list. When the
    attack force is destroyed the record has been disposed, so it reads freed
    memory and reports a casualty list built from whatever is there. The code
    plainly knows the fleet can die: ``ResultMessage`` has a branch for
    exactly that outcome.

    Here that reads a ``None`` slot, so the port takes the defined reading: a
    destroyed fleet lost everything it had, which is both true and what the
    subtraction was reaching for.
    """
    if target.ObjTyp not in FIGHTS_BACK:
        name = object_name(game, player, target, long_format=True)
        return AttackOutcome(
            result=AttackResultTypes.NoART,
            lines=[f"{name} has been destroyed."],
        )

    before = get_ships(game, flt_id)
    result, spoils = npe_attack(
        game, flt_id, target, AttackIntentionTypes.ConquerAIT
    )

    if flt_id.Index in game.GlobalSets.SetOfActiveFleets:
        after = get_ships(game, flt_id)
    else:
        # Destroyed: everything aboard was lost. See #65.
        after = {ship: 0 for ship in before}

    return AttackOutcome(
        result=result,
        casualties=casualty_report(before, after),
        spoils=spoils,
        lines=result_message(game, player, target, result),
    )


__all__ = [
    "FIGHTS_BACK",
    "TARGETABLE",
    "AttackOutcome",
    "attack_targets",
    "auto_attack_command",
    "casualty_report",
    "result_message",
]
