"""The automatic battle driver.

Port of ATTNPE.PAS.

:mod:`recreon.attack` supplies the mechanics of a single round at a single
shell; this module is the loop around them, and the only complete
attack-to-outcome path in the game that needs no user at the keyboard. The
original wrote it for non-player empires -- hence the unit name -- but nothing
here consults an NPE persona, so it resolves a player's attack just as well.
ATTCOMM.PAS is the interactive counterpart, where the player picks targets
round by round instead of :func:`_targetting` doing it.

The shape is a fixed loop, repeated until somebody wins:

1. :func:`_fleet_retreats` -- give up if this has gone on too long.
2. ``_targetting`` -- every surviving group picks something to shoot at, and
   if there is nothing in reach at all, the fleet closes.
3. :func:`group_engage` -- one round at every shell, then movement.

Worlds and fleets differ only in how targeting decides to advance, which is
why the two engage routines are near-identical but not shared: against a world
the transports have somewhere to go, and pushing them to the ground is the
whole point of the attack.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .attack import (
    AttackIntentionTypes,
    AttackResultTypes,
    CombatDataRecord,
    CombatPower,
    GroupRecord,
    GroupStatus,
    advance_groups,
    all_groups_destroyed,
    attack_array,
    battle,
    calculate_combat_data,
    default_distribution,
    destroy_construction_or_gate,
    detail_array,
    enemy_surrenders,
    forces_unknown,
    get_enemy,
    resolve_attack,
    restore_combatant,
)
from .datacnst import CombatTable
from .primintr import get_status
from .types import (
    SHIP_TYPES,
    IDNumber,
    ObjectTypes,
    ShellPos,
    TechnologyTypes,
    tech_range,
)
from .utils.int_utils import int_lmt

if TYPE_CHECKING:
    from .environ import GameEnvironment

T = TechnologyTypes

#: Rounds a fleet will keep fighting before it breaks off. Only checked once
#: the fleet has no troops left -- as long as it can still take ground, it
#: presses on however long that takes.
MAX_ENGAGE_ROUNDS = 30

#: Ships that lead an advance: everything but the transports.
COMBAT_SHIPS = (T.fgt, T.hkr, T.jmp, T.pen, T.ssp)


@dataclass(slots=True)
class TargetRecord:
    """One candidate target type, with the weight a group gives it."""

    TargTyp: TechnologyTypes = T.NoRes
    TargNum: int = 0
    Priority: int = 0


def _get_target_array(
    pos: ShellPos, en: dict[ShellPos, dict[TechnologyTypes, int]]
) -> list[TargetRecord]:
    """Everything the defender still has at ``pos``, as targeting candidates.

    Unrelated to :func:`recreon.attack.get_target_array` despite the shared
    name in the original -- that one splits the *defender* across groups, this
    one lists what a group could shoot at.
    """
    return [
        TargetRecord(thing, en[pos][thing], 0)
        for thing in tech_range(T.LAM, T.nnj)
        if en[pos][thing] > 0
    ]


def _prioritize_target_array(
    att_typ: TechnologyTypes,
    intent: AttackIntentionTypes,
    targets: list[TargetRecord],
) -> None:
    """Weight each candidate for one attacking type.

    Worth killing = how many there are, times how well this attacker fares
    against them, times how dangerous they are. The floor of 2 keeps every
    target minimally viable, so a group is never left with nothing to do. A
    fleet out to capture transports demotes them to the floor so it shoots the
    escorts first and leaves the prizes intact; one out to destroy transports
    demotes everything else instead.
    """
    for target in targets:
        total = (
            (target.TargNum / 1000)
            * (CombatTable[att_typ][target.TargTyp] / 100)
            * CombatPower[target.TargTyp]
        )
        if total < 2:
            total = 2
        if intent == AttackIntentionTypes.CaptTrnAIT and target.TargTyp in (
            T.trn,
            T.jtn,
        ):
            total = 1
        elif intent == AttackIntentionTypes.DestTrnAIT and target.TargTyp not in (
            T.trn,
            T.jtn,
        ):
            total = 1

        target.Priority = int_lmt(total)


def _get_best_target(targets: list[TargetRecord]) -> TechnologyTypes | None:
    """The highest-weighted candidate, ties going to the last one seen.

    The original compares with ``>=``, so among equals the highest-ordinal
    type wins -- troops over ships, ships over defenses.
    """
    best: TechnologyTypes | None = None
    highest = 0
    for target in targets:
        if target.Priority >= highest:
            highest = target.Priority
            best = target.TargTyp
    return best


def _all_advance(no_of_groups: int, gp: list[GroupRecord | None]) -> None:
    """Order every warship group inwards, short of sub-orbit."""
    for i in range(1, no_of_groups + 1):
        group = gp[i]
        if (
            group.Sta != GroupStatus.GDst
            and group.Pos < ShellPos.SbOrb
            and group.Typ in COMBAT_SHIPS
        ):
            group.Sta = GroupStatus.GAdvc


def _trn_advance(no_of_groups: int, gp: list[GroupRecord | None]) -> None:
    """Order the transports -- and their fighter escort -- towards the ground."""
    for i in range(1, no_of_groups + 1):
        group = gp[i]
        if (
            group.Sta != GroupStatus.GDst
            and group.Pos < ShellPos.Grnd
            and group.Typ in (T.fgt, T.jtn, T.trn)
        ):
            group.Sta = GroupStatus.GAdvc


def group_engage(
    no_of_groups: int,
    gp: list[GroupRecord | None],
    en: dict[ShellPos, dict[TechnologyTypes, int]],
    combat_data: CombatDataRecord,
    killed: dict[TechnologyTypes, int],
    casualties: dict[TechnologyTypes, int],
    result: AttackResultTypes,
) -> AttackResultTypes:
    """Fight one full round: every shell outermost first, then movement.

    Shells resolve in order, so a group that dies at DpSpc never reaches
    Orbit, and defenders drawn down at one shell are already gone by the time
    an inner one is fought.

    A retreat already decided this round stands: the surrender check is
    skipped, because a fleet that is leaving does not get to accept a
    surrender on its way out.
    """
    details = detail_array()
    for pos in ShellPos:
        battle(no_of_groups, gp, en, pos, combat_data, details, casualties, killed)

    advance_groups(no_of_groups, gp)

    if all_groups_destroyed(no_of_groups, gp):
        return AttackResultTypes.AttDestroyedART
    if result != AttackResultTypes.AttRetreatsART and enemy_surrenders(
        no_of_groups, gp, en, casualties, killed, combat_data
    ):
        return AttackResultTypes.DefConqueredART
    return result


def _no_men_left(no_of_groups: int, gp: list[GroupRecord | None]) -> bool:
    """Whether the fleet has no surviving ground troops.

    Scans back from the end for a group that is neither destroyed nor a ship,
    which after :func:`~recreon.attack.advance_groups` means a landed troop
    group. Relies on transports being the last groups in the array.
    """
    i = no_of_groups
    while i > 0 and (gp[i].Sta == GroupStatus.GDst or gp[i].Typ in SHIP_TYPES):
        i -= 1
    return i == 0


def _fleet_retreats(
    no_of_groups: int,
    gp: list[GroupRecord | None],
    engage_round: int,
    result: AttackResultTypes,
) -> AttackResultTypes:
    """Break off a stalemate once there is nothing left to land."""
    if engage_round > MAX_ENGAGE_ROUNDS and _no_men_left(no_of_groups, gp):
        return AttackResultTypes.AttRetreatsART
    return result


def _transports_left(no_of_groups: int, gp: list[GroupRecord | None]) -> bool:
    """Whether *no* transports survive.

    The name is the original's and reads backwards: it returns True when the
    scan finds nothing but destroyed groups and transports, i.e. when there is
    no surviving non-transport. World targeting uses it to decide whether the
    warships are gone and the transports must go in alone.
    """
    i = no_of_groups
    while i > 0 and (gp[i].Sta == GroupStatus.GDst or gp[i].Typ in (T.jtn, T.trn)):
        i -= 1
    return i == 0


def _targetting_fleet(
    no_of_groups: int,
    gp: list[GroupRecord | None],
    en: dict[ShellPos, dict[TechnologyTypes, int]],
    intent: AttackIntentionTypes,
) -> None:
    """Pick targets for a fleet-vs-fleet engagement.

    A group with nothing in reach keeps whatever it was shooting at last
    round. When *no* group can find anything anywhere, the whole fleet closes
    -- unless it has already reached sub-orbit, where there is nowhere left to
    go.
    """
    target_available = False
    general_pos: ShellPos | None = None

    for i in range(1, no_of_groups + 1):
        group = gp[i]
        if group.Sta == GroupStatus.GDst:
            continue

        if general_pos is None:
            general_pos = group.Pos

        targets = _get_target_array(group.Pos, en)
        if targets:
            target_available = True
            _prioritize_target_array(group.Typ, intent, targets)
            best = _get_best_target(targets)
            if best is not None:
                group.Trg = best

    if not target_available and general_pos != ShellPos.SbOrb:
        _all_advance(no_of_groups, gp)


def _targetting_world(
    no_of_groups: int,
    gp: list[GroupRecord | None],
    en: dict[ShellPos, dict[TechnologyTypes, int]],
    intent: AttackIntentionTypes,
) -> None:
    """Pick targets for an attack on a world.

    Anything that has landed shoots at ``men`` regardless of what the priority
    calculation said -- a ground assault is a ground assault. With nothing left
    to shoot, the fleet advances; but once it has reached sub-orbit, or the
    escort is gone, it is the transports that go in, not the warships.
    """
    target_available = False
    general_pos: ShellPos | None = None
    lowest_pos: ShellPos | None = None

    for i in range(1, no_of_groups + 1):
        group = gp[i]
        if group.Sta == GroupStatus.GDst:
            continue

        if general_pos is None:
            general_pos = group.Pos
            lowest_pos = group.Pos
        elif group.Pos > lowest_pos:
            lowest_pos = group.Pos

        targets = _get_target_array(group.Pos, en)
        if targets:
            target_available = True
            _prioritize_target_array(group.Typ, intent, targets)
            best = _get_best_target(targets)
            if best is not None:
                group.Trg = best

        if group.Pos == ShellPos.Grnd:
            group.Trg = T.men

    if not target_available:
        if lowest_pos == ShellPos.SbOrb or _transports_left(no_of_groups, gp):
            _trn_advance(no_of_groups, gp)
        else:
            _all_advance(no_of_groups, gp)


def _engage(
    no_of_groups: int,
    gp: list[GroupRecord | None],
    en: dict[ShellPos, dict[TechnologyTypes, int]],
    combat_data: CombatDataRecord,
    intent: AttackIntentionTypes,
    against_world: bool,
) -> tuple[dict[TechnologyTypes, int], dict[TechnologyTypes, int], AttackResultTypes]:
    """Run rounds until somebody wins. Returns casualties, kills and outcome."""
    killed = attack_array()
    casualties = attack_array()
    result = AttackResultTypes.NoART
    engage_round = 0
    targetting = _targetting_world if against_world else _targetting_fleet

    while True:
        engage_round += 1
        result = _fleet_retreats(no_of_groups, gp, engage_round, result)
        targetting(no_of_groups, gp, en, intent)
        result = group_engage(
            no_of_groups, gp, en, combat_data, killed, casualties, result
        )
        if result != AttackResultTypes.NoART:
            return casualties, killed, result


def npe_attack(
    game: GameEnvironment,
    flt_id: IDNumber,
    target: IDNumber,
    intent: AttackIntentionTypes = AttackIntentionTypes.ConquerAIT,
) -> tuple[AttackResultTypes, set[int]]:
    """Fight ``flt_id`` against ``target`` to a conclusion.

    Returns the outcome and any worlds taken as spoils. Both combatants are
    updated in place: the fight itself runs on copies, and
    :func:`~recreon.attack.restore_combatant` writes the losses back before
    :func:`~recreon.attack.resolve_attack` settles conquest, morale and news.

    Construction sites and stargates cannot fight and are simply razed.
    Anything else -- a phenomenon, an empty sector -- is not a target and the
    call does nothing.

    A capture is attempted unless the intent was specifically to destroy
    transports, which is what stops a raider from inheriting the cargo it came
    to deny.
    """
    hk_surprise = forces_unknown(game, flt_id, target)
    att_emp = get_status(game, flt_id)

    if target.ObjTyp in (ObjectTypes.Pln, ObjectTypes.Base, ObjectTypes.Flt):
        combat_data = calculate_combat_data(game, att_emp, flt_id, target)
        no_of_groups, gp = default_distribution(game, flt_id)
        en = get_enemy(game, target)

        casualties, killed, result = _engage(
            no_of_groups,
            gp,
            en,
            combat_data,
            intent,
            against_world=target.ObjTyp != ObjectTypes.Flt,
        )

        restore_combatant(game, flt_id, casualties)
        restore_combatant(game, target, killed)

        capture = intent != AttackIntentionTypes.DestTrnAIT
        booty = resolve_attack(
            game, result, flt_id, target, hk_surprise, capture, casualties, killed
        )
        return result, booty

    if target.ObjTyp in (ObjectTypes.Con, ObjectTypes.Gate):
        destroy_construction_or_gate(game, att_emp, hk_surprise, target)
        return AttackResultTypes.DefConqueredART, set()

    return AttackResultTypes.NoART, set()


__all__ = [
    "COMBAT_SHIPS",
    "MAX_ENGAGE_ROUNDS",
    "TargetRecord",
    "group_engage",
    "npe_attack",
]
