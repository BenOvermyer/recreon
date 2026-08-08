"""The world status window (F3/F4), ported from STAWIND.PAS.

One window, two stacked tables over the same worlds in the same order: world
status on top (class, type, tech, population, efficiency, trade, unrest) and
military status below (troops, ships, defenses). F3 and F4 both open it because
a player thinks of them as two screens.

The rows themselves are `intrface.get_world_status` and
`intrface.get_military_status`; what is here is *which* worlds appear and in
what order.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .primintr import get_capital, get_population, get_tech, scouted
from .types import MAX_NO_OF_STARBASES, Empire, IDNumber, ObjectTypes
from .utils.sort import quick_sort_d, word_key

if TYPE_CHECKING:
    from .environ import GameEnvironment

#: The two column headers, transcribed from `InitTitle` and `DividingBar`.
STATUS_HEADER = (
    "PlntName Sta C T Tl  Pop Eff A Impt Expt Rev  jtn  trn  amb  che  met  sup  tri "
)
MILITARY_HEADER = (
    "PlntName Sta   men ninj  fgt  hkr  jmp  jtn  pen  str  trn  LAM  def  GDM  ion  "
)


def _element_key(entry: tuple[int, int, IDNumber]) -> int:
    """The Word ``QuickSortD`` compares: ``Tech`` high, ``Pop`` low.

    The record is ``Pop: Byte; Tech: TechLevel; ID: IDNumber``, so it reads
    like a sort by population. It is not -- see :mod:`recreon.utils.sort`.
    """
    pop_hi, tech, _ = entry
    return word_key(pop_hi, tech)


def status_rows(game: GameEnvironment, player: Empire) -> list[IDNumber]:
    """Which worlds the status window lists, in order. ``InitializeStatusDataArray``.

    **The capital is always first**, pulled out before anything is sorted, and
    excluded from the sections below so it cannot appear twice.

    Then two sorted sections, each covering planets *and* starbases together:

    1. everything the player owns;
    2. everything the player has **scouted** and does not own.

    A world merely *known* about does not appear -- this table is made of
    numbers, and knowing a world is there tells you none of them. That is a
    stricter test than the map's, which keys on `KnownBy`.

    Within a section the order is by technology descending, population
    breaking ties, which is not what the record declaration suggests.
    """
    capital = get_capital(game, player)
    rows: list[IDNumber] = [capital]

    #: (population high byte, tech ordinal, ID) -- the original's ElementRecord.
    temp: list[tuple[int, int, IDNumber]] = []
    mark = 1

    def add(obj: IDNumber) -> None:
        # `Hi(GetPopulation(ID))` -- population is divided by 256 before it is
        # ever compared, so worlds within the same 25.6 billion tie.
        temp.append(
            (get_population(game, obj) >> 8, int(get_tech(game, obj)), obj)
        )

    def sort_section() -> None:
        nonlocal mark
        if len(temp) > mark:
            quick_sort_d(temp, _element_key, mark, len(temp))
        mark = len(temp) + 1

    sets = game.GlobalSets
    for i in range(1, game.NoOfPlanets + 1):
        obj = IDNumber(ObjectTypes.Pln, i)
        if i in sets.SetOfPlanetsOf[player] and obj != capital:
            add(obj)
    for i in range(1, MAX_NO_OF_STARBASES + 1):
        obj = IDNumber(ObjectTypes.Base, i)
        if i in sets.SetOfStarbasesOf[player] and obj != capital:
            add(obj)
    sort_section()

    for i in range(1, game.NoOfPlanets + 1):
        obj = IDNumber(ObjectTypes.Pln, i)
        if i not in sets.SetOfPlanetsOf[player] and scouted(game, player, obj):
            add(obj)
    others = sets.SetOfActiveStarbases - sets.SetOfStarbasesOf[player]
    for i in range(1, MAX_NO_OF_STARBASES + 1):
        obj = IDNumber(ObjectTypes.Base, i)
        if i in others and scouted(game, player, obj):
            add(obj)
    sort_section()

    rows.extend(entry[2] for entry in temp)
    return rows


__all__ = ["MILITARY_HEADER", "STATUS_HEADER", "status_rows"]
