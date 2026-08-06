"""Shared primitives every AI persona is built on.

Port of NPEINTR.PAS. This is the layer between the personas (NPE01..NPE04)
and the rest of the game: it picks targets, sizes and launches fleets, runs
each mission type to its conclusion, redesignates worlds, and moves the
diplomatic policy between empires up and down.

Three ideas carry most of the unit:

**Regions.** An AI does not think about the whole galaxy at once. Its base
worlds and capital form a ``RegionCapitalArray``, and almost every decision is
made relative to the nearest one -- where a fleet launches from, where it
retreats to, whether a world is worth fortifying. ``AverageMilitaryPower``
across those regions is the yardstick for what the empire can afford to spend.

**Fleet data.** The AI keeps a parallel record for each of its fleets --
mission, target, home base -- in a ``FleetDataArray`` indexed independently of
the global fleet array. ``NPEDataIndex`` on the fleet points back into it.
The two can drift apart when fleets die, which is what
``EnforceNPEDataLinks`` exists to repair.

**Missions.** A fleet is launched with a mission and runs it on arrival. The
``implement_*_msn`` functions are those arrival handlers; most end by either
setting a return leg or picking a fresh target.

Several routines here are visibly unfinished in v2.0 -- ``DeployHarassFleet``
is an empty stub, and the slow-attack fallback mislabels its own mission.
Both are ported as they are and filed; see the notes at each site.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..attack import AttackIntentionTypes, AttackResultTypes, lam_attack
from ..attnpe import npe_attack
from ..datacnst import (
    FUEL_PER_TON,
    CargoSpace,
    ClassIndAdj,
    MinTechForType,
    MPower,
    TrnAdj,
    _table,
    init_defense_record,
)
from ..design import designate_world
from ..fleet import (
    abort_fleet,
    change_composition_of_fleet,
    deploy_fleet,
    destroy_fleet,
    refuel_fleet,
    set_fleet_destination,
)
from ..intrface import (
    balance_fleet,
    estimated_date_of_arrival,
    estimated_range,
    get_empire_status,
)
from ..misc import (
    add_things,
    distance,
    fleet_cargo_space,
    fuel_capacity,
    military_power,
    move_things,
    same_id,
    same_xy,
    thg_lmt,
)
from ..primintr import (
    empire_active,
    get_capital,
    get_cargo,
    get_class,
    get_coord,
    get_defns,
    get_fleet_fuel,
    get_fleets,
    get_object,
    get_population,
    get_probe,
    get_ships,
    get_status,
    get_tech,
    get_trillum,
    get_type,
    known,
    launch_probe,
    npe_data_index,
    put_cargo,
    put_defns,
    put_ships,
    scouted,
    set_defense_settings,
    set_npe_data_index,
    set_status,
    set_type,
)
from ..types import (
    MAX_NO_OF_CONSTR_SITES,
    MAX_NO_OF_FLEETS,
    MAX_NO_OF_STARGATES,
    NO_OF_FLEETS_PER_EMPIRE,
    PLAYER_EMPIRES,
    SHIP_TYPES,
    Empire,
    IDNumber,
    IndusTypes,
    ObjectTypes,
    TechLevel,
    TechnologyTypes,
    WorldClass,
    WorldTypes,
    cargo_array,
    defns_array,
    empty_quadrant,
    indus_range,
    ship_array,
)
from ..utils.int_utils import greater_int, lesser_int, rnd
from ..utils.pascal import pascal_random_real, pascal_round, trunc
from .types import (
    MissionTypes,
    NPECharacterRecord,
    PolicyTypes,
    StateDeptRecord,
)

if TYPE_CHECKING:
    from ..environ import GameEnvironment

T = TechnologyTypes
WT = WorldTypes
WC = WorldClass

#: How many base worlds an AI tracks as regional capitals.
MAX_NO_OF_REGIONS = 20

#: Fleets that will sit over a base world before the AI stops stacking more
#: there. Raising it makes an empire hoard ships until it stagnates; the
#: original's comment says as much.
MAX_NO_OF_GUARDS = 3

MAX_NO_OF_RAIDERS = 3

def _word(value: int) -> int:
    """Wrap to a Pascal ``Word`` -- 16-bit unsigned, no range checking.

    Needed where the original stores a running total in a ``Word`` and lets it
    underflow; a Python int would go negative and change the outcome.
    """
    return value % 65536


#: Pascal's ``BioInd TO TriInd`` -- the industries GetNewDesignation weighs.
_DESIGNATION_INDUSTRIES = indus_range(IndusTypes.BioInd, IndusTypes.TriInd)

#: Pascal's ``AgrTyp TO TriTyp`` -- every world type, including the unnamed
#: ``*STyp`` gaps the tables below zero out.
_ALL_WORLD_TYPES = tuple(WorldTypes)


def _defense(shell_rows: tuple[tuple[int, ...], ...]):
    """One of the AI's canned defense distributions.

    The Pascal declares these as typed constants specifying ``ShellDefDist``
    only, so ``StarbaseDefDist`` is left zero-filled -- same shape as
    ``init_defense_record``.
    """
    from ..datastrc import DefenseRecord
    from ..types import ShellPos

    record = DefenseRecord()
    record.ShellDefDist = _table(
        ShellPos, tuple(_table(SHIP_TYPES, row) for row in shell_rows)
    )
    return record


#: Balanced: fighters and hunter-killers hold orbit, troops on the ground.
DEFENSE_1 = _defense(
    (
        # fgt  hkr  jmp  jtn  pen  ssp  trn
        (0, 0, 0, 0, 0, 0, 0),  # deep space
        (0, 0, 0, 0, 100, 100, 0),  # high orbit
        (50, 100, 100, 0, 0, 0, 0),  # orbit
        (0, 0, 0, 0, 0, 0, 0),  # sub-orbit
        (50, 0, 0, 100, 0, 0, 100),  # ground
    )
)

#: Everything in orbit -- a single massed shell.
DEFENSE_2 = _defense(
    (
        (0, 0, 0, 0, 0, 0, 0),
        (0, 0, 0, 0, 0, 0, 0),
        (100, 100, 100, 0, 100, 100, 0),
        (0, 0, 0, 0, 0, 0, 0),
        (0, 0, 0, 100, 0, 0, 100),
    )
)

#: Layered: skirmishers high, heavies in orbit, fighters held to the ground.
DEFENSE_3 = _defense(
    (
        (0, 0, 0, 0, 0, 0, 0),
        (0, 25, 50, 0, 75, 75, 0),
        (0, 75, 50, 0, 25, 25, 0),
        (0, 0, 0, 0, 0, 0, 0),
        (100, 0, 0, 100, 0, 0, 100),
    )
)


# --- Valuation tables --------------------------------------------------------

#: Baseline chance of designating a world to each type, before class,
#: population and geography adjust it. The ``*STyp`` entries are zero: they are
#: the "under construction" variants and the AI never picks them directly.
NPETypeDefault: dict[WT, int] = _table(
    _ALL_WORLD_TYPES,
    (
        10,  # AgrTyp
        0,  # AmbTyp
        75,  # BseTyp
        0,  # BseSTyp
        0,  # CapTyp
        30,  # CheTyp
        0,  # IndTyp
        100,  # JmpTyp
        0,  # JmpSTyp
        50,  # MinTyp
        0,  # NnjTyp
        0,  # OutTyp
        50,  # RawTyp
        0,  # RawSTyp
        100,  # StrTyp
        0,  # StrSTyp
        20,  # TrnTyp
        0,  # TrnSTyp
        50,  # RsrTyp
        0,  # TerTyp
        40,  # TriTyp
    ),
)

#: How much the AI thinks a world of each type is worth defending or taking.
NPETypeValue: dict[WT, int] = _table(
    _ALL_WORLD_TYPES,
    (
        30,  # AgrTyp
        100,  # AmbTyp
        10,  # BseTyp
        0,  # BseSTyp
        100,  # CapTyp
        50,  # CheTyp
        25,  # IndTyp
        25,  # JmpTyp
        0,  # JmpSTyp
        50,  # MinTyp
        100,  # NnjTyp
        100,  # OutTyp
        50,  # RawTyp
        0,  # RawSTyp
        25,  # StrTyp
        0,  # StrSTyp
        60,  # TrnTyp
        0,  # TrnSTyp
        50,  # RsrTyp
        0,  # TerTyp
        50,  # TriTyp
    ),
)

#: How much the AI thinks a world of each class is worth.
NPEClassValue: dict[WC, int] = _table(
    WorldClass,
    (
        100,  # AmbCls
        35,  # ArdCls
        100,  # ArtCls
        50,  # BarCls
        65,  # ClsJ
        65,  # ClsK
        65,  # ClsL
        65,  # ClsM
        50,  # DrtCls
        65,  # EthCls
        75,  # FstCls
        60,  # GsGCls
        80,  # HLfCls
        25,  # IceCls
        75,  # JngCls
        50,  # OcnCls
        100,  # ParCls
        50,  # PsnCls
        100,  # RnsCls
        60,  # UndCls
        90,  # TerCls
        75,  # VlcCls
    ),
)


# --- Fleet-data bookkeeping --------------------------------------------------


def next_fleet_data_slot(game: GameEnvironment, fleet_data: list) -> int:
    """Highest free fleet-data slot, or 0 when all are taken.

    A slot is free when the fleet it names is no longer active, so dead
    fleets release their records without anything having to clear them.
    """
    i = NO_OF_FLEETS_PER_EMPIRE
    while i > 0 and fleet_data[i].Index in game.GlobalSets.SetOfActiveFleets:
        i -= 1
    return i


def already_targetted(
    game: GameEnvironment, emp: Empire, obj: IDNumber, mission: MissionTypes, fleet_data: list
) -> bool:
    """Whether a live fleet is already flying ``mission`` against ``obj``.

    Keeps the AI from sending three fleets at the same world in one turn.
    """
    for i in range(1, NO_OF_FLEETS_PER_EMPIRE + 1):
        entry = fleet_data[i]
        if (
            entry.Index in game.GlobalSets.SetOfActiveFleets
            and mission == entry.Mission
            and same_id(entry.TargetID, obj)
        ):
            return True
    return False


def enforce_npe_data_links(game: GameEnvironment, emp: Empire, fleet_data: list) -> None:
    """Drop fleet-data records no live fleet points at.

    The link runs fleet -> record via ``NPEDataIndex``. When a fleet dies the
    record it referenced is orphaned, and ``next_fleet_data_slot`` would still
    consider it taken if its ``Index`` named a slot that has since been reused
    by a different fleet. Zeroing ``Index`` is what frees it.
    """
    active_fleets = game.GlobalSets.SetOfActiveFleets & game.GlobalSets.SetOfFleetsOf[emp]

    active_records = set()
    for i in range(1, MAX_NO_OF_FLEETS + 1):
        # The original reads NPEDataIndex for every slot *before* testing
        # whether the fleet is active, which dereferences a dangling pointer
        # for every dead one. The value is discarded in that case, so the
        # test is hoisted here rather than reproducing a read of freed memory.
        if i not in active_fleets:
            continue
        rec = npe_data_index(game, IDNumber(ObjectTypes.Flt, i))
        if rec != 0:
            active_records.add(rec)

    for i in range(1, NO_OF_FLEETS_PER_EMPIRE + 1):
        if i not in active_records:
            fleet_data[i].Index = 0


# --- Fleet composition -------------------------------------------------------

#: Ship types to draw on, in order, for each mission. The AI fills the fleet
#: from the front of the sequence until it has the power it asked for, so the
#: first entry is the backbone and later ones are makeweights.
_JSEQ = (T.jmp, T.hkr, T.pen, T.ssp, T.fgt)
_ASEQ = (T.pen, T.hkr, T.ssp, T.fgt, T.jmp)
_SSEQ = (T.hkr, T.pen, T.jmp, T.ssp, T.fgt)
_ESEQ = (T.jmp, T.hkr, T.hkr, T.hkr, T.hkr)
_RSEQ = (T.hkr, T.hkr, T.hkr, T.hkr, T.hkr)
_LSEQ = (T.fgt, T.jmp, T.pen, T.hkr, T.ssp)

_MISSION_SEQUENCE = {
    MissionTypes.ReturnMSN: _LSEQ,
    MissionTypes.ConquerMSN: _JSEQ,
    MissionTypes.StackMSN: _ASEQ,
    MissionTypes.JumpAttackMSN: _ESEQ,
    MissionTypes.RaidTrnMSN: _RSEQ,
}


def get_fleet_composition(
    game: GameEnvironment,
    obj_id: IDNumber,
    power: int,
    gat: int,
    mission: MissionTypes,
) -> tuple[dict[T, int], dict[T, int]]:
    """Pick ships and troops out of ``obj_id`` for a fleet of the given power.

    ``power`` is military power wanted, ``gat`` ground attack strength. Note
    ``_SSEQ`` is declared in the original but never selected -- no mission maps
    to it -- so it is dead weight kept for the record.

    Troops leave 500 men behind on the world whatever happens, which is what
    stops the AI stripping a world bare to fill one invasion.
    """
    sequence = _MISSION_SEQUENCE.get(mission, _JSEQ)

    ships = ship_array()
    cargo = cargo_array()
    shp_at_base = get_ships(game, obj_id)
    car_at_base = get_cargo(game, obj_id)

    i = 0
    while power > 0 and i < 5:
        shp = sequence[i]
        ships[shp] = lesser_int(shp_at_base[shp], pascal_round(power / MPower[shp]) + 1)
        power -= ships[shp] * MPower[shp]
        i += 1

    if gat > 0:
        # How many men and ninjas make up the requested ground strength.
        nnj_to_take = lesser_int(gat // 3, car_at_base[T.nnj])
        gat -= 3 * nnj_to_take
        men_to_take = lesser_int(gat, greater_int(0, car_at_base[T.men] - 500))
        gat -= men_to_take

        # Transports needed to lift them.
        space_needed = pascal_round((men_to_take + nnj_to_take) / CargoSpace[T.men])
        ships[T.jtn] = lesser_int(
            shp_at_base[T.jtn], pascal_round(space_needed / TrnAdj[T.jtn])
        )
        space_needed -= pascal_round(ships[T.jtn] * TrnAdj[T.jtn])
        ships[T.trn] = lesser_int(
            shp_at_base[T.trn], pascal_round(space_needed / TrnAdj[T.trn])
        )
        space_needed -= pascal_round(ships[T.trn] * TrnAdj[T.trn])
        total_space = pascal_round(
            ships[T.jtn] * TrnAdj[T.jtn] + ships[T.trn] * TrnAdj[T.trn]
        )

        # Load troops into the transports that were actually available.
        #
        # ORIGINAL BUG, preserved -- see issue #29. Space is deducted by
        # *multiplying* by CargoSpace where converting units back to space
        # requires dividing, so the subtraction overshoots by CargoSpace
        # squared and drives the running total negative. TotalCargoSpace is a
        # Pascal Word, so it wraps to a large positive instead, and the men
        # cap becomes effectively infinite: every troop-carrying deployment
        # loads its full complement no matter how few transports it has.
        cargo[T.nnj] = lesser_int(
            nnj_to_take, pascal_round(total_space * CargoSpace[T.nnj])
        )
        total_space = _word(total_space - pascal_round(cargo[T.nnj] * CargoSpace[T.nnj]))
        cargo[T.men] = lesser_int(
            men_to_take, pascal_round(total_space * CargoSpace[T.men])
        )

    # A berserker strike takes every transport there is.
    if mission == MissionTypes.BSRKAttackMSN:
        ships[T.trn] = shp_at_base[T.trn]
        ships[T.jtn] = shp_at_base[T.jtn]

    if (
        ships[T.hkr] + ships[T.jmp] + ships[T.jtn] + ships[T.pen] + ships[T.ssp] + ships[T.trn]
    ) == 0:
        # Fighters have no fuel capacity of their own, so a pure fighter
        # fleet needs a few tons of trillum to move at all.
        cargo[T.tri] = 10

    return ships, cargo


def get_potential_res(
    game: GameEnvironment, obj_id: IDNumber, fleet_data: list
) -> tuple[dict[T, int], dict[T, int]]:
    """What ``obj_id`` will have once everything heading home gets there.

    Counts the world's own ships and cargo plus every fleet on a ReturnMSN
    aimed at it, so the AI does not launch a second wave to cover a shortfall
    that is already in transit.
    """
    ships = get_ships(game, obj_id)
    cargo = get_cargo(game, obj_id)

    # Fleet slots are carved into per-empire blocks, so the owner's block
    # start is what the AI's own indices map onto.
    index = NO_OF_FLEETS_PER_EMPIRE * int(get_status(game, obj_id)) + 1
    for i in range(1, NO_OF_FLEETS_PER_EMPIRE + 1):
        entry = fleet_data[i]
        flt_id = IDNumber(ObjectTypes.Flt, index)
        if (
            index in game.GlobalSets.SetOfActiveFleets
            and entry.Mission == MissionTypes.ReturnMSN
            and same_id(obj_id, entry.TargetID)
        ):
            add_things(ships, cargo, get_ships(game, flt_id), get_cargo(game, flt_id))
        index += 1

    return ships, cargo


# --- Assessment --------------------------------------------------------------


def minimum_defense(
    game: GameEnvironment, obj_id: IDNumber, persona: NPECharacterRecord
) -> int:
    """What the AI thinks it takes to hold ``obj_id``, ignoring actual threats.

    ORIGINAL BUG, preserved -- see issue #23. Two things run away here. The
    character adjustment is ``BaseValue * Defensive * 50`` where ``Defensive``
    is a 0..100 index, so it scales by up to 5000x and collapses to zero for a
    wholly undefensive AI. Then the proximity adjustment multiplies by 3 (and
    again by 2 for a base or capital) *inside* the per-world loop, so it
    compounds once per nearby enemy world rather than applying once.
    """
    base_value = NPETypeValue[get_type(game, obj_id)]

    base_value = pascal_round(base_value * (0.5 + (get_population(game, obj_id) / 2500)))
    base_value = base_value * persona.Defensive * 50

    world_xy = get_coord(game, obj_id)
    emp = get_status(game, obj_id)

    for i in range(1, game.NoOfPlanets + 1):
        if i in game.GlobalSets.SetOfPlanetsOf[emp]:
            continue
        obj = IDNumber(ObjectTypes.Pln, i)
        if get_status(game, obj) == Empire.Indep:
            continue
        if distance(get_coord(game, obj), world_xy) <= 5:
            base_value = base_value * 3
            if get_type(game, obj) == WT.BseTyp:
                base_value = base_value * 2
            elif get_type(game, obj) == WT.CapTyp:
                base_value = base_value * 2

    return base_value


def average_military_power(game: GameEnvironment, rcap: list[IDNumber]) -> int:
    """Mean military power sitting on the empire's regional capitals.

    Ships only -- the zeroed defense array means planetary defenses do not
    count toward what the AI thinks it can spend.
    """
    no_of_bases = 0
    total_power = 0.0
    defns = defns_array()

    for i in range(1, MAX_NO_OF_REGIONS + 1):
        if not same_id(rcap[i], empty_quadrant()):
            no_of_bases += 1
            total_power += military_power(get_ships(game, rcap[i]), defns)

    if no_of_bases > 0:
        return pascal_round(total_power / no_of_bases)
    return 0


# --- Regions -----------------------------------------------------------------


def create_region_array(game: GameEnvironment, emp: Empire) -> list[IDNumber]:
    """Every base world and capital the empire holds, up to MAX_NO_OF_REGIONS.

    Packed from index 1 with no gaps, which is what lets
    :func:`get_regional_capital` stop at the first empty slot.
    """
    region = [empty_quadrant() for _ in range(MAX_NO_OF_REGIONS + 1)]
    next_region = 1

    index = 1
    while index <= game.NoOfPlanets and next_region <= MAX_NO_OF_REGIONS:
        obj = IDNumber(ObjectTypes.Pln, index)
        if index in game.GlobalSets.SetOfPlanetsOf[emp] and get_type(game, obj) in (
            WT.BseTyp,
            WT.CapTyp,
        ):
            region[next_region] = obj
            next_region += 1
        index += 1

    return region


def get_regional_capital(
    game: GameEnvironment, obj_id: IDNumber, rcap: list[IDNumber]
) -> IDNumber:
    """The empire's nearest regional capital to ``obj_id``.

    ORIGINAL BUG, preserved -- see issue #24. The original leaves its result
    variable uninitialised and only assigns it inside the loop, so an empire
    with no regional capitals (or none within 100 sectors) returns whatever
    was on the stack. EmptyQuadrant is returned here instead: it is the only
    defined choice, and callers that go on to read ships off the result get an
    empty array from it, which is the benign reading.
    """
    xy = get_coord(game, obj_id)
    closest_id = empty_quadrant()
    best_dist = 100

    i = 1
    while i <= MAX_NO_OF_REGIONS and not same_id(rcap[i], empty_quadrant()):
        dist = distance(xy, get_coord(game, rcap[i]))
        if dist < best_dist:
            best_dist = dist
            closest_id = rcap[i]
        i += 1

    return closest_id


# --- Target and base selection -----------------------------------------------


def get_best_base(
    game: GameEnvironment,
    emp: Empire,
    target_id: IDNumber,
    fleet_power: int,
    fleet_gat: int,
) -> IDNumber:
    """Nearest world of ``emp`` that could actually launch the fleet described.

    Within 15 sectors of the target, with at least half the military power
    wanted and enough troops. EmptyQuadrant when nothing qualifies.
    """
    best_world_id = empty_quadrant()
    best_distance = 15
    target_xy = get_coord(game, target_id)

    def qualifies(test_id: IDNumber) -> bool:
        ships = get_ships(game, test_id)
        cargo = get_cargo(game, test_id)
        return military_power(ships, defns_array()) > (fleet_power // 2) and (
            cargo[T.men] + 5 * cargo[T.nnj]
        ) > fleet_gat

    for i in range(1, game.NoOfPlanets + 1):
        if i not in game.GlobalSets.SetOfPlanetsOf[emp]:
            continue
        test_id = IDNumber(ObjectTypes.Pln, i)
        dist = distance(get_coord(game, test_id), target_xy)
        if dist < best_distance and qualifies(test_id):
            best_world_id = test_id
            best_distance = dist

    return best_world_id


def get_best_planet_to_protect(game: GameEnvironment, base_id: IDNumber) -> IDNumber:
    """The weakest ordinary world within 5 sectors of ``base_id``.

    Bases and capitals are skipped -- they defend themselves. Falls back to
    the capital when nothing else is close enough, which is why an AI with no
    outlying worlds piles everything onto its capital.
    """
    emp = get_status(game, base_id)
    base_xy = get_coord(game, base_id)
    lowest_defenses = None
    best_world_id = get_capital(game, emp)

    for i in range(1, game.NoOfPlanets + 1):
        if i not in game.GlobalSets.SetOfPlanetsOf[emp]:
            continue
        obj = IDNumber(ObjectTypes.Pln, i)
        if distance(get_coord(game, obj), base_xy) <= 5 and get_type(game, obj) not in (
            WT.BseTyp,
            WT.CapTyp,
        ):
            power = military_power(get_ships(game, obj), get_defns(game, obj))
            if lowest_defenses is None or power < lowest_defenses:
                best_world_id = obj
                lowest_defenses = power

    return best_world_id


def get_best_raider_target(
    game: GameEnvironment, emp: Empire, enemy_emp: Empire
) -> IDNumber:
    """Something of ``enemy_emp``'s worth raiding: a gate, a site, or a world.

    Preference runs gates, then construction sites, then worlds, and each pass
    only runs if the one before found nothing. Within a pass the loop does not
    stop on a hit -- it keeps overwriting -- so the *last* qualifying object
    wins rather than a uniformly random one, biasing raids toward high slot
    numbers.
    """
    best_target = empty_quadrant()

    for i in range(1, MAX_NO_OF_STARGATES + 1):
        if i not in game.GlobalSets.SetOfActiveGates:
            continue
        obj = IDNumber(ObjectTypes.Gate, i)
        if rnd(1, 100) < 50 and known(game, emp, obj) and get_status(game, obj) == enemy_emp:
            best_target = obj

    if same_id(best_target, empty_quadrant()):
        for i in range(1, MAX_NO_OF_CONSTR_SITES + 1):
            if i not in game.GlobalSets.SetOfConstructionSitesOf[enemy_emp]:
                continue
            obj = IDNumber(ObjectTypes.Con, i)
            if rnd(1, 100) < 50 and known(game, emp, obj):
                best_target = obj

    if same_id(best_target, empty_quadrant()):
        for i in range(1, game.NoOfPlanets + 1):
            if i not in game.GlobalSets.SetOfPlanetsOf[enemy_emp]:
                continue
            obj = IDNumber(ObjectTypes.Pln, i)
            if rnd(1, 100) < 25 and known(game, emp, obj):
                best_target = obj

    return best_target


def get_best_target(
    game: GameEnvironment,
    emp: Empire,
    set_of_possibilities: set[int],
    base_power: int,
    persona: NPECharacterRecord,
    fleet_data: list,
) -> tuple[IDNumber, int, int]:
    """Pick the most attractive conquerable world out of ``set_of_possibilities``.

    Returns ``(target_id, target_defense, target_men)``, with EmptyQuadrant
    when nothing qualifies. Value is tech times class times population,
    divided down by whatever is defending it, and a world is only considered
    if its defenses come in under ``base_power``.

    ``WorldPower`` in the persona scales the whole thing: a high-WorldPower AI
    weights raw value more heavily and so goes after fewer, richer worlds.
    """
    target_defense = 0
    target_men = 0
    target_value = 0.0
    target_id = empty_quadrant()

    factor = (1.5 + pascal_random_real()) * (persona.WorldPower / 20)

    for i in range(1, game.NoOfPlanets + 1):
        obj = IDNumber(ObjectTypes.Pln, i)
        if not (
            i in set_of_possibilities
            and known(game, emp, obj)
            and not already_targetted(game, emp, obj, MissionTypes.ConquerMSN, fleet_data)
        ):
            continue

        ships = get_ships(game, obj)
        cargo = get_cargo(game, obj)
        defns = get_defns(game, obj)

        calc_value = factor * (int(get_tech(game, obj)) + 1) * NPEClassValue[get_class(game, obj)]
        calc_value = calc_value * (get_population(game, obj) / 1000)

        defense = military_power(ships, defns)
        troops = cargo[T.men] + 4 * cargo[T.nnj] + 10
        def_value = 100 + pascal_round((defense + troops) / 1000)
        calc_value = calc_value / def_value

        if calc_value > target_value and defense < base_power:
            target_value = calc_value
            target_defense = defense
            target_men = troops
            target_id = obj

    return target_id, target_defense, target_men


# --- Deployment --------------------------------------------------------------


def deploy_battle_fleet(
    game: GameEnvironment,
    emp: Empire,
    fleet_data: list,
    from_id: IDNumber,
    power: int,
    gat: int,
    new_mission: MissionTypes,
    to_id: IDNumber,
) -> None:
    """Launch a fighting fleet at ``to_id`` and record its mission.

    A fleet that cannot reach its destination on the fuel it is carrying, or
    that finds no free data slot, is aborted straight back into the world it
    launched from rather than being sent to die -- which is why the range
    check happens after the launch, not before.

    Probes go out ahead of any attack on a foreign world.
    """
    ships, cargo = get_fleet_composition(game, from_id, power, gat, new_mission)
    dest_xy = get_coord(game, to_id)
    flt_id = deploy_fleet(game, emp, from_id, ships, cargo, dest_xy)

    if same_id(flt_id, empty_quadrant()):
        return

    slot = next_fleet_data_slot(game, fleet_data)
    if slot == 0 or estimated_date_of_arrival(game, flt_id) > estimated_range(game, flt_id):
        abort_fleet(game, flt_id, from_id, True)
        destroy_fleet(game, flt_id)
        return

    set_npe_data_index(game, flt_id, slot)
    entry = fleet_data[slot]
    entry.Mission = new_mission
    entry.HomeBaseID = from_id
    entry.TargetID = to_id
    entry.Waiting = 0
    entry.Index = flt_id.Index

    if get_status(game, to_id) not in (emp, Empire.Indep):
        for _ in range(rnd(1, 4)):
            pnum = get_probe(game, emp)
            if pnum != 0:
                launch_probe(game, emp, pnum, dest_xy)


def deploy_cargo_fleet(
    game: GameEnvironment,
    emp: Empire,
    fleet_data: list,
    from_id: IDNumber,
    cr: dict[T, int],
    carry_cargo: bool,
    new_mission: MissionTypes,
    to_id: IDNumber,
) -> None:
    """Launch a transport run carrying ``cr``, capped by what ``from_id`` has.

    Picks jump transports or ordinary ones but not both: whichever can carry
    the load alone. ``cr`` is modified in place, matching the original's VAR
    parameter -- callers see what was actually loaded.
    """
    sh = ship_array()
    ships = get_ships(game, from_id)

    # fleet_cargo_space is negative for an overloaded fleet, and these ships
    # are empty, so negating gives the space this cargo demands.
    cargo_space = -fleet_cargo_space(sh, cr)
    sh[T.jtn] = lesser_int(ships[T.jtn], 1 + pascal_round(cargo_space / TrnAdj[T.jtn]))
    sh[T.trn] = lesser_int(ships[T.trn], 1 + cargo_space)
    jtn_cargo = pascal_round(sh[T.jtn] * TrnAdj[T.jtn])
    if jtn_cargo < cargo_space and jtn_cargo < sh[T.trn]:
        sh[T.jtn] = 0
    else:
        sh[T.trn] = 0

    if carry_cargo:
        ground_cr = get_cargo(game, from_id)
        for car in cr:
            cr[car] = lesser_int(cr[car], ground_cr[car])
    else:
        for car in cr:
            cr[car] = 0

    balance_fleet(sh, cr)

    dest_xy = get_coord(game, to_id)
    flt_id = deploy_fleet(game, emp, from_id, sh, cr, dest_xy)

    if same_id(flt_id, empty_quadrant()):
        return

    slot = next_fleet_data_slot(game, fleet_data)
    if slot == 0 or estimated_date_of_arrival(game, flt_id) > estimated_range(game, flt_id):
        abort_fleet(game, flt_id, from_id, True)
        destroy_fleet(game, flt_id)
        return

    set_npe_data_index(game, flt_id, slot)
    entry = fleet_data[slot]
    entry.Mission = new_mission
    entry.HomeBaseID = from_id
    entry.TargetID = to_id
    entry.Waiting = 0
    entry.Index = flt_id.Index


def deploy_harass_fleet(
    game: GameEnvironment,
    emp: Empire,
    enemy_emp: Empire,
    rcap: list[IDNumber],
    persona: NPECharacterRecord,
    fleet_data: list,
) -> None:
    """Do nothing.

    ORIGINAL BUG, preserved -- see issue #25. The procedure is declared in
    NPEINTR's interface and has an empty body in v2.0, so ``HarassPLT`` --
    the first rung of the escalation ladder in :func:`state_department` -- is
    a policy under which the AI takes no action at all.
    """


def deploy_jump_attack(
    game: GameEnvironment,
    emp: Empire,
    enemy_emp: Empire,
    rcap: list[IDNumber],
    persona: NPECharacterRecord,
    fleet_data: list,
) -> None:
    """Send a jumpship strike at the best world ``enemy_emp`` has.

    Launches from the regional capital nearest the target if it can field half
    the power wanted, otherwise looks for any world that can.
    """
    base_power = average_military_power(game, rcap)
    target_id, target_defense, target_men = get_best_target(
        game, emp, game.GlobalSets.SetOfPlanetsOf[enemy_emp], base_power, persona, fleet_data
    )
    if same_id(target_id, empty_quadrant()):
        return

    fleet_power = 30000 + pascal_round(
        (pascal_random_real() + rnd(2, 5)) * target_defense
    )
    fleet_gat = pascal_round(2.0 * target_men)

    base_id = get_regional_capital(game, target_id, rcap)
    if military_power(get_ships(game, base_id), defns_array()) > (fleet_power // 2):
        deploy_battle_fleet(
            game, emp, fleet_data, base_id, fleet_power, fleet_gat,
            MissionTypes.JumpAttackMSN, target_id,
        )
        return

    base_id = get_best_base(game, emp, target_id, fleet_power, fleet_gat)
    if not same_id(base_id, empty_quadrant()):
        deploy_battle_fleet(
            game, emp, fleet_data, base_id, fleet_power, fleet_gat,
            MissionTypes.JumpAttackMSN, target_id,
        )


def deploy_hk_raiders(
    game: GameEnvironment,
    emp: Empire,
    enemy_emp: Empire,
    rcap: list[IDNumber],
    fleet_data: list,
) -> None:
    """Send hunter-killers to raid a gate, construction site or world."""
    target_id = get_best_raider_target(game, emp, enemy_emp)
    if same_id(target_id, empty_quadrant()):
        return

    base_id = get_regional_capital(game, target_id, rcap)
    fleet_power = MPower[T.hkr] * rnd(100, 5000)
    deploy_battle_fleet(
        game, emp, fleet_data, base_id, fleet_power, 0, MissionTypes.RaidTrnMSN, target_id
    )


def deploy_slow_attack(
    game: GameEnvironment,
    emp: Empire,
    enemy_emp: Empire,
    rcap: list[IDNumber],
    persona: NPECharacterRecord,
    fleet_data: list,
) -> None:
    """Send a conventional warp fleet at the best world ``enemy_emp`` has.

    Same shape as :func:`deploy_jump_attack` but with a heavier base power,
    since a slow fleet cannot pick its moment.

    ORIGINAL BUG, preserved -- see issue #26. The fallback branch, taken when
    the nearest regional capital is too weak, deploys with ``JumpAttackMSN``
    instead of ``SlowAttackMSN``. That is a copy-paste from the routine above:
    it changes the fleet's composition (the jump sequence is all hunter-killers
    behind one jumpship) and the arrival handler the persona later runs.
    """
    base_power = average_military_power(game, rcap)
    target_id, target_defense, target_men = get_best_target(
        game, emp, game.GlobalSets.SetOfPlanetsOf[enemy_emp], base_power, persona, fleet_data
    )
    if same_id(target_id, empty_quadrant()):
        return

    fleet_power = 50000 + pascal_round(
        (pascal_random_real() + rnd(2, 5)) * target_defense
    )
    fleet_gat = pascal_round(2.0 * target_men)

    base_id = get_regional_capital(game, target_id, rcap)
    if military_power(get_ships(game, base_id), defns_array()) > (fleet_power // 2):
        deploy_battle_fleet(
            game, emp, fleet_data, base_id, fleet_power, fleet_gat,
            MissionTypes.SlowAttackMSN, target_id,
        )
        return

    base_id = get_best_base(game, emp, target_id, fleet_power, fleet_gat)
    if not same_id(base_id, empty_quadrant()):
        deploy_battle_fleet(
            game, emp, fleet_data, base_id, fleet_power, fleet_gat,
            MissionTypes.JumpAttackMSN, target_id,
        )


# --- Designation -------------------------------------------------------------


def get_new_designation(
    game: GameEnvironment,
    world_id: IDNumber,
    persona: NPECharacterRecord,
    rcap: list[IDNumber],
) -> WorldTypes:
    """Roll a new designation for ``world_id``, weighted by everything at hand.

    Chances start from ``NPETypeDefault``, are zeroed for anything the world's
    tech cannot support, multiplied twentyfold for whatever it already is
    (worlds mostly stay put), then scaled by how well the world's class suits
    each industry, by population, and by geography.

    Two geographic pulls run opposite ways: a world close to an existing
    regional capital is almost never made a base itself, while one close to
    any *known* capital -- including the AI's own -- is thirty times more
    likely to become one. An ambrosia or paradise world with the tech for it
    short-circuits all of this and becomes an ambrosia world.
    """
    tech = get_tech(game, world_id)
    pop = get_population(game, world_id)
    world_class = get_class(game, world_id)

    clss_adj = {
        ind: (ClassIndAdj[world_class][ind] / 100) ** 2 for ind in _DESIGNATION_INDUSTRIES
    }

    chance: dict[WT, float] = {}
    for typ in _ALL_WORLD_TYPES:
        chance[typ] = 0.0 if tech < MinTechForType[typ] else float(NPETypeDefault[typ])

    current = get_type(game, world_id)
    chance[current] = chance[current] * 20

    IT = IndusTypes
    chance[WT.RawTyp] *= clss_adj[IT.MinInd] * clss_adj[IT.CheInd] * clss_adj[IT.TriInd]
    chance[WT.MinTyp] *= clss_adj[IT.MinInd]
    chance[WT.CheTyp] *= clss_adj[IT.CheInd]
    chance[WT.TriTyp] *= clss_adj[IT.TriInd]
    chance[WT.AgrTyp] *= clss_adj[IT.SupInd]
    chance[WT.JmpTyp] *= clss_adj[IT.CheInd] * clss_adj[IT.MinInd] * clss_adj[IT.SupInd]
    chance[WT.StrTyp] *= clss_adj[IT.MinInd] * clss_adj[IT.SupInd]
    chance[WT.BseTyp] *= clss_adj[IT.MinInd] * clss_adj[IT.SupInd]

    if pop > 2000:
        chance[WT.BseTyp] *= 25
        chance[WT.StrTyp] *= 28
        chance[WT.JmpTyp] *= 30
    elif pop > 1000:
        chance[WT.BseTyp] *= 12
        chance[WT.StrTyp] *= 6
        chance[WT.JmpTyp] *= 12

    base_id = get_regional_capital(game, world_id, rcap)
    base_xy = get_coord(game, base_id)
    world_xy = get_coord(game, world_id)
    if 0 < distance(base_xy, world_xy) < 5:
        chance[WT.BseTyp] *= 0.01

    emp = get_status(game, world_id)
    for emp_i in PLAYER_EMPIRES:
        if not empire_active(game, emp_i):
            continue
        cap_id = get_capital(game, emp_i)
        if not known(game, emp, cap_id):
            continue
        if distance(world_xy, get_coord(game, cap_id)) <= 5:
            chance[WT.BseTyp] *= 30
            break

    if world_class in (WC.AmbCls, WC.ParCls) and tech >= TechLevel.BioTchLvl:
        return WT.AmbTyp

    total = 0
    for typ in _ALL_WORLD_TYPES:
        chance[typ] = float(pascal_round(chance[typ]))
        total += pascal_round(chance[typ])

    if total < 100:
        return WT.IndTyp

    roll = trunc(pascal_random_real() * total) + 1
    new_type = WT.AgrTyp
    while (roll > chance[new_type] or pascal_round(chance[new_type]) == 0) and new_type != WT.TriTyp:
        roll -= pascal_round(chance[new_type])
        new_type = WorldTypes(int(new_type) + 1)

    if new_type == WT.TriTyp and chance[WT.TriTyp] == 0:
        return WT.IndTyp
    return new_type


def redesignate_empire(
    game: GameEnvironment, emp: Empire, rcap: list[IDNumber], persona: NPECharacterRecord
) -> None:
    """Reconsider what every ordinary world in the empire is for.

    Jumpship, starship and base worlds are left alone -- they represent
    investment the AI will not throw away -- as is the capital. Everything
    else gets a fresh roll, except about 9% of the time: the ``Rnd(1,100)<10``
    term sits inside the same negation as the protected-type test, so it acts
    as a per-world skip rather than a chance to redesignate.
    """
    cap_id = get_capital(game, emp)

    for index in range(1, game.NoOfPlanets + 1):
        if index not in game.GlobalSets.SetOfPlanetsOf[emp]:
            continue
        world_id = IDNumber(ObjectTypes.Pln, index)
        protected = get_type(game, world_id) in (WT.JmpTyp, WT.StrTyp, WT.BseTyp)
        if (protected or rnd(1, 100) < 10) or same_id(cap_id, world_id):
            continue

        new_type = get_new_designation(game, world_id, persona, rcap)
        if new_type != get_type(game, world_id):
            designate_world(game, world_id, new_type)


# --- Mission implementations -------------------------------------------------


def fleet_entry(game: GameEnvironment, flt_id: IDNumber, fleet_data: list):
    """The AI's record for ``flt_id``, or None if the fleet no longer exists.

    ORIGINAL BUG, deviated from -- see issue #39. The mission handlers below
    fight a battle and then keep working on the attacking fleet without ever
    asking whether it survived. In the original that is a use-after-free:
    ``DestroyFleet`` calls ``Dispose`` and leaves the array slot pointing at
    freed heap, so the writes land on memory the allocator has handed back.

    Python has no equivalent of "usually still intact" -- the slot is ``None``
    and the write raises. Every such site now goes through here and does
    nothing when the fleet is gone, which is the closest defined behaviour and
    matches what ``implement_stack_msn`` already did by hand.
    """
    if flt_id.Index not in game.GlobalSets.SetOfActiveFleets:
        return None
    return fleet_data[npe_data_index(game, flt_id)]


def set_fleet_return(
    game: GameEnvironment, emp: Empire, flt_id: IDNumber, base_id: IDNumber, fleet_data: list
) -> None:
    """Turn ``flt_id`` around and send it home to ``base_id``.

    A no-op for a fleet that died in the battle that led here -- see
    :func:`fleet_entry`.
    """
    entry = fleet_entry(game, flt_id, fleet_data)
    if entry is None:
        return
    entry.Mission = MissionTypes.ReturnMSN
    entry.TargetID = base_id
    set_fleet_destination(game, flt_id, get_coord(game, base_id))


def set_raiding_fleet_new_target(
    game: GameEnvironment,
    emp: Empire,
    flt_id: IDNumber,
    target_id: IDNumber,
    base_id: IDNumber,
    fleet_data: list,
    persona: NPECharacterRecord,
) -> None:
    """After a raid, either roll on to a fresh target or go home.

    The chance of pressing on is the persona's ``Offensive``. Note the new
    mission is always ``JumpAttackMSN`` whatever the fleet was flying, so a
    raider that finds a second target converts into an invasion force.
    """
    enemy_emp = get_status(game, target_id)
    fleet_power = military_power(get_ships(game, flt_id), defns_array())

    if rnd(1, 100) <= persona.Offensive and enemy_emp != emp:
        new_target_id, _, _ = get_best_target(
            game, emp, game.GlobalSets.SetOfPlanetsOf[enemy_emp], fleet_power, persona, fleet_data
        )
        if not same_id(new_target_id, empty_quadrant()):
            entry = fleet_entry(game, flt_id, fleet_data)
            if entry is None:
                return
            set_fleet_destination(game, flt_id, get_coord(game, new_target_id))
            entry.Mission = MissionTypes.JumpAttackMSN
            entry.TargetID = new_target_id
            return

    set_fleet_return(game, emp, flt_id, base_id, fleet_data)


def destroy_all_fleets_in_sector(
    game: GameEnvironment, emp: Empire, flt_id: IDNumber, fleet_power: int
) -> bool:
    """Clear enemy fleets out of ``flt_id``'s sector. True if the sector is clear.

    Only fights what it can see -- an unscouted fleet is neither attacked nor
    counted, so the AI can conclude a sector is clear while an enemy sits in
    it. Anything more than twice the AI's power is left alone.
    """
    flt_xy = get_coord(game, flt_id)
    all_destroyed = True

    for i in range(1, MAX_NO_OF_FLEETS + 1):
        if i not in game.GlobalSets.SetOfActiveFleets:
            continue
        enemy_id = IDNumber(ObjectTypes.Flt, i)
        if not (
            same_xy(flt_xy, get_coord(game, enemy_id))
            and get_status(game, enemy_id) != emp
            and scouted(game, emp, enemy_id)
        ):
            continue

        enemy_sh = get_ships(game, enemy_id)
        if fleet_power > (military_power(enemy_sh, defns_array()) // 2):
            result, _ = npe_attack(
                game, flt_id, enemy_id, AttackIntentionTypes.CaptTrnAIT
            )
            if result != AttackResultTypes.DefConqueredART:
                all_destroyed = False
        else:
            all_destroyed = False

    return all_destroyed


def implement_return_msn(game: GameEnvironment, flt_id: IDNumber, target_id: IDNumber) -> None:
    """A returning fleet lands: everything it carries goes to ``target_id``."""
    abort_fleet(game, flt_id, target_id, True)
    destroy_fleet(game, flt_id)


def implement_supply_msn(
    game: GameEnvironment,
    emp: Empire,
    flt_id: IDNumber,
    target_id: IDNumber,
    base_id: IDNumber,
    fleet_data: list,
) -> None:
    """Hand the fleet's whole cargo to ``target_id`` and send it home."""
    flt_sh = get_ships(game, flt_id)
    flt_cr = get_cargo(game, flt_id)
    targ_sh = get_ships(game, target_id)
    targ_cr = get_cargo(game, target_id)

    for car in flt_cr:
        flt_cr[car], targ_cr[car] = move_things(flt_cr[car], flt_cr[car], targ_cr[car])

    change_composition_of_fleet(game, flt_id, target_id, flt_sh, flt_cr, targ_sh, targ_cr)
    set_fleet_return(game, emp, flt_id, base_id, fleet_data)


