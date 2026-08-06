"""Behaviour every AI persona shares.

Port of NPE00.PAS. Where :mod:`recreon.npe.core` holds the primitives -- pick a
target, size a fleet, run a mission -- this is the layer that decides *when* to
use them. The four personas (NPE01..NPE04) are largely a matter of which of
these seven routines they call, in what order, and how often:

``review_news``
    Read the year's headlines and react. Losses raise aggression and push
    policy up the escalation ladder; a stranded fleet gets a tanker, a world
    short of metal gets a freighter.
``defend_empire``
    Sweep every world, compare what defends it against what the persona thinks
    it needs, and shuttle ships between the world and its regional capital.
    Enemy fleets found overhead are engaged.
``imperial_expansion``
    Roll against ``Imperialist`` and, if it passes, take one independent world.
``war_cabinet``
    Per enemy empire, deploy raiders and battle fleets according to policy, and
    probe their capital.
``cargo_supply_fleet``
    Move a specific cargo to a world that needs it, either directly or by first
    sending empty transports to a world that has it.
``npe_conquest``
    Redesignate a world just taken.
``exploration_and_probing``
    Spend every remaining probe on random sectors around the regional capitals.

Nothing here is a decision *maker* in its own right -- persona is threaded
through as ``NPECharacterRecord`` and consulted at each branch, and
``imperial_expansion`` mutates it, so an empire's temperament drifts over a
game.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..attack import AttackIntentionTypes, AttackResultTypes, lam_attack
from ..attnpe import npe_attack
from ..datacnst import FUEL_PER_TON, MPower
from ..design import designate_world
from ..fleet import abort_fleet, deploy_fleet, destroy_fleet
from ..galaxy import XYCoord
from ..misc import (
    distance,
    fleet_cargo_space,
    fuel_capacity,
    military_power,
    no_ships,
    same_id,
    same_xy,
)
from ..news import NewsRecord, NewsTypes, get_news_list
from ..primintr import (
    empire_active,
    get_capital,
    get_cargo,
    get_coord,
    get_defns,
    get_probe,
    get_ships,
    get_status,
    get_type,
    launch_probe,
    put_defns,
    scouted,
)
from ..types import (
    CARGO_TYPES,
    MAX_NO_OF_FLEETS,
    NO_OF_FLEETS_PER_EMPIRE,
    PLAYER_EMPIRES,
    Empire,
    IDNumber,
    ObjectTypes,
    TechnologyTypes,
    WorldTypes,
    cargo_array,
    defns_array,
    empty_quadrant,
)
from ..utils.int_utils import greater_int, isqrt, lesser_int, rnd, rnd_var
from ..utils.pascal import pascal_random_real, pascal_round
from .core import (
    MAX_NO_OF_GUARDS,
    MAX_NO_OF_RAIDERS,
    MAX_NO_OF_REGIONS,
    already_targetted,
    average_military_power,
    deploy_battle_fleet,
    deploy_cargo_fleet,
    deploy_hk_raiders,
    deploy_jump_attack,
    deploy_slow_attack,
    get_best_planet_to_protect,
    get_best_target,
    get_fleet_composition,
    get_new_designation,
    get_potential_res,
    get_regional_capital,
    minimum_defense,
)
from .types import MissionTypes, NPECharacterRecord, PolicyTypes, StateDeptRecord

if TYPE_CHECKING:
    from ..environ import GameEnvironment

T = TechnologyTypes
WT = WorldTypes


# --- News --------------------------------------------------------------------


def _rn_industry_lack(
    game: GameEnvironment,
    emp: Empire,
    obj_id: IDNumber,
    rcap: list[IDNumber],
    fleet_data: list,
) -> None:
    """Answer an ``IndLack`` headline with a thousand tons of metal."""
    cr = cargo_array()
    cr[T.met] = 1000
    cargo_supply_fleet(game, emp, obj_id, cr, rcap, fleet_data)


def _military_value(parm2: int) -> int:
    """``MPower`` for a ``DestDetail`` item's thing ordinal.

    ORIGINAL BUG, preserved -- see issue #33. ``AttackSeverity`` indexes
    ``MPower[AttackTypes(Parm2)]``, but ``ReportLosses`` in ATTACK.PAS files a
    ``DestDetail`` for everything in ``LAM..nnj`` -- including the two ground
    types, ``men`` and ``nnj``, which are past the end of what ``MPower``
    covers (it is read everywhere else only over ``LAM..trn``). Any battle with
    ground casualties therefore indexes the table out of range.

    ``MPower`` is declared ``ARRAY [LAM..trn] OF Byte`` at DATACNST.PAS:198,
    so this is an out-of-bounds read of adjacent memory rather than a lookup
    of undocumented entries -- and with range checking off nothing traps it.

    Returning 0 is very probably what the DOS build did anyway.
    ``CombatTable`` is declared immediately after ``MPower`` in the same
    ``CONST`` block, and its first row -- the ``NUL`` attacker -- is all
    zeroes, so the bytes just past an 11-byte ``MPower`` are zero whether or
    not the compiler pads between them. 0 is also the reading consistent with
    the rest of the unit: troops carry no military power anywhere else in the
    game, since ``MilitaryPower`` sums ships and defenses only.

    (This docstring used to say ``MPower`` was declared nowhere in
    ``original/``. It is; DATACNST.PAS is one of ten files ``grep`` treats as
    binary, so plain searches did not see it.)
    """
    try:
        return MPower[T(parm2)]
    except (KeyError, ValueError):
        return 0


def _attack_severity(news_list: list[NewsRecord], start: int, base_power: int) -> int:
    """How hard the attack reported at ``start`` hit, as a 0..100 index.

    Sums the ``DestDetail`` lines that immediately follow the headline -- they
    are the itemised losses -- and scales the total against the empire's
    average regional military power. Capped at 100, floored at 10 by the
    constant term, so any attack at all registers.
    """
    total = 1
    i = start + 1
    while i < len(news_list) and news_list[i].Headline == NewsTypes.DestDetail:
        item = news_list[i]
        total += item.Parm1 * _military_value(item.Parm2)
        i += 1

    if base_power == 0:
        base_power = 1

    return lesser_int(100, 10 + pascal_round(50 * total / base_power))


def _respond_to_enemy_attack(
    emp: Empire,
    att_emp: Empire,
    severity: int,
    persona: NPECharacterRecord,
    state: dict[Empire, StateDeptRecord],
) -> None:
    """Escalate policy toward ``att_emp`` and raise aggression.

    Each rung needs both a severity threshold and a roll against ``Provoke``,
    so a placid AI absorbs a great deal before it moves. ``NoPLT`` is not a
    case here -- an empire the state department has never assessed stays where
    it is no matter how hard it is hit.
    """
    rec = state[att_emp]

    if rec.Policy == PolicyTypes.NeutralPLT:
        if severity > 50 and rnd(1, 100) < persona.Provoke:
            rec.Policy = PolicyTypes.PreemptPLT
        else:
            rec.Policy = PolicyTypes.HarassPLT
    elif rec.Policy == PolicyTypes.HarassPLT:
        if severity > 50 and rnd(1, 100) < persona.Provoke:
            rec.Policy = PolicyTypes.ConflictPLT
        elif rnd(1, 100) < persona.Provoke:
            rec.Policy = PolicyTypes.PreemptPLT
    elif rec.Policy == PolicyTypes.PreemptPLT:
        if severity > 35 and rnd(1, 100) <= persona.Provoke:
            rec.Policy = PolicyTypes.ConflictPLT
    elif rec.Policy == PolicyTypes.ConflictPLT:
        if severity > 75 and rnd(1, 100) <= (persona.Provoke // 2):
            rec.Policy = PolicyTypes.WarPLT

    # Never less than 10, so the floor branch below always fires on a quiet
    # empire: being attacked at all pins Aggressiveness to at least 35.
    agg_inc = 10 + pascal_round(severity / 5)

    # This is also the only thing that repairs the underflow in issue #27: an
    # Aggressiveness that has wrapped to 255 sums past 100 here and is clamped
    # back down, so an AI stuck at the top of the ladder recovers the moment
    # someone hits it.
    if rec.Aggressiveness + agg_inc > 100:
        rec.Aggressiveness = 100
    elif agg_inc > 0 and (rec.Aggressiveness + agg_inc) < 35:
        rec.Aggressiveness = 35
    else:
        rec.Aggressiveness += agg_inc


def _send_rescue_fleet(
    game: GameEnvironment,
    emp: Empire,
    flt_id: IDNumber,
    rcap: list[IDNumber],
    fleet_data: list,
) -> None:
    """Send a tanker to a fleet that has run dry, if the capital can spare one.

    ORIGINAL BUG, deviated from -- see issue #39. News is read at the *end* of
    the year it was filed, and a fleet that reported itself out of fuel is a
    prime candidate for having been destroyed in between -- by an attack, or
    by an earlier item in this same review. The original sizes a tanker off the
    wreck's ship array; there is nothing to rescue, so the port returns.
    """
    if flt_id.Index not in game.GlobalSets.SetOfActiveFleets:
        return

    base_id = get_regional_capital(game, flt_id, rcap)
    sh = get_ships(game, flt_id)
    fuel_needed = 1 + pascal_round(fuel_capacity(sh) / FUEL_PER_TON)
    jtn_needed = 1 + pascal_round(fuel_needed / 10)

    sh = get_ships(game, base_id)
    cr = get_cargo(game, base_id)
    if sh[T.jtn] > jtn_needed and cr[T.tri] > fuel_needed:
        cr = cargo_array()
        cr[T.tri] = fuel_needed
        deploy_cargo_fleet(
            game, emp, fleet_data, base_id, cr, True, MissionTypes.RefuelMSN, flt_id
        )


def review_news(
    game: GameEnvironment,
    emp: Empire,
    fleet_data: list,
    rcap: list[IDNumber],
    persona: NPECharacterRecord,
    state: dict[Empire, StateDeptRecord],
) -> None:
    """React to everything that happened to the empire last year.

    Combat headlines cost the attacker standing (``Balance``) and provoke a
    policy response; a fleet out of fuel gets a tanker and a world short of
    metal gets a delivery.

    ``Balance`` drops for certain on a lost battle over something the empire
    owned, and only one time in four otherwise -- so raids in open space are
    mostly shrugged off while losing ground is always counted.

    The list is walked by index rather than snapshotted because the original
    walks a tail-appended linked list: anything filed for this same empire
    while the loop runs is seen by the loop.
    """
    base_power = average_military_power(game, rcap)
    news_list = get_news_list(game, emp)

    i = 0
    while i < len(news_list):
        item = news_list[i]

        if item.Headline in (
            NewsTypes.BattleL,
            NewsTypes.BattleW1,
            NewsTypes.BattleW2,
            NewsTypes.ConDs,
            NewsTypes.GteDs,
            NewsTypes.LAMDm,
            NewsTypes.LAMDs,
            NewsTypes.LAMDef,
        ):
            # Parm1 is the other empire's ordinal for every headline here.
            att_emp = Empire(item.Parm1)
            if item.Headline == NewsTypes.BattleL and item.Loc1.ID.ObjTyp in (
                ObjectTypes.Pln,
                ObjectTypes.Base,
                ObjectTypes.Gate,
            ):
                state[att_emp].Balance -= 1
            elif rnd(1, 100) < 25:
                state[att_emp].Balance -= 1

            severity = _attack_severity(news_list, i, base_power)
            _respond_to_enemy_attack(emp, att_emp, severity, persona, state)
        elif item.Headline == NewsTypes.NoFuel:
            _send_rescue_fleet(game, emp, item.Loc1.ID, rcap, fleet_data)
        elif item.Headline == NewsTypes.IndLack:
            _rn_industry_lack(game, emp, item.Loc1.ID, rcap, fleet_data)

        i += 1


# --- Defense -----------------------------------------------------------------


def _attack_enemy_fleets(
    game: GameEnvironment, emp: Empire, obj_id: IDNumber, base_id: IDNumber
) -> None:
    """Engage any scouted enemy fleet sitting over ``obj_id``.

    LAMs go first when the fleet is worth it and the base is close enough --
    and the whole stock is spent whatever the outcome, since ``Df[LAM]`` is
    zeroed rather than decremented by what was launched.

    A fleet is then composed from ``obj_id`` and sent up. Note the two-armed
    test: the AI attacks either when the world plus ``base_id``'s defenses
    still come to less than the enemy, or when its ships alone come to more.
    The second arm is the sensible one; the first commits to a fight it has
    already judged it loses, and the defenses being weighed belong to the
    regional capital rather than to the world the ships are leaving.
    """
    xy = get_coord(game, obj_id)
    base_xy = get_coord(game, base_id)
    enemy_fleets = game.GlobalSets.SetOfActiveFleets - game.GlobalSets.SetOfFleetsOf[emp]

    for index in range(1, MAX_NO_OF_FLEETS + 1):
        flt_id = IDNumber(ObjectTypes.Flt, index)
        if index not in enemy_fleets or not scouted(game, emp, flt_id):
            continue
        if not same_xy(get_coord(game, flt_id), xy):
            continue

        null_df = defns_array()
        flt_sh = get_ships(game, flt_id)
        m_power = military_power(flt_sh, null_df)

        if m_power > 30000 and distance(base_xy, xy) <= 5:
            df = get_defns(game, base_id)
            if df[T.LAM] > 500 and rnd(1, 100) < 50:
                lam_attack(game, emp, df[T.LAM], flt_id)
                df = get_defns(game, base_id)
                df[T.LAM] = 0
                put_defns(game, base_id, df)

        if index in game.GlobalSets.SetOfActiveFleets:
            # The enemy fleet survived the missiles. The original reads the
            # base's ships here too, but GetFleetComposition overwrites them
            # before they are used; only the defenses below are live.
            df = get_defns(game, base_id)
            null_df = defns_array()

            sh, cr = get_fleet_composition(
                game, obj_id, m_power * 2, 0, MissionTypes.JumpAttackMSN
            )

            if (not no_ships(sh)) and (
                military_power(sh, df) < m_power or military_power(sh, null_df) > m_power
            ):
                battle_id = deploy_fleet(game, emp, obj_id, sh, cr, xy)
                if not same_id(battle_id, empty_quadrant()):
                    result, _ = npe_attack(
                        game, battle_id, flt_id, AttackIntentionTypes.CaptTrnAIT
                    )
                    if result != AttackResultTypes.AttDestroyedART:
                        abort_fleet(game, battle_id, obj_id, True)
                        destroy_fleet(game, battle_id)


def _no_of_guards_at_base(
    game: GameEnvironment, emp: Empire, base_id: IDNumber, fleet_data: list
) -> int:
    """How many of the empire's fleets are sitting on ``base_id`` guarding it."""
    no_of_guards = 0
    base_xy = get_coord(game, base_id)

    for i in range(1, NO_OF_FLEETS_PER_EMPIRE + 1):
        entry = fleet_data[i]
        if (
            entry.Index in game.GlobalSets.SetOfActiveFleets
            and entry.Mission == MissionTypes.GuardMSN
        ):
            flt_id = IDNumber(ObjectTypes.Flt, entry.Index)
            if same_xy(get_coord(game, flt_id), base_xy):
                no_of_guards += 1

    return no_of_guards


