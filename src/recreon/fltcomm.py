"""Fleet commands.

Port of FLTCOMM.PAS. The mechanics are all in :mod:`recreon.fleet` -- deploy,
abort, transfer, refuel, move, run orders; this is the nine commands a player
drives them with, and the guards each one puts in front of the mechanic.

Two of those guards are the interesting part, because they are *warnings*
rather than refusals: aborting a fleet onto something you do not own, and
aborting one that would push a stack past 9999 ships, both ask "are you sure"
and then do it anyway. The original trusts the player and says what it will
cost. Drawing all of it is :mod:`recreon.ui.fleet`.
"""

from __future__ import annotations

from dataclasses import dataclass

from .datacnst import FUEL_PER_TON
from .environ import GameEnvironment
from .fleet import (
    abort_fleet,
    change_composition_of_fleet,
    deploy_fleet,
    destroy_fleet,
    refuel_fleet,
    set_fleet_destination,
)
from .galaxy import Location, XYCoord, limbo
from .intrface import balance_fleet
from .misc import fleet_cargo_space, fuel_capacity, no_ships, same_id
from .orders import (
    BAD_COMMAND_OER,
    BAD_DEST_OER,
    BAD_RESOURCE_OER,
    BAD_TRANSFER_OER,
    NO_OER,
    compile_orders,
    decompile_orders,
    dispose_orders,
    fleet_next_statement,
    get_fleet_code,
    initialize_orders,
    number_of_commands,
    set_fleet_code,
    set_fleet_next_statement,
)
from .primintr import (
    add_name,
    empire_name,
    enemy_mine,
    get_cargo,
    get_coord,
    get_fleet_fuel,
    get_fleets,
    get_name,
    get_object,
    get_probe,
    get_ships,
    get_status,
    get_trillum,
    launch_probe,
    my_lord,
    object_name,
    put_mine,
    scouted,
)
from .news import NewsTypes, add_news
from .types import (
    MAX_NO_OF_FLEETS,
    MAX_RESOURCES,
    NO_OF_PROBES_PER_EMPIRE,
    SHIP_TYPES,
    Empire,
    IDNumber,
    ObjectTypes,
    TechnologyTypes,
    empty_quadrant,
)
from .utils.int_utils import lesser_int
from .utils.pascal import trunc

T = TechnologyTypes

#: Most of any one ship type an object can hold. Aborting a fleet that would
#: push a stack past this loses the excess -- the command warns and proceeds.
MAX_SHIPS_PER_STACK = MAX_RESOURCES



# --- Choosing what to act on -------------------------------------------------


def ground_candidates(
    game: GameEnvironment,
    player: Empire,
    flt_id: IDNumber,
    player_only: bool,
    include_fleet: bool,
) -> list[tuple[IDNumber, str]]:
    """What a fleet can join, transfer with, or refuel from. ``GetGround``.

    Everything in the fleet's own sector: the other fleets there, then the
    world or base under it. Two flags shape the list, and the commands differ
    in what they pass:

    * ``player_only`` -- Refuel passes True, because you can only refuel from
      your own stores. Abort and Transfer pass False, which is how you hand
      ships to another empire.
    * ``include_fleet`` -- whether the fleet itself is a candidate. Refuel
      passes True, so a fleet can burn the trillum in its own hold.

    **Every** fleet must have been scouted to be offered, including your own
    -- the original's `Scouted(Player, Flt2)` has no exemption for them. In
    practice yours always are, because `set_up_turn` runs `scout_fleets`
    before the player does anything; but a fleet conjured outside a turn is
    invisible to these menus until something scouts it. The world or base
    under the fleet gets no such test.
    """
    xy = get_coord(game, flt_id)
    found: list[tuple[IDNumber, str]] = []

    fleets = set(get_fleets(game, xy))
    if not include_fleet:
        fleets.discard(flt_id.Index)

    for index in sorted(fleets):
        other = IDNumber(ObjectTypes.Flt, index)
        emp = get_status(game, other)
        if (not player_only or emp == player) and scouted(game, player, other):
            found.append((other, _ground_label(game, player, other, emp)))

    obj = get_object(game, xy)
    if obj.ObjTyp in (ObjectTypes.Pln, ObjectTypes.Base):
        emp = get_status(game, obj)
        if emp == player or not player_only:
            found.append((obj, _ground_label(game, player, obj, emp)))

    return found


