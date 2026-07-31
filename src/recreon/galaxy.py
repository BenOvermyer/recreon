"""Galaxy grid coordinates, sector records, and the sector grid itself.

Port of GALAXY.PAS. LoadSector/SaveSector are deferred to Phase 8 with the
rest of save/load.

ARCHITECTURE.md sketches XYCoord as living in types.py, but the original
declares it here and DATASTRC.PAS depends on Galaxy for it. Keeping it here
preserves the one-module-per-unit mapping.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .types import Empire, IDNumber, ObjectTypes

MAX_SIZE_OF_GALAXY = 100  # in sectors; Coordinate = 0..MaxSizeOfGalaxy


@dataclass(slots=True)
class XYCoord:
    x: int = 0
    y: int = 0


@dataclass(slots=True)
class Location:
    XY: XYCoord = field(default_factory=XYCoord)
    ID: IDNumber = field(default_factory=IDNumber)


@dataclass(slots=True)
class SectorRecord:
    """One sector of the galaxy grid."""

    #: ID of the object in this sector.
    Obj: IDNumber = field(default_factory=IDNumber)
    #: Empires that have a fleet here.
    Flts: set[Empire] = field(default_factory=set)
    #: Empires that know about the SRM mine here.
    MineScout: set[Empire] = field(default_factory=set)
    #: Low 4 bits = nebula type, high 4 bits = owner of the SRM field.
    Special: int = 0


def limbo() -> XYCoord:
    """Pascal's ``Limbo`` constant -- the off-map coordinate (0, 0)."""
    return XYCoord(0, 0)


#: Sentinel stored in the high nibble of ``SectorRecord.Special`` meaning
#: "no SRM field here". Depends on ``Ord(Indep) == 8``.
NO_SRM_FIELD = int(Empire.Indep) * 16


def nebula_of(special: int) -> int:
    """Low 4 bits of ``Special``."""
    return special & 0x0F


def srm_owner_of(special: int) -> int:
    """High 4 bits of ``Special``."""
    return (special >> 4) & 0x0F


class Galaxy:
    """The sector grid.

    Rows and columns run ``0..size`` inclusive, matching Pascal's
    ``Coordinate = 0..MaxSizeOfGalaxy``, so the grid is ``size + 1`` square.
    Row and column 0 are allocated but lie *outside* the playable area:
    :func:`in_galaxy` requires ``x > 0 and y > 0``, and ``Limbo`` is (0, 0),
    the coordinate objects get parked at when they are nowhere.

    Replaces the Pascal globals ``Sector`` and ``SizeOfGalaxy``, per the
    convention that global state lives on an object.
    """

    __slots__ = ("size", "_sectors")

    def __init__(self, size: int = 0) -> None:
        self.size = 0
        self._sectors: list[list[SectorRecord]] = []
        if size > 0:
            self.initialize(size)

    def initialize(self, size: int) -> None:
        """Allocate an empty grid: no objects, no nebulae, no minefields.

        Sizes above MAX_SIZE_OF_GALAXY are clamped, as in the original.
        A size of 0 or less leaves the grid unallocated.
        """
        if size <= 0:
            self.size = 0
            self._sectors = []
            return

        size = min(size, MAX_SIZE_OF_GALAXY)
        self.size = size
        self._sectors = [
            [SectorRecord(Special=NO_SRM_FIELD) for _ in range(size + 1)]
            for _ in range(size + 1)
        ]

    def in_galaxy(self, x: int, y: int) -> bool:
        """Whether (x, y) is a playable sector.

        Port of MISC.PAS ``InGalaxy``. Note the lower bound is exclusive:
        row/column 0 exists in the grid but is not in the galaxy.
        """
        return 0 < x <= self.size and 0 < y <= self.size

    def sector(self, xy: XYCoord) -> SectorRecord:
        """The sector at ``xy``.

        Raises IndexError outside the allocated grid. The original indexes
        without bounds checks; the check is added here because Python's
        negative indexing would silently wrap to the far edge of the galaxy
        instead of failing.
        """
        if not (0 <= xy.x <= self.size and 0 <= xy.y <= self.size):
            raise IndexError(f"sector {(xy.x, xy.y)} outside galaxy of size {self.size}")
        return self._sectors[xy.x][xy.y]

    def set_mine_scout(self, emp: Empire, xy: XYCoord) -> None:
        """Record that ``emp`` knows about the minefield at ``xy``."""
        self.sector(xy).MineScout.add(emp)

    def clr_mine_scout(self, xy: XYCoord) -> None:
        self.sector(xy).MineScout.clear()

    def coordinates(self):
        """Every playable coordinate, in column-major order like the original."""
        for x in range(1, self.size + 1):
            for y in range(1, self.size + 1):
                yield XYCoord(x, y)


__all__ = [
    "MAX_SIZE_OF_GALAXY",
    "NO_SRM_FIELD",
    "Galaxy",
    "Location",
    "ObjectTypes",
    "SectorRecord",
    "XYCoord",
    "limbo",
    "nebula_of",
    "srm_owner_of",
]
