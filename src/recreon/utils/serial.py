"""JSON codec for the ported record types.

Not a port of anything. LOADSAVE.PAS and its siblings read and write records
with ``BlockRead``/``BlockWrite`` over raw memory, which is only possible
because a Turbo Pascal record has a fixed, known layout. Python's dataclasses
do not, so the sections in :mod:`recreon.loadsave` need something to turn a
record into JSON and back; this is it.

It walks the annotations rather than the values, so decoding restores the
declared types -- an ``IntEnum`` comes back as that enum, a ``set[Empire]``
as a set of :class:`~recreon.types.Empire`, not as the bare ints JSON stores.
That matters: nearly every ported routine compares enum members and indexes
dicts keyed by them, so a save that round-tripped ``Empire.Empire3`` as ``2``
would look right in a diff and fail at the first ``dict`` lookup.

Two things it deliberately does not do:

* **Unions with more than one non-``None`` member.** JSON carries no tag to
  pick between them, and inventing one would put a discriminator in the file
  that the game does not have. The single such field --
  :attr:`~recreon.npe.types.NPEDataRecord.Data` -- is dispatched on the ``Typ``
  beside it, which is what NPE.PAS's ``LoadNPE`` does too, so the sections
  handle it and this raises rather than guessing.
* **Bare containers**, e.g. a field annotated ``list`` with no element type.
  There is one (``FleetRecord.OrderData``); SaveFleets writes orders as their
  own block anyway, so :mod:`recreon.loadsave` follows the original and
  encodes them separately.
"""

from __future__ import annotations

import dataclasses
import typing
from enum import IntEnum
from types import UnionType
from typing import Any, Union

__all__ = ["SerialisationError", "decode", "encode", "encode_record"]


class SerialisationError(Exception):
    """A value or annotation the codec cannot handle."""


#: ``typing.get_type_hints`` is not cheap and the record types never change,
#: so resolved annotations are cached per class.
_HINTS: dict[type, dict[str, Any]] = {}


def _hints(cls: type) -> dict[str, Any]:
    cached = _HINTS.get(cls)
    if cached is None:
        # The record modules all use ``from __future__ import annotations``,
        # so the raw __annotations__ are strings; this resolves them against
        # the defining module.
        cached = typing.get_type_hints(cls)
        _HINTS[cls] = cached
    return cached


def _unwrap_optional(tp: Any) -> Any:
    """``X | None`` -> ``X``. Any other union is an error."""
    if typing.get_origin(tp) not in (Union, UnionType):
        return tp

    args = [a for a in typing.get_args(tp) if a is not type(None)]
    if len(args) == 1:
        return args[0]
    raise SerialisationError(
        f"cannot decode the union {tp!r}: JSON carries no tag to choose a member. "
        "Dispatch on the record's own type field instead, as LOADSAVE.PAS does."
    )


def encode(value: Any) -> Any:
    """Turn a record, or anything inside one, into JSON-safe data.

    Sets are sorted so that saving the same game twice produces the same
    bytes -- Python's set iteration order is not stable across runs, and an
    unstable save file makes round-trip tests and diffs useless.
    """
    if isinstance(value, IntEnum):
        return int(value)
    if isinstance(value, (bool, int, float, str)) or value is None:
        return value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: encode(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, (set, frozenset)):
        return sorted(encode(item) for item in value)
    if isinstance(value, dict):
        return {str(encode(k)): encode(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode(item) for item in value]

    raise SerialisationError(f"cannot encode {type(value).__name__}")


def _decode_key(tp: Any, key: str) -> Any:
    """JSON object keys are always strings; restore the declared key type."""
    tp = _unwrap_optional(tp)
    if isinstance(tp, type) and issubclass(tp, IntEnum):
        return tp(int(key))
    if tp is int:
        return int(key)
    if tp is str or tp is Any:
        return key
    raise SerialisationError(f"cannot decode a dict key of type {tp!r}")


def decode(tp: Any, data: Any) -> Any:
    """Rebuild a value of the declared type ``tp`` from JSON data."""
    tp = _unwrap_optional(tp)
    if data is None:
        return None

    origin = typing.get_origin(tp)

    if origin is None:
        if tp is Any:
            return data
        if isinstance(tp, type) and issubclass(tp, IntEnum):
            return tp(data)
        if dataclasses.is_dataclass(tp):
            hints = _hints(tp)
            # Fields missing from the file keep their defaults, which is how
            # a save written before a field existed still loads.
            return tp(
                **{
                    f.name: decode(hints[f.name], data[f.name])
                    for f in dataclasses.fields(tp)
                    if f.name in data
                }
            )
        if tp in (bool, int, float, str):
            return data
        if tp in (list, tuple, set, frozenset, dict):
            # An unparameterised container: there is no element type to decode
            # into, so the contents would come back as raw JSON.
            raise SerialisationError(
                f"cannot decode the bare container {tp!r}; annotate its element type "
                "or encode the field as its own block"
            )
        raise SerialisationError(f"cannot decode the annotation {tp!r}")

    if origin in (set, frozenset):
        (arg,) = typing.get_args(tp)
        return origin(decode(arg, item) for item in data)

    if origin is dict:
        key_tp, val_tp = typing.get_args(tp)
        return {
            _decode_key(key_tp, key): decode(val_tp, val) for key, val in data.items()
        }

    if origin in (list, tuple):
        args = typing.get_args(tp)
        if not args:
            raise SerialisationError(f"cannot decode the bare container {tp!r}")
        return [decode(args[0], item) for item in data]

    raise SerialisationError(f"cannot decode the annotation {tp!r}")


def encode_record(value: Any, *, skip: tuple[str, ...] = ()) -> dict:
    """Encode a record, omitting named fields.

    ``skip`` exists for fields the caller writes as their own block, the way
    SaveFleets writes a fleet's orders separately from the fleet.
    """
    encoded = encode(value)
    for name in skip:
        encoded.pop(name, None)
    return encoded
