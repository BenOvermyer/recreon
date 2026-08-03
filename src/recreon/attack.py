"""Combat mechanics.

Port of ATTACK.PAS.

An attack is fought by *groups*. The attacking fleet is split into one group
per ship type (:func:`default_distribution`), and each group occupies one of
the five orbital shells -- DpSpc, HiOrb, Orbit, SbOrb, Grnd -- working inwards.
The defender is flattened into an :class:`EnemyArray`, a count of everything it
has at each shell. :func:`battle` resolves one round at one shell; the driver
that loops over shells and rounds is in :mod:`recreon.attnpe`.

Within a round the sequence is fixed and each step feeds the next:

1. :func:`get_conflict` -- which groups are at this shell.
2. ``get_target_array`` -- how the defender's units split across those groups.
   Priority runs in two passes: how valuable each group is, then how well each
   defending type does against it. LAMs and GDMs are *spent* here, not in the
   exchange proper, so the counts they draw down are gone whether or not they
   destroy anything.
3. :func:`group_attack` -- what the groups destroy.
4. :func:`enemy_attack` -- what the defender destroys.
5. Both sides' losses are applied, attacker first.

Both sides fire on the pre-round state, so an exchange is simultaneous: a
group that is wiped out still gets its shots off.

Several tables live here rather than in :mod:`recreon.datacnst` because the
original declares them inside ATTACK.PAS, not DATACNST.PAS -- ``CombatTechAdj``
notably, despite what one might expect from its size and shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING

from .datacnst import (
    CargoSpace,
    CombatTable,
    ProtecNeeded,
    ProtecOffered,
    ShipValue,
    TechDev,
    TrnAdj,
    WeapEff,
)
from .fleet import abort_fleet, destroy_fleet, fleet_name_destruction
from .galaxy import Location, limbo
from .intrface import (
    balance_fleet,
    destroy_construction,
    destroy_empire,
    destroy_stargate,
    scout,
)
from .misc import (
    distance,
    fleet_cargo_space,
    fuel_capacity,
    military_power,
    no_ships,
    same_id,
    thg_lmt,
)
from .news import NewsTypes, add_global_news, add_news
from .primintr import (
    centralized_capital,
    change_rev_index,
    change_total_rev_index,
    empire_player,
    get_base_type,
    get_capital,
    get_cargo,
    get_class,
    get_coord,
    get_defense_settings,
    get_defns,
    get_efficiency,
    get_empire_technology,
    get_fleet_fuel,
    get_indus,
    get_population,
    get_rev_index,
    get_ships,
    get_status,
    get_tech,
    get_type,
    put_cargo,
    put_defns,
    put_indus,
    put_ships,
    scouted,
    set_capital,
    set_efficiency,
    set_empire_technology,
    set_fleet_fuel,
    set_population,
    set_status,
    set_tech,
    set_type,
    type_of_fleet,
)
from .types import (
    ATTACK_TYPES,
    DEFNS_TYPES,
    SHIP_TYPES,
    Empire,
    FleetTypes,
    IDNumber,
    IndusTypes,
    ObjectTypes,
    ShellPos,
    TechLevel,
    TechnologyTypes,
    WorldClass,
    WorldTypes,
    defns_array,
    empty_quadrant,
    indus_array,
    ship_array,
    tech_range,
)
from .utils.int_utils import greater_int, int_lmt, lesser_int, rnd
from .utils.pascal import pascal_random, pascal_round, trunc

if TYPE_CHECKING:
    from .environ import GameEnvironment

T = TechnologyTypes
TL = TechLevel

MAX_NO_OF_GROUPS = 9


# --- Types -------------------------------------------------------------------


class AttackIntentionTypes(IntEnum):
    NoAIT = 0
    ConquerAIT = 1  # conquer world
    DestTrnAIT = 2  # destroy transports
    CaptTrnAIT = 3  # capture transports


class AttackResultTypes(IntEnum):
    NoART = 0
    AttDestroyedART = 1
    AttRetreatsART = 2
    DefConqueredART = 3
    DefCapturedART = 4


class HoloResultTypes(IntEnum):
    NoHRT = 0
    WorldSurrendersHRT = 1
    WorldDestroyedHRT = 2


class GroupStatus(IntEnum):
    GReady = 0
    GAdvc = 1
    GRtrt = 2
    GDst = 3


@dataclass(slots=True)
class CombatDataRecord:
    """The fixed modifiers for one engagement, computed once up front."""

    DTyp: ObjectTypes = ObjectTypes.Void
    DTech: TechLevel = TechLevel.PreTchLvl
    AShipAdj: int = 0
    DShipAdj: int = 0
    DGrndAdj: int = 0
    MaxGDM: int = 0
    RevIndex: int = 0


@dataclass(slots=True)
class GroupRecord:
    """One homogeneous formation of the attacking fleet."""

    Typ: TechnologyTypes = T.NoRes
    Num: int = 0
    Trg: TechnologyTypes = T.NoRes
    Pos: ShellPos = ShellPos.DpSpc
    Sta: GroupStatus = GroupStatus.GReady
    #: Ground assault troops riding along, and their type.
    GAT: int = 0
    GATTyp: TechnologyTypes = T.NoRes
    #: Where ``Typ`` is parked while the group is fighting as its troops.
    TrnTyp: TechnologyTypes = T.NoRes
    #: For hunter-killers, whether the cloak has been dropped.
    Flg: bool = False


def attack_array() -> dict[TechnologyTypes, int]:
    """Pascal ``AttackArray = ARRAY [AttackTypes] OF Resources``."""
    return dict.fromkeys(ATTACK_TYPES, 0)


def group_array() -> list[GroupRecord | None]:
    """Pascal ``ARRAY [1..MaxNoOfGroups]``; index 0 is unused."""
    return [None] + [GroupRecord() for _ in range(MAX_NO_OF_GROUPS)]


def enemy_array() -> dict[ShellPos, dict[TechnologyTypes, int]]:
    """Everything the defender has, counted per orbital shell."""
    return {shell: attack_array() for shell in ShellPos}


def detail_array() -> dict[TechnologyTypes, list[int]]:
    """Damage each attack type did to each group.

    Pascal indexes ``[AttackTypes, 0..MaxNoOfGroups]``; slot 0 is not a group
    but a flag saying this attack type did damage to something.
    """
    return {thing: [0] * (MAX_NO_OF_GROUPS + 1) for thing in ATTACK_TYPES}


# --- Tables ------------------------------------------------------------------

#: Military power of each weapon, 1..100, used only by the surrender test.
#: Distinct from ``datacnst.MPower``, which serves the same idea elsewhere.
CombatPower: dict[TechnologyTypes, int] = dict(
    zip(
        ATTACK_TYPES,
        # None LAM def GDM ion fgt hkr jmp jtn pen ssp trn men  nnj
        (0, 80, 75, 20, 65, 2, 15, 10, 1, 20, 100, 1, 20, 100),
        strict=True,
    )
)

#: Destructive power of attacker tech vs defender tech, as a percentage.
#: 100 is no adjustment; above 100 favours the attacker, below it the defender.
CombatTechAdj: dict[TechLevel, dict[TechLevel, int]] = {
    attacker: dict(zip(TechLevel, row, strict=True))
    for attacker, row in zip(
        TechLevel,
        (
            #  pt    p   pa    a   pw    w    j    b    s   pg    g
            (100, 90, 50, 25, 10, 5, 3, 1, 1, 1, 1),  # pt
            (120, 100, 80, 40, 25, 10, 5, 3, 1, 1, 1),  # p
            (150, 110, 100, 60, 40, 25, 10, 5, 3, 1, 1),  # pa
            (160, 140, 130, 100, 60, 40, 30, 20, 10, 5, 3),  # a
            (200, 170, 145, 120, 100, 90, 85, 75, 70, 55, 45),  # pw
            (250, 200, 175, 140, 110, 100, 95, 90, 85, 70, 55),  # w
            (280, 210, 190, 175, 115, 110, 100, 97, 93, 80, 70),  # j
            (320, 250, 210, 195, 120, 115, 105, 100, 95, 90, 80),  # b
            (360, 320, 280, 220, 125, 120, 115, 110, 100, 97, 90),  # s
            (500, 400, 300, 250, 130, 125, 120, 115, 110, 100, 95),  # pg
            (530, 415, 310, 260, 135, 130, 125, 120, 115, 110, 100),  # g
        ),
        strict=True,
    )
}

#: How much the terrain of each world class helps its ground defenders.
CombatClassAdj: dict[WorldClass, int] = dict(
    zip(
        WorldClass,
        (
            100,  # AmbCls
            100,  # ArdCls
            100,  # ArtCls
            50,  # BarCls
            100,  # ClsJ
            100,  # ClsK
            100,  # ClsL
            100,  # ClsM
            140,  # DrtCls
            100,  # EthCls
            140,  # FstCls
            50,  # GsGCls
            100,  # HLfCls
            160,  # IceCls
            150,  # JngCls
            80,  # OcnCls
            100,  # ParCls
            60,  # PsnCls
            100,  # RnsCls
            130,  # UndCls
            100,  # TerCls
            120,  # VlcCls
        ),
        strict=True,
    )
)

#: The same, for the four starbase types.
CombatBaseAdj: dict[TechnologyTypes, int] = dict(
    zip(
        tech_range(T.cmm, T.out),
        # cmm  frt  cmp  out
        (150, 250, 100, 125),
        strict=True,
    )
)

#: Ground-defense missiles a world can put up at once, by tech level.
GDMLaunch: dict[TechLevel, int] = dict(
    zip(
        TechLevel,
        #  pt  p  pa   a   pw    w     j     b     s    pg    g
        (0, 0, 0, 20, 217, 662, 1013, 1261, 2163, 2644, 2759),
        strict=True,
    )
)

#: GDMs shot down on approach per 10 ships, by the ship type being attacked.
GDMKill: dict[TechnologyTypes, int] = dict(
    zip(
        SHIP_TYPES,
        # fgt hkr jmp jtn pen ssp trn
        (0, 3, 2, 1, 15, 20, 0),
        strict=True,
    )
)


# --- Group movement ----------------------------------------------------------


def advance_groups(no_of_groups: int, gp: list[GroupRecord | None]) -> None:
    """Move every group that decided to advance or retreat last round.

    A transport group reaching the ground stops being transports and becomes
    its troops: ``Num`` and ``GAT`` swap, ``Typ`` and ``GATTyp`` swap, and the
    group starts shooting at ``men``. The transports are not gone -- they are
    parked in ``GAT``/``TrnTyp`` -- but from here on the group fights as
    infantry, and casualties come off the troops.
    """
    for i in range(1, no_of_groups + 1):
        group = gp[i]
        if group.Sta == GroupStatus.GAdvc:
            group.Pos = ShellPos(int(group.Pos) + 1)
            group.Sta = GroupStatus.GReady
            if group.Pos == ShellPos.Grnd and group.GAT != 0:
                group.Num, group.GAT = group.GAT, group.Num
                group.TrnTyp = group.Typ
                group.Typ = group.GATTyp
                group.Trg = T.men
        elif group.Sta == GroupStatus.GRtrt:
            group.Pos = ShellPos(int(group.Pos) - 1)
            group.Sta = GroupStatus.GReady


def all_groups_destroyed(no_of_groups: int, gp: list[GroupRecord | None]) -> bool:
    """Whether the attacking fleet has been wiped out."""
    i = no_of_groups
    while i > 0 and gp[i].Sta == GroupStatus.GDst:
        i -= 1
    return i == 0


def enemy_surrenders(
    no_of_groups: int,
    gp: list[GroupRecord | None],
    en: dict[ShellPos, dict[TechnologyTypes, int]],
    casualties: dict[TechnologyTypes, int],
    killed: dict[TechnologyTypes, int],
    combat_data: CombatDataRecord,
) -> bool:
    """Whether the defender gives up.

    Fleets and worlds are judged on different things. A fleet surrenders on
    the exchange rate -- it is losing far worse than it is giving, and is
    outgunned. A world surrenders on whether the attacker can actually take
    the ground: troop strength against defending troops, tempered by how
    restive the population already was and capped by tech, since a
    star-faring world will not capitulate to an army it can still out-shoot.
    """
    # Attacking troop strength. Transports count for their carrying capacity
    # while still in space, and for their actual troops once landed, because
    # advance_groups has by then rewritten Typ to men or nnj.
    pl_gat = 0.0
    pl_sh_pow = 0.0  # attacking firepower
    for i in range(1, no_of_groups + 1):
        group = gp[i]
        if group.Sta == GroupStatus.GDst:
            continue
        if group.Typ == T.nnj:
            pl_gat += 5.0 * group.Num
        elif group.Typ == T.men:
            pl_gat += group.Num
        elif group.Typ == T.trn:
            pl_gat += group.Num / 5
        elif group.Typ == T.jtn:
            pl_gat += group.Num / 2
        else:
            pl_sh_pow += CombatPower[group.Typ] * (group.Num / 100)

    pl_gat = pl_gat * combat_data.AShipAdj / 100
    pl_sh_pow = pl_sh_pow * combat_data.AShipAdj / 100

    en_sh_pow = 0.0  # all defending firepower
    at_sh_pow = 0.0  # the part of it that can shoot back at ships
    for pos in ShellPos:
        for thing in tech_range(T.LAM, T.trn):
            power = CombatPower[thing] * (en[pos][thing] / 100)
            en_sh_pow += power
            # Transports contribute to the total but cannot contest space.
            if thing not in (T.jtn, T.trn):
                at_sh_pow += power

    en_men = float(en[ShellPos.Grnd][T.men] + 5.0 * en[ShellPos.Grnd][T.nnj])

    en_men = en_men * combat_data.DGrndAdj / 100
    en_sh_pow = en_sh_pow * combat_data.DShipAdj / 100

    att_killed = 0.0
    def_killed = 0.0
    for thing in tech_range(T.LAM, T.trn):
        att_killed += (CombatPower[thing] / 100) * casualties[thing]
        def_killed += (CombatPower[thing] / 100) * killed[thing]

    att_a = att_killed / pl_sh_pow if pl_sh_pow > 0 else 0.0
    def_a = def_killed / en_sh_pow if en_sh_pow > 0 else 0.0

    if combat_data.DTyp == ObjectTypes.Flt:
        if def_a > att_a * 2 and en_sh_pow < pl_sh_pow / 3:
            return True
        if def_a > 0 and att_a == 0 and pl_sh_pow > at_sh_pow:
            return True
        return en_sh_pow == 0

    if combat_data.RevIndex > 70 and pl_gat > en_men and pl_sh_pow > at_sh_pow:
        return True
    if en_men == 0 and pl_gat > 0:
        return True
    atomic_to_warp = tech_range(TL.AtomicLvl, TL.WrpTchLvl)
    if (
        at_sh_pow < pl_sh_pow / 2
        and en_men < pl_gat / 2
        and def_a > att_a
        and combat_data.DTech in atomic_to_warp
    ):
        return True
    if en_men < pl_gat / 4 and combat_data.DTech in atomic_to_warp:
        return True
    return (
        def_a > att_a * 2
        and en_men < pl_gat / 2
        and combat_data.DTech in tech_range(TL.WrpTchLvl, TL.JmpTchLvl)
    )


def calculate_combat_data(
    game: GameEnvironment,
    attacker: Empire,
    flt_id: IDNumber,
    target_id: IDNumber,
) -> CombatDataRecord:
    """Work out the fixed modifiers for an engagement.

    The attacker's tech comes from its *capital*, not from the fleet, so a
    backwater raid is fought at empire standard. A fleet defender is likewise
    rated at its empire's tech rather than any world's.
    """
    combat_data = CombatDataRecord()
    combat_data.DTyp = target_id.ObjTyp

    cap_id = get_capital(game, attacker)
    a_tech = get_tech(game, cap_id)
    if combat_data.DTyp == ObjectTypes.Flt:
        combat_data.DTech, _ = get_empire_technology(game, get_status(game, target_id))
    else:
        combat_data.DTech = get_tech(game, target_id)

    combat_data.AShipAdj = CombatTechAdj[a_tech][combat_data.DTech]
    combat_data.DShipAdj = CombatTechAdj[combat_data.DTech][a_tech]
    combat_data.DGrndAdj = combat_data.DShipAdj

    if combat_data.DTyp == ObjectTypes.Base:
        combat_data.DGrndAdj = pascal_round(
            (combat_data.DGrndAdj / 100) * CombatBaseAdj[get_base_type(game, target_id)]
        )
    elif combat_data.DTyp == ObjectTypes.Flt:
        combat_data.DGrndAdj = 0
    else:
        combat_data.DGrndAdj = pascal_round(
            (combat_data.DGrndAdj / 100) * CombatClassAdj[get_class(game, target_id)]
        )

    combat_data.MaxGDM = GDMLaunch[combat_data.DTech]

    if combat_data.DTyp == ObjectTypes.Pln:
        combat_data.RevIndex = get_rev_index(game, target_id)
    else:
        combat_data.RevIndex = 0

    return combat_data


# --- One round of battle -----------------------------------------------------


def get_conflict(
    cur_pos: ShellPos, no_of_groups: int, gp: list[GroupRecord | None]
) -> set[int]:
    """Indices of the surviving groups at ``cur_pos``."""
    return {
        i
        for i in range(1, no_of_groups + 1)
        if gp[i].Pos == cur_pos and gp[i].Sta != GroupStatus.GDst
    }


def total_protection(
    no_of_groups: int, gp: list[GroupRecord | None], attacking_groups: set[int]
) -> float:
    """Cover the engaged groups give each other.

    Only groups that have picked a target count -- an idle escort protects
    nobody -- and troops never do.
    """
    total = 0.0
    for i in range(1, no_of_groups + 1):
        if i not in attacking_groups:
            continue
        group = gp[i]
        if group.Trg != T.NoRes and group.Typ != T.men and group.Typ != T.nnj:
            total += ProtecOffered[group.Typ] * group.Num
    return total


def ships_destroyed(
    number_attacking: int,
    attacker: TechnologyTypes,
    defender: TechnologyTypes,
    adj: int,
) -> int:
    """Units of ``defender`` that ``number_attacking`` ``attacker``s destroy.

    ``adj`` is the *defender's* adjustment for tech and terrain -- higher
    means a tougher defender, so it divides. The fractional remainder is
    resolved by a die roll rather than dropped, which is what makes small
    forces able to score at all.
    """
    temp = number_attacking * (CombatTable[attacker][defender] / 100)

    if adj == 0:
        adj = 1
    temp = 100 * (temp / adj)

    whole = int_lmt(temp)
    remainder = (temp - whole) * 100

    if remainder > 100:
        # int_lmt clamped, so there is no fraction left to round up.
        remainder = 0

    if rnd(1, 100) < remainder:
        whole += 1

    return thg_lmt(whole)


def get_target_array(
    cur_pos: ShellPos,
    no_of_groups: int,
    gp: list[GroupRecord | None],
    attacking_groups: set[int],
    en: dict[ShellPos, dict[TechnologyTypes, int]],
    killed: dict[TechnologyTypes, int],
    combat_data: CombatDataRecord,
) -> list[dict[TechnologyTypes, int]]:
    """Decide how the defender's units split across the attacking groups.

    Returns a 1-based array, one entry per group, of how many of each
    defending type are shooting at it.

    Mutates ``en`` and ``killed``: LAMs and GDMs are expended when they launch,
    so they are removed from the defender and booked as killed here, before
    anything is resolved. They then count against the groups even if the
    launch achieves nothing.
    """
    targ: list[dict[TechnologyTypes, int]] = [{}] + [
        attack_array() for _ in range(MAX_NO_OF_GROUPS)
    ]
    priority1 = [0] * (MAX_NO_OF_GROUPS + 1)
    priority2 = [attack_array() for _ in range(MAX_NO_OF_GROUPS + 1)]

    _build_priority1(no_of_groups, gp, attacking_groups, combat_data, priority1)
    _build_priority2(no_of_groups, gp, attacking_groups, priority1, priority2)
    _build_target_array(cur_pos, no_of_groups, gp, en, combat_data, killed, priority2, targ)
    return targ


def _build_priority1(
    no_of_groups: int,
    gp: list[GroupRecord | None],
    attacking_groups: set[int],
    combat_data: CombatDataRecord,
    priority1: list[int],
) -> None:
    """Rate each group by how badly the defender wants it dead.

    Value scales with what the group is worth, then three corrections apply:
    transports get more urgent the closer they are to the surface (they must
    be stopped before they land), starships get *less* urgent as they close
    (they are worth killing at range, where they do their damage), and a group
    under cover is discounted by how well it is covered. A cloaked
    hunter-killer that has not fired is invisible and drops to zero.

    The table is finally scaled to sum to 1000.
    """
    cover = total_protection(no_of_groups, gp, attacking_groups)
    total = 0.0

    for i in range(1, no_of_groups + 1):
        if i not in attacking_groups:
            continue
        group = gp[i]
        priority1[i] = pascal_round((ShipValue[group.Typ] / 1000) * group.Num) + 1

        if group.Typ in (T.trn, T.jtn) and combat_data.DTyp != ObjectTypes.Flt:
            priority1[i] = int_lmt(priority1[i] * (1.0 + int(group.Pos)))
        elif group.Typ == T.ssp:
            priority1[i] = int_lmt(priority1[i] * (16.0 - 2 * int(group.Pos)))

        if group.Trg == T.NoRes and group.Typ != T.men and group.Typ != T.nnj:
            per_cent_cover = int_lmt(
                ((cover / group.Num) / ProtecNeeded[group.Typ]) * 100
            )
            per_cent_cover = min(per_cent_cover, 100)
            priority1[i] = pascal_round(priority1[i] * (1 - per_cent_cover / 100))

        if group.Trg == T.NoRes and group.Typ == T.hkr and not group.Flg:
            priority1[i] = 0

        total += priority1[i]

    if total == 0:
        total = 1

    for i in range(1, no_of_groups + 1):
        priority1[i] = pascal_round((priority1[i] / total) * 1000)


def _build_priority2(
    no_of_groups: int,
    gp: list[GroupRecord | None],
    attacking_groups: set[int],
    priority1: list[int],
    priority2: list[dict[TechnologyTypes, int]],
) -> None:
    """Refine priority per defending type: who is best placed to shoot what.

    Jumpships fare better against fighters than penetrators do, so they weight
    towards them. Carrying priority1 through means a starship still draws fire
    from things that struggle to hurt it. Each column is scaled to sum to 1000.
    """
    for i in range(1, no_of_groups + 1):
        if i not in attacking_groups:
            continue
        group = gp[i]
        for thing in tech_range(T.LAM, T.nnj):
            priority2[i][thing] = pascal_round(
                priority1[i] * (CombatTable[thing][group.Typ] / WeapEff[thing])
            )

    for thing in tech_range(T.LAM, T.nnj):
        total = 0
        for i in range(1, no_of_groups + 1):
            total += priority2[i][thing]
        if total == 0:
            total = 1
        for i in range(1, no_of_groups + 1):
            priority2[i][thing] = pascal_round((priority2[i][thing] / total) * 1000)


def _build_target_array(
    cur_pos: ShellPos,
    no_of_groups: int,
    gp: list[GroupRecord | None],
    en: dict[ShellPos, dict[TechnologyTypes, int]],
    combat_data: CombatDataRecord,
    killed: dict[TechnologyTypes, int],
    priority2: list[dict[TechnologyTypes, int]],
    targ: list[dict[TechnologyTypes, int]],
) -> None:
    """Turn the priority weights into actual counts of defenders per group.

    Each defending type is only present at the shells it can reach: satellites
    cover HiOrb and Orbit, ion cannons only SbOrb, troops only the ground.
    LAMs and GDMs are the exception -- they launch from SbOrb at whatever is
    within reach, so they are drawn down from the defender's stock here.
    """
    for thing in SHIP_TYPES:
        for i in range(1, no_of_groups + 1):
            targ[i][thing] = pascal_round((priority2[i][thing] / 1000) * en[cur_pos][thing])

    if cur_pos == ShellPos.Grnd:
        for i in range(1, no_of_groups + 1):
            targ[i][T.men] = pascal_round(
                (priority2[i][T.men] / 1000) * en[ShellPos.Grnd][T.men]
            )
            targ[i][T.nnj] = pascal_round(
                (priority2[i][T.nnj] / 1000) * en[ShellPos.Grnd][T.nnj]
            )

    if cur_pos in (ShellPos.HiOrb, ShellPos.Orbit):
        for i in range(1, no_of_groups + 1):
            targ[i][T.def_] = pascal_round(
                (priority2[i][T.def_] / 1000) * en[ShellPos.Orbit][T.def_]
            )

    if cur_pos == ShellPos.SbOrb:
        for i in range(1, no_of_groups + 1):
            targ[i][T.ion] = pascal_round(
                (priority2[i][T.ion] / 1000) * en[ShellPos.SbOrb][T.ion]
            )

    # LAMs. The defender launches as many as the groups warrant, capped by
    # stock; they are spent whatever happens.
    no_of_lam = 0
    for i in range(1, no_of_groups + 1):
        if priority2[i][T.LAM] != 0:
            group = gp[i]
            no_of_lam = thg_lmt(
                no_of_lam
                + (group.Num * ((100 + rnd(0, 100)) / CombatTable[T.LAM][group.Typ]))
            )
    no_of_lam = lesser_int(no_of_lam, en[ShellPos.SbOrb][T.LAM])

    en[ShellPos.SbOrb][T.LAM] -= no_of_lam
    killed[T.LAM] += no_of_lam
    for i in range(1, no_of_groups + 1):
        targ[i][T.LAM] = pascal_round((priority2[i][T.LAM] / 1000) * no_of_lam)

    # GDMs only reach Orbit, and the ships they pass through shoot some down.
    if cur_pos == ShellPos.Orbit:
        no_of_gdm = 0
        for i in range(1, no_of_groups + 1):
            if priority2[i][T.GDM] != 0:
                group = gp[i]
                no_of_gdm = thg_lmt(
                    no_of_gdm
                    + (group.Num * ((100 + rnd(0, 100)) / CombatTable[T.GDM][group.Typ]))
                )

        no_of_gdm = lesser_int(no_of_gdm, combat_data.MaxGDM + rnd(0, 10))
        no_of_gdm = lesser_int(no_of_gdm, en[ShellPos.SbOrb][T.GDM])

        en[ShellPos.SbOrb][T.GDM] -= no_of_gdm
        killed[T.GDM] += no_of_gdm
        for i in range(1, no_of_groups + 1):
            group = gp[i]
            gdm_at_target = pascal_round((priority2[i][T.GDM] / 1000) * no_of_gdm)
            gdm_at_target -= pascal_round((GDMKill[group.Typ] / 10) * group.Num)
            targ[i][T.GDM] = max(gdm_at_target, 0)


def _in_range_of_defense(
    attacker: TechnologyTypes, target: TechnologyTypes, attacking_from: ShellPos
) -> bool:
    """Whether a group at ``attacking_from`` can reach the defending type.

    Fixed defenses can only be hit from the shell they sit in. Ion cannons are
    the odd one: reachable from SbOrb by anything but a fighter, and always
    from the ground. Troops can be hit from orbit only by penetrators and
    starships. Anything not listed -- ships, and no target at all -- is always
    in range.
    """
    if target in (T.GDM, T.LAM):
        return attacking_from == ShellPos.SbOrb
    if target == T.ion:
        if attacking_from == ShellPos.SbOrb and attacker != T.fgt:
            return True
        return attacking_from == ShellPos.Grnd
    if target == T.def_:
        return attacking_from == ShellPos.Orbit
    if target in (T.men, T.nnj):
        if attacking_from == ShellPos.Grnd:
            return True
        return attacking_from == ShellPos.SbOrb and attacker in (T.pen, T.ssp)
    return True


def group_attack(
    no_of_groups: int,
    gp: list[GroupRecord | None],
    attacking_groups: set[int],
    e_sh_dest: dict[TechnologyTypes, int],
    combat_data: CombatDataRecord,
) -> None:
    """Resolve what the attacking groups destroy, into ``e_sh_dest``.

    A group pushing inwards fights harder against the things blocking it, and
    a hunter-killer that fires gives away its position for good.
    """
    for i in range(1, no_of_groups + 1):
        if i not in attacking_groups:
            continue
        group = gp[i]

        if group.Trg in (T.men, T.nnj):
            temp = ships_destroyed(
                group.Num, group.Typ, group.Trg, combat_data.DGrndAdj
            )
        else:
            temp = ships_destroyed(
                group.Num, group.Typ, group.Trg, combat_data.DShipAdj
            )

        if group.Sta == GroupStatus.GAdvc and group.Trg in (T.ssp, T.trn, T.def_):
            temp += temp // 2

        if not _in_range_of_defense(group.Typ, group.Trg, group.Pos):
            temp = 0

        e_sh_dest[group.Trg] = thg_lmt(e_sh_dest[group.Trg] + temp)

        if group.Typ == T.hkr and group.Trg != T.NoRes:
            group.Flg = True


def enemy_attack(
    no_of_groups: int,
    gp: list[GroupRecord | None],
    attacking_groups: set[int],
    g_sh_dest: list[int],
    targ: list[dict[TechnologyTypes, int]],
    combat_data: CombatDataRecord,
    details: dict[TechnologyTypes, list[int]],
) -> None:
    """Resolve what the defender destroys, into ``g_sh_dest`` per group.

    ``details`` accumulates the same losses broken out by what caused them,
    for the battle report.
    """
    for i in range(1, no_of_groups + 1):
        if i not in attacking_groups:
            continue
        for thing in tech_range(T.LAM, T.nnj):
            temp = ships_destroyed(
                targ[i][thing], thing, gp[i].Typ, combat_data.AShipAdj
            )

            if gp[i].Sta == GroupStatus.GAdvc and (
                thing in (T.ssp, T.trn)
                or (thing == T.def_ and gp[i].Pos == ShellPos.Orbit)
            ):
                temp += temp // 2

            g_sh_dest[i] = thg_lmt(g_sh_dest[i] + temp)
            details[thing][i] = lesser_int(
                thg_lmt(details[thing][i] + temp), gp[i].Num
            )
            if temp > 0:
                details[thing][0] = 1


def update_enemy_destroyed(
    cur_pos: ShellPos,
    en: dict[ShellPos, dict[TechnologyTypes, int]],
    e_sh_dest: dict[TechnologyTypes, int],
    killed: dict[TechnologyTypes, int],
) -> None:
    """Apply the attacker's kills to the defender at this shell."""
    for thing in tech_range(T.LAM, T.nnj):
        destroyed = lesser_int(e_sh_dest[thing], en[cur_pos][thing])
        en[cur_pos][thing] -= destroyed
        killed[thing] += destroyed


