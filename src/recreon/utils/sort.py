"""Sorting, ported from QSORT.PAS.

The original sorts records by **the first Word of each element** and nothing
else -- `QuickSortD` casts the array to `ARRAY [0..32766] OF Word` and compares
`A[i*Size]`, where `Size` has been halved into words. Whatever follows that
first two bytes is carried along but never looked at.

That has a consequence worth stating loudly, because it is invisible in the
record declarations and it decides what order the status windows list things
in. **On little-endian x86 the first Word of a record whose first two fields
are single bytes is `second*256 + first`** -- so the *second* byte is the major
key. Both callers are written as though the first field sorted first, and
neither does:

* `STAWIND.PAS`'s `RECORD Pop: Byte; Tech: TechLevel; ID: IDNumber END` sorts
  by **technology**, with population only breaking ties.
* `FLTWIND.PAS`'s `RECORD XY: XYCoord; ID: IDNumber END` sorts by **y**, with
  x only breaking ties -- so fleets list from the bottom of the map upwards.

Whether that was intended is unknowable; it is certainly what players saw.

The algorithm itself is reproduced rather than replaced by `list.sort` because
the key is coarse -- two bytes -- so ties are the common case, and a stable
sort would put tied rows in a different order from the one the original showed.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def quick_sort_d(
    items: list[Any], key: Callable[[Any], int], first: int, last: int
) -> None:
    """Sort ``items[first-1:last]`` descending, in place. ``QuickSortD``.

    ``first`` and ``last`` are 1-based and inclusive, as the original's are;
    the Pascal converts them with ``SortD(First-1,Last-1)`` and so does this.

    Hoare partitioning around the middle element, whose key is taken *by value*
    before any swapping -- the original copies the pivot record out with
    ``Move`` for exactly that reason.
    """

    def sort_d(lo: int, hi: int) -> None:
        i, j = lo, hi
        pivot = key(items[(lo + hi) // 2])
        while True:
            while key(items[i]) > pivot:
                i += 1
            while pivot > key(items[j]):
                j -= 1
            if i <= j:
                items[i], items[j] = items[j], items[i]
                i += 1
                j -= 1
            if i > j:
                break
        if lo < j:
            sort_d(lo, j)
        if i < hi:
            sort_d(i, hi)

    sort_d(first - 1, last - 1)


def quick_sort_a(
    items: list[Any], key: Callable[[Any], int], first: int, last: int
) -> None:
    """Ascending twin of :func:`quick_sort_d`. ``QuickSortA``.

    Declared in QSORT.PAS's interface but called from nowhere in v2.0. Ported
    for completeness, since the unit is only useful as a pair.
    """

    def sort_a(lo: int, hi: int) -> None:
        i, j = lo, hi
        pivot = key(items[(lo + hi) // 2])
        while True:
            while key(items[i]) < pivot:
                i += 1
            while pivot < key(items[j]):
                j -= 1
            if i <= j:
                items[i], items[j] = items[j], items[i]
                i += 1
                j -= 1
            if i > j:
                break
        if lo < j:
            sort_a(lo, j)
        if i < hi:
            sort_a(i, hi)

    sort_a(first - 1, last - 1)


def word_key(first_byte: int, second_byte: int) -> int:
    """The Word the original actually compares, from two byte-wide fields.

    Little-endian: the second field is the high byte and therefore the major
    key. Both callers pass fields that fit in a byte -- `Coordinate` is 0..100
    and `TechLevel` has eleven members -- so no masking is needed, but the
    shift is what makes the ordering what it is.
    """
    return (second_byte << 8) | first_byte


__all__ = ["quick_sort_a", "quick_sort_d", "word_key"]
