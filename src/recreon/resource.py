"""Cargo capacity and combat casualties.

Port of RESOURCE.PAS.

Note this unit carries its *own* cargo-size and transport-capacity tables,
which disagree with the CargoSpace/TrnAdj tables in DATACNST.PAS that
MISC.PAS uses: here a transport holds 100 units of space and a megaton of
supplies costs 50, where MISC.PAS works in whole transports. Both are
transcribed as they stand -- combat and cargo transfer genuinely use
different scales in the original, and reconciling them would change
behaviour.
"""

from __future__ import annotations

from .types import CARGO_TYPES, SHIP_TYPES, TechnologyTypes, tech_range

T = TechnologyTypes

#: Space one unit of each cargo occupies, in this unit's own scale.
CargoSize: dict[T, int] = dict(
    zip(CARGO_TYPES, (2, 2, 1, 10, 30, 50, 1), strict=True)
)

#: Cargo space each ship type provides, in the same scale.
TransCapacity: dict[T, int] = dict(
    zip(SHIP_TYPES, (0, 0, 0, 20, 0, 0, 100), strict=True)
)

#: Order cargo is jettisoned in when a fleet loses its transports.
CargoPriority: tuple[T, ...] = (T.che, T.sup, T.met, T.men, T.nnj, T.tri, T.amb)


def cargo_space_avail(resources: dict[T, int]) -> int:
    """Cargo space left in a force. Negative when overloaded."""
    free_space = (
        resources[T.trn] * TransCapacity[T.trn]
        + resources[T.jtn] * TransCapacity[T.jtn]
    )
    for cargo in CARGO_TYPES:
        free_space -= resources[cargo] * CargoSize[cargo]
    return free_space


def balance_resources(resources: dict[T, int]) -> None:
    """Jettison cargo until it fits, in :data:`CargoPriority` order.

    Each cargo type is dumped entirely; if that overshoots, the last one is
    partly refilled to exactly fill the space freed.
    """
    to_remove = 0
    thing = CargoPriority[to_remove]
    space_left = cargo_space_avail(resources)

    while space_left < 0:
        resources[thing] = 0
        new_space_left = cargo_space_avail(resources)
        if new_space_left < 0:
            space_left = new_space_left
            to_remove += 1
            if to_remove >= len(CargoPriority):
                # Everything jettisoned and still overloaded: nothing more to
                # give. The original would run off the end of its array here.
                return
            thing = CargoPriority[to_remove]
        else:
            resources[thing] = new_space_left // CargoSize[thing]
            space_left = 0


def subtract_casualties(
    resources: dict[T, int],
    casualties: dict[T, int],
    destroy_cargo_in_trans: bool,
) -> bool:
    """Apply combat losses. Returns whether any ships remain.

    With ``destroy_cargo_in_trans`` set, cargo goes down with the transports
    that were carrying it.

    Assumes casualties never exceed what is present, as the original does.
    """
    no_ships_left = True

    for res in tech_range(T.LAM, T.tri):
        resources[res] -= casualties.get(res, 0)
        if res in SHIP_TYPES and resources[res] > 0:
            no_ships_left = False

    if destroy_cargo_in_trans:
        balance_resources(resources)

    return no_ships_left