def update_groups_destroyed(
    no_of_groups: int,
    gp: list[GroupRecord | None],
    attacking_groups: set[int],
    g_sh_dest: list[int],
    casualties: dict[TechnologyTypes, int],
) -> set[int]:
    """Apply the defender's kills to the groups. Returns those wiped out.

    When a transport group takes losses its troops die with it, in proportion
    to how full the transports were -- plus two, so a hit is never free.
    """
    groups_destroyed: set[int] = set()
    for i in range(1, no_of_groups + 1):
        if i not in attacking_groups:
            continue
        group = gp[i]

        if group.Num - g_sh_dest[i] <= 0:
            casualties[group.Typ] += group.Num
            group.Num = 0
            group.Sta = GroupStatus.GDst

            if group.Typ in (T.jtn, T.trn) and group.GAT > 0:
                casualties[group.GATTyp] += group.GAT

            groups_destroyed.add(i)
        else:
            if group.Typ in (T.jtn, T.trn) and g_sh_dest[i] > 0 and group.GAT > 0:
                # CargoSpace[men] regardless of what the troops actually are,
                # as in the original.
                trn_with_men = group.GAT / (CargoSpace[T.men] * TrnAdj[group.Typ])
                men_lost = thg_lmt((g_sh_dest[i] * trn_with_men / group.Num) + 2)
                men_lost = lesser_int(group.GAT, men_lost)
                group.GAT -= men_lost
                casualties[group.GATTyp] += men_lost

            group.Num -= g_sh_dest[i]
            casualties[group.Typ] += g_sh_dest[i]

    return groups_destroyed


