"""AI type definitions.

Port of NPETYPES.PAS. Types only -- the AI behaviour that uses them is Phase 7.

``Spare: ARRAY [1..50] OF Word`` padding on the per-AI data records is dropped,
for the same reason as ``Reserved`` in datastrc.py: it only exists to hold the
on-disk record size steady.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

from ..galaxy import MAX_SIZE_OF_GALAXY
from ..types import (
    MAX_NO_OF_STARBASES,
    NO_OF_FLEETS_PER_EMPIRE,
    Empire,
    IDNumber,
)

#: Galaxy is divided into blocks of 5 sectors for the pirate hunting grounds.
MAX_NO_OF_BLOCKS = MAX_SIZE_OF_GALAXY // 5


class NPEmpireTypes(IntEnum):
    NoNPE = 0
    PirateNPE = 1  # Pirate empire
    Kingdom1NPE = 2  # Passive empire, but easy to provoke
    Kingdom2NPE = 3  # Aggressive empire, attacks others
    BerserkerNPE = 4  # Berserker empire
    GuardianNPE = 5  # Guardian empire
    TraderNPE = 6


class MissionTypes(IntEnum):
    NoMSN = 0
    ReturnMSN = 1  # Abort at destination.
    HKMSN = 2
    WaitForTrnMSN = 3  # Wait for enemy transports.
    AttackTrnMSN = 4  # Attack enemy fleets.
    AttackWrldMSN = 5  # Attack enemy world.
    BSRKAttackMSN = 6  # Berserker attack.
    BSRKReturnMSN = 7  # Return to berserker base.
    StackMSN = 8  # Stack at base planet.
    GuardMSN = 9  # Wait at base planet.
    ConquerMSN = 10  # Conquer independent world.
    JumpAttackMSN = 11  # Conquer enemy with jumpships.
    RefuelMSN = 12  # Refuel another fleet.
    SlowAttackMSN = 13  # Conquer enemy with slow fleets.
    RaidTrnMSN = 14  # Raid transports over worlds.
    SupplyMSN = 15  # Supply world.
    SupplyTrnMSN = 16  # Send transports to material worlds.


class BaseMissionTypes(IntEnum):
    NoBMS = 0
    DefendBMS = 1  # Defend a base planet.
    AttackBMS = 2  # Attack target.
    FindHomeBMS = 3  # Look for a base to go to.
    RefuelBMS = 4  # Go to nearest base to refuel.
    WaitForAttackBMS = 5  # Waiting.
    WanderAroundBMS = 6  # Wander around the galaxy.


class PolicyTypes(IntEnum):
    """Diplomatic stance, escalating from NeutralPLT to WarPLT."""

    NoPLT = 0
    NeutralPLT = 1  # Ignore.
    DefendPLT = 2  # Defend worlds against attack.
    HarassPLT = 3  # Attack fleets.
    PreemptPLT = 4  # Attack small worlds.
    ConflictPLT = 5  # Attack major bases.
    WarPLT = 6  # Take capital.


@dataclass(slots=True)
class NPECharacterRecord:
    """An AI's personality. All fields are 0..100 unless noted."""

    # Genes control how the traits below drift over time.
    ImpGene: int = 0  # Controls Imperialist
    DefGene: int = 0  # Controls Defensive
    OffGene: int = 0  # Controls Offensive
    FactorGene: int = 0  # Controls change in attributes
    RandomGene: int = 0  # Controls unpredictability

    Defensive: int = 0  # 100 = very defensive, protects all worlds
    Offensive: int = 0  # 100 = very aggressive, attacks others often
    Techno: int = 0  # 100 = likes technology, university worlds
    Provoke: int = 0  # 100 = provoked very easily
    Imperialist: int = 0  # 100 = likes to expand
    WorldPower: int = 0  # 100 = takes few powerful worlds
    Honorable: int = 0  # 100 = will not attack friends
    SphereX: int = 0  # 100 = expand from capital outwards

    Clock: int = 0  # years since beginning
    Offset: int = 0  # clock offset


