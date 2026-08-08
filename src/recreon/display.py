"""The command line, and the two parsers that read it. Port of DISPLAY.PAS.

Most of DISPLAY.PAS is video. ``DrawScreen`` opens the two windows a turn is
played in, ``WriteCommLine`` and ``WriteErrorMessage`` write into them,
``GetInputString`` reads back, and ``GetIDMenuChoice`` runs a picker over an
``IDList``. Textual replaces every one of those, so none of them are here.

What survives the move is the pair of routines that turn a string the player
typed into something the game can act on -- :func:`interpret_xy` and
:func:`interpret_obj`. :mod:`recreon.playturn`'s parameter validation calls the
second of them, and neither has any screen in it beyond the message it hands
back.

**Both write their own error text and then report a bare boolean**, which is
why they return the message rather than an error code. That matters at the one
place they meet the error table: PLAYTURN's ``InterpretParameter`` maps a
failed ``InterpretObj`` to ``NoObj``, and ``NoObj`` is one of the few error
codes with no entry in ``WriteError``'s case -- so nothing further is printed
and the message the player actually reads is the one from here. The port keeps
that division: :func:`recreon.playturn.error_message` returns ``""`` for
``NoObj``, and the caller shows what the interpreter said.
"""

from __future__ import annotations

from .environ import GameEnvironment
from .galaxy import XYCoord, limbo
from .misc import same_id, same_xy
from .primintr import get_coord, get_location, my_lord
from .types import Empire, IDNumber, ObjectTypes, empty_quadrant

#: The function-key reminder ``WriteMainHelpLine`` puts along the bottom of the
#: map. It is transcribed because it is *evidence*: together with HLPWIND.PAS's
#: fallback page it is the second independent statement in the source of what
#: the function keys do, and the two agree. F10 is the map, not the menu.
MAIN_HELP_LINE = "F1:Help F3:Status F5:Fleets F7:News F8:Empire F9:Names F10:Map"

#: How many characters ``InputParameter`` accepts. Names are capped at 8 by
#: ``InterpretNewName``; this is the wider limit on the input field itself.
MAX_PARAMETER_LENGTH = 16


def interpret_xy(
    game: GameEnvironment, player: Empire, parm: str
) -> tuple[XYCoord, str]:
    """Resolve a typed string to a coordinate. Returns ``(xy, error)``.

    A string naming an object resolves to *where that object is*, so a fleet
    name is a usable destination. Only when the string names nothing and parses
    as no coordinate does this fail, and then it fails to ``Limbo``.

    Note this is **not** what the parameter table calls for an ``XYParm``:
    ``GetParameters`` declares its own ``InterpretCoord``, which is this logic
    with the message removed and an ``UndefCoord`` code in its place. The two
    are kept separate because the original keeps them separate -- this one is
    for the map screens, which have nowhere to put an error code.
    """
    xy = limbo()
    loc = get_location(game, player, parm)

    if not same_id(loc.ID, empty_quadrant()):
        return get_coord(game, loc.ID), ""
    if not same_xy(loc.XY, limbo()):
        return loc.XY, ""

    return xy, f'"{parm}" are undefined coordinates, {my_lord(game, player)}.'


def interpret_obj(
    game: GameEnvironment, player: Empire, parm: str
) -> tuple[IDNumber, str]:
    """Resolve a typed string to an object. Returns ``(id, error)``.

    Two ways to fail: the string resolves to no object at all, or it resolves
    to a starbase or stargate that has since been destroyed. The second check
    is why a name outliving the thing it named does not crash the game -- a
    name record keeps pointing at the dead index, and this is what notices.

    On failure the returned ID is ``EmptyQuadrant``, as the original's is: it
    assigns that first and only overwrites it on the success path.
    """
    obj_id = empty_quadrant()
    loc = get_location(game, player, parm)
    sets = game.GlobalSets

    # `Parm[1]:=UpCase(Parm[1])` -- on the original's own local copy, so it
    # changes only the "has been destroyed" message below, not the lookup that
    # has already happened above.
    parm = parm[:1].upper() + parm[1:]

    if same_id(loc.ID, empty_quadrant()):
        return obj_id, (
            f"There is no object at that location, {my_lord(game, player)}."
        )

    destroyed = (
        loc.ID.ObjTyp == ObjectTypes.Base
        and loc.ID.Index not in sets.SetOfActiveStarbases
    ) or (
        loc.ID.ObjTyp == ObjectTypes.Gate
        and loc.ID.Index not in sets.SetOfActiveGates
    )
    if destroyed:
        return obj_id, f"{parm} has been destroyed."

    return loc.ID, ""


__all__ = [
    "MAIN_HELP_LINE",
    "MAX_PARAMETER_LENGTH",
    "interpret_obj",
    "interpret_xy",
]
