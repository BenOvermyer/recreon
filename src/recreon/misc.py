"""Utility calculations.

Port of MISC.PAS.

``InGalaxy`` lives on :class:`~recreon.galaxy.Galaxy` instead of here, since it
needs the galaxy size that the original read from a global.
"""

from __future__ import annotations

from .datacnst import (
    K1,
    K2,
    K3,
    CargoSpace,
    FuelCap,
    FuelCons,
    MPower,
    TechAdj,
    TrnAdj,
)
from .galaxy import Location, XYCoord
from .types import (
    CARGO_TYPES,
    MAX_INDUS_INDEX,
    MAX_RESOURCES,
    SHIP_TYPES,
    IDNumber,
    IndusTypes,
    TechLevel,
    TechnologyTypes,
    tech_range,
)
from .utils.int_utils import greater_int
from .utils.pascal import pascal_round, trunc
from .utils.real1 import expnt

T = TechnologyTypes


def thg_lmt(x: float) -> int:
    """Clamp a resource quantity to 0..MaxResources, truncating."""
    if x > MAX_RESOURCES:
        return MAX_RESOURCES
    if x < 0:
        return 0
    return trunc(x)


def distance(first: XYCoord, second: XYCoord) -> int:
    """Sectors between two points -- Chebyshev distance.

    Diagonal movement costs the same as orthogonal, so this is the greater of
    the two axis deltas, not a Euclidean or Manhattan distance.
    """
    return greater_int(abs(first.x - second.x), abs(first.y - second.y))


def same_xy(first: XYCoord, second: XYCoord) -> bool:
    return first == second


def same_id(first: IDNumber, second: IDNumber) -> bool:
    """Whether two IDs point at the same object.

    The original compares the two-byte record as a single Integer; here the
    dataclass compares field by field, which is the same test.
    """
    return first == second


def same_location(first: Location, second: Location) -> bool:
    """Whether two locations match in *both* object and coordinate.

    The original compares all four bytes at once, so a location naming an
    object at Limbo does not match the same object at a real coordinate.
    Name lookup depends on that: callers normalise a Location before
    comparing, rather than the comparison being forgiving.
    """
    return first == second


def no_ships(ships: dict[T, int]) -> bool:
    """Whether a ship distribution is entirely empty."""
    return all(ships[ship] == 0 for ship in SHIP_TYPES)


def fuel_capacity(ships: dict[T, int]) -> float:
    """Maximum fuel loadable onto the given ship distribution.

    Starts the accumulator at 1, not 0, exactly as the original does -- every
    fleet has one unit of slack capacity. Preserved deliberately.
    """
    total = 1.0
    for ship in SHIP_TYPES:
        total += (FuelCap[ship] / 100) * ships[ship]
    return total


def fuel_consumption(ships: dict[T, int], cargo: dict[T, int]) -> float:
    """Units of fuel the fleet burns per sector moved.

    Also starts at 1, matching the original.
    """
    total = 1.0
    for ship in SHIP_TYPES:
        total += (FuelCons[ship] / 1000) * ships[ship]
    for thing in CARGO_TYPES:
        total += (FuelCons[thing] / 1000) * cargo[thing]
    return total


def fleet_cargo_space(ships: dict[T, int], cargo: dict[T, int]) -> int:
    """Free cargo space in the fleet, in units of transports.

    Returns a negative number when the fleet is overloaded; a fleet need not
    be balanced.
    """
    free_space = ships[T.trn] + ships[T.jtn] * TrnAdj[T.jtn]

    for thing in CARGO_TYPES:
        free_space -= cargo[thing] / CargoSpace[thing]

    return pascal_round(free_space)


def ship_yard_ind(indus: dict[IndusTypes, int]) -> IndusTypes:
    """Which shipyard industry dominates on this world.

    Ties resolve to the lowest-ordinal industry, since the original compares
    with a strict ``>``.
    """
    best = IndusTypes.SYGInd
    greatest = indus[IndusTypes.SYGInd]
    for ind in (
        IndusTypes.SYGInd,
        IndusTypes.SYJInd,
        IndusTypes.SYSInd,
        IndusTypes.SYTInd,
    ):
        if indus[ind] > greatest:
            best = ind
            greatest = indus[ind]
    return best


def total_prod(pop: int, tech: TechLevel) -> int:
    """Total Industrial Production (TIP) of a world.

    ``K1 * (Pop + K2) ** K3 * TechAdj[Tech] / 100``, clamped to 0..999.
    """
    if pop <= 0:
        pop = 1
    value = K1 * expnt(pop + K2, K3) * TechAdj[tech] / 100
    if value > MAX_INDUS_INDEX:
        value = MAX_INDUS_INDEX
    elif value < 0:
        value = 0
    return pascal_round(value)


def add_things(
    ships: dict[T, int],
    cargo: dict[T, int],
    ships2: dict[T, int],
    cargo2: dict[T, int],
) -> None:
    """Add ships2/cargo2 into ships/cargo in place, clamped."""
    for ship in SHIP_TYPES:
        ships[ship] = thg_lmt(ships[ship] + ships2[ship])
    for thing in CARGO_TYPES:
        cargo[thing] = thg_lmt(cargo[thing] + cargo2[thing])


def sub_things(
    ships: dict[T, int],
    cargo: dict[T, int],
    ships2: dict[T, int],
    cargo2: dict[T, int],
) -> None:
    """Subtract ships2/cargo2 from ships/cargo in place, clamped at 0."""
    for ship in SHIP_TYPES:
        ships[ship] = thg_lmt(ships[ship] - ships2[ship])
    for thing in CARGO_TYPES:
        cargo[thing] = thg_lmt(cargo[thing] - cargo2[thing])


def move_things(no_of_thg: int, source: int, dest: int) -> tuple[int, int]:
    """Move up to ``no_of_thg`` units from source to dest.

    Returns the new ``(source, dest)`` pair -- the original takes both by
    reference, which Python cannot do for ints. Moves everything available
    when the source is short.
    """
    if source > no_of_thg:
        return thg_lmt(source - no_of_thg), thg_lmt(dest + no_of_thg)
    return 0, thg_lmt(dest + source)


def military_power(ships: dict[T, int], defns: dict[T, int]) -> int:
    """Combined strength of a force of ships and defenses. See MPower."""
    total = 0
    for res in tech_range(T.LAM, T.ion):
        total += defns[res] * MPower[res]
    for res in SHIP_TYPES:
        total += ships[res] * MPower[res]
    return total


def hi_lo(ind: int) -> str:
    """Coarse label for a 0..100 index, as shown in the status windows."""
    if 0 <= ind <= 10:
        return "no "
    if 11 <= ind <= 25:
        return "Lo-"
    if 26 <= ind <= 50:
        return "Lo+"
    if 51 <= ind <= 75:
        return "Hi-"
    if 76 <= ind <= 100:
        return "Hi+"
    return "---"


def yes_no(ind: int) -> str:
    """Coarse label for a resource quantity, in thousands."""
    if ind == 0:
        return "   no"
    if 1 <= ind <= 500:
        return " yes-"
    if 9501 <= ind <= 9999:
        return " yes+"
    if 501 <= ind <= 9500:
        # Buckets are 1000 wide and centred on the thousands: 501..1500 is
        # yes1, 1501..2500 is yes2, and so on.
        return f" yes{(ind + 499) // 1000}"
    return " ----"
