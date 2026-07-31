"""Checks on the scripting bytecode types ported from CDETYPES.PAS."""

from recreon.cdetypes import (
    LAST_ACT,
    ActionRecord,
    ActionTypes,
    VariableRecord,
    VariableTypes,
    register_array,
)
from recreon.galaxy import XYCoord
from recreon.types import Empire


def test_enum_sizes_match_pascal():
    assert len(VariableTypes) == 5
    assert len(ActionTypes) == 25


def test_last_act_sentinel():
    # CDETYPES.PAS: LastACT = WinGameACT. Bounds-checks on decoded opcodes
    # rely on this being the highest ordinal.
    assert LAST_ACT == ActionTypes.WinGameACT
    assert max(ActionTypes) == LAST_ACT


def test_registers_are_zero_based():
    # ARRAY [0..9] in the original, unlike most arrays in this codebase.
    registers = register_array()
    assert len(registers) == 10
    assert all(isinstance(r, VariableRecord) for r in registers)


def test_registers_are_independent():
    registers = register_array()
    registers[0].Value = 42
    assert registers[1].Value == 0


def test_variable_holds_any_tagged_type():
    assert VariableRecord(VariableTypes.BoolVRT, True).Value is True
    assert VariableRecord(VariableTypes.EmpVRT, Empire.Empire3).Value == Empire.Empire3
    assert VariableRecord(VariableTypes.XYVRT, XYCoord(4, 7)).Value == XYCoord(4, 7)


def test_action_params_are_one_based():
    action = ActionRecord()
    assert action.AType == ActionTypes.NoACT
    # Pascal ARRAY [1..4]; index 0 is the unused slot.
    assert len(action.Parm) == 5
