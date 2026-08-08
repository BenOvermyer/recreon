"""The fleet status window (F5/F6), ported from FLTWIND.PAS.

The mobile counterpart to :mod:`recreon.stawind`: one window, two stacked
tables over the same craft. Position, destination, status and range on top;
what is aboard below.

The rows are `intrface.get_fleet_position_status` and
`intrface.get_fleet_status_line`; this module decides which craft appear.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .primintr import get_base_type, get_coord, known, scouted
from .types import (
    MAX_NO_OF_FLEETS,
    MAX_NO_OF_STARBASES,
    Empire,
    IDNumber,
    ObjectTypes,
    TechnologyTypes,
)
from .utils.sort import quick_sort_d, word_key

if TYPE_CHECKING:
    from .environ import GameEnvironment

#: The two column headers, transcribed from `InitTitle` and `DividingBar`.
POSITION_HEADER = (
    "     Fleet      Pos        Des        Status              Range                 "
)
CONTENTS_HEADER = (
    "Fleet     fgt   hk  jmp  jtn  pen  str  trn  men ninj  amb  che  met  sup  tri  "
)


def _element_key(entry: tuple[int, int, IDNumber]) -> int:
    """The Word ``QuickSortD`` compares: ``y`` high, ``x`` low.

    The record is ``XY: XYCoord; ID: IDNumber`` and `XYCoord` is two bytes, so
    the sort runs down the map by row -- highest y first -- and only then
    across. See :mod:`recreon.utils.sort`.
    """
    x, y, _ = entry
    return word_key(x, y)


def fleet_rows(game: GameEnvironment, player: Empire) -> list[IDNumber]:
    """Which craft the fleet window lists, in order. ``InitializeFleetDataArray``.

    Four sorted sections, each sorted on its own:

    1. the player's active fleets;
    2. the player's **command bases and fortresses** -- ``cmm`` and ``frt``
       only, because a compound base or outpost does not move and has no
       destination to report. This is the one place the two kinds of starbase
       are told apart by mobility rather than by function;
    3. enemy fleets the player has **scouted**;
    4. enemy fleets the player merely **knows** of.

    Sections 3 and 4 are what makes this table worth opening: an unscouted
    enemy fleet still gets a row, reading ``(unknown)`` for its destination and
    ``(out of range)`` for its status. You are told something is out there
    before you are told what.
    """
    sets = game.GlobalSets
    active = sets.SetOfFleetsOf[player] & sets.SetOfActiveFleets
    enemy = sets.SetOfActiveFleets - sets.SetOfFleetsOf[player]

    #: (x, y, ID) -- the original's ElementRecord.
    temp: list[tuple[int, int, IDNumber]] = []
    mark = 1

    def add(obj: IDNumber) -> None:
        xy = get_coord(game, obj)
        temp.append((xy.x, xy.y, obj))

    def sort_section() -> None:
        nonlocal mark
        if len(temp) > mark:
            quick_sort_d(temp, _element_key, mark, len(temp))
        mark = len(temp) + 1

    for i in range(1, MAX_NO_OF_FLEETS + 1):
        if i in active:
            add(IDNumber(ObjectTypes.Flt, i))
    sort_section()

    for i in range(1, MAX_NO_OF_STARBASES + 1):
        obj = IDNumber(ObjectTypes.Base, i)
        if i in sets.SetOfStarbasesOf[player] and get_base_type(game, obj) in (
            TechnologyTypes.cmm,
            TechnologyTypes.frt,
        ):
            add(obj)
    sort_section()

    for i in range(1, MAX_NO_OF_FLEETS + 1):
        obj = IDNumber(ObjectTypes.Flt, i)
        if i in enemy and scouted(game, player, obj):
            add(obj)
    sort_section()

    for i in range(1, MAX_NO_OF_FLEETS + 1):
        obj = IDNumber(ObjectTypes.Flt, i)
        if i in enemy and not scouted(game, player, obj) and known(game, player, obj):
            add(obj)
    sort_section()

    return [entry[2] for entry in temp]


__all__ = ["CONTENTS_HEADER", "POSITION_HEADER", "fleet_rows"]