def _ground_label(
    game: GameEnvironment, player: Empire, obj: IDNumber, emp: Empire
) -> str:
    name = object_name(game, player, obj, long_format=True)
    return f"{name}  ({empire_name(game, emp) or emp.name})"


def player_fleets(
    game: GameEnvironment, player: Empire
) -> list[tuple[IDNumber, str]]:
    """Every fleet the player has, for the commands to pick from."""
    return [
        (
            IDNumber(ObjectTypes.Flt, index),
            object_name(game, player, IDNumber(ObjectTypes.Flt, index)),
        )
        for index in sorted(game.GlobalSets.SetOfFleetsOf[player])
    ]


# --- Launch ------------------------------------------------------------------


def launch_fleet_command(
    game: GameEnvironment,
    player: Empire,
    fleet_name: str,
    launch_pt: IDNumber,
    ships: dict[T, int],
    cargo: dict[T, int],
    destination: XYCoord,
) -> tuple[IDNumber, str]:
    """Deploy a fleet. Port of ``LaunchFleetCommand`` past the distribution grid.

    Returns the new fleet and the acknowledgement. **A fleet with no ships is
    not launched at all** -- ``IF NOT NoShips(FltSh)`` -- so cargo alone
    cannot make one, and the command quietly does nothing.

    The name is attached to the fleet's ID rather than to a coordinate, so it
    follows the fleet as it moves.
    """
    if no_ships(ships):
        return empty_quadrant(), ""

    fleet_name = f"{fleet_name[:1].upper()}{fleet_name[1:]}"
    flt_id = deploy_fleet(game, player, launch_pt, ships, cargo, destination)

    if same_id(flt_id, empty_quadrant()):
        # The original prints this too rather than refusing earlier.
        return flt_id, "(ERROR: Discrepancy in SetOfActiveFleets.)"

    add_name(game, player, Location(XY=limbo(), ID=flt_id), fleet_name)
    return flt_id, f"{fleet_name} deployed, {my_lord(game, player)}."


def masked_amounts(
    amounts: dict[T, int], ground_status: Empire, player: Empire
) -> dict[T, str]:
    """The ground column of the distribution grid, as the player may see it.

    Another empire's holdings read ``????`` -- you can move things across but
    you cannot count what is already there. Your own show the numbers.
    """
    if ground_status == player:
        return {thing: str(amount) for thing, amount in amounts.items()}
    return {thing: "????" for thing in amounts}


def distribution_error(
    ground: IDNumber,
    ground_status: Empire,
    player: Empire,
    fleet_ships: dict[T, int],
    fleet_cargo: dict[T, int],
    ground_ships: dict[T, int],
    ground_cargo: dict[T, int],
) -> str | None:
    """Why a proposed split cannot be accepted, or None. ``InputNewDistribution``.

    Cargo needs transports to carry it, so a fleet can be loaded past what it
    can lift. Two asymmetries in the original, both kept:

    * **Only a fleet can be overloaded.** A world or base has unlimited room,
      so the ground side is checked only when it is another fleet.
    * **Only your own fleet errors.** Overload *another empire's* fleet and
      the original silently calls ``BalanceFleet`` on it instead -- their
      problem, and the transfer goes through.
    """
    if fleet_cargo_space(fleet_ships, fleet_cargo) < 0:
        return "There aren't enough transports in the fleet."

    if ground.ObjTyp == ObjectTypes.Flt and fleet_cargo_space(
        ground_ships, ground_cargo
    ) < 0:
        if ground_status != player:
            balance_fleet(ground_ships, ground_cargo)
            return None
        return "There aren't enough transports left in the fleet."

    return None


