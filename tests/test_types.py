"""Checks that the ported enums keep the ordinals the Pascal code relies on."""

from recreon.galaxy import MAX_SIZE_OF_GALAXY, NO_SRM_FIELD
from recreon.types import (
    ATTACK_TYPES,
    CARGO_TYPES,
    CONSTR_TYPES,
    DEFNS_TYPES,
    PLAYER_EMPIRES,
    RESOURCE_TYPES,
    SHIP_TYPES,
    STARBASE_TYPES,
    STARGATE_TYPES,
    Empire,
    IndusTypes,
    ObjectTypes,
    ShellPos,
    TechLevel,
    TechnologyTypes,
    WorldClass,
    WorldTypes,
    tech_range,
)


def test_empire_ordinals_are_zero_based():
    # Pascal enums start at 0; NoSRMField below depends on Indep being 8.
    assert Empire.Empire1 == 0
    assert Empire.Empire8 == 7
    assert Empire.Indep == 8
    assert len(PLAYER_EMPIRES) == 8
    assert Empire.Indep not in PLAYER_EMPIRES


def test_no_srm_field_sentinel():
    # GALAXY.PAS: NoSRMField = Ord(Indep) * 16
    assert NO_SRM_FIELD == 128
    assert MAX_SIZE_OF_GALAXY == 100


def test_enum_sizes_match_pascal():
    assert len(TechnologyTypes) == 28
    assert len(WorldClass) == 22
    assert len(WorldTypes) == 21
    assert len(TechLevel) == 11
    assert len(IndusTypes) == 9
    assert len(ObjectTypes) == 12
    assert len(ShellPos) == 5


def test_technology_subranges():
    T = TechnologyTypes
    assert SHIP_TYPES == (T.fgt, T.hkr, T.jmp, T.jtn, T.pen, T.ssp, T.trn)
    assert CARGO_TYPES == (T.men, T.nnj, T.amb, T.che, T.met, T.sup, T.tri)
    assert DEFNS_TYPES == (T.LAM, T.def_, T.GDM, T.ion)
    assert STARBASE_TYPES == (T.cmm, T.frt, T.cmp, T.out)
    assert STARGATE_TYPES == (T.gte, T.lnk, T.dis)
    assert len(CONSTR_TYPES) == 8
    assert len(RESOURCE_TYPES) == 19
    assert len(ATTACK_TYPES) == 14


def test_tech_range_is_inclusive():
    # Pascal subranges include both endpoints.
    T = TechnologyTypes
    assert tech_range(T.che, T.tri) == (T.che, T.met, T.sup, T.tri)


def test_shell_order_is_outermost_first():
    assert list(ShellPos) == [
        ShellPos.DpSpc,
        ShellPos.HiOrb,
        ShellPos.Orbit,
        ShellPos.SbOrb,
        ShellPos.Grnd,
    ]
