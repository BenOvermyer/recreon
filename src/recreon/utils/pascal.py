"""Turbo Pascal builtin semantics that differ from Python's.

Not a port of any one unit -- a compatibility shim for the handful of
builtins whose behaviour Python does not match. Using the Python equivalent
directly is a silent correctness bug, so ported code should call these.
"""

from __future__ import annotations

import math


def pascal_round(x: float) -> int:
    """Turbo Pascal ``Round``: ties go away from zero.

    Python's built-in ``round`` is banker's rounding, so ``round(0.5) == 0``
    and ``round(2.5) == 2``. Pascal gives 1 and 3. Every ``Round`` in the
    original must come through here.
    """
    return math.floor(x + 0.5) if x >= 0 else math.ceil(x - 0.5)


def trunc(x: float) -> int:
    """Turbo Pascal ``Trunc``: truncate toward zero.

    Matches Python's ``int()`` on floats; wrapped for symmetry with
    :func:`pascal_round` so ported code reads like the original and does not
    have to remember which of the two is safe.
    """
    return math.trunc(x)