def report_transfer_to_other_empire(
    game: GameEnvironment,
    player: Empire,
    ground: IDNumber,
    ground_status: Empire,
    moved: dict[T, int],
) -> None:
    """Tell another empire what it has just been handed.

    ``moved`` is per resource, positive for what came *out of* the ground into
    the fleet. The original files nothing unless the player left something
    behind -- it scans for the first negative -- and then reports every
    resource, so a mixed transfer shows what went each way.
    """
    if ground_status == player:
        return
    if not any(amount < 0 for amount in moved.values()):
        return

    loc = Location(XY=limbo(), ID=ground)
    add_news(game, ground_status, NewsTypes.TrnsShp, loc, int(player))
    for thing, amount in moved.items():
        add_news(game, ground_status, NewsTypes.Trns2, loc, -amount, int(thing))


# --- Abort -------------------------------------------------------------------


def abort_warnings(
    game: GameEnvironment, player: Empire, flt_id: IDNumber, ground: IDNumber
) -> list[str]:
    """What the player is asked to confirm before aborting. Both are warnings.

    The original refuses neither -- it asks "(y/N)" and proceeds on yes:

    * **The target is not yours.** Aborting onto another empire's world hands
      them the ships. Deliberate: it is the only way to give ships away.
    * **The stack would overflow.** Any ship type whose combined total would
      pass 9999 means "some will be lost". The original scans from ``trn``
      *downwards* and reports on the first overflow it finds, so the warning
      is one message however many types overflow.
    """
    warnings: list[str] = []

    if get_status(game, ground) != player:
        name = object_name(game, player, ground, long_format=True)
        warnings.append(
            f"{my_lord(game, player)}, {name} is not part of "
            f"{empire_name(game, player)}."
        )

    ground_ships = get_ships(game, ground)
    fleet_ships = get_ships(game, flt_id)
    if any(
        ground_ships[ship] + fleet_ships[ship] > MAX_SHIPS_PER_STACK
        for ship in SHIP_TYPES
    ):
        warnings.append(
            f"{my_lord(game, player)}, an object cannot hold so many "
            "ships--some will be lost."
        )

    return warnings


def abort_fleet_command(
    game: GameEnvironment, player: Empire, flt_id: IDNumber, ground: IDNumber
) -> str:
    """Unload a fleet onto ``ground`` and disband it. ``AbortFleetCommand``.

    ``abort_fleet`` then ``destroy_fleet``, in that order -- the first moves
    everything across, the second removes the now-empty fleet. Keeping them
    separate is what lets the caller inspect the emptied fleet in between.
    """
    fleet_name = object_name(game, player, flt_id)
    ground_name = object_name(game, player, ground, long_format=True)
    joined = ground.ObjTyp == ObjectTypes.Flt

    abort_fleet(game, flt_id, ground, True)
    destroy_fleet(game, flt_id)

    verb = "joined with" if joined else "aborted to"
    return f"{fleet_name} has been {verb} {ground_name}, {my_lord(game, player)}."


# --- Destination -------------------------------------------------------------


def change_destination_command(
    game: GameEnvironment, player: Empire, flt_id: IDNumber, destination: XYCoord
) -> str:
    """Point a fleet somewhere else. ``ChangeDestinationCommand``."""
    set_fleet_destination(game, flt_id, destination)

    fleet_name = object_name(game, player, flt_id)
    where = get_name(
        game, player, Location(XY=destination, ID=empty_quadrant()), False
    )
    return f"New destination for {fleet_name}: {where}"


# --- Transfer ----------------------------------------------------------------


