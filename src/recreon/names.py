"""Place names, and the empire status report.

Port of NAMES.PAS. Two small commands -- name a place, remove a name -- and
``StatusHardcopy``, a one-page summary of everything the empire knows.

**The printer is not portable; the report is.** ``StatusHardcopy`` sends its
lines to ``LST:`` after asking the player to ready the paper. What it *builds*
is a compact table of every world and base the empire owns or has scouted, and
that is worth having, so :func:`status_report` returns the lines and the UI
shows them or writes them to a file.
"""

from __future__ import annotations

from .datacnst import ClassStr, TechStr, TypeStr
from .environ import GameEnvironment
from .galaxy import Location, XYCoord, limbo
from .misc import same_id
from .primintr import (
    add_name,
    delete_name,
    empire_name,
    get_capital,
    get_cargo,
    get_class,
    get_defns,
    get_name,
    get_population,
    get_ships_known,
    get_status,
    get_tech,
    get_type,
    my_lord,
    scouted,
)
from .types import (
    DEFNS_TYPES,
    SHIP_TYPES,
    Empire,
    IDNumber,
    ObjectTypes,
    TechnologyTypes,
    tech_range,
)
from .utils.pascal import pascal_round

T = TechnologyTypes

#: The report's column headings, verbatim.
STATUS_HEADER = (
    "PlntName Sta C T Tl  Pop am ch mt sp tr MN NJ FT HK JM JT PN ST TN lm df gd in",
    "-" * 78,
)

#: Columns in the order the report prints them: raw materials, then troops,
#: then ships, then defenses.
REPORT_COLUMNS = (
    tuple(tech_range(T.amb, T.tri))
    + (T.men, T.nnj)
    + tuple(SHIP_TYPES)
    + tuple(DEFNS_TYPES)
)


# --- Naming ------------------------------------------------------------------


def add_name_command(
    game: GameEnvironment,
    player: Empire,
    obj: IDNumber,
    coord: XYCoord,
    name: str,
) -> str:
    """Name a place or a thing. Port of ``AddNameCommand``.

    The first letter is capitalised whatever the player typed. ``AddName``
    then fills the coordinate in from the object for a world, gate or
    construction site, so a name given to a *thing* follows it and a name
    given to a bare coordinate stays put.

    The original's error branch -- "there isn't room to define another name"
    -- cannot fire here: it existed because the name list was a fixed heap
    allocation, and a Python list grows.
    """
    name = f"{name[:1].upper()}{name[1:]}"
    add_name(game, player, Location(XY=coord, ID=obj), name)
    return f'"{name}" has been added to the list, {my_lord(game, player)}.'


def delete_name_command(game: GameEnvironment, player: Empire, name: str) -> str:
    """Forget a name. Port of ``DeleteNameCommand``.

    Reports success whether or not the name existed -- ``DeleteName`` is
    silent about a miss and the command does not ask.
    """
    delete_name(game, player, name)
    return f'"{name}" has been deleted from the list, {my_lord(game, player)}.'


# --- The status report -------------------------------------------------------


def resource_entry(player: Empire, owner: Empire, res: T, amount: int) -> str:
    """One two-character cell. Port of ``GetResourceEntry``.

    Two encodings, and which one you get depends on whose world it is:

    * **Yours** -- hundreds, so ``42`` means about 4200, and ``++`` above 99.
    * **Someone else's** -- an intelligence estimate, not a count. Raw
      materials read ``--`` because you cannot see another empire's stores at
      all; everything else is ``no``, or ``y`` plus thousands, or ``y+`` above
      9500.

    So a scouted enemy world tells you roughly how many ships it has and
    nothing about what it is made of.
    """
    if owner != player:
        if res in tech_range(T.amb, T.tri):
            return "--"
        if amount == 0:
            return "no"
        if amount > 9500:
            return "y+"
        return f"y{pascal_round(amount / 1000):1d}"

    hundreds = pascal_round(amount / 100)
    return "++" if hundreds > 99 else f"{hundreds:2d}"


def world_status_line(
    game: GameEnvironment, player: Empire, world: IDNumber
) -> str:
    """One row. Port of ``PrintWorldStatus``."""
    name = get_name(game, player, Location(XY=limbo(), ID=world), False)[:8].ljust(8)
    owner = get_status(game, world)
    emp = (empire_name(game, owner) or owner.name)[:3].ljust(3)

    line = (
        f"{name} {emp} "
        f"{ClassStr[get_class(game, world)]} "
        f"{TypeStr[get_type(game, world)]} "
        f"{TechStr[get_tech(game, world)]} "
        f"{get_population(game, world) / 100:4.1f} "
    )

    ships = get_ships_known(game, player, world)
    cargo = get_cargo(game, world)
    defns = get_defns(game, world)

    cells = []
    for res in REPORT_COLUMNS:
        if res in SHIP_TYPES:
            amount = ships[res]
        elif res in DEFNS_TYPES:
            amount = defns[res]
        else:
            amount = cargo[res]
        cells.append(resource_entry(player, owner, res, amount))

    return line + " ".join(cells)


def status_report(game: GameEnvironment, player: Empire) -> list[str]:
    """The whole report. Port of ``StatusHardcopy``'s content.

    Ordered as the original prints it, which is an order of decreasing
    interest: **the capital first**, then the empire's other worlds, then its
    bases, then every scouted foreign world, then every scouted foreign base.

    The capital is printed first and then skipped in the sweeps, so it appears
    once.
    """
    lines = [
        f"{empire_name(game, player) or player.name} status: {game.Year}",
        "",
        *STATUS_HEADER,
    ]

    capital = get_capital(game, player)
    if capital.ObjTyp != ObjectTypes.Void:
        lines.append(world_status_line(game, player, capital))

    for index in range(1, game.NoOfPlanets + 1):
        if index in game.GlobalSets.SetOfPlanetsOf[player]:
            world = IDNumber(ObjectTypes.Pln, index)
            if not same_id(world, capital):
                lines.append(world_status_line(game, player, world))

    for index in sorted(game.GlobalSets.SetOfStarbasesOf[player]):
        base = IDNumber(ObjectTypes.Base, index)
        if not same_id(base, capital):
            lines.append(world_status_line(game, player, base))

    for index in range(1, game.NoOfPlanets + 1):
        if index not in game.GlobalSets.SetOfPlanetsOf[player]:
            world = IDNumber(ObjectTypes.Pln, index)
            if scouted(game, player, world):
                lines.append(world_status_line(game, player, world))

    for index in sorted(game.GlobalSets.SetOfActiveStarbases):
        if index not in game.GlobalSets.SetOfStarbasesOf[player]:
            base = IDNumber(ObjectTypes.Base, index)
            if scouted(game, player, base):
                lines.append(world_status_line(game, player, base))

    return lines


__all__ = [
    "REPORT_COLUMNS",
    "STATUS_HEADER",
    "add_name_command",
    "delete_name_command",
    "resource_entry",
    "status_report",
    "world_status_line",
]