def battle(
    no_of_groups: int,
    gp: list[GroupRecord | None],
    en: dict[ShellPos, dict[TechnologyTypes, int]],
    cur_pos: ShellPos,
    combat_data: CombatDataRecord,
    details: dict[TechnologyTypes, list[int]],
    casualties: dict[TechnologyTypes, int],
    killed: dict[TechnologyTypes, int],
) -> set[int]:
    """Resolve one round at one shell. Returns the groups wiped out.

    Both sides fire on the state as it stood at the start, so an exchange is
    simultaneous -- a group destroyed here still lands its shots.

    The original returns the destroyed set through a VAR parameter; Python
    cannot rebind a caller's set, so it comes back as the return value.
    """
    attacking_groups = get_conflict(cur_pos, no_of_groups, gp)
    if not attacking_groups:
        return set()

    e_sh_dest = attack_array()
    g_sh_dest = [0] * (MAX_NO_OF_GROUPS + 1)
    targ = get_target_array(
        cur_pos, no_of_groups, gp, attacking_groups, en, killed, combat_data
    )

    group_attack(no_of_groups, gp, attacking_groups, e_sh_dest, combat_data)
    enemy_attack(no_of_groups, gp, attacking_groups, g_sh_dest, targ, combat_data, details)

    groups_destroyed = update_groups_destroyed(
        no_of_groups, gp, attacking_groups, g_sh_dest, casualties
    )
    update_enemy_destroyed(cur_pos, en, e_sh_dest, killed)
    return groups_destroyed