def transfer_fleet_command(
    game: GameEnvironment,
    player: Empire,
    flt_id: IDNumber,
    ground: IDNumber,
    fleet_ships: dict[T, int],
    fleet_cargo: dict[T, int],
    ground_ships: dict[T, int],
    ground_cargo: dict[T, int],
) -> str:
    """Apply a new split between fleet and ground. ``TransferFleetCommand``."""
    fleet_name = object_name(game, player, flt_id)
    ground_name = object_name(game, player, ground, long_format=True)

    change_composition_of_fleet(
        game, flt_id, ground, fleet_ships, fleet_cargo, ground_ships, ground_cargo
    )
    return f"Transfer from {fleet_name} to {ground_name} completed."


# --- Refuel ------------------------------------------------------------------


def max_trillum_to_use(
    game: GameEnvironment, flt_id: IDNumber, ground: IDNumber
) -> int:
    """Most trillum a refuel can usefully take. ``RefuelFleetCommand``'s sum.

    The lesser of what would fill the tanks and what is actually there. The
    ``+ 1`` is the original's: it rounds the requirement up so a fleet can
    always reach full rather than stopping a fraction short.
    """
    tons_on_ground = get_trillum(game, ground)
    max_fuel = fuel_capacity(get_ships(game, flt_id))
    tons_needed = trunc((max_fuel - get_fleet_fuel(game, flt_id)) / FUEL_PER_TON) + 1
    return lesser_int(tons_needed, tons_on_ground)


def trillum_to_use(requested: int, maximum: int) -> int:
    """What ``GetTrillumToUse`` accepts. Zero means "as much as possible"."""
    if requested == 0:
        return maximum
    if requested > maximum:
        raise ValueError(f"The maximum amount allowable is {maximum} tons")
    if requested < 0:
        raise ValueError("That is a most bizarre request")
    return requested


def refuel_fleet_command(
    game: GameEnvironment,
    player: Empire,
    flt_id: IDNumber,
    ground: IDNumber,
    trillum: int,
) -> None:
    """Burn trillum into fuel. ``RefuelFleetCommand``.

    ``ground`` may be the fleet itself, which is how a fleet refuels from the
    trillum in its own hold -- ``GetGround`` is called with ``IncludeFleet``
    set for exactly that.
    """
    refuel_fleet(game, flt_id, ground, trillum)


# --- Probe -------------------------------------------------------------------


def launch_probe_command(
    game: GameEnvironment, player: Empire, coord: XYCoord
) -> str:
    """Send a probe. Port of ``LaunchProbeCommand``.

    The number shown counts *up* as probes are used: ``GetProbe`` hands back
    the highest free slot and the message prints ``11 - PNum``, so the first
    launch is "Probe #1" and the tenth is "Probe #10".
    """
    number = get_probe(game, player)
    if number == 0:
        return (
            f"I'm sorry, {my_lord(game, player)} there are no more probes "
            "available."
        )

    launch_probe(game, player, number, coord)

    where = get_name(game, player, Location(XY=coord, ID=empty_quadrant()), True)
    return f"Probe #{NO_OF_PROBES_PER_EMPIRE + 1 - number} launched to {where}"


# --- Mine sweeping -----------------------------------------------------------


def mine_sweeper_command(
    game: GameEnvironment, player: Empire, flt_id: IDNumber
) -> str:
    """Clear the minefield in the fleet's own sector. ``MineSweeperCommand``.

    **Original bug (#60): this asks nothing of the fleet.** The same action as
    a compiled ``SRMS`` order needs a hundred starships aboard
    (``fleet.execute_sweep_com``); here a single fighter will do. Reproduced,
    with the asymmetry documented at both call sites -- do not "fix" one to
    match the other without reading the issue.

    The field's owner is told, unless it was the player's own field.
    """
    xy = get_coord(game, flt_id)
    owner = enemy_mine(game, xy)

    if owner == Empire.Indep:
        return f"No SRMs found, {my_lord(game, player)}."

    if owner != player:
        add_news(
            game,
            owner,
            NewsTypes.SRMClear,
            Location(XY=xy, ID=empty_quadrant()),
            int(player),
        )

    put_mine(game, xy, Empire.Indep)
    game.Galaxy.clr_mine_scout(xy)
    return f"Mine sweeping completed, {my_lord(game, player)}."


