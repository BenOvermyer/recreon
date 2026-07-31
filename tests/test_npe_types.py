"""Checks on the AI types ported from NPETYPES.PAS."""

from recreon.npe.types import (
    MAX_NO_OF_BLOCKS,
    BaseMissionTypes,
    Kingdom1DataRecord,
    MissionTypes,
    NPEDataRecord,
    NPEmpireTypes,
    PirateDataRecord,
    PolicyTypes,
    fleet_data_array,
    npe_data_array,
)
from recreon.types import MAX_NO_OF_STARBASES, NO_OF_FLEETS_PER_EMPIRE, Empire


def test_enum_sizes_match_pascal():
    assert len(NPEmpireTypes) == 7
    assert len(MissionTypes) == 17
    assert len(BaseMissionTypes) == 7
    assert len(PolicyTypes) == 7


def test_block_size_is_derived_from_galaxy_size():
    # NPETYPES.PAS: MaxNoOfBlocks = MaxSizeOfGalaxy DIV 5
    assert MAX_NO_OF_BLOCKS == 20


def test_policy_escalates_in_order():
    # NPE code compares policies by ordinal to decide whether to escalate.
    assert (
        PolicyTypes.NeutralPLT
        < PolicyTypes.DefendPLT
        < PolicyTypes.HarassPLT
        < PolicyTypes.PreemptPLT
        < PolicyTypes.ConflictPLT
        < PolicyTypes.WarPLT
    )


def test_fleet_data_array_is_one_based():
    fleets = fleet_data_array()
    assert fleets[0] is None
    assert len(fleets) == NO_OF_FLEETS_PER_EMPIRE + 1
    assert fleets[NO_OF_FLEETS_PER_EMPIRE] is not None


def test_ai_data_records_instantiate():
    pirate = PirateDataRecord()
    assert set(pirate.Sheep) == set(Empire)
    # HuntingGround is a square 1-based grid.
    assert len(pirate.HuntingGround) == MAX_NO_OF_BLOCKS + 1
    assert len(pirate.HuntingGround[1]) == MAX_NO_OF_BLOCKS + 1

    kingdom = Kingdom1DataRecord()
    assert set(kingdom.State) == set(Empire)
    assert kingdom.Persona.Offensive == 0


def test_berserker_base_data_covers_every_starbase():
    from recreon.npe.types import BerserkerDataRecord

    berserker = BerserkerDataRecord()
    assert len(berserker.BaseData) == MAX_NO_OF_STARBASES + 1


def test_npe_data_starts_empty():
    data = npe_data_array()
    assert set(data) == set(Empire)
    assert all(d == NPEDataRecord(NPEmpireTypes.NoNPE, None) for d in data.values())