# --- Conquest ----------------------------------------------------------------


def conquer_world(game: GameEnvironment, world_id: IDNumber, emp: Empire) -> None:
    """Hand a world to ``emp``.

    Efficiency drops for the administrative upheaval. The revolution index
    moves *towards the middle*: a contented world resents the new master, a
    seething one is glad of the change. The bands overlap deliberately -- in
    the 11..55 range the outcome is a die roll and can go either way.
    """
    set_status(game, world_id, emp)

    temp = rnd(10, 20)
    efficiency = get_efficiency(game, world_id)
    set_efficiency(game, world_id, 0 if efficiency - temp < 0 else efficiency - temp)

    rev = get_rev_index(game, world_id)
    if rev <= 10:
        change_rev_index(game, world_id, rnd(10, 20))
    elif rev <= 30:
        roll = rnd(1, 100)
        if roll <= 20:
            change_rev_index(game, world_id, -rnd(5, 15))
        elif roll <= 50:
            change_rev_index(game, world_id, -rnd(3, 10))
        elif roll <= 90:
            change_rev_index(game, world_id, rnd(10, 15))
        else:
            change_rev_index(game, world_id, rnd(20, 30))
    elif rev <= 55:
        roll = rnd(1, 100)
        if roll <= 50:
            change_rev_index(game, world_id, -rnd(10, 20))
        elif roll <= 75:
            change_rev_index(game, world_id, -rnd(5, 10))
        elif roll <= 90:
            change_rev_index(game, world_id, rnd(1, 5))
        else:
            change_rev_index(game, world_id, rnd(5, 15))
    elif rev <= 75:
        change_rev_index(game, world_id, -rnd(40, 55))
    elif rev <= 90:
        change_rev_index(game, world_id, -rnd(50, 65))
    else:
        change_rev_index(game, world_id, -rnd(30, 40))

    scout(game, emp, get_coord(game, world_id))


