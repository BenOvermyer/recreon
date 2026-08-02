"""Integer routines.

Port of INT.PAS. ``SwapInt`` is dropped -- Python has tuple assignment.
"""

from __future__ import annotations

from .pascal import pascal_random, trunc

#: Turbo Pascal's 16-bit ``MaxInt``, the clamp bound used by IntLmt.
MAXINT = 32767


def sgn(x: int) -> int:
    """-1, 0 or +1 according to the sign of ``x``."""
    if x == 0:
        return 0
    return -1 if x < 0 else 1


def int_lmt(x: float) -> int:
    """Truncate to an integer, clamped to -MaxInt..MaxInt."""
    if x > MAXINT:
        return MAXINT
    if x < -MAXINT:
        return -MAXINT
    return trunc(x)


def greater_int(a: int, b: int) -> int:
    return a if a > b else b


def lesser_int(a: int, b: int) -> int:
    return a if a < b else b


def isqrt(x: int) -> int:
    """Square root of ``x`` rounded to the nearest integer.

    The original walks the sequence of odd numbers rather than calling Sqrt,
    presumably to avoid floating point on a 1988 target. Ported literally: it
    is cheap, and matching it exactly rules out any edge-case disagreement at
    the rounding boundary.
    """
    odd_seq = -1
    square = 0

    while True:
        odd_seq += 2
        square += odd_seq
        if x < square:
            break

    root = (odd_seq >> 1) + 1
    if x <= square - root:
        root -= 1

    return root


def rnd(minimum: int, maximum: int) -> int:
    """Random integer in ``minimum..maximum`` inclusive.

    Returns ``minimum`` when ``maximum <= minimum``, as the original does.

    Goes through Turbo Pascal's generator rather than Python's, so a scenario
    seed reproduces the galaxy the DOS build produced. Every random draw in
    the game funnels through here.
    """
    if maximum <= minimum:
        return minimum
    return pascal_random((maximum - minimum) + 1) + minimum


def rnd_var(value: int, variation: int) -> int:
    """A random integer within ``variation`` percent of ``value``."""
    delta = trunc(value * (variation / 100))
    return rnd(value - delta, value + delta)
