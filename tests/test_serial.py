"""The JSON codec the save sections are built on.

Not a port of anything -- the original writes records straight out of memory
with ``BlockWrite`` -- so these test the codec's own contract rather than any
Pascal behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from recreon.datastrc import PlanetRecord
from recreon.galaxy import SectorRecord, XYCoord
from recreon.types import Empire, IDNumber, ObjectTypes, TechLevel, TechnologyTypes
from recreon.utils.serial import SerialisationError, decode, encode, encode_record


def round_trip(cls, value):
    return decode(cls, encode(value))


# --- Types are restored, not merely preserved --------------------------------


def test_an_enum_comes_back_as_the_enum():
    assert encode(Empire.Empire3) == 2
    assert decode(Empire, 2) is Empire.Empire3


def test_a_nested_record_round_trips():
    original = IDNumber(ObjectTypes.Flt, 17)
    restored = round_trip(IDNumber, original)

    assert restored == original
    assert restored.ObjTyp is ObjectTypes.Flt


def test_a_set_of_enums_comes_back_as_enums():
    """JSON has no set and no enum, so both have to be rebuilt from a list of
    ints -- and the members have to be enum instances, because the callers
    index enum-keyed dicts with them."""
    sector = SectorRecord(Flts={Empire.Empire2, Empire.Empire5})
    restored = round_trip(SectorRecord, sector)

    assert restored.Flts == {Empire.Empire2, Empire.Empire5}
    assert all(isinstance(emp, Empire) for emp in restored.Flts)


def test_an_enum_keyed_dict_comes_back_keyed_by_enums():
    planet = PlanetRecord()
    planet.Cargo[TechnologyTypes.tri] = 250
    restored = round_trip(PlanetRecord, planet)

    assert restored.Cargo[TechnologyTypes.tri] == 250
    assert all(isinstance(key, TechnologyTypes) for key in restored.Cargo)


def test_a_whole_planet_round_trips():
    planet = PlanetRecord(
        XY=XYCoord(4, 9),
        Emp=Empire.Empire2,
        Tech=TechLevel.StrTchLvl,
        Pop=1234,
        KnownBy={Empire.Empire1},
    )
    assert round_trip(PlanetRecord, planet) == planet


def test_encoding_is_stable_across_runs():
    """Sets are sorted on the way out.

    Python's set iteration order is not stable, and an unstable save file
    makes both the round-trip tests and any diff of two saves useless.
    """
    sector = SectorRecord(Flts=set(Empire), MineScout=set(Empire))
    assert encode(sector) == encode(sector)
    assert encode(sector)["Flts"] == sorted(encode(sector)["Flts"])


# --- Defaults and omissions --------------------------------------------------


def test_a_field_missing_from_the_data_keeps_its_default():
    """Which is what lets a save written before a field existed still load."""
    restored = decode(IDNumber, {"Index": 5})

    assert restored.Index == 5
    assert restored.ObjTyp is ObjectTypes.Void


def test_encode_record_can_omit_fields():
    """``skip`` is how loadsave writes a fleet's orders as their own block,
    the way SaveFleets does."""
    encoded = encode_record(IDNumber(ObjectTypes.Pln, 3), skip=("ObjTyp",))

    assert encoded == {"Index": 3}


def test_none_survives_as_none():
    assert encode(None) is None
    assert decode(IDNumber, None) is None


# --- What it refuses ---------------------------------------------------------


@dataclass
class _Ambiguous:
    value: IDNumber | XYCoord = field(default_factory=IDNumber)


def test_an_ambiguous_union_is_refused_rather_than_guessed():
    """JSON carries no tag to choose a union member.

    The one such field in the game -- ``NPEDataRecord.Data`` -- is dispatched
    on the ``Typ`` beside it, exactly as NPE.PAS's ``LoadNPE`` does, so the
    codec refuses rather than inventing a discriminator the game does not have.
    """
    with pytest.raises(SerialisationError, match="no tag to choose"):
        decode(_Ambiguous, {"value": {"Index": 1}})


@dataclass
class _Bare:
    items: list = field(default_factory=list)


def test_a_bare_container_is_refused():
    """``FleetRecord.OrderData`` is the only one, and loadsave encodes it
    separately."""
    with pytest.raises(SerialisationError, match="bare container"):
        decode(_Bare, {"items": [1, 2]})


def test_an_unencodable_value_is_refused():
    with pytest.raises(SerialisationError, match="cannot encode"):
        encode(object())