def implement_refuel_msn(
    game: GameEnvironment, flt_id: IDNumber, target_id: IDNumber
) -> None:
    """A tanker merges into the fleet it came to refuel.

    Everything after the abort works on ``target_id``, which is correct: the
    tanker's trillum has just been unloaded into the target, and the refuel
    then burns that trillum to fill the target's own tanks.

    ORIGINAL BUG, deviated from -- see issue #39. ``RefuelMSN`` is the one
    mission whose target is another *fleet*, and a fleet that reported itself
    out of fuel is quite likely to be gone by the time the tanker arrives. The
    original aborts into it regardless: ``DestroyFleet`` disposes the pointer
    without nilling it, so this reads and writes freed heap. The tanker's cargo
    goes nowhere either way, so the port destroys the tanker and stops --
    the defined behaviour closest to the original's, on the same grounds as
    #30. Without the guard this raises ``AttributeError`` on a normal turn.
    """
    if target_id.Index not in game.GlobalSets.SetOfActiveFleets:
        destroy_fleet(game, flt_id)
        return

    abort_fleet(game, flt_id, target_id, True)
    destroy_fleet(game, flt_id)

    tons_on_ground = get_trillum(game, target_id)
    ships = get_ships(game, target_id)
    flt_fuel = get_fleet_fuel(game, target_id)
    max_fuel = fuel_capacity(ships)
    tons_needed = trunc((max_fuel - flt_fuel) / FUEL_PER_TON) + 1
    max_tri = lesser_int(tons_needed, tons_on_ground)

    refuel_fleet(game, target_id, target_id, max_tri)


