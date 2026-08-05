"""Fleets: deployment, composition, movement and standing orders.

Port of FLEET.PAS.

Fuel is the spine of this module. A fleet burns ``FuelConsumption`` once per
year that it moves -- not per sector, so distance is free once the fleet is
under way -- refuels itself out of any trillum it is carrying, and goes
inactive where it stands when both run out. Every
transfer of ships between a fleet and the ground moves fuel too, in proportion
to the fuel *capacity* that moved -- which is why ``DeployFleet`` reverses its
arguments when launching from another fleet, and why so little here can be
reordered safely.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .datacnst import FUEL_PER_TON, CargoSpace, FltMovementRate, ProtecNeeded
from .galaxy import Location, XYCoord, limbo
from .intrface import balance_fleet, passing_through_fortress, passing_through_gate
from .misc import (
    add_things,
    distance,
    fleet_cargo_space,
    fuel_capacity,
    fuel_consumption,
    no_ships,
    same_id,
    same_xy,
    sub_things,
    thg_lmt,
)
from .news import NewsTypes, add_news, get_news_list
from .orders import (
    CommandTypes,
    dispose_orders,
    fleet_next_statement,
    get_command_record,
    get_fleet_code,
    number_of_commands,
    set_fleet_code,
    set_fleet_next_statement,
)
from .primintr import (
    add_name,
    delete_name,
    enemy_mine,
    get_cargo,
    get_coord,
    get_fleet_fuel,
    get_fleet_status,
    get_fleets,
    get_gate_type,
    get_nebula,
    get_object,
    get_ships,
    get_status,
    get_trillum,
    get_warp_link_freq,
    location2index,
    object_name,
    put_cargo,
    put_mine,
    put_ships,
    put_trillum,
    set_fleet_fuel,
    set_fleet_status,
    type_of_fleet,
)
from .types import (
    CARGO_TYPES,
    MAX_NO_OF_FLEETS,
    MAX_NO_OF_STARGATES,
    MAX_RESOURCES,
    SHIP_TYPES,
    Empire,
    FleetStatus,
    FleetTypes,
    IDNumber,
    NebulaTypes,
    ObjectTypes,
    TechnologyTypes,
    empty_quadrant,
    tech_range,
)
from .utils.int_utils import greater_int, lesser_int, rnd, sgn
from .utils.pascal import pascal_round

if TYPE_CHECKING:
    from .environ import GameEnvironment

T = TechnologyTypes

#: Ship types a minefield damages: everything that jumps. ``hkr..jtn``.
MINEABLE_SHIPS = tech_range(T.hkr, T.jtn)

#: Fleet types that travel by jump drive, and so trip minefields and are
#: stopped by enemy disrupters.
JUMP_FLEET_TYPES = (FleetTypes.JumpFleet, FleetTypes.HKFleet)

#: Fleet types that travel by warp drive, and so ride a friendly disrupter's
#: field at jump speed instead.
WARP_FLEET_TYPES = (FleetTypes.Standard, FleetTypes.Penetrator, FleetTypes.AdvWrpFleet)


# --- Naming ------------------------------------------------------------------


def fleet_name_destruction(
    game: GameEnvironment, emp: Empire, flt_id: IDNumber
) -> Location:
    """Re-point a destroyed fleet's name, and its news, at a ``DestFlt`` ID.

    The slot the fleet occupied is about to be reused, so anything still
    referring to it by index would come to mean a different fleet. Renaming
    it out to ``DestFlt`` keeps this year's news readable without pinning the
    slot. Returns the new location, which callers pass to ``AddNews``.
    """
    new_loc = Location(limbo(), flt_id)
    if flt_id.ObjTyp != ObjectTypes.Flt:
        return new_loc

    name = location2index(game, emp, new_loc)
    if name is None:
        return new_loc

    flt_name = name.Name
    delete_name(game, emp, flt_name)
    new_loc = Location(limbo(), IDNumber(ObjectTypes.DestFlt, flt_id.Index))
    add_name(game, emp, new_loc, flt_name)

    for news in get_news_list(game, emp):
        if same_id(news.Loc1.ID, flt_id):
            news.Loc1 = new_loc

    return new_loc


# --- Position and destination ------------------------------------------------


def get_fleet_destination(game: GameEnvironment, flt_id: IDNumber) -> XYCoord:
    """Where a fleet -- or a starbase under tow -- is headed."""
    if flt_id.ObjTyp == ObjectTypes.Flt:
        return game.Universe.Fleet[flt_id.Index].Dest
    if flt_id.ObjTyp == ObjectTypes.Base:
        return game.Universe.Starbase[flt_id.Index].Dest
    return limbo()


def set_fleet_destination(
    game: GameEnvironment, flt_id: IDNumber, new_dest: XYCoord
) -> None:
    """Set a destination, and the status that follows from it.

    A fleet ordered to where it already is becomes FReady immediately, which
    is what lets ``UpdateFleet`` run its next order the same year.
    """
    if flt_id.ObjTyp == ObjectTypes.Flt:
        game.Universe.Fleet[flt_id.Index].Dest = new_dest
    elif flt_id.ObjTyp == ObjectTypes.Base:
        game.Universe.Starbase[flt_id.Index].Dest = new_dest

    flt_xy = get_coord(game, flt_id)
    if same_xy(flt_xy, new_dest):
        set_fleet_status(game, flt_id, FleetStatus.FReady)
    else:
        set_fleet_status(game, flt_id, FleetStatus.FInTrans)


def no_other_fleets_in_sect(
    game: GameEnvironment, flt_id: IDNumber, emp: Empire, xy: XYCoord
) -> bool:
    """Whether ``emp`` would still hold ``xy`` with ``flt_id`` discounted."""
    fleets = get_fleets(game, xy) & game.GlobalSets.SetOfFleetsOf[emp]
    return not (fleets - {flt_id.Index})


def move_fleet(game: GameEnvironment, flt_id: IDNumber, new_coord: XYCoord) -> None:
    """Put a fleet in a new sector and keep the per-sector presence flags right.

    The sector's ``Flts`` set is what the map draws from, so the old sector
    has to be cleared -- but only when this was the empire's last fleet there.
    """
    fleet = game.Universe.Fleet[flt_id.Index]
    old_coord = fleet.XY
    fleet.XY = new_coord

    if no_other_fleets_in_sect(game, flt_id, fleet.Emp, old_coord):
        game.Galaxy.sector(old_coord).Flts.discard(fleet.Emp)

    game.Galaxy.sector(new_coord).Flts.add(fleet.Emp)


def get_new_pos(game: GameEnvironment, pos: XYCoord, dest: XYCoord) -> XYCoord:
    """One step from ``pos`` toward ``dest``, or Limbo if a dense nebula blocks it.

    Movement is Chebyshev, so this steps both axes at once and a diagonal
    costs no more than an orthogonal move. Limbo doubles as the "blocked"
    signal, which is why every caller tests for it before moving.
    """
    new_pos = XYCoord(pos.x + sgn(dest.x - pos.x), pos.y + sgn(dest.y - pos.y))
    if get_nebula(game, new_pos) == NebulaTypes.DenseNebula:
        return limbo()
    return new_pos


# --- Creation and destruction ------------------------------------------------


def get_next_fleet(game: GameEnvironment, new_emp: Empire) -> IDNumber:
    """Claim a free fleet slot for ``new_emp``, or EmptyQuadrant if full.

    Counts down from the top, as the original does, so slot numbers match
    when comparing runs side by side.
    """
    next_slot = 0
    i = MAX_NO_OF_FLEETS
    while i > 0 and next_slot == 0:
        if i not in game.GlobalSets.SetOfActiveFleets:
            next_slot = i
        i -= 1

    if next_slot == 0:
        return empty_quadrant()

    from .datastrc import FleetRecord

    flt_id = IDNumber(ObjectTypes.Flt, next_slot)
    game.Universe.Fleet[next_slot] = FleetRecord(Emp=new_emp, NextOrder=0)
    game.GlobalSets.SetOfFleetsOf[new_emp].add(next_slot)
    game.GlobalSets.SetOfActiveFleets.add(next_slot)
    return flt_id


def destroy_fleet(game: GameEnvironment, flt_id: IDNumber) -> None:
    """Remove a fleet from the game. Its cargo is *not* recovered -- call
    :func:`abort_fleet` first if it should be."""
    if flt_id.Index not in game.GlobalSets.SetOfActiveFleets:
        return

    fleet = game.Universe.Fleet[flt_id.Index]
    flt_pos = fleet.XY
    flt_sta = fleet.Emp

    if fleet_next_statement(game, flt_id) > 0:
        dispose_orders(get_fleet_code(game, flt_id))

    game.Universe.Fleet[flt_id.Index] = None

    game.GlobalSets.SetOfActiveFleets.discard(flt_id.Index)
    game.GlobalSets.SetOfFleetsOf[flt_sta].discard(flt_id.Index)

    if no_other_fleets_in_sect(game, flt_id, flt_sta, flt_pos):
        game.Galaxy.sector(flt_pos).Flts.discard(flt_sta)


def abort_fleet(
    game: GameEnvironment, flt1: IDNumber, ground_id: IDNumber, report: bool
) -> None:
    """Unload a fleet entirely onto ``ground_id``.

    Leftover fuel comes back as trillum when unloading onto a world or base,
    but transfers as fuel when the receiver is another fleet -- reconverting
    it would lose the fraction under a ton.

    Does *not* remove the fleet; the original requires ``DestroyFleet`` to
    follow, and the two are separate so the caller can inspect the empty
    fleet in between.
    """
    fuel_left = get_fleet_fuel(game, flt1)
    fleet = game.Universe.Fleet[flt1.Index]
    sh2 = dict(fleet.Ships)
    cr2 = dict(fleet.Cargo)

    if ground_id.ObjTyp != ObjectTypes.Flt:
        cr2[T.tri] = thg_lmt(cr2[T.tri] + thg_lmt(fuel_left / FUEL_PER_TON))
    else:
        set_fleet_fuel(game, ground_id, get_fleet_fuel(game, ground_id) + fuel_left)

    other_emp = get_status(game, ground_id)
    emp = get_status(game, flt1)
    loc = Location(limbo(), ground_id)

    if other_emp != emp and report:
        # Unloading onto someone else's world is a gift, and they are told
        # what they received down to the item.
        add_news(game, other_emp, NewsTypes.TrnsShp, loc, int(emp), 0, 0)
        for res in SHIP_TYPES:
            if sh2[res] != 0:
                add_news(game, other_emp, NewsTypes.Trns2, loc, sh2[res], int(res), 0)
        for res in CARGO_TYPES:
            if cr2[res] != 0:
                add_news(game, other_emp, NewsTypes.Trns2, loc, cr2[res], int(res), 0)

    sh = get_ships(game, ground_id)
    cr = get_cargo(game, ground_id)
    add_things(sh, cr, sh2, cr2)
    put_ships(game, ground_id, sh)
    put_cargo(game, ground_id, cr)

    delete_name(game, emp, object_name(game, emp, flt1))


def change_composition_of_fleet(
    game: GameEnvironment,
    flt_id: IDNumber,
    ground_id: IDNumber,
    new_f_sh: dict[T, int],
    new_f_cr: dict[T, int],
    new_g_sh: dict[T, int],
    new_g_cr: dict[T, int],
) -> None:
    """Write a new split of ships and cargo between a fleet and the ground,
    moving fuel to match.

    Either side emptying of ships aborts that side instead: a fleet with no
    hulls cannot exist, so it unloads into the other and is destroyed.

    Fuel follows differently depending on what the ground is. Between two
    fleets it moves in proportion to the fuel capacity that moved, capped at
    what the donor has. Against a world or base it is bought and sold as
    trillum at ``FUEL_PER_TON``, and the fleet ends up topped up to its new
    capacity if the ground has the trillum to do it.
    """
    old_f_sh = get_ships(game, flt_id)
    # The original also reads the ground's old ships to compute its old and
    # new fuel capacity, then never uses either -- only the fleet's capacities
    # drive the transfer. Dropped rather than transcribed.

    if no_ships(new_f_sh):
        abort_fleet(game, flt_id, ground_id, True)
        destroy_fleet(game, flt_id)
        return

    if no_ships(new_g_sh) and ground_id.ObjTyp == ObjectTypes.Flt:
        abort_fleet(game, ground_id, flt_id, True)
        destroy_fleet(game, ground_id)
        return

    if ground_id.ObjTyp == ObjectTypes.Flt:
        flt_fuel = get_fleet_fuel(game, flt_id)
        grd_fuel = get_fleet_fuel(game, ground_id)

        old_fu_cap = fuel_capacity(old_f_sh)
        new_fu_cap = fuel_capacity(new_f_sh)

        fuel_change = (flt_fuel * new_fu_cap / old_fu_cap) - flt_fuel
        if fuel_change > grd_fuel:
            fuel_change = grd_fuel

        set_fleet_fuel(game, flt_id, flt_fuel + fuel_change)
        set_fleet_fuel(game, ground_id, grd_fuel - fuel_change)

        put_ships(game, flt_id, new_f_sh)
        put_cargo(game, flt_id, new_f_cr)
        put_ships(game, ground_id, new_g_sh)
        put_cargo(game, ground_id, new_g_cr)
        return

    flt_fuel = get_fleet_fuel(game, flt_id)
    new_fu_cap = fuel_capacity(new_f_sh)

    put_ships(game, ground_id, new_g_sh)
    put_cargo(game, ground_id, new_g_cr)

    fuel_change = new_fu_cap - flt_fuel
    # Positive when fuel moves from ground to fleet, negative when the fleet
    # is shedding hulls and selling its fuel back as trillum.
    tons_needed = pascal_round(fuel_change / FUEL_PER_TON)

    tons_on_ground = get_trillum(game, ground_id)
    if tons_on_ground >= tons_needed:
        put_trillum(game, ground_id, thg_lmt(tons_on_ground - tons_needed))
    else:
        put_trillum(game, ground_id, 0)
        fuel_change = 1.0 * tons_on_ground * FUEL_PER_TON

    set_fleet_fuel(game, flt_id, flt_fuel + fuel_change)

    put_ships(game, flt_id, new_f_sh)
    put_cargo(game, flt_id, new_f_cr)


def deploy_fleet(
    game: GameEnvironment,
    emp: Empire,
    launch_id: IDNumber,
    sh: dict[T, int],
    cr: dict[T, int],
    dest_xy: XYCoord,
) -> IDNumber:
    """Launch a new fleet out of ``launch_id`` and send it to ``dest_xy``.

    Returns the new fleet's ID, or EmptyQuadrant when no slot is free.
    """
    flt_id = get_next_fleet(game, emp)
    if flt_id.ObjTyp == ObjectTypes.Void:
        return flt_id

    launch_xy = get_coord(game, launch_id)
    fleet = game.Universe.Fleet[flt_id.Index]
    fleet.XY = limbo()
    fleet.ScoutedBy = {emp}
    fleet.KnownBy = {emp}
    fleet.Ships = {ship: 0 for ship in SHIP_TYPES}
    fleet.Cargo = {thing: 0 for thing in CARGO_TYPES}

    set_fleet_fuel(game, flt_id, 0)
    game.GlobalSets.SetOfActiveFleets.add(flt_id.Index)
    move_fleet(game, flt_id, launch_xy)
    set_fleet_destination(game, flt_id, dest_xy)

    lau_sh = get_ships(game, launch_id)
    lau_cr = get_cargo(game, launch_id)
    sub_things(lau_sh, lau_cr, sh, cr)

    # Argument order is reversed when launching from another fleet so that
    # the fuel transfer runs in the right direction: the side named first is
    # the one whose fuel capacity drives the split.
    if launch_id.ObjTyp == ObjectTypes.Flt:
        change_composition_of_fleet(game, launch_id, flt_id, lau_sh, lau_cr, sh, cr)
    else:
        change_composition_of_fleet(game, flt_id, launch_id, sh, cr, lau_sh, lau_cr)

    if flt_id.Index not in game.GlobalSets.SetOfActiveFleets:
        # ``change_composition_of_fleet`` destroys a fleet that ends up with no
        # hulls, which happens whenever ``sh`` was empty to begin with -- the
        # AI asking a fighter-only world for a jump fleet is the live case.
        # The original reads the freed record on the next line; returning the
        # "could not deploy" signal callers already test for is the defined
        # reading of that. See issue #30.
        return empty_quadrant()

    if get_fleet_fuel(game, flt_id) == 0:
        # A fleet launched with no fuel at all would be stranded on the spot
        # and impossible to recover; the original hands it a token 10.
        set_fleet_fuel(game, flt_id, 10)

    return flt_id


def refuel_fleet(
    game: GameEnvironment, flt_id: IDNumber, ground_id: IDNumber, trillum: int
) -> None:
    """Burn ``trillum`` tons off ``ground_id`` to refuel ``flt_id``.

    Assumes the trillum is there -- the caller checks. Fuel over the fleet's
    capacity is lost, but the trillum is spent either way.
    """
    flt_sh = get_ships(game, flt_id)
    flt_cr = get_cargo(game, flt_id)
    flt_fuel = get_fleet_fuel(game, flt_id)
    max_fuel = fuel_capacity(flt_sh)
    tons_on_ground = get_trillum(game, ground_id)

    tons_on_ground -= trillum
    flt_fuel += 1.0 * trillum * FUEL_PER_TON
    if flt_fuel > max_fuel:
        flt_fuel = max_fuel

    put_trillum(game, ground_id, tons_on_ground)
    set_fleet_fuel(game, flt_id, flt_fuel)

    if flt_fuel > fuel_consumption(flt_sh, flt_cr):
        # It can move again, so lift FInactive.
        if same_xy(get_coord(game, flt_id), get_fleet_destination(game, flt_id)):
            set_fleet_status(game, flt_id, FleetStatus.FReady)
        else:
            set_fleet_status(game, flt_id, FleetStatus.FInTrans)


# --- Order execution ---------------------------------------------------------


def execute_dest_com(game: GameEnvironment, flt_id: IDNumber, loc: Location) -> None:
    """A DEST order aimed at an object resolves to wherever that object is
    *now*, so a fleet ordered to follow a starbase tracks it."""
    xy = loc.XY
    if same_xy(xy, limbo()):
        xy = get_coord(game, loc.ID)
    set_fleet_destination(game, flt_id, xy)


def execute_sweep_com(game: GameEnvironment, flt_id: IDNumber) -> None:
    """An SRMS order: clear the minefield in the fleet's own sector.

    Needs 100 starships aboard. Sweeping is unconditional once they are
    there -- it is not a combat -- and the field's owner is told it happened.
    """
    xy = get_coord(game, flt_id)

    srm_owner = enemy_mine(game, xy)
    player = get_status(game, flt_id)
    srm_loc = Location(xy, empty_quadrant())
    fleet_loc = Location(limbo(), flt_id)
    ships_in_fleet = get_ships(game, flt_id)

    if ships_in_fleet[T.ssp] < 100:
        add_news(game, player, NewsTypes.OrdersNoSSP, fleet_loc, 0, 0, 0)
        return

    if srm_owner == Empire.Indep:
        add_news(game, player, NewsTypes.OrdersNoSRMs, fleet_loc, 0, 0, 0)
        return

    if srm_owner != player:
        add_news(game, srm_owner, NewsTypes.SRMClear, srm_loc, int(player), 0, 0)
    put_mine(game, xy, Empire.Indep)
    game.Galaxy.clr_mine_scout(xy)
    add_news(game, player, NewsTypes.OrdersSRMClear, fleet_loc, 0, 0, 0)


def get_resource(
    ships: dict[T, int], cargo: dict[T, int], res: TechnologyTypes
) -> int:
    """Read a quantity from whichever of the two arrays holds it.

    ``trn`` is the last ship type, so anything past it is cargo.
    """
    return cargo[res] if res > T.trn else ships[res]


def put_resource(
    ships: dict[T, int], cargo: dict[T, int], res: TechnologyTypes, val: int
) -> None:
    if res > T.trn:
        cargo[res] = val
    else:
        ships[res] = val


def execute_trans_com(
    game: GameEnvironment, flt_id: IDNumber, res: TechnologyTypes, trans: int
) -> None:
    """A TRAN order: move ``trans`` units between fleet and ground.

    Positive picks up, negative drops off. Needs a world or starbase of the
    same empire in the fleet's sector; anything else is a silent no-op, as in
    the original. Requests are clipped to what is available, to what the
    receiver can hold, and -- when picking up cargo -- to the fleet's free
    transport space.
    """
    flt_xy = get_coord(game, flt_id)
    ground_id = get_object(game, flt_xy)
    if (
        same_id(ground_id, empty_quadrant())
        or get_status(game, ground_id) != get_status(game, flt_id)
        or ground_id.ObjTyp not in (ObjectTypes.Pln, ObjectTypes.Base)
    ):
        return

    grn_sh = get_ships(game, ground_id)
    grn_cr = get_cargo(game, ground_id)
    flt_sh = get_ships(game, flt_id)
    flt_cr = get_cargo(game, flt_id)

    flt_res = get_resource(flt_sh, flt_cr, res)
    grn_res = get_resource(grn_sh, grn_cr, res)

    if trans > 0:
        trans = lesser_int(trans, grn_res)
        trans = lesser_int(trans, MAX_RESOURCES - flt_res)
        if res in CARGO_TYPES:
            trans = lesser_int(
                fleet_cargo_space(flt_sh, flt_cr) * CargoSpace[res], trans
            )
    else:
        trans = -trans
        trans = lesser_int(trans, flt_res)
        trans = lesser_int(trans, MAX_RESOURCES - grn_res)
        trans = -trans

    put_resource(flt_sh, flt_cr, res, flt_res + trans)
    put_resource(grn_sh, grn_cr, res, grn_res - trans)

    balance_fleet(flt_sh, flt_cr)
    change_composition_of_fleet(game, flt_id, ground_id, flt_sh, flt_cr, grn_sh, grn_cr)


def execute_fleet_orders(game: GameEnvironment, emp: Empire, flt_id: IDNumber) -> None:
    """Run the fleet's standing orders from where it left off.

    Runs straight through until it hits a DEST or WAIT -- both of which end
    the fleet's year -- or runs off the end of the list, or the fleet ceases
    to exist mid-order (a transfer can empty and abort it).

    REPE jumps back to the first order, but only once per call: ``IgnoreRepeat``
    is what stops an order list of nothing but REPE from spinning forever.
    """
    com = fleet_next_statement(game, flt_id)
    if com == 0:
        return

    ignore_repeat = False
    fleet_destroyed = False
    code = get_fleet_code(game, flt_id)
    last_command = number_of_commands(code)

    while True:
        command = get_command_record(code, com)
        match command.Typ:
            case CommandTypes.DestCOM:
                execute_dest_com(game, flt_id, command.Loc)
            case CommandTypes.TransCOM:
                execute_trans_com(game, flt_id, command.Res, command.Trns)
            case CommandTypes.SweepCOM:
                execute_sweep_com(game, flt_id)

        if flt_id.Index in game.GlobalSets.SetOfActiveFleets:
            if command.Typ == CommandTypes.RepeatCOM and not ignore_repeat:
                com = 1
                ignore_repeat = True
            elif com < last_command:
                com += 1
            else:
                com = 0
                dispose_orders(code)
                set_fleet_code(game, flt_id, code)
        else:
            fleet_destroyed = True

        if (
            command.Typ in (CommandTypes.DestCOM, CommandTypes.WaitCOM)
            or com == 0
            or fleet_destroyed
        ):
            break

    if not fleet_destroyed:
        set_fleet_next_statement(game, flt_id, com)


# --- Disrupters --------------------------------------------------------------


def in_range_of_disrupter(
    game: GameEnvironment, emp: Empire, pos: XYCoord
) -> Empire | None:
    """The empire whose disrupter covers ``pos`` and is hostile to ``emp``.

    Hostile means the frequency does *not* match: a disrupter stops every
    jump fleet except those tuned to it. Range 3, one further than the
    friendly effect below.
    """
    for i in range(1, MAX_NO_OF_STARGATES + 1):
        if i not in game.GlobalSets.SetOfActiveGates:
            continue
        gte_id = IDNumber(ObjectTypes.Gate, i)
        if get_gate_type(game, gte_id) != T.dis:
            continue
        if get_warp_link_freq(game, emp, gte_id) == get_warp_link_freq(
            game, get_status(game, gte_id), gte_id
        ):
            continue
        if distance(get_coord(game, gte_id), pos) <= 3:
            return get_status(game, gte_id)
    return None


def in_range_of_my_disrupter(
    game: GameEnvironment, emp: Empire, pos: XYCoord
) -> bool:
    """Whether a disrupter tuned to ``emp`` covers ``pos``.

    Range 2 -- deliberately shorter than the hostile range, so the band where
    a disrupter helps its owner is strictly inside the band where it stops
    everyone else.
    """
    for i in range(1, MAX_NO_OF_STARGATES + 1):
        if i not in game.GlobalSets.SetOfActiveGates:
            continue
        gte_id = IDNumber(ObjectTypes.Gate, i)
        if get_gate_type(game, gte_id) != T.dis:
            continue
        if get_warp_link_freq(game, emp, gte_id) != get_warp_link_freq(
            game, get_status(game, gte_id), gte_id
        ):
            continue
        if distance(get_coord(game, gte_id), pos) <= 2:
            return True
    return False


# --- The annual fleet tick ---------------------------------------------------


def use_up_fuel(game: GameEnvironment, flt_id: IDNumber) -> bool:
    """Burn one sector's worth of fuel, refuelling from cargo if short.

    Returns False when the fleet has neither fuel nor trillum, in which case
    it has already been set FInactive and told about it. Recurses because
    refuelling is capped at the fleet's tank, so one top-up may not cover the
    burn; each pass consumes at least one ton, so it terminates.
    """
    sh = get_ships(game, flt_id)
    cr = get_cargo(game, flt_id)
    emp = get_status(game, flt_id)

    fuel_con = fuel_consumption(sh, cr)
    fuel_left = get_fleet_fuel(game, flt_id)

    if fuel_left >= fuel_con:
        set_fleet_fuel(game, flt_id, fuel_left - fuel_con)
        return True

    if cr[T.tri] == 0:
        add_news(game, emp, NewsTypes.NoFuel, Location(limbo(), flt_id), 0, 0, 0)
        set_fleet_status(game, flt_id, FleetStatus.FInactive)
        return False

    tri_to_use = greater_int(
        1, lesser_int(cr[T.tri], pascal_round(fuel_con / FUEL_PER_TON))
    )
    refuel_fleet(game, flt_id, flt_id, tri_to_use)
    return use_up_fuel(game, flt_id)


def mine_field_damage(
    game: GameEnvironment, flt_id: IDNumber, mined_by: Empire
) -> bool:
    """Apply minefield losses to a fleet. Returns True if it was destroyed.

    Losses are per ship type: a flat 1..100 plus a percentage set by how much
    protection that hull needs. The flat term is what makes a small fleet
    disproportionately likely to be wiped out.
    """
    sh = get_ships(game, flt_id)
    cr = get_cargo(game, flt_id)
    emp = get_status(game, flt_id)

    ships_dest: dict[T, int] = {}
    for res in MINEABLE_SHIPS:
        ships_dest[res] = lesser_int(
            sh[res],
            rnd(1, 100) + pascal_round(sh[res] * ((ProtecNeeded[res] + 20) / 100)),
        )
        sh[res] -= ships_dest[res]

    loc = Location(limbo(), flt_id)
    if no_ships(sh):
        loc = fleet_name_destruction(game, emp, flt_id)
        add_news(game, emp, NewsTypes.MinesDs, loc, int(mined_by), 0, 0)
        destroy_fleet(game, flt_id)
        destroyed = True
    else:
        add_news(game, emp, NewsTypes.MinesDm, loc, int(mined_by), 0, 0)
        balance_fleet(sh, cr)
        put_ships(game, flt_id, sh)
        put_cargo(game, flt_id, cr)
        destroyed = False

    for res in MINEABLE_SHIPS:
        if ships_dest[res] != 0:
            add_news(game, emp, NewsTypes.DestDetail, loc, ships_dest[res], int(res), 0)

    return destroyed


def update_fleet(game: GameEnvironment, flt_id: IDNumber) -> None:
    """Move a fleet one year and, if it has arrived, run its orders.

    The move resolves in one of three ways:

    * **Teleport.** A usable stargate under the fleet, or a fortress with the
      destination within 5 sectors, puts it straight on the destination -- a
      dense nebula there is the one thing that stops it.
    * **A fortress boost.** A fortress with a farther destination advances the
      fleet up to 5 sectors before its normal move even begins.
    * **A normal move** of ``FltMovementRate`` sectors, one at a time, stopping
      early on a minefield, a hostile disrupter or a dense nebula.
    """
    flt_xy = get_coord(game, flt_id)
    dest = get_fleet_destination(game, flt_id)
    flt_typ = type_of_fleet(game, flt_id)
    emp = get_status(game, flt_id)
    flt_destroyed = False

    if not same_xy(dest, flt_xy):
        teleport = False
        if passing_through_gate(game, flt_id, flt_xy, dest):
            teleport = True
        elif passing_through_fortress(game, flt_xy):
            if distance(flt_xy, dest) <= 5:
                teleport = True
            else:
                # The catapult. Five passes, but the fleet is left on the
                # position from the pass before last -- the final step is
                # computed and thrown away -- so it advances four sectors,
                # not five. Preserved as-is: it is balance, not a crash.
                j = 5
                new_pos = flt_xy
                while j > 0 and not same_xy(new_pos, limbo()):
                    flt_xy = new_pos
                    new_pos = get_new_pos(game, new_pos, dest)
                    j -= 1

                move_fleet(game, flt_id, flt_xy)

        if use_up_fuel(game, flt_id):
            if teleport:
                if get_nebula(game, dest) == NebulaTypes.DenseNebula:
                    add_news(
                        game, emp, NewsTypes.NebGate, Location(limbo(), flt_id), 0, 0, 0
                    )
                else:
                    move_fleet(game, flt_id, dest)
                    set_fleet_status(game, flt_id, FleetStatus.FReady)
            else:
                new_pos = flt_xy
                old_pos = flt_xy

                for _ in range(1, FltMovementRate[flt_typ] + 1):
                    old_pos = new_pos
                    new_pos = get_new_pos(game, new_pos, dest)

                    if flt_typ in JUMP_FLEET_TYPES:
                        mined_by = enemy_mine(game, new_pos)
                        if mined_by not in (Empire.Indep, emp):
                            # The fleet still ends up in the mined sector --
                            # it is stopped there, not turned back.
                            flt_destroyed = mine_field_damage(game, flt_id, mined_by)
                            add_news(
                                game,
                                mined_by,
                                NewsTypes.Mines,
                                Location(new_pos, empty_quadrant()),
                                int(emp),
                                0,
                                0,
                            )
                            game.Galaxy.set_mine_scout(emp, new_pos)
                            break

                        disrupt_by = in_range_of_disrupter(game, emp, new_pos)
                        if disrupt_by is not None:
                            add_news(
                                game,
                                emp,
                                NewsTypes.Disrupt,
                                Location(limbo(), flt_id),
                                int(disrupt_by),
                                0,
                                0,
                            )
                            break

                    if flt_typ in WARP_FLEET_TYPES and in_range_of_my_disrupter(
                        game, emp, new_pos
                    ):
                        # A warp fleet inside its owner's disrupter field
                        # travels at jump speed: up to 10 extra sectors, so
                        # long as it stays in the field and short of its
                        # destination.
                        disrupter_counter = 1
                        while (
                            in_range_of_my_disrupter(game, emp, new_pos)
                            and disrupter_counter <= 10
                            and not same_xy(new_pos, dest)
                            and not same_xy(new_pos, limbo())
                        ):
                            old_pos = new_pos
                            new_pos = get_new_pos(game, new_pos, dest)
                            disrupter_counter += 1

                    if same_xy(new_pos, limbo()):
                        # Blocked by a dense nebula: fall back to the last
                        # good sector rather than moving into it.
                        flt_destroyed = False
                        new_pos = old_pos
                        add_news(
                            game,
                            emp,
                            NewsTypes.FltBlocked,
                            Location(limbo(), flt_id),
                            0,
                            0,
                            0,
                        )
                        break

                if not flt_destroyed:
                    move_fleet(game, flt_id, new_pos)
                    if same_xy(dest, new_pos):
                        set_fleet_status(game, flt_id, FleetStatus.FReady)

    if not flt_destroyed and get_fleet_status(game, flt_id) == FleetStatus.FReady:
        execute_fleet_orders(game, emp, flt_id)


def update_all_fleets(
    game: GameEnvironment, player: Empire, next_player: Empire
) -> None:
    """Move the fleets that are due to move at this point in the rotation.

    Fleets do not all move at the same moment in the turn cycle, and the
    split is deliberate. Slow warp fleets and anything sitting on a gate move
    for the *incoming* player, so that player sees them arrive at the start
    of their turn. Fast jump and hunter-killer fleets move for the *outgoing*
    player, after their orders are set, so a jump ordered this turn lands
    this turn. Every other fleet is left alone.
    """
    for i in range(1, MAX_NO_OF_FLEETS + 1):
        if i not in game.GlobalSets.SetOfActiveFleets:
            continue

        flt_id = IDNumber(ObjectTypes.Flt, i)
        flt_typ = type_of_fleet(game, flt_id)
        obj_id = get_object(game, get_coord(game, flt_id))
        emp = get_status(game, flt_id)

        if emp == next_player and (
            flt_typ in WARP_FLEET_TYPES or obj_id.ObjTyp == ObjectTypes.Gate
        ):
            update_fleet(game, flt_id)
        elif (
            emp == player
            and flt_typ in JUMP_FLEET_TYPES
            and obj_id.ObjTyp != ObjectTypes.Gate
        ):
            update_fleet(game, flt_id)
