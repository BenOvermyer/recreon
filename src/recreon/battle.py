"""Simplified attack resolution.

Port of BATTLE.PAS.

Where :mod:`recreon.attack` fights out an engagement group by group and shell
by shell, this reduces both sides to a single power number and settles a round
in one step. Nothing in the shipped v2.0 source calls it -- it is a second,
coarser combat model that was written but never wired up. It is ported because
it is a complete unit with its own balance table, and because that table is
the only surviving statement of relative ship worth outside ``MPower`` and
``CombatPower``, both of which disagree with it.

The empire arguments are accepted and ignored, exactly as in the original --
the tech adjustment the signature anticipates was never written.
"""

from __future__ import annotations

from .types import (
    FIRST_WAR_MACHINE,
    LAST_WAR_MACHINE,
    Empire,
    TechnologyTypes,
    tech_range,
)
from .utils.int_utils import greater_int, lesser_int, rnd
from .utils.pascal import pascal_div, pascal_round

#: Everything that can fight, LAM through trn.
WAR_MACHINES = tech_range(FIRST_WAR_MACHINE, LAST_WAR_MACHINE)

#: Worth of each war machine in this model. Distinct from ``datacnst.MPower``
#: and ``attack.CombatPower``, which score the same units differently; nothing
#: reconciles the three.
MilitaryPower: dict[TechnologyTypes, int] = dict(
    zip(
        WAR_MACHINES,
        # LAM def GDM ion fgt hkr jmp jtn pen ssp trn
        (30, 75, 10, 25, 2, 10, 4, 1, 15, 100, 1),
        strict=True,
    )
)


def calc_military_power(emp: Empire, force: dict[TechnologyTypes, int]) -> int:
    """Total worth of an attack force.

    ``emp`` is unused; the original takes it and never reads it.
    """
    return sum(force[thing] * MilitaryPower[thing] for thing in WAR_MACHINES)


def calc_attack_round(
    att_emp: Empire,
    def_emp: Empire,
    attacker: dict[TechnologyTypes, int],
    defender: dict[TechnologyTypes, int],
) -> dict[TechnologyTypes, int]:
    """Damage ``attacker`` inflicts on ``defender`` in one round.

    Returns the casualties; neither input is modified, and cargo riding in
    destroyed transports is *not* accounted for -- callers must rebalance the
    fleet themselves.

    The result is a percentage of the defending force, scaled by the power
    ratio and jittered twice: once on the round's overall severity, once per
    ship type. Not deterministic; identical inputs give different answers.
    """
    attack_power = calc_military_power(att_emp, attacker)
    defense_power = calc_military_power(def_emp, defender)

    casualties = dict.fromkeys(WAR_MACHINES, 0)
    if attack_power > 0 and defense_power > 0:
        # Per cent of the defending force destroyed, in tenths of a per cent.
        destroyed = lesser_int(
            1000,
            pascal_round((250.0 * attack_power + 1000.0 * rnd(1, 100)) / defense_power),
        )

        for thing in WAR_MACHINES:
            casualties[thing] = lesser_int(
                defender[thing],
                greater_int(
                    0,
                    # Truncating division, not flooring: the jitter can take
                    # the dividend negative.
                    pascal_div((destroyed + rnd(-50, 50)) * defender[thing], 1000)
                    + rnd(-5, 5),
                ),
            )

    return casualties


__all__ = [
    "WAR_MACHINES",
    "MilitaryPower",
    "calc_attack_round",
    "calc_military_power",
]