def _get_best_base_to_protect(
    game: GameEnvironment,
    emp: Empire,
    rcap: list[IDNumber],
    fleet_data: list,
    from_id: IDNumber,
) -> IDNumber:
    """The regional capital with the fewest guards, other than ``from_id``.

    Returns EmptyQuadrant when every other base already has its full
    complement, which is what stops a rich empire shuffling fleets forever.
    """
    lowest_no = MAX_NO_OF_GUARDS
    best_base_id = empty_quadrant()

    for i in range(1, MAX_NO_OF_REGIONS + 1):
        if same_id(rcap[i], empty_quadrant()) or same_id(rcap[i], from_id):
            continue
        guards = _no_of_guards_at_base(game, emp, rcap[i], fleet_data)
        if guards < lowest_no:
            lowest_no = guards
            best_base_id = rcap[i]

    return best_base_id


def defend_empire(
    game: GameEnvironment,
    emp: Empire,
    rcap: list[IDNumber],
    fleet_data: list,
    persona: NPECharacterRecord,
) -> None:
    """Balance defenses across every world the empire holds.

    General defense only -- no immediate threat is assessed beyond engaging
    enemy fleets found overhead. An under-defended world is topped up from its
    regional capital on a ReturnMSN; a world with a surplus ships the excess
    back on a StackMSN, provided the capital has room for another guard.

    ORIGINAL BUG, preserved -- see issue #34. The 10000-power deadband takes
    the smaller of the shortfall and ``ShipPower``, and ``ShipPower`` is the
    ships already sitting on *the world being assessed*. For the stack branch
    that is right -- you cannot ship away more than you have. For the reinforce
    branch it is backwards: a world with no ships scores ``min(0, shortfall)``
    and can never be topped up however badly it needs it, so the worlds most in
    need -- freshly conquered, freshly raided -- are exactly the ones the AI
    refuses to help.

    Bases and capitals take the other branch: once one is holding its full
    complement of guards it pushes ships out to the weakest nearby world and to
    whichever sibling base is thinnest.

    Missions: GuardMSN, ReturnMSN, StackMSN.
    """
    for index in range(1, game.NoOfPlanets + 1):
        if index not in game.GlobalSets.SetOfPlanetsOf[emp]:
            continue
        obj_id = IDNumber(ObjectTypes.Pln, index)

        if get_type(game, obj_id) not in (WT.BseTyp, WT.CapTyp):
            ships, cargo = get_potential_res(game, obj_id, fleet_data)
            defns = get_defns(game, obj_id)
            power_avail = military_power(ships, defns)
            ship_power = military_power(ships, defns_array())
            optimum_power = minimum_defense(game, obj_id, persona)
            optimum_gat = optimum_power // 20
            gat_power = cargo[T.men] + 3 * cargo[T.nnj]
            base_id = get_regional_capital(game, obj_id, rcap)

            _attack_enemy_fleets(game, emp, obj_id, base_id)

            power_diff = optimum_power - power_avail
            gat_diff = optimum_gat - gat_power

            if lesser_int(ship_power, abs(power_diff)) > 10000:
                if power_avail < optimum_power:
                    base_cargo = get_cargo(game, base_id)
                    # The capital keeps 3000 of ground strength for itself.
                    max_base_gat = greater_int(
                        0, (base_cargo[T.men] + 3 * base_cargo[T.nnj]) - 3000
                    )
                    gat_diff = lesser_int(max_base_gat, greater_int(0, gat_diff))
                    deploy_battle_fleet(
                        game,
                        emp,
                        fleet_data,
                        base_id,
                        power_diff,
                        gat_diff,
                        MissionTypes.ReturnMSN,
                        obj_id,
                    )
                elif _no_of_guards_at_base(game, emp, base_id, fleet_data) < MAX_NO_OF_GUARDS:
                    gat_diff = greater_int(0, -gat_diff)
                    deploy_battle_fleet(
                        game,
                        emp,
                        fleet_data,
                        obj_id,
                        -power_diff,
                        gat_diff,
                        MissionTypes.StackMSN,
                        base_id,
                    )
        else:
            _attack_enemy_fleets(game, emp, obj_id, obj_id)
            if _no_of_guards_at_base(game, emp, obj_id, fleet_data) == MAX_NO_OF_GUARDS:
                world_id = get_best_planet_to_protect(game, obj_id)
                if not same_id(world_id, empty_quadrant()):
                    deploy_battle_fleet(
                        game,
                        emp,
                        fleet_data,
                        obj_id,
                        9000 * MPower[T.fgt],
                        0,
                        MissionTypes.ReturnMSN,
                        world_id,
                    )

                sibling_id = _get_best_base_to_protect(
                    game, emp, rcap, fleet_data, obj_id
                )
                if not same_id(sibling_id, empty_quadrant()):
                    deploy_battle_fleet(
                        game,
                        emp,
                        fleet_data,
                        obj_id,
                        150000,
                        0,
                        MissionTypes.StackMSN,
                        sibling_id,
                    )