@dataclass(slots=True)
class FleetDataRecord:
    Mission: MissionTypes = MissionTypes.NoMSN
    #: Final destination or target.
    TargetID: IDNumber = field(default_factory=IDNumber)
    HomeBaseID: IDNumber = field(default_factory=IDNumber)
    #: Coordinate to gather at or rendezvous.
    Midway: IDNumber = field(default_factory=IDNumber)
    Waiting: int = 0
    BlockX: int = 0
    BlockY: int = 0
    #: Fleet index.
    Index: int = 0


@dataclass(slots=True)
class BaseDataRecord:
    Mission: BaseMissionTypes = BaseMissionTypes.NoBMS
    TargetID: IDNumber = field(default_factory=IDNumber)
    Count: int = 0


@dataclass(slots=True)
class StateDeptRecord:
    """What one AI thinks of one other empire."""

    Policy: PolicyTypes = PolicyTypes.NoPLT
    AttackChance: int = 0  # chance to attack this enemy
    TotalMilitary: int = 0  # strength of enemy military
    Worlds: int = 0  # number of worlds in the empire
    ThreatAssess: int = 0  # threat assessment of enemy
    Aggressiveness: int = 0  # attacks on this empire

    #: Positive means the NPE has conquered some of its target's worlds;
    #: negative means it has worlds to take back.
    Balance: int = 0


def fleet_data_array() -> list[FleetDataRecord | None]:
    """Pascal ``ARRAY [1..NoOfFleetsPerEmpire]``; index 0 unused."""
    return [None] + [FleetDataRecord() for _ in range(NO_OF_FLEETS_PER_EMPIRE)]


def base_data_array() -> list[BaseDataRecord | None]:
    """Pascal ``ARRAY [1..MaxNoOfStarbases]``; index 0 unused."""
    return [None] + [BaseDataRecord() for _ in range(MAX_NO_OF_STARBASES)]


def state_dept_array() -> dict[Empire, StateDeptRecord]:
    return {e: StateDeptRecord() for e in Empire}


def hunting_ground_array() -> list[list[int]]:
    """Pascal ``ARRAY [1..MaxNoOfBlocks,1..MaxNoOfBlocks]``; row/col 0 unused."""
    return [[0] * (MAX_NO_OF_BLOCKS + 1) for _ in range(MAX_NO_OF_BLOCKS + 1)]


@dataclass(slots=True)
class PirateDataRecord:
    FleetData: list[FleetDataRecord | None] = field(default_factory=fleet_data_array)
    HuntingGround: list[list[int]] = field(default_factory=hunting_ground_array)
    #: How attractive each empire is as prey.
    Sheep: dict[Empire, int] = field(default_factory=lambda: dict.fromkeys(Empire, 0))


@dataclass(slots=True)
class Kingdom1DataRecord:
    FleetData: list[FleetDataRecord | None] = field(default_factory=fleet_data_array)
    State: dict[Empire, StateDeptRecord] = field(default_factory=state_dept_array)
    Persona: NPECharacterRecord = field(default_factory=NPECharacterRecord)


@dataclass(slots=True)
class BerserkerDataRecord:
    FleetData: list[FleetDataRecord | None] = field(default_factory=fleet_data_array)
    BaseData: list[BaseDataRecord | None] = field(default_factory=base_data_array)


@dataclass(slots=True)
class GuardianDataRecord:
    FleetData: list[FleetDataRecord | None] = field(default_factory=fleet_data_array)


#: The per-AI payload hanging off NPEDataRecord.Data, an untyped Pointer in the
#: original discriminated by the Typ field beside it.
NPEData = (
    PirateDataRecord | Kingdom1DataRecord | BerserkerDataRecord | GuardianDataRecord
)


@dataclass(slots=True)
class NPEDataRecord:
    Typ: NPEmpireTypes = NPEmpireTypes.NoNPE
    Data: NPEData | None = None


def npe_data_array() -> dict[Empire, NPEDataRecord]:
    return {e: NPEDataRecord() for e in Empire}
