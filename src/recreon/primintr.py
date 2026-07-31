"""Low-level entity property access.

Port of PRIMINTR.PAS -- the subset Phase 2 needs (sector access, coordinate
and resource lookup, empire status, turn order). The remainder arrives with
the phases that use it.

Every function takes the :class:`~recreon.environ.GameEnvironment` explicitly
where the original read the ``Universe`` and ``Sector`` globals.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .datacnst import DEFAULT_ISSP
from .galaxy import XYCoord, limbo, nebula_of
from .types import (
    MAX_INDEX,
    MAX_NO_OF_FLEETS,
    MAX_RESOURCES,
    PLAYER_EMPIRES,
    Empire,
    IDNumber,
    IndusTypes,
    NebulaTypes,
    ObjectTypes,
    TechLevel,
    TechnologyTypes,
    WorldClass,
    WorldTypes,
    cargo_array,
    defns_array,
    indus_array,
    ship_array,
)

if TYPE_CHECKING:
    from .environ import GameEnvironment

T = TechnologyTypes


# --- Sector access -----------------------------------------------------------


def get_nebula(game: GameEnvironment, pos: XYCoord) -> NebulaTypes:
    """Nebula type at ``pos``, or NoNeb outside the galaxy."""
    if not game.Galaxy.in_galaxy(pos.x, pos.y):
        return NebulaTypes.NoNeb
    return NebulaTypes(nebula_of(game.Galaxy.sector(pos).Special))


def put_nebula(game: GameEnvironment, pos: XYCoord, neb: NebulaTypes) -> None:
    """Set the nebula in the low nibble, leaving the minefield owner intact."""
    sector = game.Galaxy.sector(pos)
    sector.Special = (sector.Special & 0xF0) | int(neb)


def put_mine(game: GameEnvironment, pos: XYCoord, emp: Empire) -> None:
    """Set the minefield owner in the high nibble, leaving the nebula intact."""
    sector = game.Galaxy.sector(pos)
    sector.Special = (sector.Special & 0x0F) | (16 * int(emp))


def enemy_mine(game: GameEnvironment, pos: XYCoord) -> Empire:
    """Empire that has mined ``pos``, or Indep if there is no minefield."""
    return Empire(game.Galaxy.sector(pos).Special // 16)


def get_object(game: GameEnvironment, pos: XYCoord) -> IDNumber:
    """The object occupying ``pos``. Void when the sector is empty."""
    return game.Galaxy.sector(pos).Obj


def put_object(game: GameEnvironment, pos: XYCoord, obj: IDNumber) -> None:
    game.Galaxy.sector(pos).Obj = obj


def get_fleets(game: GameEnvironment, pos: XYCoord) -> set[int]:
    """Indices of every active fleet currently at ``pos``."""
    universe = game.Universe
    return {
        i
        for i in range(1, MAX_NO_OF_FLEETS + 1)
        if i in game.GlobalSets.SetOfActiveFleets
        and universe.Fleet[i] is not None
        and universe.Fleet[i].XY == pos
    }


# --- Entity lookup -----------------------------------------------------------


def _entity(game: GameEnvironment, obj: IDNumber):
    """The record ``obj`` refers to, or None for a type that has no record."""
    universe = game.Universe
    match obj.ObjTyp:
        case ObjectTypes.Pln:
            return universe.Planet[obj.Index]
        case ObjectTypes.Base:
            return universe.Starbase[obj.Index]
        case ObjectTypes.Flt:
            return universe.Fleet[obj.Index]
        case ObjectTypes.Gate:
            return universe.Stargate[obj.Index]
        case ObjectTypes.Con:
            return universe.Constr[obj.Index]
        case _:
            return None


def get_coord(game: GameEnvironment, obj: IDNumber) -> XYCoord:
    """Where ``obj`` is. Limbo for phenomena and unknown types."""
    entity = _entity(game, obj)
    return entity.XY if entity is not None else limbo()


def get_ships(game: GameEnvironment, obj: IDNumber) -> dict[T, int]:
    """Ships at ``obj``. An empty distribution for anything that has none."""
    entity = _entity(game, obj)
    if obj.ObjTyp in (ObjectTypes.Pln, ObjectTypes.Base, ObjectTypes.Flt):
        return dict(entity.Ships)
    return ship_array()


def get_cargo(game: GameEnvironment, obj: IDNumber) -> dict[T, int]:
    entity = _entity(game, obj)
    if obj.ObjTyp in (ObjectTypes.Pln, ObjectTypes.Base, ObjectTypes.Flt):
        return dict(entity.Cargo)
    return cargo_array()


def get_defns(game: GameEnvironment, obj: IDNumber) -> dict[T, int]:
    entity = _entity(game, obj)
    if obj.ObjTyp in (ObjectTypes.Pln, ObjectTypes.Base):
        return dict(entity.Defns)
    return defns_array()


def get_indus(game: GameEnvironment, obj: IDNumber) -> dict[IndusTypes, int]:
    entity = _entity(game, obj)
    if obj.ObjTyp in (ObjectTypes.Pln, ObjectTypes.Base):
        return dict(entity.Indus)
    return indus_array()


def get_status(game: GameEnvironment, obj: IDNumber) -> Empire:
    """Which empire owns ``obj``. Indep for unowned and unknown types."""
    entity = _entity(game, obj)
    return entity.Emp if entity is not None else Empire.Indep


def get_class(game: GameEnvironment, obj: IDNumber) -> WorldClass:
    entity = _entity(game, obj)
    if obj.ObjTyp == ObjectTypes.Pln:
        return entity.Cls
    return WorldClass.BarCls


def get_type(game: GameEnvironment, obj: IDNumber) -> WorldTypes:
    entity = _entity(game, obj)
    if obj.ObjTyp in (ObjectTypes.Pln, ObjectTypes.Base):
        return entity.Typ
    return WorldTypes.OutTyp


def get_tech(game: GameEnvironment, obj: IDNumber) -> TechLevel:
    entity = _entity(game, obj)
    if obj.ObjTyp in (ObjectTypes.Pln, ObjectTypes.Base):
        return entity.Tech
    return TechLevel.PreTchLvl


def get_population(game: GameEnvironment, obj: IDNumber) -> int:
    entity = _entity(game, obj)
    if obj.ObjTyp in (ObjectTypes.Pln, ObjectTypes.Base):
        return entity.Pop
    return 0


def get_efficiency(game: GameEnvironment, obj: IDNumber) -> int:
    entity = _entity(game, obj)
    if obj.ObjTyp in (ObjectTypes.Pln, ObjectTypes.Base):
        return entity.Eff
    return 0


def get_special(game: GameEnvironment, obj: IDNumber) -> set:
    entity = _entity(game, obj)
    if obj.ObjTyp in (ObjectTypes.Pln, ObjectTypes.Base):
        return entity.Special
    return set()


def get_rev_index(game: GameEnvironment, obj: IDNumber) -> int:
    entity = _entity(game, obj)
    if obj.ObjTyp in (ObjectTypes.Pln, ObjectTypes.Base):
        return entity.RevIndex
    return 0


def troop_strength(game: GameEnvironment, obj: IDNumber) -> int:
    """Troop strength: men + 2 * ninja."""
    cargo = get_cargo(game, obj)
    return cargo[T.men] + 2 * cargo[T.nnj]


def trillum_reserves(game: GameEnvironment, obj: IDNumber) -> int:
    """Trillum left in the ground. Starbases draw on an unlimited supply."""
    if obj.ObjTyp == ObjectTypes.Pln:
        return game.Universe.Planet[obj.Index].TriReserve
    if obj.ObjTyp == ObjectTypes.Base:
        return MAX_RESOURCES
    return 0


def get_base_type(game: GameEnvironment, obj: IDNumber) -> TechnologyTypes:
    return game.Universe.Starbase[obj.Index].STyp


# --- Setters -----------------------------------------------------------------


def put_ships(game: GameEnvironment, obj: IDNumber, ships: dict[T, int]) -> None:
    entity = _entity(game, obj)
    if obj.ObjTyp in (ObjectTypes.Pln, ObjectTypes.Base, ObjectTypes.Flt):
        entity.Ships = dict(ships)


def put_cargo(game: GameEnvironment, obj: IDNumber, cargo: dict[T, int]) -> None:
    entity = _entity(game, obj)
    if obj.ObjTyp in (ObjectTypes.Pln, ObjectTypes.Base, ObjectTypes.Flt):
        entity.Cargo = dict(cargo)


def put_defns(game: GameEnvironment, obj: IDNumber, defns: dict[T, int]) -> None:
    entity = _entity(game, obj)
    if obj.ObjTyp in (ObjectTypes.Pln, ObjectTypes.Base):
        entity.Defns = dict(defns)


def put_indus(game: GameEnvironment, obj: IDNumber, indus: dict) -> None:
    entity = _entity(game, obj)
    if obj.ObjTyp in (ObjectTypes.Pln, ObjectTypes.Base):
        entity.Indus = dict(indus)


def put_trillum_reserves(game: GameEnvironment, obj: IDNumber, new_res: int) -> None:
    if obj.ObjTyp == ObjectTypes.Pln:
        game.Universe.Planet[obj.Index].TriReserve = new_res


def set_class(game: GameEnvironment, obj: IDNumber, cls: WorldClass) -> None:
    if obj.ObjTyp == ObjectTypes.Pln:
        game.Universe.Planet[obj.Index].Cls = cls


def set_tech(game: GameEnvironment, obj: IDNumber, tech: TechLevel) -> None:
    entity = _entity(game, obj)
    if obj.ObjTyp in (ObjectTypes.Pln, ObjectTypes.Base):
        entity.Tech = tech


def set_population(game: GameEnvironment, obj: IDNumber, pop: int) -> None:
    entity = _entity(game, obj)
    if obj.ObjTyp in (ObjectTypes.Pln, ObjectTypes.Base):
        entity.Pop = pop


def set_efficiency(game: GameEnvironment, obj: IDNumber, eff: int) -> None:
    entity = _entity(game, obj)
    if obj.ObjTyp in (ObjectTypes.Pln, ObjectTypes.Base):
        entity.Eff = eff


def set_status(game: GameEnvironment, obj: IDNumber, emp: Empire) -> None:
    entity = _entity(game, obj)
    if entity is not None:
        entity.Emp = emp


def set_type(game: GameEnvironment, obj: IDNumber, typ: WorldTypes) -> None:
    entity = _entity(game, obj)
    if obj.ObjTyp in (ObjectTypes.Pln, ObjectTypes.Base):
        entity.Typ = typ


def set_special(game: GameEnvironment, obj: IDNumber, setting: set) -> None:
    entity = _entity(game, obj)
    if obj.ObjTyp in (ObjectTypes.Pln, ObjectTypes.Base):
        entity.Special = set(setting)


def set_terraform_target(
    game: GameEnvironment, obj: IDNumber, target: WorldClass
) -> None:
    if obj.ObjTyp == ObjectTypes.Pln:
        game.Universe.Planet[obj.Index].TerraformTarget = target


def get_terraform_target(game: GameEnvironment, obj: IDNumber) -> WorldClass:
    if obj.ObjTyp == ObjectTypes.Pln:
        return game.Universe.Planet[obj.Index].TerraformTarget
    return WorldClass.BarCls


def change_rev_index(game: GameEnvironment, obj: IDNumber, chg: int) -> None:
    """Adjust the revolution index, clamped to 0..100."""
    entity = _entity(game, obj)
    if obj.ObjTyp not in (ObjectTypes.Pln, ObjectTypes.Base):
        return
    entity.RevIndex = max(0, min(MAX_INDEX, entity.RevIndex + chg))


# --- ISSP --------------------------------------------------------------------
#
# The four adjustable ISSP settings are packed into the 16-bit ImpExp word,
# one nibble each. Production industries are not adjustable and answer with a
# fixed index.

#: Nibble shift within ImpExp for each adjustable industry.
_ISSP_SHIFT = {
    IndusTypes.CheInd: 0,
    IndusTypes.MinInd: 4,
    IndusTypes.SupInd: 8,
    IndusTypes.TriInd: 12,
}

#: Industries whose ISSP is fixed rather than stored.
_FIXED_ISSP_INDUSTRIES = frozenset(
    {
        IndusTypes.BioInd,
        IndusTypes.SYGInd,
        IndusTypes.SYJInd,
        IndusTypes.SYSInd,
        IndusTypes.SYTInd,
    }
)


def get_issp(game: GameEnvironment, obj: IDNumber, ind: IndusTypes) -> int:
    """Index into the ISSP table for one industry.

    Production industries always answer 6 (150%); starbases always answer 0.
    """
    if ind in _FIXED_ISSP_INDUSTRIES:
        return 6
    if obj.ObjTyp == ObjectTypes.Base:
        return 0
    if obj.ObjTyp != ObjectTypes.Pln:
        return 0
    imp_exp = game.Universe.Planet[obj.Index].ImpExp
    return (imp_exp >> _ISSP_SHIFT[ind]) & 0x0F


def set_issp(game: GameEnvironment, obj: IDNumber, ind: IndusTypes, issp_ind: int) -> None:
    if ind in _FIXED_ISSP_INDUSTRIES or obj.ObjTyp != ObjectTypes.Pln:
        return
    planet = game.Universe.Planet[obj.Index]
    shift = _ISSP_SHIFT[ind]
    planet.ImpExp = (planet.ImpExp & ~(0x0F << shift)) | ((issp_ind & 0x0F) << shift)


def initialize_issp(game: GameEnvironment, obj: IDNumber) -> None:
    if obj.ObjTyp == ObjectTypes.Pln:
        game.Universe.Planet[obj.Index].ImpExp = DEFAULT_ISSP


# --- Empire technology -------------------------------------------------------


def get_empire_technology(
    game: GameEnvironment, emp: Empire
) -> tuple[TechLevel, set[TechnologyTypes]]:
    data = game.Universe.EmpireData[emp]
    return data.TechnologyLevel, data.Technology


def set_empire_technology(
    game: GameEnvironment,
    emp: Empire,
    tech: TechLevel,
    tech_set: set[TechnologyTypes],
) -> None:
    data = game.Universe.EmpireData[emp]
    data.TechnologyLevel = tech
    data.Technology = set(tech_set)


def total_rev_index(game: GameEnvironment, emp: Empire) -> int:
    return game.Universe.EmpireData[emp].TotalRevIndex


def set_total_rev_index(game: GameEnvironment, emp: Empire, new_index: int) -> None:
    game.Universe.EmpireData[emp].TotalRevIndex = new_index


def change_total_rev_index(game: GameEnvironment, emp: Empire, inc: int) -> None:
    game.Universe.EmpireData[emp].TotalRevIndex += inc


# --- Scouting ----------------------------------------------------------------


def scouted(game: GameEnvironment, emp: Empire, obj: IDNumber) -> bool:
    entity = _entity(game, obj)
    return entity is not None and emp in entity.ScoutedBy


def known(game: GameEnvironment, emp: Empire, obj: IDNumber) -> bool:
    entity = _entity(game, obj)
    if entity is None or not hasattr(entity, "KnownBy"):
        return False
    return emp in entity.KnownBy


def scout_object(game: GameEnvironment, emp: Empire, obj: IDNumber) -> None:
    """Mark ``obj`` as scouted by ``emp``, which also makes it known."""
    entity = _entity(game, obj)
    if entity is None:
        return
    entity.ScoutedBy.add(emp)
    if hasattr(entity, "KnownBy"):
        entity.KnownBy.add(emp)


def clear_scout_set(game: GameEnvironment, emp: Empire) -> None:
    """Forget everything ``emp`` had scouted, before rescouting for the turn.

    Knowledge (KnownBy) persists; only direct observation is cleared.
    """
    universe = game.Universe
    for planet in universe.Planet[1:]:
        planet.ScoutedBy.discard(emp)
    for starbase in universe.Starbase[1:]:
        starbase.ScoutedBy.discard(emp)
    for gate in universe.Stargate[1:]:
        gate.ScoutedBy.discard(emp)
    for site in universe.Constr[1:]:
        site.ScoutedBy.discard(emp)
    for fleet in universe.Fleet[1:]:
        if fleet is not None:
            fleet.ScoutedBy.discard(emp)


# --- Empire status -----------------------------------------------------------


def empire_active(game: GameEnvironment, emp: Empire) -> bool:
    """Whether ``emp`` is in play."""
    return game.Universe.EmpireData[emp].InUse


def empire_player(game: GameEnvironment, emp: Empire) -> bool:
    """Whether ``emp`` is human-controlled rather than an NPE."""
    return game.Universe.EmpireData[emp].IsAPlayer


def empress(game: GameEnvironment, emp: Empire) -> bool:
    return game.Universe.EmpireData[emp].IsAnEmpress


def empire_name(game: GameEnvironment, emp: Empire) -> str:
    return game.Universe.EmpireData[emp].EmpireName


def empire_age(game: GameEnvironment, emp: Empire) -> int:
    """Years since founding."""
    return game.Year - game.Universe.EmpireData[emp].Founding


def get_capital(game: GameEnvironment, emp: Empire) -> IDNumber:
    return game.Universe.EmpireData[emp].Capital


def set_capital(game: GameEnvironment, emp: Empire, cap_id: IDNumber) -> None:
    game.Universe.EmpireData[emp].Capital = cap_id


def next_empire(game: GameEnvironment, player: Empire) -> Empire:
    """The next active empire in turn order, wrapping Empire8 -> Empire1.

    Loops forever if no empire is active, exactly as the original does; the
    caller is expected to have at least one.
    """
    while True:
        player = Empire.Empire1 if player == Empire.Empire8 else Empire(int(player) + 1)
        if empire_active(game, player):
            return player


def no_more_players(game: GameEnvironment) -> bool:
    """Whether every human empire has been knocked out."""
    return not any(
        empire_active(game, emp) and empire_player(game, emp) for emp in PLAYER_EMPIRES
    )


def absolute_x(game: GameEnvironment, x: int) -> int:
    """Convert an empire-relative X to an absolute galaxy X.

    Coordinates are entered relative to the active player's capital.
    """
    return x + get_coord(game, get_capital(game, game.Player)).x


def absolute_y(game: GameEnvironment, y: int) -> int:
    return y + get_coord(game, get_capital(game, game.Player)).y
