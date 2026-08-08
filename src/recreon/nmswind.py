"""The names window (F9), ported from NMSWIND.PAS.

Every place and fleet the player has named, with where it is now. The list a
player builds with the Name command (NAMES.PAS) is only useful if there is
somewhere to read it back, and this is that.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .datacnst import ObjName
from .primintr import get_coord_name, get_fleet_name
from .types import Empire, ObjectTypes

if TYPE_CHECKING:
    from .datastrc import NameRecord
    from .environ import GameEnvironment


def get_name_line(game: GameEnvironment, player: Empire, entry: NameRecord) -> str:
    """One row: the name, then what it currently refers to. ``GetNameLine``.

    Three cases, and the middle one is the reason this window earns its place.
    A name attached to a **fleet** resolves to that fleet's current name; a
    name whose fleet has been **destroyed** reads ``(destroyed)``; anything
    else is a sector and resolves to its coordinates.

    So a player who named a task force and lost it finds out here, and the name
    stays in the list rather than vanishing -- FLEET.PAS rewrites the object
    type to ``DestFlt`` instead of deleting the record.
    """
    name = entry.Name[:8].ljust(8)
    obj = entry.Coord.ID

    if obj.ObjTyp == ObjectTypes.Flt:
        where = get_fleet_name(game, player, obj)
    elif obj.ObjTyp == ObjectTypes.DestFlt:
        where = ObjName[ObjectTypes.DestFlt]
    else:
        where = get_coord_name(game, entry.Coord.XY)

    return f"{name}     {where[:12].ljust(12)}"


def name_rows(game: GameEnvironment, player: Empire) -> list[NameRecord]:
    """The named things, fleets first. ``InitNamesDataArray``.

    Two passes: every name pointing at a live fleet, then everything else --
    which puts sectors and destroyed fleets together in the second group,
    since ``DestFlt`` is not ``Flt``. A task force you lost sorts down among
    the place names.

    Within each group the list keeps the order names were added in.
    """
    names = game.Universe.EmpireData[player].Names
    return [n for n in names if n.Coord.ID.ObjTyp == ObjectTypes.Flt] + [
        n for n in names if n.Coord.ID.ObjTyp != ObjectTypes.Flt
    ]


def name_lines(game: GameEnvironment, player: Empire) -> list[str]:
    """The whole window, ready to display. ``DrawNamesWindow``."""
    rows = name_rows(game, player)
    if not rows:
        return ["No names have been defined."]
    return [get_name_line(game, player, entry) for entry in rows]


__all__ = ["get_name_line", "name_lines", "name_rows"]