def implement_conquer_msn(
    game: GameEnvironment,
    emp: Empire,
    flt_id: IDNumber,
    target_id: IDNumber,
    base_id: IDNumber,
    fleet_data: list,
) -> AttackResultTypes:
    """Take an independent world, if nobody else's fleet is in the way.

    A contested sector is not fought over -- the fleet waits, with a 1-in-4
    chance each year of giving up and going home instead.
    """
    fleets_at_target = get_fleets(game, get_coord(game, target_id))
    fleets_at_target -= game.GlobalSets.SetOfFleetsOf[get_status(game, flt_id)]

    if not fleets_at_target and get_status(game, target_id) == Empire.Indep:
        result, _ = npe_attack(game, flt_id, target_id, AttackIntentionTypes.ConquerAIT)
        should_return = True
    else:
        should_return = rnd(1, 4) == 1
        result = AttackResultTypes.AttRetreatsART

    if should_return:
        set_fleet_return(game, emp, flt_id, base_id, fleet_data)

    return result


def implement_raid_trn_msn(
    game: GameEnvironment,
    emp: Empire,
    flt_id: IDNumber,
    target_id: IDNumber,
    base_id: IDNumber,
    fleet_data: list,
) -> None:
    """Clear the sector, raze any site or gate in it, then loiter.

    ``target_id`` is re-read from whatever is actually in the fleet's sector,
    so the raider hits what it found rather than what it was sent after.
    After five years of waiting it goes home.

    Everything captured is then destroyed -- hunter-killers are the only ships
    that survive the purge, and all cargo is dumped. Raiding denies the enemy
    its transports; it does not enrich the raider.
    """
    fleet_power = military_power(get_ships(game, flt_id), defns_array())
    all_destroyed = destroy_all_fleets_in_sector(game, emp, flt_id, fleet_power)

    target_id = get_object(game, get_coord(game, flt_id))
    if all_destroyed and target_id.ObjTyp in (ObjectTypes.Con, ObjectTypes.Gate):
        npe_attack(game, flt_id, target_id, AttackIntentionTypes.DestTrnAIT)

    entry = fleet_entry(game, flt_id, fleet_data)
    if entry is None:
        return
    if entry.Waiting == 5:
        set_fleet_return(game, emp, flt_id, base_id, fleet_data)
    else:
        entry.Waiting += 1

    ships = get_ships(game, flt_id)
    for shp in (T.fgt, T.jmp, T.jtn, T.pen, T.ssp, T.trn):
        ships[shp] = 0
    put_ships(game, flt_id, ships)
    put_cargo(game, flt_id, cargo_array())