#: World types that make a world a natural seat of government.
BASE_WORLD_TYPES = (
    WorldTypes.BseTyp,
    WorldTypes.BseSTyp,
    WorldTypes.JmpTyp,
    WorldTypes.JmpSTyp,
    WorldTypes.StrTyp,
    WorldTypes.StrSTyp,
)


def _new_capital(game: GameEnvironment, emp: Empire, new_cap: IDNumber) -> None:
    """Move an empire's seat to a surviving world.

    Empire tech follows the new capital in both directions, but a *promotion*
    keeps only the technologies of the level below -- the world has the level
    without having had time to develop everything in it.
    """
    old_tech, _ = get_empire_technology(game, emp)
    new_tech = get_tech(game, new_cap)
    if old_tech > new_tech:
        set_empire_technology(game, emp, new_tech, set(TechDev[new_tech]))
    elif old_tech < new_tech:
        set_empire_technology(
            game, emp, new_tech, set(TechDev[TechLevel(int(new_tech) - 1)])
        )
    set_capital(game, emp, new_cap)
    set_type(game, new_cap, WorldTypes.CapTyp)
    change_rev_index(game, new_cap, -rnd(30, 50))
    set_efficiency(game, new_cap, rnd(40, 60))


def conquer_empire(
    game: GameEnvironment, player: Empire, enemy_emp: Empire
) -> set[int]:
    """Break up ``enemy_emp`` after its capital falls. Returns the spoils.

    Small worlds far from the fallen capital but close to the conqueror change
    hands outright. Large restive ones go independent rather than submit to
    anyone. What is left stays with the enemy, and the best of it -- most
    advanced, then most populous, with base worlds preferred -- becomes the
    new capital. If nothing qualifies, or the empire was built around a single
    centralized capital, the empire ends: NPEs are deleted outright, while a
    human player's capital is replaced by a Void ID whose index records who
    beat them.

    Iterates ``SetOfPlanetsOf[enemy_emp]``, which the original only ever
    rebuilds on load and at planet creation -- so worlds this empire has lost
    since the game was loaded are still swept, and worlds it has taken are
    not. Faithful to the original; not a transcription slip.
    """
    enemy_cap_id = get_capital(game, enemy_emp)
    play_cap_id = get_capital(game, player)
    cap_xy = get_coord(game, enemy_cap_id)
    conq_xy = get_coord(game, play_cap_id)
    new_cap_id = empty_quadrant()
    booty: set[int] = set()

    for i in range(1, game.NoOfPlanets + 1):
        if i not in game.GlobalSets.SetOfPlanetsOf[enemy_emp]:
            continue

        world_id = IDNumber(ObjectTypes.Pln, i)
        loc = Location(world_id, limbo())
        xy = get_coord(game, world_id)

        dist = distance(xy, cap_xy)
        dist_to_conq = distance(xy, conq_xy)
        pop = get_population(game, world_id)
        rev_i = get_rev_index(game, world_id)

        if dist > 10 and dist_to_conq < 10 and pop < rnd(900, 1100):
            conquer_world(game, world_id, player)
            add_news(game, enemy_emp, NewsTypes.Join, loc, int(player))
            booty.add(i)
        elif pop > rnd(900, 1100) and rev_i > 50 and rnd(1, 100) < 75:
            set_status(game, world_id, Empire.Indep)
            set_type(game, world_id, WorldTypes.IndTyp)
            add_news(game, enemy_emp, NewsTypes.DInd, loc)
        elif dist_to_conq < 10 and rnd(1, 100) < 60 and rev_i > 35:
            conquer_world(game, world_id, player)
            add_news(game, enemy_emp, NewsTypes.Join, loc, int(player))
            booty.add(i)
        elif same_id(new_cap_id, empty_quadrant()):
            if get_tech(game, world_id) > TechLevel.JmpTchLvl:
                new_cap_id = world_id
        elif get_tech(game, world_id) > get_tech(game, new_cap_id):
            new_cap_id = world_id
        elif get_tech(game, world_id) == get_tech(game, new_cap_id):
            if get_type(game, new_cap_id) not in BASE_WORLD_TYPES:
                if (
                    pop > get_population(game, new_cap_id)
                    or get_type(game, world_id) in BASE_WORLD_TYPES
                ):
                    new_cap_id = world_id
            elif get_type(game, world_id) in BASE_WORLD_TYPES and pop > get_population(
                game, new_cap_id
            ):
                new_cap_id = world_id

    if centralized_capital(game, enemy_emp) or same_id(new_cap_id, empty_quadrant()):
        if empire_player(game, enemy_emp):
            set_capital(game, enemy_emp, IDNumber(ObjectTypes.Void, int(player)))
        else:
            destroy_empire(game, enemy_emp)
    else:
        _new_capital(game, enemy_emp, new_cap_id)
        add_news(game, enemy_emp, NewsTypes.NewCap, Location(new_cap_id, limbo()))

    return booty


