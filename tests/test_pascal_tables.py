"""Balance tables that are *not* in DATACNST.PAS, checked against their unit.

`test_datacnst_source.py` verifies 30 numeric and 12 string tables against
DATACNST.PAS, and porting convention 11 describes that as "the only automatic
check on a bulk transcription that a reviewer cannot eyeball". It was also
incomplete: **several units declare their own balance tables**, and those were
transcribed by hand with nothing checking them.

The six combat adjustments in ATTACK.PAS are the ones that matter most --
AGENTS.md already had to correct itself once about where they live, having
claimed `CombatTechAdj` was in DATACNST. A slip in any of them changes every
battle in the game and fails nothing else.

This is Phase 9 §9.3: validating the port's numbers against the Pascal's.
"""

from __future__ import annotations

import pytest
from pascal_source import PascalUnit, flatten

from recreon import attack, battle, intrface, newgame, resource, update
from recreon.npe import core as npe_core

#: (unit, table name, the ported object). Listed rather than discovered, so a
#: table vanishing from either side fails instead of quietly not being
#: compared -- the same reasoning as the DATACNST list.
NUMERIC_TABLES = [
    # ATTACK.PAS. The whole of combat's tuning, and none of it is in DATACNST.
    ("ATTACK", "CombatPower", lambda: attack.CombatPower),
    ("ATTACK", "CombatTechAdj", lambda: attack.CombatTechAdj),
    ("ATTACK", "CombatClassAdj", lambda: attack.CombatClassAdj),
    ("ATTACK", "CombatBaseAdj", lambda: attack.CombatBaseAdj),
    ("ATTACK", "GDMLaunch", lambda: attack.GDMLaunch),
    ("ATTACK", "GDMKill", lambda: attack.GDMKill),
    # UPDATE.PAS. World class drift and the population ceiling.
    ("UPDATE", "MaxPop", lambda: update.MaxPop),
    ("UPDATE", "ProbabilityOfChange", lambda: update.ProbabilityOfChange),
    ("UPDATE", "ProbabilityOfChaos", lambda: update.ProbabilityOfChaos),
    # NPEINTR.PAS. What the AI thinks a world is worth.
    ("NPEINTR", "NPETypeDefault", lambda: npe_core.NPETypeDefault),
    ("NPEINTR", "NPETypeValue", lambda: npe_core.NPETypeValue),
    ("NPEINTR", "NPEClassValue", lambda: npe_core.NPEClassValue),
    # NEWGAME.PAS. Scales starting military by an empire's technology.
    ("NEWGAME", "RndMilTechAdj", lambda: newgame.RndMilTechAdj),
    # INTRFACE.PAS. The industry cross-coupling matrix.
    ("INTRFACE", "Gamma", lambda: intrface.Gamma),
    # Units outside the v2.0 build, ported anyway -- see tests/test_dead_code.py.
    ("BATTLE", "MilitaryPower", lambda: battle.MilitaryPower),
    ("RESOURCE", "CargoSize", lambda: resource.CargoSize),
    ("RESOURCE", "TransCapacity", lambda: resource.TransCapacity),
]


@pytest.mark.parametrize(
    "unit,name,get", NUMERIC_TABLES, ids=[f"{u}.{n}" for u, n, _ in NUMERIC_TABLES]
)
def test_numeric_table_matches_its_unit(unit, name, get):
    assert flatten(get()) == PascalUnit(unit).numbers(name)


def test_target_of_chaos_maps_class_to_class():
    """`TargetOfChaos` is the one table whose *values* are enum names rather
    than numbers, so it cannot go through `numbers()`. A world in chaos drifts
    toward the class named here."""
    from recreon.types import WorldClass

    unit = PascalUnit("UPDATE")
    names = [
        token.strip()
        for token in unit.literal("TargetOfChaos").strip("()").split(",")
    ]

    assert len(names) == len(update.TargetOfChaos)
    for (source_cls, target_cls), pascal_name in zip(
        update.TargetOfChaos.items(), names, strict=True
    ):
        assert isinstance(source_cls, WorldClass)
        assert target_cls.name == pascal_name, source_cls


def test_the_empire_names_are_the_originals_fifty_nine():
    """The table's order *and* its count are load-bearing.

    `GetRandomEmpireName` rolls `Rnd(1, 59)` and re-rolls when the name is
    taken, so drawing from a pre-filtered list would call `Rnd` with a smaller
    bound and make a different number of draws -- diverging the generator from
    the first collision onward. This file once carried 16 invented names under
    a comment claiming the real table "is not in the source".
    """
    pascal = PascalUnit("NEWGAME").strings("RndEmpireName")

    assert len(pascal) == 59
    assert list(newgame.RND_EMPIRE_NAMES) == pascal


def test_the_help_index_page_numbers_are_the_originals():
    """HLPWIND.PAS's `IndexPageNo` -- the only surviving description of what
    the manual covered, since `ANACREON.HLP` never shipped."""
    from recreon import hlpwind

    pages = PascalUnit("HLPWIND").numbers("IndexPageNo")

    assert [float(page) for _, page in hlpwind.HELP_INDEX] == pages


def test_the_parameter_questions_are_the_originals_twenty_seven():
    """PLAYTURN.PAS's `QuestionArray`, transcribed with the parameter table."""
    from recreon import playturn

    pascal = PascalUnit("PLAYTURN").strings("QuestionArray")

    assert len(pascal) == 27
    assert list(playturn.QUESTIONS[1:]) == pascal


# --- What this does and does not cover ---------------------------------------


def test_every_attack_table_in_the_pascal_is_checked():
    """ATTACK.PAS declares exactly six constant tables and all six are above.

    A seventh appearing is a table someone added to the balance without this
    file noticing, which is the failure mode the list is guarding against.
    """
    import re

    unit = PascalUnit("ATTACK")
    declared = set(
        re.findall(
            r"^[ \t]*([A-Za-z_]\w*)\s*:\s*(?:ARRAY|array)\b[^=;]*=",
            unit.text,
            flags=re.M,
        )
    )
    checked = {name for u, name, _ in NUMERIC_TABLES if u == "ATTACK"}

    assert declared == checked


# The three ship-worth tables -- `MPower`, `CombatPower`, `MilitaryPower` --
# disagree, and `test_attack.py::test_battle_power_table_disagrees_with_the_others`
# pins that with exact values. Not repeated here; what this file adds is that
# all three now match the Pascal they were transcribed from, so the
# disagreement is the original's rather than a transcription slip.