# --- Expansion ---------------------------------------------------------------


def _get_power_to_use(target_defense: int, target_men: int) -> tuple[int, int]:
    """Size a conquest fleet: 1.5x to 2.5x the defense, 1.5x the troops.

    The original takes ``Persona`` and does not read it -- temperament governs
    whether to attack at all, not how hard.
    """
    fleet_power = pascal_round((1.5 + pascal_random_real()) * target_defense)
    fleet_gat = pascal_round(1.5 * target_men)
    return fleet_power, fleet_gat


def _modify_persona(persona: NPECharacterRecord) -> None:
    """Drift ``Imperialist`` toward ``ImpGene``, clamped to 0..100.

    Runs once a year on a ``RandomGene`` roll. Both endpoints are jittered by
    ``FactorGene`` before the difference is taken, so the trait wanders rather
    than converging, and ``FactorGene`` scales both the jitter and the step.
    """
    if rnd(1, 100) <= persona.RandomGene:
        delta = rnd_var(persona.ImpGene, persona.FactorGene) - rnd_var(
            persona.Imperialist, persona.FactorGene
        )
        temp = persona.Imperialist + pascal_round((delta / 12) * persona.FactorGene)

        if temp > 100:
            persona.Imperialist = 100
        elif temp < 0:
            persona.Imperialist = 0
        else:
            persona.Imperialist = temp


