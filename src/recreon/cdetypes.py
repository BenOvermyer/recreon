"""Scenario/artifact scripting types.

Port of CDETYPES.PAS -- the bytecode format for the little interpreted language
that drives artifacts and scripted scenario events.

**Unreachable in v2.0**, and the interpreter is not "not yet ported" -- it is
*deliberately* unported. CODE.PAS, ARTIFACT.PAS and TRANSACT.PAS are all
outside `ANACREON.PAS`'s `USES` graph, and the directives that would reach them
are commented out of the scenario dispatch, so the shipped executable never
linked any of it. Reviving the subsystem is a feature decision, not a porting
task. `tests/test_dead_code.py` pins that nothing in the port imports this.

ARCHITECTURE.md does not list a module for this unit; it goes here at package
root to keep the one-module-per-unit mapping.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

from .galaxy import XYCoord
from .types import Empire, IDNumber


class VariableTypes(IntEnum):
    BoolVRT = 0
    ScalarVRT = 1
    EmpVRT = 2
    IDVRT = 3
    XYVRT = 4


#: What a VariableRecord may hold, per its VType tag.
VariableValue = bool | int | Empire | IDNumber | XYCoord


@dataclass(slots=True)
class VariableRecord:
    """A script variable.

    The original is a Pascal variant record -- one overlaid storage slot read
    through whichever field the ``VType`` tag selects. Here the tag stays and
    the variants collapse into a single ``Value``, since only the one selected
    by the tag was ever valid to read.
    """

    VType: VariableTypes = VariableTypes.ScalarVRT
    Value: VariableValue = 0


def register_array() -> list[VariableRecord]:
    """Pascal ``ARRAY [0..9]`` -- 0-based in the original, so no unused slot."""
    return [VariableRecord() for _ in range(10)]


class ActionTypes(IntEnum):
    """Script opcodes.

    The ``*CODE`` members are control flow; the ``*ACT`` members are actions.
    Comments give the operand meaning, where ``p1``..``p4`` are ``Parm``.
    """

    NoACT = 0

    CaseCODE = 1
    ElseCODE = 2
    EndCODE = 3
    IfCODE = 4
    SwitchCODE = 5
    WhileCODE = 6

    AnyKeyACT = 7  # prints message and waits for any key
    AssignACT = 8  # p1 := p2
    ClsACT = 9  # clears display screen
    CreateACT = 10  # create artifact of type p1 at p2
    DebugDumpACT = 11  # displays all registers
    DestructACT = 12  # destroy artifact p1
    DisplayACT = 13  # display text p1 on screen
    GetArtifactCoordACT = 14  # returns the coords of artifact in p1
    GetObjectPowerACT = 15
    IsEqualACT = 16  # p3 := (p1 = p2)
    IsGreaterACT = 17  # p3 := (p1 > p2)
    IsLesserACT = 18  # p3 := (p1 < p2)
    IsNotEqualACT = 19  # p3 := (p1 <> p2)
    MenuAddFleetsACT = 20
    MenuDisplayACT = 21
    MenuInitializeACT = 22  # initializes a menu of type p1
    NullACT = 23  # no action
    WinGameACT = 24  # p1 player wins the game


LAST_ACT = ActionTypes.WinGameACT

#: Pascal ``ActionArray = ARRAY [1..1000]``.
MAX_NO_OF_ACTIONS = 1000


@dataclass(slots=True)
class ActionRecord:
    """One instruction: an opcode, an inline operand, and four parameter bytes."""

    AType: ActionTypes = ActionTypes.NoACT
    Immediate: VariableRecord = field(default_factory=VariableRecord)
    #: Pascal ``ARRAY [1..4] OF Byte``; index 0 unused.
    Parm: list[int] = field(default_factory=lambda: [0] * 5)
