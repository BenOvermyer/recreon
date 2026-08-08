"""Pull a constant table out of a Pascal unit, so the port can be checked.

`tests/test_datacnst_source.py` proved the approach on DATACNST.PAS: parse the
declaration, flatten both sides, compare. This is the same machinery with the
source file as a parameter, because **balance tables are not all in DATACNST**
-- ATTACK.PAS carries the six combat adjustments, UPDATE.PAS the four class
tables, NPEINTR.PAS the AI's world valuations. Those are as load-bearing as
anything in DATACNST and were transcribed by hand with nothing checking them.

Not a test module itself; `tests/test_datacnst_source.py` and
`tests/test_pascal_tables.py` both import it.
"""

from __future__ import annotations

import re
from pathlib import Path

ORIGINAL = Path(__file__).parent.parent / "original"


def strip_comments(text: str) -> str:
    text = re.sub(r"\{[^}]*\}", " ", text)
    return re.sub(r"\(\*.*?\*\)", " ", text, flags=re.S)


class PascalUnit:
    """One `.PAS` file, with its constant declarations extractable by name."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.path = ORIGINAL / f"{name}.PAS"
        assert self.path.exists(), f"no such unit: {name}"
        # CP437; only the glyph tables use the high half, and latin-1 keeps
        # every byte round-trippable.
        self.text = self.path.read_text(encoding="latin-1")

    def declares(self, name: str) -> bool:
        return bool(
            re.search(
                rf"^[ \t]*{name}\s*:\s*(?:ARRAY|array)\b", self.text, flags=re.M
            )
        )

    def literal(self, name: str) -> str:
        """The right-hand side of one `Name: ARRAY ... = ...` declaration.

        Parentheses are balanced rather than scanning for `;`, because several
        blocks close with `);` followed by a trailing comment rather than at
        the end of a line, and a naive scan swallows the table after them.
        """
        match = re.search(
            rf"^[ \t]*{name}\s*:\s*(?:ARRAY|array)\b[^=]*=", self.text, flags=re.M
        )
        assert match, f"{name} is not declared in {self.name}.PAS"
        rest = strip_comments(self.text[match.end() :])

        if rest.lstrip().startswith("'"):
            # A packed literal: one string, one character per key.
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

    def numbers(self, name: str) -> list[float]:
        return [float(n) for n in re.findall(r"-?\d+\.?\d*", self.literal(name))]

    def strings(self, name: str) -> list[str]:
        return [
            s.replace("''", "'")
            for s in re.findall(r"'((?:[^']|'')*)'", self.literal(name))
        ]


def flatten(value) -> list[float]:
    """Every number in a ported table, in key order.

    Enums flatten to their ordinals, which is what makes a table like
    `TargetOfChaos` -- a mapping from one enum to another -- comparable to the
    Pascal, where the same table is a list of enum *names* rather than numbers.
    Those need :func:`ordinals` instead.
    """
    if isinstance(value, dict):
        return [n for key in value for n in flatten(value[key])]
    if isinstance(value, (list, tuple)):
        return [n for item in value for n in flatten(item)]
    if isinstance(value, bool):
        return [float(value)]
    if isinstance(value, (int, float)):
        return [float(value)]
    return []
