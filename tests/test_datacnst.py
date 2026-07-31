"""Spot checks pinning the balance tables to DATACNST.PAS.

The _table helper already enforces row lengths at import time. These check
values at known coordinates, so a shifted row or transposed table is caught.
"""

from recreon import datacnst as C
from recreon.types import (
    CARGO_TYPES,
    IndusTypes,
    ShellPos,
    TechLevel,
    TechnologyTypes,
    WorldClass,
    WorldTypes,
)

T = TechnologyTypes


def test_combat_table_corners():
    # NB: the column header in DATACNST.PAS lists 13 defenders for 14 columns
    # -- it omits the leading NUL column. These values are read against the
    # corrected alignment, where column 0 is NUL.
    assert C.CombatTable[T.ssp][T.fgt] == 1000
    assert C.CombatTable[T.ssp][T.trn] == 500
    assert C.CombatTable[T.ssp][T.ssp] == 15
    assert C.CombatTable[T.LAM][T.LAM] == 200
    assert C.CombatTable[T.LAM][T.trn] == 200
    assert C.CombatTable[T.nnj][T.nnj] == 10
    assert C.CombatTable[T.NoRes][T.NoRes] == 0


def test_combat_table_is_not_symmetric():
    # Attacker and defender axes are distinct: starships slaughter fighters,
    # fighters barely scratch starships. A transposed transcription would
    # make these equal.
    assert C.CombatTable[T.ssp][T.fgt] == 1000
    assert C.CombatTable[T.fgt][T.ssp] == 1


def test_combat_table_nul_row_and_column_are_zero():
    # NoRes is a placeholder, never a real combatant.
    assert all(v == 0 for v in C.CombatTable[T.NoRes].values())
    assert all(row[T.NoRes] == 0 for row in C.CombatTable.values())


def test_class_industry_adjustments():
    # Terraforming worlds are crippled while in progress.
    assert C.ClassIndAdj[WorldClass.TerCls][IndusTypes.BioInd] == 1
    assert C.ClassIndAdj[WorldClass.TerCls][IndusTypes.SupInd] == 10
    # Artificial worlds are shipyards, not farms.
    assert C.ClassIndAdj[WorldClass.ArtCls][IndusTypes.SYSInd] == 300
    assert C.ClassIndAdj[WorldClass.ArtCls][IndusTypes.SupInd] == 40


def test_raw_material_costs():
    assert C.RawM[T.ssp][T.met] == 520
    assert C.RawM[T.ssp][T.che] == 175
    assert C.RawM[T.nnj][T.amb] == 100
    # Raw materials cost nothing to make.
    assert all(v == 0 for v in C.RawM[T.tri].values())


def test_industry_outputs():
    assert C.ThgAdj[IndusTypes.SupInd][T.sup] == 320
    assert C.ThgAdj[IndusTypes.MinInd][T.met] == 350
    assert C.ThgAdj[IndusTypes.BioInd][T.amb] == 175
    assert C.ThgAdj[IndusTypes.BioInd][T.nnj] == 10


def test_tech_dev_accumulates():
    # Pre-tech empires have supplies and nothing else; gate-level has everything.
    assert C.TechDev[TechLevel.PreTchLvl] == {T.sup}
    assert C.TechDev[TechLevel.GteTchLvl] == set(range(int(T.LAM), int(T.ter) + 1))
    assert T.ter not in C.TechDev[TechLevel.PreGteLvl]
    # Ranges inside the set literals expand correctly.
    assert C.TechDev[TechLevel.AtomicLvl] == {T.GDM, T.men, T.che, T.met, T.sup, T.tri}


def test_construction_times_and_costs():
    assert C.YearsToBuild[T.SRM] == 2
    assert C.YearsToBuild[T.gte] == 15
    assert C.ConsCargoNeeded[T.gte][T.met] == 3920
    assert C.ConsCargoNeeded[T.gte][T.tri] == 1450


def test_fuel_and_cargo():
    assert C.FuelCons[T.ssp] == 1427
    assert C.FuelCons[T.fgt] == 10
    assert C.FuelCap[T.ssp] == 2854
    assert C.CargoSpace[T.tri] == 100
    assert C.CargoSpace[T.che] == 3


def test_default_defense_distribution():
    record = C.init_defense_record()
    # Fighters concentrate in sub-orbit, starships never sit in deep space.
    assert record.ShellDefDist[ShellPos.SbOrb][T.fgt] == 55
    assert record.ShellDefDist[ShellPos.DpSpc][T.ssp] == 0
    assert record.ShellDefDist[ShellPos.Grnd][T.trn] == 100
    # The Pascal constant leaves the starbase distribution zeroed.
    assert all(
        v == 0 for shell in record.StarbaseDefDist.values() for v in shell.values()
    )


def test_type_data_rows():
    assert C.TypeData[WorldTypes.AgrTyp][IndusTypes.SupInd] == 10.0
    assert C.TypeData[WorldTypes.TriTyp][IndusTypes.TriInd] == 80
    # Outposts have no industry at all.
    assert all(v == 0 for v in C.TypeData[WorldTypes.OutTyp].values())


def test_issp_scale():
    assert len(C.ISSP) == C.MAX_ISSP + 1
    assert C.ISSP[C.NORMAL_ISSP] == 1.00
    assert C.DEFAULT_ISSP == 0x5555


def test_direction_vectors():
    # DirX/DirY are parallel; index 0 (NoDir) must not move.
    assert len(C.DirX) == len(C.DirY) == 9
    from recreon.types import Directions

    assert (C.DirX[Directions.NoDir], C.DirY[Directions.NoDir]) == (0, 0)
    assert (C.DirX[Directions.No], C.DirY[Directions.No]) == (0, -1)
    assert (C.DirX[Directions.Se], C.DirY[Directions.Se]) == (1, 1)


def test_terraform_table_is_one_based():
    row = C.TerraformPotentialClasses[WorldClass.AmbCls]
    assert row[0] is None
    assert len(row) == 11
    assert row[1] == WorldClass.OcnCls
    assert row[10] == WorldClass.AmbCls


def test_name_tables_cover_every_member():
    assert C.TechnologyName[T.ter] == "terraforming"
    assert C.TypeName[WorldTypes.CapTyp] == "capital"
    assert C.ThingNames[T.tri] == "kilotons of trillum"
    assert C.TechN[TechLevel.GteTchLvl] == "gate"
    assert len(C.ClassStr) == len(WorldClass)
    assert len(C.TypeStr) == len(WorldTypes)


def test_cargo_keyed_tables_use_cargo_subrange():
    assert tuple(C.CargoSpace) == CARGO_TYPES
    assert tuple(C.ConsCargoNeeded[T.SRM]) == CARGO_TYPES
