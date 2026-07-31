"""Real number routines.

Port of REAL1.PAS.
"""

from __future__ import annotations

import math


def expnt(base: float, exponent: float) -> float:
    """``base`` raised to ``exponent``.

    The original computes ``Exp(Exponent * Ln(Base))`` because Turbo Pascal
    had no power operator. That form is undefined for ``base <= 0``; Python's
    ``**`` is kept here since it agrees for every value the game actually
    passes (population, which is clamped to at least 1 before the call).
    """
    return math.pow(base, exponent)