# --- Orders ------------------------------------------------------------------


def fleet_order_source(
    game: GameEnvironment, player: Empire, flt_id: IDNumber
) -> list[str]:
    """The fleet's current orders as editable text. ``DeCompileOrders``."""
    if fleet_next_statement(game, flt_id) == 0:
        return []
    return decompile_orders(game, player, get_fleet_code(game, flt_id))


def fleet_orders_command(
    game: GameEnvironment, player: Empire, flt_id: IDNumber, source: list[str]
) -> str:
    """Compile and install a fleet's orders. Port of ``FleetOrdersCommand``.

    Raises :class:`~recreon.orders.OrderError`-shaped information through the
    compiler's return -- the caller shows the message and keeps editing, as
    the original's ``REPEAT ... UNTIL Ok OR Abort`` does.

    **The resume point is preserved**, so editing does not restart a route the
    fleet is already half-way through. An empty list cancels the orders
    outright.

    **Original bug (#59), deviated from.** The original writes the old resume
    point back without checking it against the new list, so shortening the
    orders below the fleet's current position leaves it indexing past the end
    -- undefined in Pascal, an ``IndexError`` here. The position is clamped to
    the last command instead: defined, and it keeps what the resume point is
    *for*. See the issue for the alternative.
    """
    com = fleet_next_statement(game, flt_id) or 1

    code = initialize_orders()
    error, line_no = compile_orders(game, player, source, code)
    if error != NO_OER:
        raise OrderCompileError(error, line_no)

    fleet_name = object_name(game, player, flt_id, long_format=True)

    if number_of_commands(code) == 0:
        dispose_orders(code)
        set_fleet_next_statement(game, flt_id, 0)
        set_fleet_code(game, flt_id, code)
        return f"All orders to {fleet_name} cancelled, {my_lord(game, player)}."

    set_fleet_next_statement(game, flt_id, min(com, number_of_commands(code)))
    set_fleet_code(game, flt_id, code)
    return f"Orders to {fleet_name} completed, {my_lord(game, player)}."


class OrderCompileError(Exception):
    """A compile failure, carrying the line the original names in its window."""

    #: ``SourceError``'s messages, keyed by the OER code the compiler returns.
    MESSAGES = {
        BAD_COMMAND_OER: "Unknown command in line",
        BAD_DEST_OER: "Unknown destination in line",
        BAD_RESOURCE_OER: "Unknown resource in line",
        BAD_TRANSFER_OER: "Bad transfer value in line",
    }

    def __init__(self, error: int, line_no: int) -> None:
        self.error = error
        self.line_no = line_no
        text = self.MESSAGES.get(error, "Error in line")
        super().__init__(f"{text} {line_no}")


def fleet_cancel_orders_command(
    game: GameEnvironment, player: Empire, flt_id: IDNumber
) -> str:
    """Throw a fleet's orders away. ``FleetCancelOrdersCommand``."""
    dispose_orders(get_fleet_code(game, flt_id))
    set_fleet_next_statement(game, flt_id, 0)

    fleet_name = object_name(game, player, flt_id, long_format=True)
    return f"All orders to {fleet_name} cancelled, {my_lord(game, player)}."


__all__ = [
    "MAX_SHIPS_PER_STACK",
    "OrderCompileError",
    "abort_fleet_command",
    "abort_warnings",
    "change_destination_command",
    "distribution_error",
    "fleet_cancel_orders_command",
    "fleet_order_source",
    "fleet_orders_command",
    "ground_candidates",
    "launch_fleet_command",
    "launch_probe_command",
    "masked_amounts",
    "max_trillum_to_use",
    "mine_sweeper_command",
    "player_fleets",
    "refuel_fleet_command",
    "report_transfer_to_other_empire",
    "transfer_fleet_command",
    "trillum_to_use",
]
