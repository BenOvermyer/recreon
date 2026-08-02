"""Turbo Pascal builtin semantics that differ from Python's.

Not a port of any one unit -- a compatibility shim for the handful of
builtins whose behaviour Python does not match. Using the Python equivalent
directly is a silent correctness bug, so ported code should call these.
"""

from __future__ import annotations

import math
import time


def pascal_round(x: float) -> int:
    """Turbo Pascal ``Round``: ties go away from zero.

    Python's built-in ``round`` is banker's rounding, so ``round(0.5) == 0``
    and ``round(2.5) == 2``. Pascal gives 1 and 3. Every ``Round`` in the
    original must come through here.
    """
    return math.floor(x + 0.5) if x >= 0 else math.ceil(x - 0.5)


def pascal_val(s: str) -> int:
    """Turbo Pascal ``Val`` on an Integer: parse, or raise ``ValueError``.

    Python's ``int`` accepts surrounding whitespace, underscores as digit
    separators and a unicode minus; Pascal's ``Val`` reports an error at the
    offending character for all three. The difference matters wherever a
    parse failure is meant to be caught rather than silently succeed.
    """
    body = s[1:] if s[:1] in "+-" else s
    if not body.isascii() or not body.isdigit():
        raise ValueError(f"invalid integer: {s!r}")
    return int(s)


def trunc(x: float) -> int:
    """Turbo Pascal ``Trunc``: truncate toward zero.

    Matches Python's ``int()`` on floats; wrapped for symmetry with
    :func:`pascal_round` so ported code reads like the original and does not
    have to remember which of the two is safe.
    """
    return math.trunc(x)


# --- Random ------------------------------------------------------------------
#
# Borland's linear congruential generator, as used by Turbo Pascal 5 through 7
# and every Delphi. Reproducing it exactly is what lets a scenario's `Seed`
# regenerate the galaxy the DOS build produced from the same seed -- the whole
# reason it is here rather than a call to Python's `random`.
#
# `RandSeed` is a System-unit global in the original and stays a module global
# here rather than moving onto GameEnvironment: `Rnd` is called from a dozen
# modules that have no game to thread through, exactly as in the Pascal.

#: The multiplier, $08088405. Together with an increment of 1 and a modulus of
#: 2**32 this gives a full-period sequence over the 32-bit seed space.
RAND_MULTIPLIER = 134775813
RAND_INCREMENT = 1
RAND_MODULUS = 1 << 32

#: Pascal's ``Random(Range: Word)`` takes a 16-bit range; larger values wrap.
RAND_MAX_RANGE = 1 << 16

_rand_seed = 0


def rand_seed() -> int:
    """Pascal's ``RandSeed``, as the signed LongInt the original exposes."""
    return _rand_seed - RAND_MODULUS if _rand_seed >= RAND_MODULUS // 2 else _rand_seed


def set_rand_seed(value: int) -> None:
    """Assign ``RandSeed``. Accepts the signed or unsigned form of the value."""
    global _rand_seed
    _rand_seed = value % RAND_MODULUS


def randomize() -> None:
    """Pascal's ``Randomize``: seed unpredictably.

    The original reads the DOS clock into RandSeed. The entropy source differs
    here; what matters is only that the result is not reproducible, which is
    the whole contract of a zero ``Seed`` in a scenario file.
    """
    set_rand_seed(time.time_ns())


def _next_rand() -> int:
    """Advance RandSeed and return it as an unsigned 32-bit value."""
    global _rand_seed
    _rand_seed = (_rand_seed * RAND_MULTIPLIER + RAND_INCREMENT) % RAND_MODULUS
    return _rand_seed


def pascal_random(range_: int) -> int:
    """Pascal's ``Random(Range: Word): Word`` -- an integer in ``0..range-1``.

    The seed advances first, then the result is the top 32 bits of the
    64-bit product ``seed * range`` -- equivalently ``(seed / 2**32) * range``
    truncated. It is *not* ``seed mod range``, a common but wrong description
    that produces a different sequence.

    ``Random(1)`` is therefore always 0, and ``Random(0)`` is too: both are
    quirks of the original that call sites depend on.
    """
    return (_next_rand() * (range_ % RAND_MAX_RANGE)) >> 32


def pascal_random_real() -> float:
    """Pascal's ``Random: Real`` -- a float in ``[0, 1)``.

    Takes values in multiples of 2**-32, since it is just the fresh seed
    divided by the modulus.
    """
    return _next_rand() / RAND_MODULUS
