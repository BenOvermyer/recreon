"""Check every DATACNST table against the Pascal it was transcribed from.

CLAUDE.md's rule is that the balance tables are transcribed exactly and never
re-derived, and `_table` already catches a row or key miscount at import time.
Nothing checked the *values* -- and for three tables this file long claimed
nothing could, on the belief that `CargoSpace`, `ObjName` and `MPower` were
declared in no file in the tree.

They are all in DATACNST.PAS. They looked absent because ten files in
`original/` carry CP437 box-drawing bytes, so `grep` classes them as binary and
`-I` skips them without saying so. DATACNST.PAS is one of them.

So this parses the Pascal and compares. It is the Phase 9 validation the plan
calls for, done early for the one file where a silent transcription slip would
change game balance without failing anything else.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from recreon import datacnst

SOURCE = Path(__file__).parent.parent / "original" / "DATACNST.PAS"

#: The Pascal is CP437; only the glyph tables use the high half.
PASCAL = SOURCE.read_text(encoding="latin-1")


def strip_comments(text: str) -> str:
    text = re.sub(r"\{[^}]*\}", " ", text)
    return re.sub(r"\(\*.*?\*\)", " ", text, flags=re.S)


def literal(name: str) -> str:
    """The right-hand side of one `Name: ARRAY ... = ...` declaration.

    Parentheses are balanced rather than scanning for `;`, because several
    blocks close with `);` followed by a trailing comment rather than at the
    end of a line -- `ThgAdj` and `ConsCargoNeeded` both do, and a naive scan
    swallows the table after them.
    """
    match = re.search(
        r"^[ \t]*" + name + r"\s*:\s*(?:ARRAY|array)\b[^=]*=", PASCAL, flags=re.M
    )
    assert match, f"{name} is not declared in DATACNST.PAS"
    rest = strip_comments(PASCAL[match.end() :])

    if rest.lstrip().startswith("'"):
        # A packed literal: one string, one character per key. TypeStr et al.
        return rest[: rest.index(";")]

    start = rest.index("(")
    depth = 0
    for i in range(start, len(rest)):
        if rest[i] == "(":
            depth += 1
        elif rest[i] == ")":
            depth -= 1
            if depth == 0:
                return rest[start : i + 1]
    raise AssertionError(f"unbalanced parentheses in {name}")


def pascal_numbers(name: str) -> list[float]:
    return [float(n) for n in re.findall(r"-?\d+\.?\d*", literal(name))]


def pascal_strings(name: str) -> list[str]:
    return [s.replace("''", "'") for s in re.findall(r"'((?:[^']|'')*)'", literal(name))]


def flatten(value) -> list[float]:
    """Every number in a ported table, in key order."""
    if isinstance(value, dict):
        return [n for key in value for n in flatten(value[key])]
    if isinstance(value, (list, tuple)):
        return [n for item in value for n in flatten(item)]
    if isinstance(value, bool):
        return [float(value)]
    if isinstance(value, (int, float)):
        return [float(value)]
    return []


#: Every numeric table in DATACNST.PAS. Listed rather than discovered so that
#: a table vanishing from either side fails instead of quietly not being
#: compared.
NUMERIC_TABLES = [
    "BasePop",
    "ClassIndAdj",
    "CombatTable",
    "ConsCargoNeeded",
    "DefAdj",
    "DefBuildRate",
    "DirX",
    "DirY",
    "FltMovementRate",
    "FuelCap",
    "FuelCons",
    "ISSP",
    "MPower",
    "MilitPer",
    "NewIndRawN",
    "OptMilitary",
    "ProtecNeeded",
    "ProtecOffered",
    "RawM",
    "ShipValue",
    "TechAdj",
    "TechAdj2",
    "ThgAdj",
    "TriResByClass",
    "TrnAdj",
    "TypeData",
    "WeapEff",
    "YearsToBuild",
]

#: Tables of quoted strings, one per key.
STRING_TABLES = [
    "IndusNames",
    "ObjName",
    "TechN",
    "TechStr",
    "TechnologyName",
    "ThingNames",
    "TypeName",
]

#: Tables written as one packed string, one character per key.
CHAR_TABLES = ["ClassStr", "SYLetN", "TypeStr"]

#: Glyph tables: CP437 characters in the Pascal, stored as code points here
#: because the port draws through Textual rather than DOS video memory.
GLYPH_TABLES = ["BaseTypeData", "GateTypeData"]


@pytest.mark.parametrize("name", NUMERIC_TABLES)
def test_numeric_table_matches_the_pascal(name):
    ported = getattr(datacnst, name)
    assert flatten(ported) == pascal_numbers(name)


@pytest.mark.parametrize("name", STRING_TABLES)
def test_string_table_matches_the_pascal(name):
    ported = getattr(datacnst, name)
    assert [str(v) for v in ported.values()] == pascal_strings(name)


@pytest.mark.parametrize("name", CHAR_TABLES)
def test_char_table_matches_the_pascal(name):
    ported = getattr(datacnst, name)
    assert [str(v) for v in ported.values()] == list(pascal_strings(name)[0])


@pytest.mark.parametrize("name", GLYPH_TABLES)
def test_glyph_table_matches_the_pascal_code_points(name):
    ported = getattr(datacnst, name)
    assert [int(v) for v in ported.values()] == [
        ord(c) for c in pascal_strings(name)[0]
    ]


def test_the_three_tables_this_repo_thought_were_missing_are_present():
    """`CargoSpace`, `ObjName` and `MPower` are declared in DATACNST.PAS.

    Kept as its own test because the claim that they were not is load-bearing
    in reverse: it is why #33 was filed as unresolvable, and why porting
    convention 11 used to carve out an exception to "transcribed exactly".
    """
    for name in ["CargoSpace", "ObjName", "MPower"]:
        assert re.search(rf"^[ \t]*{name}\s*:\s*ARRAY", PASCAL, flags=re.M)

    assert flatten(datacnst.CargoSpace) == pascal_numbers("CargoSpace")
    assert flatten(datacnst.MPower) == pascal_numbers("MPower")
    assert [str(v) for v in datacnst.ObjName.values()] == pascal_strings("ObjName")


def test_mpower_stops_at_trn():
    """`MPower: ARRAY [LAM..trn] OF Byte` -- troops are past its end.

    This is what #33 turns on. `AttackSeverity` indexes it with `men` (12) and
    `nnj` (13) after any ground assault, which is an out-of-bounds read in the
    original rather than a lookup of undocumented entries.
    """
    from recreon.types import TechnologyTypes

    assert re.search(r"MPower\s*:\s*ARRAY\s*\[LAM\.\.trn\]", PASCAL)
    assert max(datacnst.MPower) == TechnologyTypes.trn
    assert TechnologyTypes.men not in datacnst.MPower
    assert TechnologyTypes.nnj not in datacnst.MPower
