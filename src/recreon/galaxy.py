"""Galaxy grid coordinates and sector records.

Port of GALAXY.PAS -- type definitions only. The sector runtime
(InitializeSector, LoadSector, SaveSector, CleanUpSector) is Phase 2.

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


__all__ = [
    "MAX_SIZE_OF_GALAXY",
    "NO_SRM_FIELD",
    "Location",
    "ObjectTypes",
    "SectorRecord",
    "XYCoord",
    "limbo",
    "nebula_of",
    "srm_owner_of",
]