def restore_combatant(
    game: GameEnvironment, obj_id: IDNumber, casualties: dict[TechnologyTypes, int]
) -> None:
    """Write a combatant's losses back onto the object itself.

    Combat runs on copies; nothing above this touches the real fleet or world.
    A fleet that has lost transports may no longer fit its cargo, so it is
    rebalanced and its fuel capped.
    """
    sh = get_ships(game, obj_id)
    cr = get_cargo(game, obj_id)

    for thing in SHIP_TYPES:
        sh[thing] = greater_int(0, sh[thing] - casualties[thing])
    for thing in (T.men, T.nnj):
        cr[thing] = greater_int(0, cr[thing] - casualties[thing])

    if obj_id.ObjTyp in (ObjectTypes.Pln, ObjectTypes.Base):
        df = get_defns(game, obj_id)
        for thing in DEFNS_TYPES:
            df[thing] = greater_int(0, df[thing] - casualties[thing])

        put_ships(game, obj_id, sh)
        put_cargo(game, obj_id, cr)
        put_defns(game, obj_id, df)
    elif obj_id.ObjTyp == ObjectTypes.Flt:
        if fleet_cargo_space(sh, cr) < 0:
            balance_fleet(sh, cr)

        put_ships(game, obj_id, sh)
        put_cargo(game, obj_id, cr)

        fuel_cap = fuel_capacity(sh)
        if get_fleet_fuel(game, obj_id) > fuel_cap:
            set_fleet_fuel(game, obj_id, fuel_cap)


def _report_losses(
    game: GameEnvironment,
    emp: Empire,
    loc: Location,
    killed: dict[TechnologyTypes, int],
) -> None:
    for thing in tech_range(T.LAM, T.nnj):
        if killed[thing] > 0:
            add_news(game, emp, NewsTypes.DestDetail, loc, killed[thing], int(thing))


def resolve_attack(
    game: GameEnvironment,
    result: AttackResultTypes,
    flt_id: IDNumber,
    target: IDNumber,
    hk_attack: bool,
    capture: bool,
    casualties: dict[TechnologyTypes, int],
    killed: dict[TechnologyTypes, int],
) -> set[int]:
    """Apply the outcome of a battle: news, morale, conquest. Returns spoils.

    Morale is the point of most of this. Winning steadies the victor's empire
    and unsettles the loser's; taking a world does the reverse, because
    conquest is unpopular at home. Fighting independents barely registers
    either way. An unseen hunter-killer strike is reported without naming who
    did it.
    """
    loc = Location(target, limbo())
    emp = get_status(game, flt_id)
    enemy_emp = get_status(game, target)
    empire_conquered = False
    booty: set[int] = set()

    if result == AttackResultTypes.AttDestroyedART:
        if enemy_emp == Empire.Indep:
            change_total_rev_index(game, emp, rnd(1, 4))
        else:
            change_total_rev_index(game, emp, rnd(2, 5))
            change_total_rev_index(game, enemy_emp, -rnd(3, 6))
            add_news(game, enemy_emp, NewsTypes.BattleW1, loc, int(emp))
            _report_losses(game, enemy_emp, loc, killed)
            add_global_news(
                game,
                {emp, enemy_emp},
                target,
                NewsTypes.GLBDest,
                loc,
                int(emp),
                int(enemy_emp),
            )

        fleet_name_destruction(game, emp, flt_id)
        destroy_fleet(game, flt_id)

    elif result == AttackResultTypes.AttRetreatsART:
        if enemy_emp != Empire.Indep:
            if hk_attack:
                add_news(game, enemy_emp, NewsTypes.BattleW2UNK, loc)
            else:
                add_news(game, enemy_emp, NewsTypes.BattleW2, loc, int(emp))
                add_global_news(
                    game,
                    {emp, enemy_emp},
                    target,
                    NewsTypes.GLBDest,
                    loc,
                    int(emp),
                    int(enemy_emp),
                )

            _report_losses(game, enemy_emp, loc, killed)
            change_total_rev_index(game, emp, rnd(1, 3))
            change_total_rev_index(game, enemy_emp, -rnd(1, 3))

    elif result == AttackResultTypes.DefConqueredART:
        if target.ObjTyp in (ObjectTypes.Pln, ObjectTypes.Base):
            conquer_world(game, target, emp)
            if get_type(game, target) == WorldTypes.CapTyp:
                set_type(game, target, WorldTypes.IndTyp)
                empire_conquered = True
                rev_change = rnd(25, 50)
                add_global_news(
                    game,
                    {emp, enemy_emp},
                    target,
                    NewsTypes.GLBCapConq,
                    loc,
                    int(emp),
                    int(enemy_emp),
                )
            else:
                rev_change = rnd(5, 10)
                add_global_news(
                    game,
                    {emp, enemy_emp},
                    target,
                    NewsTypes.GLBConq,
                    loc,
                    int(emp),
                    int(enemy_emp),
                )
        else:
            sh = get_ships(game, target)
            for thing in SHIP_TYPES:
                killed[thing] += sh[thing]

            fleet_name_destruction(game, enemy_emp, target)

            if target.Index in game.GlobalSets.SetOfActiveFleets and capture:
                abort_fleet(game, target, flt_id, False)

            destroy_fleet(game, target)
            rev_change = rnd(1, 5)
            add_global_news(
                game,
                {emp, enemy_emp},
                target,
                NewsTypes.GLBConq,
                loc,
                int(emp),
                int(enemy_emp),
            )

        if enemy_emp == Empire.Indep:
            change_total_rev_index(game, emp, -rnd(2, 4))
        else:
            if hk_attack and target.ObjTyp == ObjectTypes.Flt:
                add_news(game, enemy_emp, NewsTypes.BattleLUNK, loc)
            else:
                add_news(game, enemy_emp, NewsTypes.BattleL, loc, int(emp))

            _report_losses(game, enemy_emp, loc, killed)
            change_total_rev_index(game, emp, -rnd(3, 6))
            change_total_rev_index(game, enemy_emp, rev_change)

        if empire_conquered:
            booty = conquer_empire(game, emp, enemy_emp)

    return booty


# --- Setting up an engagement ------------------------------------------------