def implement_jump_attack_msn(
    game: GameEnvironment,
    emp: Empire,
    flt_id: IDNumber,
    target_id: IDNumber,
    base_id: IDNumber,
    fleet_data: list,
) -> AttackResultTypes:
    """Clear the sector, soften the world with LAMs, then assault it.

    LAMs only fly if the home base has more than 500 of them and is within 5
    sectors, and the number launched is sized against the target's own
    defenses. They are spent out of the *base's* stock, not the fleet's.

    Returns NoART when the AI declines the fight -- either the defending
    fleets held, or the world turned out to be more than twice the fleet's
    strength -- which is the persona's cue to look elsewhere.
    """
    fleet_power = military_power(get_ships(game, flt_id), defns_array())
    all_destroyed = destroy_all_fleets_in_sector(game, emp, flt_id, fleet_power)

    if not (all_destroyed and get_status(game, target_id) != emp):
        return AttackResultTypes.NoART

    target_xy = get_coord(game, target_id)
    base_xy = get_coord(game, base_id)
    enemy_sh = get_ships(game, target_id)
    enemy_df = get_defns(game, target_id)
    ships = get_ships(game, flt_id)
    defns = get_defns(game, base_id)

    if defns[T.LAM] > 500 and distance(target_xy, base_xy) <= 5:
        lams_to_use = lesser_int(
            defns[T.LAM],
            2 * enemy_df[T.def_] + enemy_df[T.ion] + (enemy_df[T.GDM] // 2),
        )
        # ORIGINAL BUG, preserved -- see issue #40. LAMAttack takes EnemySh and
        # EnemyDf as VAR parameters and overwrites both with what it destroyed.
        # EnemyDf is re-read from the world on the next line; EnemySh never is,
        # so the strength test below weighs the *casualty list* as if it were
        # the garrison. Against a world LAMs only hit defenses, so the ships
        # figure comes back all zeros and the target reads as having no fleet
        # at all -- which is what makes the AI commit.
        enemy_sh, enemy_df = lam_attack(game, emp, lams_to_use, target_id)
        defns[T.LAM] -= lams_to_use
        put_defns(game, base_id, defns)

    enemy_df = get_defns(game, target_id)
    if military_power(ships, defns_array()) > (military_power(enemy_sh, enemy_df) // 2):
        result, _ = npe_attack(game, flt_id, target_id, AttackIntentionTypes.ConquerAIT)
        return result

    return AttackResultTypes.NoART


def implement_stack_msn(game: GameEnvironment, flt_id: IDNumber, fleet_data: list) -> None:
    """Pour a fleet's ships into the guards already parked here.

    Every friendly fleet in the sector already on ``GuardMSN`` takes as much
    as it can hold, capped at 9999 per ship type. If there is room for another
    guard the fleet becomes one; otherwise it is sent off to defend whichever
    nearby world is weakest.
    """
    emp = get_status(game, flt_id)
    active_fleets = get_fleets(game, get_coord(game, flt_id))
    active_fleets = (active_fleets & game.GlobalSets.SetOfFleetsOf[emp]) - {flt_id.Index}

    no_of_guards = 0
    for i in range(1, NO_OF_FLEETS_PER_EMPIRE + 1):
        entry = fleet_data[i]
        if entry.Index in active_fleets and entry.Mission == MissionTypes.GuardMSN:
            no_of_guards += 1
            # ORIGINAL BUG, deviated from -- see issue #39. `_dump_stuff` ends
            # in `change_composition_of_fleet`, which destroys a fleet left
            # with no hulls; pouring everything into the first guard therefore
            # destroys the donor, and the original keeps dumping from it for
            # every remaining guard. The count still advances, exactly as the
            # original's does, so only the freed-memory access is skipped.
            if flt_id.Index not in game.GlobalSets.SetOfActiveFleets:
                continue
            _dump_stuff(game, flt_id, IDNumber(ObjectTypes.Flt, entry.Index))

    if flt_id.Index in game.GlobalSets.SetOfActiveFleets and no_of_guards < MAX_NO_OF_GUARDS:
        fleet_data[npe_data_index(game, flt_id)].Mission = MissionTypes.GuardMSN
    else:
        new_world_id = get_best_planet_to_protect(game, flt_id)
        set_fleet_return(game, emp, flt_id, new_world_id, fleet_data)


def _dump_stuff(game: GameEnvironment, flt_id: IDNumber, guard_id: IDNumber) -> None:
    """Move ships, and the troops riding in them, from one fleet to another.

    Troops follow their transports: handing over a jump transport hands over
    the men it was carrying. The men-per-transport arithmetic differs between
    ``jtn`` and ``trn`` in the original and is transcribed as written.
    """
    flt_sh = get_ships(game, flt_id)
    grd_sh = get_ships(game, guard_id)
    flt_cr = get_cargo(game, flt_id)
    grd_cr = get_cargo(game, guard_id)

    for shp in SHIP_TYPES:
        if flt_sh[shp] + grd_sh[shp] < 9999:
            trans = flt_sh[shp]
        else:
            trans = 9999 - grd_sh[shp]

        flt_sh[shp] -= trans
        grd_sh[shp] += trans

        if shp == T.jtn:
            gat_trn = lesser_int(trans, flt_cr[T.men])
            flt_cr[T.men] -= gat_trn
            grd_cr[T.men] = lesser_int(9999, grd_cr[T.men] + gat_trn)
            trans -= gat_trn

            gat_trn = lesser_int(trans, flt_cr[T.nnj])
            flt_cr[T.nnj] -= gat_trn
            grd_cr[T.nnj] = lesser_int(9999, grd_cr[T.nnj] + gat_trn)
        elif shp == T.trn:
            gat_trn = lesser_int(trans, CargoSpace[T.men] * flt_cr[T.men])
            flt_cr[T.men] -= gat_trn
            grd_cr[T.men] = lesser_int(9999, grd_cr[T.men] + gat_trn)
            trans = greater_int(0, trans - (gat_trn // CargoSpace[T.men]))

            gat_trn = lesser_int(trans, flt_cr[T.nnj])
            flt_cr[T.nnj] -= gat_trn
            grd_cr[T.nnj] = lesser_int(9999, grd_cr[T.nnj] + gat_trn)

    change_composition_of_fleet(game, flt_id, guard_id, flt_sh, flt_cr, grd_sh, grd_cr)


def implement_guard_msn(game: GameEnvironment, flt_id: IDNumber, base_id: IDNumber) -> None:
    """Land a guard fleet's ships onto the world it is guarding.

    The world takes ships up to 9000 of each type; cargo is passed through
    untouched, so troops stay in the fleet even as their transports land.
    """
    flt_sh = get_ships(game, flt_id)
    base_sh = get_ships(game, base_id)
    flt_cr = get_cargo(game, flt_id)
    base_cr = get_cargo(game, base_id)

    for shp in SHIP_TYPES:
        if base_sh[shp] + flt_sh[shp] <= 9000:
            trans = flt_sh[shp]
        else:
            trans = 9000 - base_sh[shp]

        if (flt_sh[shp] - trans) > 9999:
            trans = flt_sh[shp] - 9999

        base_sh[shp] = thg_lmt(base_sh[shp] + trans)
        flt_sh[shp] = thg_lmt(flt_sh[shp] - trans)

    change_composition_of_fleet(game, flt_id, base_id, flt_sh, flt_cr, base_sh, base_cr)


def mid_course_correction(
    game: GameEnvironment, emp: Empire, flt_id: IDNumber, rcap: list[IDNumber], fleet_data: list
) -> None:
    """Redirect a fleet whose destination fell to somebody else while in transit.

    Only returning fleets are checked -- a fleet on its way to attack is
    expected to find its target hostile.

    ``get_regional_capital`` is passed the *fleet* rather than the lost world,
    so the new destination is the capital nearest where the fleet is now.
    """
    entry = fleet_data[npe_data_index(game, flt_id)]
    if entry.Mission == MissionTypes.ReturnMSN and get_status(game, entry.TargetID) != emp:
        base_id = get_regional_capital(game, flt_id, rcap)
        set_fleet_destination(game, flt_id, get_coord(game, base_id))
        entry.TargetID = base_id


def plunder_world(game: GameEnvironment, emp: Empire, flt_id: IDNumber, target_id: IDNumber) -> None:
    """Strip a just-conquered world bare and abandon it to independence.

    Only runs if the attack actually took the world. Everything portable goes
    into the fleet, whatever will not fit is jettisoned by ``balance_fleet``,
    and the world is left as an independent industrial world with nothing on
    it. This is how the raider personas turn conquest into cargo rather than
    territory.
    """
    if emp != get_status(game, target_id):
        return

    flt_sh = get_ships(game, flt_id)
    target_sh = get_ships(game, target_id)
    flt_cr = get_cargo(game, flt_id)
    target_cr = get_cargo(game, target_id)

    add_things(flt_sh, flt_cr, target_sh, target_cr)
    balance_fleet(flt_sh, flt_cr)
    put_ships(game, flt_id, flt_sh)
    put_cargo(game, flt_id, flt_cr)

    put_ships(game, target_id, ship_array())
    put_cargo(game, target_id, cargo_array())

    set_type(game, target_id, WT.IndTyp)
    set_status(game, target_id, Empire.Indep)


# --- Diplomacy ---------------------------------------------------------------


def state_department(
    game: GameEnvironment,
    emp: Empire,
    persona: NPECharacterRecord,
    state: dict[Empire, StateDeptRecord],
) -> None:
    """Move policy toward each other empire up or down the escalation ladder.

    Power is compared per-world rather than in total, so a small dense empire
    can out-rank a sprawling weak one. ``Balance`` short-circuits everything:
    an AI that has lost ground goes straight to Preempt or Conflict without
    consulting its own temperament.

    ORIGINAL BUG, preserved -- see issue #27. ``Aggressiveness`` is a Pascal
    ``Index`` (0..100) decremented by 1 or 2 every year with no floor. Once it
    reaches zero it underflows, and the port keeps it unsigned to match: every
    de-escalation test (``Aggressiveness < 10/15/20``) then fails permanently
    while ``> 80`` starts passing, so a long-quiet AI can never stand down.
    """
    if state[emp].Worlds == 0:
        useful_power = float(state[emp].TotalMilitary)
    else:
        useful_power = state[emp].TotalMilitary / state[emp].Worlds

    for enemy_emp in PLAYER_EMPIRES:
        if not empire_active(game, enemy_emp) or enemy_emp == emp:
            continue

        rec = state[enemy_emp]
        if rec.Worlds == 0:
            enemy_power = float(rec.TotalMilitary)
        else:
            enemy_power = rec.TotalMilitary / rec.Worlds

        new_policy = rec.Policy
        offensive = persona.Offensive

        if rec.Balance < -1:
            new_policy = PolicyTypes.ConflictPLT
        elif rec.Balance < 0:
            new_policy = PolicyTypes.PreemptPLT
        elif rec.Policy == PolicyTypes.NeutralPLT:
            if (
                useful_power > enemy_power
                and useful_power > 10
                and rec.ThreatAssess > 50
                and rnd(1, 100) < offensive
            ):
                new_policy = PolicyTypes.HarassPLT
            elif (
                useful_power > 3 * enemy_power
                and useful_power > 30
                and rec.ThreatAssess > 75
                and rnd(1, 100) < offensive // 2
            ):
                new_policy = PolicyTypes.PreemptPLT
        elif rec.Policy == PolicyTypes.HarassPLT:
            if (
                useful_power > enemy_power
                and useful_power > 30
                and rec.ThreatAssess > 50
                and rnd(1, 100) < offensive
            ):
                new_policy = PolicyTypes.PreemptPLT
            elif (
                useful_power > 3 * enemy_power
                and useful_power > 30
                and rec.ThreatAssess > 75
                and rnd(1, 100) < offensive
            ):
                new_policy = PolicyTypes.PreemptPLT
            elif rec.Aggressiveness < 10 and rnd(1, 100) > offensive:
                new_policy = PolicyTypes.NeutralPLT
            elif useful_power < 5:
                new_policy = PolicyTypes.NeutralPLT
        elif rec.Policy == PolicyTypes.PreemptPLT:
            if useful_power > enemy_power and rec.ThreatAssess > 50 and rnd(1, 100) < offensive:
                new_policy = PolicyTypes.ConflictPLT
            elif (
                useful_power > 4 * enemy_power
                and rec.ThreatAssess > 50
                and rnd(1, 100) < offensive
            ):
                new_policy = PolicyTypes.ConflictPLT
            elif (
                rec.Aggressiveness < 15
                and rec.ThreatAssess < 50
                and rnd(1, 100) > offensive
            ):
                new_policy = PolicyTypes.NeutralPLT
            elif useful_power < 10:
                new_policy = PolicyTypes.HarassPLT
        elif rec.Policy == PolicyTypes.ConflictPLT:
            if (
                rec.Aggressiveness < 20
                and rec.ThreatAssess < 50
                and rnd(1, 100) > offensive
            ):
                new_policy = PolicyTypes.NeutralPLT
            elif rec.Aggressiveness > 80 and enemy_power > 2 * useful_power:
                new_policy = PolicyTypes.NeutralPLT

        rec.Policy = new_policy
        rec.Aggressiveness = _index_dec(rec.Aggressiveness, rnd(1, 2))


def _index_dec(value: int, amount: int) -> int:
    """Decrement a Pascal ``Index`` (0..100) the way the DOS build did.

    Turbo Pascal stores the subrange in a byte and, with range checking off,
    wraps rather than clamping. Reproduced so the underflow in
    :func:`state_department` behaves as it did; see issue #27.
    """
    return (value - amount) % 256


def state_dept_report(
    game: GameEnvironment, emp: Empire, state: dict[Empire, StateDeptRecord]
) -> None:
    """Refresh military strength, world counts and threat scores for everyone.

    Military strength counts ships in thousands, so an empire with fewer than
    500 of a type contributes nothing for it -- small navies round away
    entirely. Threat starts at 50 and is scaled by shipyard industry and by
    relative military strength.

    ORIGINAL BUG, preserved -- see issue #28. The per-enemy tech lookup reads
    ``GetCapital(Emp, ...)`` -- the AI's *own* capital -- instead of the
    enemy's. ``Tech`` therefore always equals ``EmpireTech``, so both arms of
    the tech comparison are dead and technology never affects threat.
    """
    planets, _, empire_s_ind, total_ships = get_empire_status(game, emp)

    empire_military = 1
    for shp in SHIP_TYPES:
        empire_military += pascal_round(total_ships[shp] / 1000) * MPower[shp]

    state[emp].TotalMilitary = empire_military
    state[emp].Worlds = planets

    empire_tech = get_tech(game, get_capital(game, emp))

    for enemy_emp in PLAYER_EMPIRES:
        if not empire_active(game, enemy_emp) or enemy_emp == emp:
            continue

        rec = state[enemy_emp]
        worlds, _, s_ind, total_ships = get_empire_status(game, enemy_emp)
        rec.Worlds = worlds

        rec.TotalMilitary = 1
        for shp in SHIP_TYPES:
            rec.TotalMilitary += pascal_round(total_ships[shp] / 1000) * MPower[shp]

        tech = get_tech(game, get_capital(game, emp))

        threat = 50.0
        if tech > empire_tech:
            threat = threat * 1.5
        elif tech < empire_tech:
            threat = threat * 0.75

        threat = threat * (1 + ((s_ind - empire_s_ind) / 5))
        threat = threat * (rec.TotalMilitary / empire_military)

        rec.ThreatAssess = 100 if threat > 100 else pascal_round(threat)


# --- Miscellaneous -----------------------------------------------------------


def set_empire_defenses(game: GameEnvironment, emp: Empire) -> None:
    """Roll one of the four defense distributions for the empire.

    Half the time the AI keeps the game's default spread; the rest of the time
    it commits to massed orbit, layered shells, or the balanced arrangement.
    """
    roll = rnd(1, 100)
    if roll <= 25:
        set_defense_settings(game, emp, init_defense_record())
    elif roll <= 75:
        set_defense_settings(game, emp, DEFENSE_1)
    elif roll <= 85:
        set_defense_settings(game, emp, DEFENSE_3)
    else:
        set_defense_settings(game, emp, DEFENSE_2)


__all__ = [
    "DEFENSE_1",
    "DEFENSE_2",
    "DEFENSE_3",
    "MAX_NO_OF_GUARDS",
    "MAX_NO_OF_RAIDERS",
    "MAX_NO_OF_REGIONS",
    "NPEClassValue",
    "NPETypeDefault",
    "NPETypeValue",
    "already_targetted",
    "average_military_power",
    "create_region_array",
    "deploy_battle_fleet",
    "deploy_cargo_fleet",
    "deploy_harass_fleet",
    "deploy_hk_raiders",
    "deploy_jump_attack",
    "deploy_slow_attack",
    "destroy_all_fleets_in_sector",
    "enforce_npe_data_links",
    "get_best_base",
    "get_best_planet_to_protect",
    "get_best_raider_target",
    "get_best_target",
    "get_fleet_composition",
    "get_new_designation",
    "get_potential_res",
    "get_regional_capital",
    "implement_conquer_msn",
    "implement_guard_msn",
    "implement_jump_attack_msn",
    "implement_raid_trn_msn",
    "implement_refuel_msn",
    "implement_return_msn",
    "implement_stack_msn",
    "implement_supply_msn",
    "mid_course_correction",
    "minimum_defense",
    "next_fleet_data_slot",
    "plunder_world",
    "redesignate_empire",
    "set_empire_defenses",
    "set_fleet_return",
    "set_raiding_fleet_new_target",
    "state_department",
    "state_dept_report",
]
