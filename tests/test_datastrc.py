"""Milestone 1: the core data structures instantiate and are 1-based."""

from recreon.datastrc import (
    MAXINT16,
    FleetRecord,
    PlanetRecord,
    UniverseRecord,
    fuel_of,
    set_fuel,
)
from recreon.types import (
    CARGO_TYPES,
    MAX_NO_OF_CONSTR_SITES,
    MAX_NO_OF_FLEETS,
    MAX_NO_OF_PLANETS,
    MAX_NO_OF_STARBASES,
    MAX_NO_OF_STARGATES,
    SHIP_TYPES,
    Empire,
    TechnologyTypes,
)


def test_universe_instantiates():
    universe = UniverseRecord()
    assert isinstance(universe.Planet[1], PlanetRecord)
    assert set(universe.EmpireData) == set(Empire)


def test_entity_arrays_are_one_based():
    universe = UniverseRecord()
    # Index 0 is unused; the last valid index equals the Pascal upper bound.
    assert universe.Planet[0] is None
    assert len(universe.Planet) == MAX_NO_OF_PLANETS + 1
    assert universe.Planet[MAX_NO_OF_PLANETS] is not None

    assert len(universe.Starbase) == MAX_NO_OF_STARBASES + 1
    assert len(universe.Stargate) == MAX_NO_OF_STARGATES + 1
    assert len(universe.Constr) == MAX_NO_OF_CONSTR_SITES + 1


def test_fleet_slots_start_empty():
    # FleetArray is an array of pointers in the original, so every slot is
    # genuinely absent until a fleet is deployed.
    universe = UniverseRecord()
    assert len(universe.Fleet) == MAX_NO_OF_FLEETS + 1
    assert all(slot is None for slot in universe.Fleet)


def test_records_do_not_share_mutable_state():
    universe = UniverseRecord()
    universe.Planet[1].Ships[TechnologyTypes.fgt] = 100
    universe.Planet[1].ScoutedBy.add(Empire.Empire1)

    assert universe.Planet[2].Ships[TechnologyTypes.fgt] == 0
    assert universe.Planet[2].ScoutedBy == set()


def test_resource_dicts_are_keyed_by_subrange():
    planet = PlanetRecord()
    assert tuple(planet.Ships) == SHIP_TYPES
    assert tuple(planet.Cargo) == CARGO_TYPES


def test_split_fuel_round_trips():
    # Fuel is stored as FuelHigh * MaxInt + Fuel because a 16-bit Integer
    # could not hold the range.
    fleet = FleetRecord()
    set_fuel(fleet, 3 * MAXINT16 + 17)
    assert fleet.FuelHigh == 3
    assert fleet.Fuel == 17
    assert fuel_of(fleet) == 3 * MAXINT16 + 17