def _default_group(
    sh: dict[TechnologyTypes, int],
    cr: dict[TechnologyTypes, int],
    group: GroupRecord,
    thing: TechnologyTypes,
) -> None:
    """Fill one group from the fleet, consuming what it takes from ``sh``/``cr``.

    Transports load troops -- ninjas by preference, since they are worth five
    ordinary soldiers each, and all of them or none.
    """
    group.Typ = thing
    group.Num = sh[thing]
    sh[thing] = 0
    group.Trg = T.NoRes
    group.Pos = ShellPos.DpSpc
    group.Sta = GroupStatus.GReady
    group.Flg = False

    if thing in (T.jtn, T.trn):
        if cr[T.nnj] > 0:
            max_men = thg_lmt(pascal_round(TrnAdj[thing] * group.Num * CargoSpace[T.nnj]))
            max_men = lesser_int(max_men, cr[T.nnj])
            group.GAT = max_men
            group.GATTyp = T.nnj
            cr[T.nnj] -= max_men
        else:
            max_men = thg_lmt(pascal_round(TrnAdj[thing] * group.Num * CargoSpace[T.men]))
            max_men = lesser_int(max_men, cr[T.men])
            group.GAT = max_men
            group.GATTyp = T.men
            cr[T.men] -= max_men
    else:
        group.GAT = 0


def default_distribution(
    game: GameEnvironment, flt_id: IDNumber
) -> tuple[int, list[GroupRecord | None]]:
    """Split a fleet into groups, one per ship type it carries.

    Warships are numbered before transports regardless of enum order, so the
    transports are always the last groups -- which is what lets targeting and
    the advance rules treat "the transports" as a suffix of the array.
    """
    sh = get_ships(game, flt_id)
    cr = get_cargo(game, flt_id)
    gp = group_array()
    no_of_groups = 0

    for thing in SHIP_TYPES:
        if sh[thing] != 0 and thing in (T.fgt, T.hkr, T.jmp, T.pen, T.ssp):
            no_of_groups += 1
            _default_group(sh, cr, gp[no_of_groups], thing)
    for thing in SHIP_TYPES:
        if sh[thing] != 0 and thing in (T.jtn, T.trn):
            no_of_groups += 1
            _default_group(sh, cr, gp[no_of_groups], thing)

    return no_of_groups, gp


def get_enemy(
    game: GameEnvironment, target: IDNumber
) -> dict[ShellPos, dict[TechnologyTypes, int]]:
    """Lay the defender out across the orbital shells.

    A world spreads its ships according to its empire's standing defense
    settings; independents can only field what their tech level covers. Fixed
    defenses sit where they always sit, and troops on the ground.

    A defending fleet has no settings, so it splits three-quarters high and a
    quarter low -- unless it has no transports, in which case it meets the
    attack entirely at HiOrb. Transports always sit at Orbit, behind the
    screen.
    """
    en = enemy_array()
    status = get_status(game, target)
    tech = get_tech(game, target)
    sh = get_ships(game, target)
    cr = get_cargo(game, target)

    if target.ObjTyp in (ObjectTypes.Pln, ObjectTypes.Base):
        # Starbases use ShellDefDist too, not StarbaseDefDist, as in the
        # original.
        defenses = get_defense_settings(game, status)
        defns = get_defns(game, target)

        for pos in ShellPos:
            for thing in SHIP_TYPES:
                if status != Empire.Indep or thing in TechDev[tech]:
                    en[pos][thing] = pascal_round(
                        (defenses.ShellDefDist[pos][thing] / 100) * sh[thing]
                    )

        en[ShellPos.Orbit][T.def_] = defns[T.def_]
        en[ShellPos.SbOrb][T.GDM] = defns[T.GDM]
        en[ShellPos.SbOrb][T.ion] = defns[T.ion]
        en[ShellPos.SbOrb][T.LAM] = defns[T.LAM]
        en[ShellPos.Grnd][T.men] = cr[T.men]
        en[ShellPos.Grnd][T.nnj] = cr[T.nnj]

    elif target.ObjTyp == ObjectTypes.Flt:
        split = 1.0 if sh[T.jtn] + sh[T.trn] == 0 else 0.75

        for thing in SHIP_TYPES:
            if thing not in (T.jtn, T.trn):
                en[ShellPos.HiOrb][thing] = pascal_round(split * sh[thing])
                en[ShellPos.Orbit][thing] = pascal_round((1 - split) * sh[thing])
            else:
                en[ShellPos.Orbit][thing] = sh[thing]

    return en


def forces_unknown(game: GameEnvironment, flt_id: IDNumber, target: IDNumber) -> bool:
    """Whether the defender will never learn who hit it.

    A small hunter-killer force the target has not scouted stays anonymous;
    over 500 hulls it is too big to hide.
    """
    sh = get_ships(game, flt_id)
    return (
        type_of_fleet(game, flt_id) == FleetTypes.HKFleet
        and sh[T.hkr] <= 500
        and not scouted(game, get_status(game, target), flt_id)
    )


# --- Holocaust ---------------------------------------------------------------
#
# Unreachable in v2.0: the only caller, HolocaustCommand in MSCCOMM.PAS, is
# inside a commented-out block, so no code path reaches these. Ported because
# they are part of the unit's published interface, and because the changelog
# treats the mechanic as live.


def holocaust_effectiveness(
    game: GameEnvironment, flt_id: IDNumber, world_id: IDNumber
) -> int:
    """How thoroughly a fleet can bombard a world, 0..100.

    An undefended world is razed completely. Below 5000 points of attack, or
    anything short of parity with the defense, the strike does nothing at all.
    """
    df = get_defns(game, world_id)
    sh = get_ships(game, world_id)
    total_defense = military_power(sh, df)

    flt_sh = get_ships(game, flt_id)
    total_attack = military_power(flt_sh, defns_array())

    if total_defense == 0:
        return 100
    if total_attack < 5000 or total_attack / total_defense < 1:
        return 0
    return lesser_int(100, pascal_round(10 * total_attack / total_defense))


