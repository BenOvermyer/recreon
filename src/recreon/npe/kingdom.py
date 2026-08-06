"""The kingdom empires.

Port of NPE02.PAS. This is the reference persona: it is the only one that uses
the whole stack -- regions, fleet missions, news review, the state department,
the war cabinet, defense balancing, expansion and redesignation -- in a fixed
annual order. Reading `implement_kingdom1_npe` is the clearest single statement
of what an Anacreon AI turn *is*.

**Kingdom1 and Kingdom2 share every line of behaviour.** They differ only in
the numbers `initialize_*` rolls into the persona and the starting policy:

|  | Kingdom1 | Kingdom2 |
|---|---|---|
| Starting policy toward everyone | `NeutralPLT` | `HarassPLT` |
| `ImpGene` (drives expansion) | 1–5 | 50–100 |
| `DefGene` | 50–75 | 5–10 |
| `OffGene` | 1–2 | 50–100 |
| `FactorGene` (drift rate) | 15 | 25 |
| `Provoke` | 75 | 50–100 |

So Kingdom1 is a homebody that defends heavily and barely expands, but is
provoked easily once hit; Kingdom2 starts already hostile to everyone and
expands hard. `NPE.PAS` dispatches both to `ImplementKingdom1NPE`, which is why
there is no `implement_kingdom2_npe` here.

The annual order matters and is not arbitrary: fleets are updated *before* news
is reviewed, so a fleet that arrived this year has already acted by the time
the AI reads the headlines its arrival generated.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..attack import AttackResultTypes
from ..fleet import abort_fleet, destroy_fleet
from ..primintr import get_fleet_status, get_status
from ..types import (
    NO_OF_FLEETS_PER_EMPIRE,
    PLAYER_EMPIRES,
    Empire,
    FleetStatus,
    IDNumber,
    ObjectTypes,
)
from ..utils.int_utils import rnd
from .common import (
    defend_empire,
    exploration_and_probing,
    imperial_expansion,
    npe_conquest,
    review_news,
    war_cabinet,
)
from .core import (
    create_region_array,
    enforce_npe_data_links,
    get_regional_capital,
    implement_conquer_msn,
    implement_guard_msn,
    implement_jump_attack_msn,
    implement_raid_trn_msn,
    implement_refuel_msn,
    implement_return_msn,
    implement_stack_msn,
    implement_supply_msn,
    mid_course_correction,
    redesignate_empire,
    set_empire_defenses,
    set_fleet_return,
    set_raiding_fleet_new_target,
    state_department,
    state_dept_report,
)
from .types import (
    Kingdom1DataRecord,
    MissionTypes,
    NPECharacterRecord,
    PolicyTypes,
)

if TYPE_CHECKING:
    from ..environ import GameEnvironment

#: How often the empire re-reads the balance of power and redesignates worlds.
#: `Offset` is rolled per empire so the eight AIs do not all do it in the same
#: year.
REVIEW_PERIOD = 7


def _update_fleets(
    game: GameEnvironment,
    emp: Empire,
    rcap: list[IDNumber],
    persona: NPECharacterRecord,
    data: Kingdom1DataRecord,
) -> None:
    """Run the arrival handler for every fleet that has reached its destination.

    A mission with no arm here -- anything the kingdom never launches -- falls
    to the ``ELSE`` and the fleet is destroyed outright, cargo and all. That is
    the original's handling of a fleet whose record has drifted out of step.

    Two of the arms bank a conquest against the enemy's ``Balance``, which is
    what drives the state department's escalation from the winning side.
    """
    for i in range(1, NO_OF_FLEETS_PER_EMPIRE + 1):
        entry = data.FleetData[i]
        index = entry.Index
        if index <= 0 or index not in game.GlobalSets.SetOfActiveFleets:
            continue

        flt_id = IDNumber(ObjectTypes.Flt, index)
        mid_course_correction(game, emp, flt_id, rcap, data.FleetData)

        if get_fleet_status(game, flt_id) != FleetStatus.FReady:
            continue

        base_id = get_regional_capital(game, flt_id, rcap)
        current_mission = entry.Mission
        targ_id = entry.TargetID

        if current_mission == MissionTypes.ReturnMSN:
            implement_return_msn(game, flt_id, targ_id)
        elif current_mission == MissionTypes.RefuelMSN:
            implement_refuel_msn(game, flt_id, targ_id)
        elif current_mission == MissionTypes.GuardMSN:
            implement_guard_msn(game, flt_id, targ_id)
        elif current_mission == MissionTypes.StackMSN:
            implement_stack_msn(game, flt_id, data.FleetData)
        elif current_mission == MissionTypes.RaidTrnMSN:
            implement_raid_trn_msn(game, emp, flt_id, targ_id, base_id, data.FleetData)
        elif current_mission == MissionTypes.SupplyMSN:
            implement_supply_msn(game, emp, flt_id, targ_id, base_id, data.FleetData)
        elif current_mission == MissionTypes.SupplyTrnMSN:
            # A transport run home is just a return leg.
            implement_return_msn(game, flt_id, targ_id)
        elif current_mission == MissionTypes.ConquerMSN:
            # Read before the attack: after it the world answers to Emp.
            enemy_emp = get_status(game, targ_id)
            result = implement_conquer_msn(
                game, emp, flt_id, targ_id, base_id, data.FleetData
            )
            if result == AttackResultTypes.DefConqueredART:
                npe_conquest(game, emp, targ_id, result, rcap, persona)
                data.State[enemy_emp].Balance += 1
        elif current_mission in (MissionTypes.SlowAttackMSN, MissionTypes.JumpAttackMSN):
            enemy_emp = get_status(game, targ_id)
            result = implement_jump_attack_msn(
                game, emp, flt_id, targ_id, base_id, data.FleetData
            )
            if result == AttackResultTypes.DefConqueredART:
                npe_conquest(game, emp, targ_id, result, rcap, persona)
                data.State[enemy_emp].Balance += 1

                # The fleet stays as the garrison: it is unloaded onto the
                # world it just took and then struck off.
                abort_fleet(game, flt_id, targ_id, True)
                destroy_fleet(game, flt_id)
            elif result == AttackResultTypes.NoART:
                # Nothing happened -- look for something else to hit.
                set_raiding_fleet_new_target(
                    game, emp, flt_id, targ_id, base_id, data.FleetData, persona
                )
            else:
                set_fleet_return(game, emp, flt_id, base_id, data.FleetData)
        else:
            destroy_fleet(game, flt_id)


def _initialize_kingdom(
    game: GameEnvironment,
    emp: Empire,
    data: Kingdom1DataRecord,
    policy: PolicyTypes,
    persona: NPECharacterRecord,
) -> None:
    """Shared body of the two initialisers -- they differ only in their inputs."""
    for emp_i in PLAYER_EMPIRES:
        rec = data.State[emp_i]
        rec.Policy = policy
        rec.AttackChance = 50
        rec.Aggressiveness = 0
        rec.Balance = 0

    data.Persona = persona
    set_empire_defenses(game, emp)


def initialize_kingdom1_npe(
    game: GameEnvironment, emp: Empire, data: Kingdom1DataRecord
) -> None:
    """A passive kingdom: defends heavily, barely expands, provoked easily.

    ``ImpGene`` of 1--5 means `imperial_expansion` almost never fires, and
    ``_modify_persona`` drags ``Imperialist`` back down toward it all game. The
    aggression comes from ``Provoke`` at 75 instead: hit one and it climbs the
    policy ladder fast.
    """
    persona = NPECharacterRecord()
    persona.ImpGene = rnd(1, 5)
    persona.DefGene = rnd(50, 75)
    persona.OffGene = rnd(1, 2)
    persona.FactorGene = 15
    persona.RandomGene = 50

    persona.Defensive = persona.DefGene
    persona.Offensive = persona.OffGene
    persona.Techno = 50
    persona.Provoke = 75
    persona.Imperialist = persona.ImpGene
    persona.WorldPower = rnd(25, 75)
    persona.Honorable = 50
    persona.SphereX = rnd(25, 75)

    persona.Clock = 0
    persona.Offset = rnd(1, 10)

    _initialize_kingdom(game, emp, data, PolicyTypes.NeutralPLT, persona)


def initialize_kingdom2_npe(
    game: GameEnvironment, emp: Empire, data: Kingdom1DataRecord
) -> None:
    """An aggressive kingdom: starts at Harass toward everyone and expands hard.

    Every trait is the mirror of Kingdom1 -- high ``ImpGene``, low ``DefGene``,
    high ``OffGene`` -- and ``FactorGene`` of 25 against Kingdom1's 15 makes
    its temperament drift faster too.
    """
    persona = NPECharacterRecord()
    persona.ImpGene = rnd(50, 100)
    persona.DefGene = rnd(5, 10)
    persona.OffGene = rnd(50, 100)
    persona.FactorGene = 25
    persona.RandomGene = 50

    persona.Defensive = persona.DefGene
    persona.Offensive = persona.OffGene
    persona.Techno = 50
    persona.Provoke = rnd(50, 100)
    persona.Imperialist = persona.ImpGene
    persona.WorldPower = rnd(25, 75)
    persona.Honorable = 50
    persona.SphereX = rnd(25, 100)

    persona.Clock = 0
    persona.Offset = rnd(1, 10)

    _initialize_kingdom(game, emp, data, PolicyTypes.HarassPLT, persona)


def implement_kingdom1_npe(
    game: GameEnvironment, emp: Empire, data: Kingdom1DataRecord
) -> None:
    """One kingdom turn, in the order the original runs it.

    1. Repair the fleet-data links, and on the very first year take a reading
       of everyone's strength so the state department has something to work from.
    2. Build the region array -- everything downstream is relative to it.
    3. Run arriving fleets, *then* review the news. Fleets first means a fleet
       that landed this year has already acted before the AI reads about it.
    4. Foreign affairs: reassess policy, then act on it.
    5. Internal affairs: balance defenses, then try to expand.
    6. Every seventh year (offset per empire) re-read the balance of power and
       redesignate worlds.
    7. Spend whatever probes are left, and age the clock.

    Both kingdoms come through here; the difference is entirely in `Persona`.
    """
    enforce_npe_data_links(game, emp, data.FleetData)

    if data.Persona.Clock == 0:
        state_dept_report(game, emp, data.State)

    rcap = create_region_array(game, emp)

    _update_fleets(game, emp, rcap, data.Persona, data)
    review_news(game, emp, data.FleetData, rcap, data.Persona, data.State)

    # Wars and foreign affairs.
    state_department(game, emp, data.Persona, data.State)
    war_cabinet(game, emp, rcap, data.FleetData, data.Persona, data.State)

    # Internal affairs.
    defend_empire(game, emp, rcap, data.FleetData, data.Persona)
    imperial_expansion(game, emp, rcap, data.FleetData, data.Persona)

    if (data.Persona.Clock + data.Persona.Offset) % REVIEW_PERIOD == 0:
        state_dept_report(game, emp, data.State)
        redesignate_empire(game, emp, rcap, data.Persona)

    exploration_and_probing(game, emp, rcap, data.Persona)

    data.Persona.Clock += 1


def clean_up_kingdom_npe(game: GameEnvironment, data: Kingdom1DataRecord) -> None:
    """Release the persona's data. Nothing to unwind."""