def _get_possibilities(
    game: GameEnvironment,
    emp: Empire,
    rcap: list[IDNumber],
    persona: NPECharacterRecord,
) -> set[int]:
    """Independent worlds close enough to one of the empire's regions to take.

    ``SphereX`` tightens the radius: an empire that expands outward from its
    capital reaches 2 sectors, one that does not reaches 12.
    """
    threshold = 2 + 10 - (persona.SphereX // 10)
    possibilities: set[int] = set()

    for i in range(1, game.NoOfPlanets + 1):
        world_id = IDNumber(ObjectTypes.Pln, i)
        if get_status(game, world_id) != Empire.Indep:
            continue
        world_xy = get_coord(game, world_id)
        base_xy = get_coord(game, get_regional_capital(game, world_id, rcap))
        if distance(world_xy, base_xy) <= threshold:
            possibilities.add(i)

    return possibilities


def imperial_expansion(
    game: GameEnvironment,
    emp: Empire,
    rcap: list[IDNumber],
    fleet_data: list,
    persona: NPECharacterRecord,
) -> None:
    """Take one independent world, if the roll and the arithmetic both allow.

    A single fleet, from the region nearest the target, and only when that
    region's ships already outweigh the target's defenses -- so worlds needing
    more than one fleet are never attempted and other empires' worlds are not
    considered here at all (that is :func:`war_cabinet`).

    ``_modify_persona`` runs whether or not the empire expanded.

    Mission: ConquerMSN.
    """
    if rnd(1, 100) <= persona.Imperialist:
        base_power = average_military_power(game, rcap)
        possibilities = _get_possibilities(game, emp, rcap, persona)
        target_id, target_defense, target_men = get_best_target(
            game, emp, possibilities, base_power, persona, fleet_data
        )

        if not same_id(target_id, empty_quadrant()):
            fleet_power, fleet_gat = _get_power_to_use(target_defense, target_men)
            base_id = get_regional_capital(game, target_id, rcap)
            ships_avail = get_ships(game, base_id)
            if military_power(ships_avail, defns_array()) > target_defense:
                deploy_battle_fleet(
                    game,
                    emp,
                    fleet_data,
                    base_id,
                    fleet_power,
                    fleet_gat,
                    MissionTypes.ConquerMSN,
                    target_id,
                )

    _modify_persona(persona)


# --- War ---------------------------------------------------------------------


def _get_no_of_raiders_out(fleet_data: list) -> int:
    """How many raiding fleets the empire already has flying.

    Counts any slot with a non-zero index rather than checking the active set,
    so a record left behind by a dead raider still counts against the cap until
    ``enforce_npe_data_links`` clears it.
    """
    count = 0
    for i in range(1, NO_OF_FLEETS_PER_EMPIRE + 1):
        entry = fleet_data[i]
        if entry.Index > 0 and entry.Mission == MissionTypes.RaidTrnMSN:
            count += 1
    return count


def war_cabinet(
    game: GameEnvironment,
    emp: Empire,
    rcap: list[IDNumber],
    fleet_data: list,
    persona: NPECharacterRecord,
    state: dict[Empire, StateDeptRecord],
) -> None:
    """Run war maneuvers against every other empire, according to policy.

    Three independent things happen per enemy: hunter-killer raiders go out if
    the empire is behind on ``Balance`` or rolls its ``AttackChance``; a main
    battle fleet is deployed on a second roll, with the policy deciding whether
    that is more raiders, a jump attack or a slow one; and probes are scattered
    around the enemy capital in proportion to ``Aggressiveness``.

    ``HarassPLT`` deploys through :func:`~recreon.npe.core.deploy_harass_fleet`
    nowhere -- it re-deploys raiders instead. The harass rung being inert is
    issue #25.

    The loop covers the empire itself, which the original does not exclude.
    That is harmless only because both :func:`~recreon.npe.core.state_department`
    and :func:`~recreon.npe.core.state_dept_report` skip self, leaving
    ``state[emp]`` at its defaults -- ``NoPLT``, zero ``AttackChance``, zero
    ``Aggressiveness``, ``Balance`` of 0 -- so every test below fails. Anything
    that starts writing a self-entry would have the AI raid its own worlds.
    """
    for enemy_emp in PLAYER_EMPIRES:
        if not empire_active(game, enemy_emp):
            continue

        rec = state[enemy_emp]
        # Sampled once and not refreshed, so everything below sees the count
        # from before this year's raiders launched.
        no_of_raiders_out = _get_no_of_raiders_out(fleet_data)

        if no_of_raiders_out < MAX_NO_OF_RAIDERS and (
            rec.Balance < 0
            or (rec.Policy >= PolicyTypes.HarassPLT and rnd(1, 100) <= rec.AttackChance)
        ):
            deploy_hk_raiders(game, emp, enemy_emp, rcap, fleet_data)

        if (rec.Balance < 0 and rnd(1, 2) == 1) or rnd(1, 100) <= rec.AttackChance:
            if rec.Policy == PolicyTypes.HarassPLT:
                if no_of_raiders_out < MAX_NO_OF_RAIDERS:
                    deploy_hk_raiders(game, emp, enemy_emp, rcap, fleet_data)
            elif rec.Policy == PolicyTypes.PreemptPLT:
                if rnd(1, 100) <= 50:
                    if no_of_raiders_out < MAX_NO_OF_RAIDERS:
                        deploy_hk_raiders(game, emp, enemy_emp, rcap, fleet_data)
                else:
                    deploy_jump_attack(game, emp, enemy_emp, rcap, persona, fleet_data)
            elif rec.Policy == PolicyTypes.ConflictPLT:
                if rnd(1, 100) <= 75:
                    deploy_jump_attack(game, emp, enemy_emp, rcap, persona, fleet_data)
                else:
                    deploy_slow_attack(game, emp, enemy_emp, rcap, persona, fleet_data)
            elif rec.Policy == PolicyTypes.WarPLT:
                if rnd(1, 100) <= 50:
                    deploy_jump_attack(game, emp, enemy_emp, rcap, persona, fleet_data)
                else:
                    deploy_slow_attack(game, emp, enemy_emp, rcap, persona, fleet_data)

        if rnd(1, 100) <= rec.Aggressiveness:
            cap_xy = get_coord(game, get_capital(game, enemy_emp))
            for _ in range(rnd(1, 4)):
                x = rnd(cap_xy.x - 4, cap_xy.x + 4)
                y = rnd(cap_xy.y - 4, cap_xy.y + 4)
                if game.Galaxy.in_galaxy(x, y):
                    p_num = get_probe(game, emp)
                    if p_num != 0:
                        launch_probe(game, emp, p_num, XYCoord(x, y))


# --- Supply ------------------------------------------------------------------


def _get_closest_cargo_world(
    game: GameEnvironment, emp: Empire, world_id: IDNumber, cr: dict[T, int]
) -> IDNumber:
    """The empire's nearest world holding at least ``cr`` of everything.

    A world qualifies only if it covers *every* line of the request, checked
    from ``men`` up to ``tri``; falling short on any one disqualifies it
    entirely rather than partially filling the order.
    """
    xy = get_coord(game, world_id)
    closest_dist = 99
    closest_id = empty_quadrant()

    for i in range(1, game.NoOfPlanets + 1):
        if i not in game.GlobalSets.SetOfPlanetsOf[emp]:
            continue
        obj_id = IDNumber(ObjectTypes.Pln, i)
        obj_xy = get_coord(game, obj_id)
        if distance(obj_xy, xy) >= closest_dist:
            continue

        obj_cr = get_cargo(game, obj_id)
        if all(obj_cr[res] >= cr[res] for res in CARGO_TYPES):
            closest_id = obj_id
            closest_dist = distance(obj_xy, xy)

    return closest_id


def cargo_supply_fleet(
    game: GameEnvironment,
    emp: Empire,
    world_id: IDNumber,
    cr: dict[T, int],
    rcap: list[IDNumber],
    fleet_data: list,
) -> None:
    """Get ``cr`` to ``world_id`` from wherever the empire has it.

    Two cases. If the source world has the transports to carry the load, it
    ships it directly on a SupplyMSN. If it has the goods but no hulls, empty
    transports are sent to *it* from its regional capital on a SupplyTrnMSN,
    and the delivery waits for a later year.

    Both are guarded by ``already_targetted`` so a world short of something for
    several years running does not accumulate freighters.
    """
    cargo_id = _get_closest_cargo_world(game, emp, world_id, cr)
    if same_id(cargo_id, empty_quadrant()):
        return

    sh = get_ships(game, cargo_id)
    if fleet_cargo_space(sh, cr) > 0:
        if not already_targetted(game, emp, world_id, MissionTypes.SupplyMSN, fleet_data):
            deploy_cargo_fleet(
                game, emp, fleet_data, cargo_id, cr, True, MissionTypes.SupplyMSN, world_id
            )
    elif not already_targetted(
        game, emp, cargo_id, MissionTypes.SupplyTrnMSN, fleet_data
    ):
        base_id = get_regional_capital(game, cargo_id, rcap)
        deploy_cargo_fleet(
            game, emp, fleet_data, base_id, cr, False, MissionTypes.SupplyTrnMSN, cargo_id
        )


# --- Conquest and exploration ------------------------------------------------


def npe_conquest(
    game: GameEnvironment,
    emp: Empire,
    world_id: IDNumber,
    result: AttackResultTypes,
    rcap: list[IDNumber],
    persona: NPECharacterRecord,
) -> None:
    """Redesignate a world the empire has just taken.

    Only fires when the attack actually conquered it *and* the world now
    belongs to ``emp`` -- a world that changed hands and was lost again in the
    same exchange is left alone.

    The original also looks up the world's and its regional capital's
    coordinates at the end and does nothing with either; the leftover of
    something removed before release.
    """
    if result == AttackResultTypes.DefConqueredART and emp == get_status(game, world_id):
        new_typ = get_new_designation(game, world_id, persona, rcap)
        if new_typ != get_type(game, world_id):
            designate_world(game, world_id, new_typ)


def exploration_and_probing(
    game: GameEnvironment,
    emp: Empire,
    rcap: list[IDNumber],
    persona: NPECharacterRecord,
) -> None:
    """Spend every remaining probe on sectors around the regional capitals.

    The radius shrinks as ``SphereX`` rises -- an empire that expands outward
    from its capital looks close to home. Because this drains the pool, it has
    to run after any other probing the turn wants to do.

    ORIGINAL BUG, preserved -- see issue #35. The REPEAT loop only ends when a
    ``GetProbe`` returns 0, and that call sits inside a test for a live region.
    An empire with no regional capitals at all -- every ``RCap`` slot empty --
    never reaches it and spins forever. Reproduced faithfully, on the same
    grounds as the ``NextEmpire`` hang in issue #9.
    """
    max_probe_dist = 24 - (2 * isqrt(persona.SphereX))

    no_more_probes = False
    while not no_more_probes:
        for i in range(1, MAX_NO_OF_REGIONS + 1):
            if same_id(rcap[i], empty_quadrant()):
                continue
            base_xy = get_coord(game, rcap[i])
            x = rnd(base_xy.x - max_probe_dist, base_xy.x + max_probe_dist)
            y = rnd(base_xy.y - max_probe_dist, base_xy.y + max_probe_dist)
            if game.Galaxy.in_galaxy(x, y):
                p_num = get_probe(game, emp)
                if p_num != 0:
                    launch_probe(game, emp, p_num, XYCoord(x, y))
                else:
                    no_more_probes = True