def holocaust_world(
    game: GameEnvironment,
    emp: Empire,
    effectiveness: int,
    world_id: IDNumber,
    flt_id: IDNumber,
) -> tuple[
    HoloResultTypes, dict[TechnologyTypes, int], dict[IndusTypes, int], int, bool
]:
    """Nuclear bombardment of a world's population and industry.

    Returns ``(result, losses, industry destroyed, deaths, reverted)``.
    ``losses`` are the attacker's, computed but -- as in the original -- not
    written back to the fleet; only its fuel is capped to the surviving hulls.
    Applying them is the caller's job.

    An independent world may capitulate at the sight of the fleet rather than
    be hit at all. Otherwise the population is culled, industry flattened,
    efficiency reduced to almost nothing, and the world may be knocked back to
    pre-technological.
    """
    losses = ship_array()
    indus_dest = indus_array()
    deaths = 0
    revert = False
    # Both start at zero because the original leaves them uninitialised on the
    # surrender path and then applies them anyway. Zero is the only defined
    # reading of what a Turbo Pascal stack would have held.
    rev_change = 0
    enemy_rev = 0
    enemy_emp = get_status(game, world_id)

    if enemy_emp == Empire.Indep and _world_surrenders(game, effectiveness, world_id):
        result = HoloResultTypes.WorldSurrendersHRT
        conquer_world(game, world_id, emp)

        change_rev_index(game, world_id, rnd(20, 45))

        if rnd(1, 100) <= 50:
            rev_change = rnd(15, 25)
        else:
            rev_change = -rnd(1, 10)
    else:
        result = HoloResultTypes.WorldDestroyedHRT

        pop = get_population(game, world_id)
        deaths = pascal_round((pop / rnd(850, 1200)) * effectiveness)
        set_population(game, world_id, pop - deaths)

        indus = get_indus(game, world_id)
        per_cent_damage = effectiveness / rnd(200, 800)
        for ind in IndusTypes:
            indus_dest[ind] = pascal_round(indus[ind] * per_cent_damage)
            indus[ind] -= indus_dest[ind]
        put_indus(game, world_id, indus)

        set_efficiency(game, world_id, rnd(1, 10))

        # Deaths is passed where an Index (0..100) is expected, so on any
        # sizeable world the reversion roll is a foregone conclusion. The
        # original's own call, kept.
        if rnd(1, 100) <= deaths // 2:
            revert = True
            set_tech(game, world_id, TechLevel.PreTchLvl)

        _attacker_losses(game, flt_id, effectiveness, losses)

        enemy_rev = min((deaths // 7) + rnd(1, 10), 30)
        rev_change = min((deaths // 6) + rnd(-15, 3), 50)

        loc = Location(world_id, limbo())
        add_news(game, enemy_emp, NewsTypes.WHolo, loc, int(emp))
        add_news(game, enemy_emp, NewsTypes.DthHolo, loc, deaths)
        for ind in IndusTypes:
            if indus_dest[ind] > 0:
                # Reports what survives, not what was lost -- Indus was
                # already decremented above. The original's wording.
                add_news(game, enemy_emp, NewsTypes.IndDs, loc, indus[ind], int(ind))

    change_total_rev_index(game, emp, rev_change)
    change_total_rev_index(game, enemy_emp, enemy_rev)

    return result, losses, indus_dest, deaths, revert


def _world_surrenders(
    game: GameEnvironment, effectiveness: int, world_id: IDNumber
) -> bool:
    """Whether an independent world gives in before being hit.

    Pre-warp worlds always surrender and star-tech ones never do. In between,
    the original rolls ``Random(1)``, which is identically 0, so the
    comparison against a squared probability always holds -- every world in
    the band capitulates. Preserved: the quirk is the behaviour.
    """
    tech = get_tech(game, world_id)
    pop = get_population(game, world_id)
    chance_to_surrender = (effectiveness / 100) ** 2

    if pop > 1000:
        chance_to_surrender /= 2

    if tech < TechLevel.PreWrpLvl:
        return True
    if tech > TechLevel.StrTchLvl:
        return False
    return pascal_random(1) <= chance_to_surrender


def _attacker_losses(
    game: GameEnvironment,
    flt_id: IDNumber,
    effectiveness: int,
    losses: dict[TechnologyTypes, int],
) -> None:
    """Ships the bombarding fleet loses to return fire.

    Inversely proportional to effectiveness -- a world that can barely be
    scratched is a world that shoots back. Transports are spared.
    """
    per_cent_damage = (100 - effectiveness) / rnd(600, 1000)
    sh = get_ships(game, flt_id)

    for thing in SHIP_TYPES:
        if thing not in (T.jtn, T.trn):
            losses[thing] = pascal_round(
                sh[thing] * per_cent_damage * CombatTable[T.GDM][thing] / 100
            )
            sh[thing] -= losses[thing]

    fuel_cap = fuel_capacity(sh)
    if get_fleet_fuel(game, flt_id) > fuel_cap:
        set_fleet_fuel(game, flt_id, fuel_cap)


# --- Standalone strikes ------------------------------------------------------


def lam_attack(
    game: GameEnvironment, player: Empire, lam_to_use: int, target: IDNumber
) -> tuple[dict[TechnologyTypes, int], dict[TechnologyTypes, int]]:
    """Launch light attack missiles at a fleet or a world's defenses.

    Returns ``(ships destroyed, defenses destroyed)``; only one is ever
    non-empty. Against a fleet the missiles spread by how much protection each
    ship type needs, so they concentrate on the things worth killing; against
    a world they spread evenly over the defense stock. A fleet left with no
    ships is destroyed outright.
    """
    ships_dest = ship_array()
    defns_dest = defns_array()
    loc = Location(target, limbo())
    emp = get_status(game, target)

    if target.ObjTyp == ObjectTypes.Flt:
        ships = get_ships(game, target)
        total_ship_space = 0.0
        for res in SHIP_TYPES:
            total_ship_space += ships[res] * (ProtecNeeded[res] / 100)
        if total_ship_space == 0:
            total_ship_space = 1

        for res in SHIP_TYPES:
            lams_per_type = pascal_round(
                lam_to_use * ((ships[res] * (ProtecNeeded[res] / 100)) / total_ship_space)
            )
            ships_dest[res] = lesser_int(
                trunc((lams_per_type / 100) * CombatTable[T.LAM][res]), ships[res]
            )
            ships[res] -= ships_dest[res]

        if no_ships(ships):
            fleet_name_destruction(game, emp, target)
            add_news(game, emp, NewsTypes.LAMDs, loc, int(player))
            destroy_fleet(game, target)
        else:
            add_news(game, get_status(game, target), NewsTypes.LAMDm, loc, int(player))
            cargo = get_cargo(game, target)
            balance_fleet(ships, cargo)
            put_ships(game, target, ships)
            put_cargo(game, target, cargo)

        for res in SHIP_TYPES:
            if ships_dest[res] > 0:
                add_news(
                    game, emp, NewsTypes.DestDetail, loc, ships_dest[res], int(res)
                )
    else:
        add_news(game, emp, NewsTypes.LAMDef, loc, int(player))
        defns = get_defns(game, target)
        total_defns = 0
        for res in DEFNS_TYPES:
            total_defns += defns[res]
        if total_defns == 0:
            total_defns = 1

        for res in DEFNS_TYPES:
            lams_per_type = pascal_round((lam_to_use / total_defns) * defns[res])
            defns_dest[res] = lesser_int(
                trunc((lams_per_type / 100) * CombatTable[T.LAM][res]), defns[res]
            )
            defns[res] -= defns_dest[res]
            if defns_dest[res] > 0:
                add_news(
                    game, emp, NewsTypes.DestDetail, loc, defns_dest[res], int(res)
                )

        put_defns(game, target, defns)

    add_global_news(
        game,
        {emp, player},
        target,
        NewsTypes.GLBLAMStrk,
        loc,
        int(player),
        int(emp),
    )
    return ships_dest, defns_dest


def destroy_construction_or_gate(
    game: GameEnvironment, emp: Empire, forces_unk: bool, target_id: IDNumber
) -> None:
    """Raze a construction site or stargate -- neither can defend itself.

    Losing a gate is the bigger blow to morale: it is infrastructure the
    empire was already relying on, not something still being built.
    """
    loc = Location(empty_quadrant(), get_coord(game, target_id))
    enemy_emp = get_status(game, target_id)

    if target_id.ObjTyp == ObjectTypes.Con:
        destroy_construction(game, target_id)
        change_total_rev_index(game, enemy_emp, rnd(3, 7))
        if forces_unk:
            add_news(game, enemy_emp, NewsTypes.ConDsUNK, loc)
        else:
            add_news(game, enemy_emp, NewsTypes.ConDs, loc, int(emp))
    elif target_id.ObjTyp == ObjectTypes.Gate:
        destroy_stargate(game, target_id)
        change_total_rev_index(game, enemy_emp, rnd(7, 15))
        if forces_unk:
            add_news(game, enemy_emp, NewsTypes.GteDsUNK, loc)
        else:
            add_news(game, enemy_emp, NewsTypes.GteDs, loc, int(emp))


__all__ = [
    "MAX_NO_OF_GROUPS",
    "AttackIntentionTypes",
    "AttackResultTypes",
    "CombatBaseAdj",
    "CombatClassAdj",
    "CombatDataRecord",
    "CombatPower",
    "CombatTechAdj",
    "GDMKill",
    "GDMLaunch",
    "GroupRecord",
    "GroupStatus",
    "HoloResultTypes",
    "advance_groups",
    "all_groups_destroyed",
    "attack_array",
    "battle",
    "calculate_combat_data",
    "conquer_empire",
    "conquer_world",
    "default_distribution",
    "destroy_construction_or_gate",
    "detail_array",
    "enemy_array",
    "enemy_attack",
    "enemy_surrenders",
    "forces_unknown",
    "get_conflict",
    "get_enemy",
    "get_target_array",
    "group_array",
    "group_attack",
    "holocaust_effectiveness",
    "holocaust_world",
    "lam_attack",
    "resolve_attack",
    "restore_combatant",
    "ships_destroyed",
    "total_protection",
    "update_enemy_destroyed",
    "update_groups_destroyed",
]
