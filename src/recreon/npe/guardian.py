"""The guardian empire.

Port of NPE03.PAS, and by a wide margin the simplest of the four. A guardian
does exactly one thing: every year, each of its worlds and starbases holding
LAMs fires them at nearby fleets, hardest target first. It builds nothing,
launches nothing, expands nowhere, and never consults a persona -- the
`NPECharacterRecord` machinery the other personas run on is not used here at
all, and `GuardianDataRecord` is allocated and then never read.

Two things about the targeting are worth knowing before reading it as a purely
defensive AI:

**It shoots at everyone.** The filter is ``GetStatus(FltID) <> Emp`` -- any
fleet that is not the guardian's own. Neutral empires, empires it has never
met and independents are all fired on the moment they come within 5 sectors of
a world, unprovoked. There is no policy, no `StateDeptArray`, and nothing that
distinguishes an attacker from a passer-by.

**Priority is military power, so the biggest fleet is hit first** and the
missiles are rationed across targets by that same weight -- ``Rnd(75,150) *
priority`` per target, until either the targets or the LAMs run out.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..attack import lam_attack
from ..misc import distance, military_power
from ..primintr import (
    get_coord,
    get_defns,
    get_ships,
    get_status,
    known,
    put_defns,
)
from ..types import (
    MAX_NO_OF_FLEETS,
    MAX_NO_OF_STARBASES,
    Empire,
    IDNumber,
    ObjectTypes,
    TechnologyTypes,
    defns_array,
)
from ..utils.int_utils import greater_int, lesser_int, rnd
from .core import set_empire_defenses
from .types import GuardianDataRecord

if TYPE_CHECKING:
    from ..environ import GameEnvironment

T = TechnologyTypes

#: Pascal's ``MaxInt`` -- the ceiling a target's priority is clamped to.
MAX_INT = 32767

#: How far a base will reach out to shoot at something.
LAM_RANGE = 5


def _grdn_lam_attack(game: GameEnvironment, emp: Empire, base_id: IDNumber) -> None:
    """Spend ``base_id``'s LAM stock on every fleet within range.

    Targets are scored by military power over 1000, floored at 1 so anything
    that qualifies is worth at least one salvo, and taken strongest first. Each
    gets ``Rnd(75,150)`` missiles per point of priority, capped by what is
    left, and the loop ends when the stock is empty or nothing is left to hit.
    """
    defns = get_defns(game, base_id)
    no_of_lams = defns[T.LAM]
    base_xy = get_coord(game, base_id)

    # Score every fleet in range. Note the ownership test is "not mine" rather
    # than "hostile": a guardian fires on neutrals and independents alike.
    priority: dict[int, int] = {}
    null_df = defns_array()
    for i in range(1, MAX_NO_OF_FLEETS + 1):
        if i not in game.GlobalSets.SetOfActiveFleets:
            continue
        flt_id = IDNumber(ObjectTypes.Flt, i)
        if (
            known(game, emp, flt_id)
            and distance(get_coord(game, flt_id), base_xy) <= LAM_RANGE
            and get_status(game, flt_id) != emp
        ):
            flt_sh = get_ships(game, flt_id)
            priority[i] = lesser_int(
                MAX_INT, greater_int(1, military_power(flt_sh, null_df) // 1000)
            )

    while True:
        best_priority = 0
        best_target = 0
        for i in range(1, MAX_NO_OF_FLEETS + 1):
            if priority.get(i, 0) > best_priority:
                best_priority = priority[i]
                best_target = i

        if best_priority > 0:
            flt_id = IDNumber(ObjectTypes.Flt, best_target)
            lams_to_use = lesser_int(no_of_lams, rnd(75, 150) * best_priority)
            lam_attack(game, emp, lams_to_use, flt_id)
            priority[best_target] = 0
            no_of_lams -= lams_to_use

        if best_priority == 0 or no_of_lams == 0:
            break

    # Written back whatever happened, so a base that found nothing to shoot at
    # still stores the stock it started with.
    defns = get_defns(game, base_id)
    defns[T.LAM] = no_of_lams
    put_defns(game, base_id, defns)


def _grdn_update_bases(game: GameEnvironment, emp: Empire) -> None:
    """Fire from every world and starbase that has missiles to fire."""
    for i in range(1, game.NoOfPlanets + 1):
        if i in game.GlobalSets.SetOfPlanetsOf[emp]:
            base_id = IDNumber(ObjectTypes.Pln, i)
            if get_defns(game, base_id)[T.LAM] > 0:
                _grdn_lam_attack(game, emp, base_id)

    for i in range(1, MAX_NO_OF_STARBASES + 1):
        if i in game.GlobalSets.SetOfStarbasesOf[emp]:
            base_id = IDNumber(ObjectTypes.Base, i)
            if get_defns(game, base_id)[T.LAM] > 0:
                _grdn_lam_attack(game, emp, base_id)


def initialize_guardian_npe(
    game: GameEnvironment, emp: Empire, data: GuardianDataRecord
) -> None:
    """Roll the empire's defense distribution. Nothing else is set up.

    The original allocates a `GuardianDataRecord` here and never writes a field
    of it -- `ImplementGuardianNPE` opens a ``WITH Data^`` block whose body
    reads nothing from the record. It is carried for save/load symmetry with
    the other three personas and for no other reason.
    """
    set_empire_defenses(game, emp)


def implement_guardian_npe(
    game: GameEnvironment, emp: Empire, data: GuardianDataRecord
) -> None:
    """Run one guardian turn: shoot, and nothing else.

    No fleets, no construction, no diplomacy, no expansion. A guardian that
    runs out of LAMs -- it has no way to build more beyond ordinary world
    production -- does nothing at all for the rest of the game.
    """
    _grdn_update_bases(game, emp)


def clean_up_guardian_npe(game: GameEnvironment, data: GuardianDataRecord) -> None:
    """Release the persona's data. Nothing to unwind."""
