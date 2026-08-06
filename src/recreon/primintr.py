"""Low-level entity property access.

Port of PRIMINTR.PAS -- the subset Phase 2 needs (sector access, coordinate
and resource lookup, empire status, turn order). The remainder arrives with
the phases that use it.

Every function takes the :class:`~recreon.environ.GameEnvironment` explicitly
where the original read the ``Universe`` and ``Sector`` globals.
"""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

from .datacnst import DEFAULT_ISSP, ObjName
from .datastrc import MAXINT16, DefenseRecord, NameRecord
from .galaxy import Location, XYCoord, limbo, nebula_of
from .misc import same_id, same_location, same_xy
from .types import (
    MAX_INDEX,
    MAX_NO_OF_FLEETS,
    MAX_RESOURCES,
    NO_OF_PROBES_PER_EMPIRE,
    PLAYER_EMPIRES,
    Empire,
    EmpireModifiers,
    FleetStatus,
    FleetTypes,
    IDNumber,
    IndusTypes,
    NebulaTypes,
    ObjectTypes,
    ProbeStatus,
    TechLevel,
    TechnologyTypes,
    WorldClass,
    WorldTypes,
    cargo_array,
    defns_array,
    empty_quadrant,
    indus_array,
    ship_array,
)
from .utils.int_utils import rnd
from .utils.pascal import pascal_val, trunc

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
    """World class. Anything that is not a planet is ``ArtCls`` -- artificial.

    Starbases have no ``Cls`` field of their own, and the class they answer
    with is load-bearing: it selects the ``ClassIndAdj`` row that sizes their
    industry. ``ArtCls`` is the shipyard-heavy row, which is what makes an
    industrial complex worth building.
    """
    entity = _entity(game, obj)
    if obj.ObjTyp == ObjectTypes.Pln:
        return entity.Cls
    return WorldClass.ArtCls


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


def get_trillum(game: GameEnvironment, obj: IDNumber) -> int:
    """Trillum in an object's hold -- not the reserves still in the ground."""
    if obj.ObjTyp in (ObjectTypes.Pln, ObjectTypes.Base, ObjectTypes.Flt):
        return _entity(game, obj).Cargo[T.tri]
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


def put_trillum(game: GameEnvironment, obj: IDNumber, tons: int) -> None:
    if obj.ObjTyp in (ObjectTypes.Pln, ObjectTypes.Base, ObjectTypes.Flt):
        _entity(game, obj).Cargo[T.tri] = tons


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
    """Hand ``obj`` to ``emp``, moving it between the per-empire index sets.

    Planets, starbases and construction sites each carry a set per empire
    (``SetOfPlanetsOf`` and friends), and almost everything that sweeps an
    empire's holdings iterates those rather than scanning for a matching
    ``Emp``. The original moves the index out of the old owner's set and into
    the new one right here (PRIMINTR.PAS:724-750); leaving that out desynchs
    every such sweep from the moment a world first changes hands -- which for a
    scenario is at load, since worlds are created independent and assigned
    owners afterwards.
    """
    entity = _entity(game, obj)
    if entity is None:
        return

    sets = None
    if obj.ObjTyp == ObjectTypes.Pln:
        sets = game.GlobalSets.SetOfPlanetsOf
    elif obj.ObjTyp == ObjectTypes.Base:
        sets = game.GlobalSets.SetOfStarbasesOf
    elif obj.ObjTyp == ObjectTypes.Con:
        sets = game.GlobalSets.SetOfConstructionSitesOf

    if sets is not None:
        sets[entity.Emp].discard(obj.Index)
        sets[emp].add(obj.Index)

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


def create_empire(
    game: GameEnvironment,
    emp: Empire,
    *,
    is_player: bool,
    is_empress: bool,
    name: str,
    password: str,
    tech: TechLevel,
    tech_set: set[TechnologyTypes],
    rev_factor: int,
    modifiers: set,
    year_founded: int,
    capital: IDNumber | None = None,
) -> None:
    """Bring an empire into play."""
    from .datacnst import init_defense_record

    data = game.Universe.EmpireData[emp]
    data.InUse = True
    data.IsAPlayer = is_player
    data.IsAnEmpress = is_empress
    data.EmpireName = name
    data.Pass = password

    data.TimeLeft = 1500
    data.Capital = capital or IDNumber()
    data.DefenseSettings = init_defense_record()

    data.TechnologyLevel = tech
    data.Technology = set(tech_set)

    #: Added to every world's revolution index each year.
    data.RevFactor = rev_factor
    data.Modifiers = set(modifiers)
    data.Founding = year_founded


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


#: How a minister addresses an emperor, and an empress. Rolled fresh on every
#: line of dialogue -- see :func:`my_lord`.
MY_LORD_EMPRESS = ("My Lady", "Your Highness", "Your Excellency", "My Empress")
MY_LORD_EMPEROR = (
    "My Lord",
    "Your Highness",
    "Your Majesty",
    "My Liege",
    "Your Excellency",
    "Sir",
)


def my_lord(game: GameEnvironment, emp: Empire) -> str:
    """How the empire's staff address its ruler, picked at random.

    **This draws from the generator**, once per call: ``Rnd(1,4)`` for an
    empress and ``Rnd(1,6)`` for an emperor. It is the one piece of pure
    presentation in the game that moves the LCG, and the command handlers call
    it constantly -- so in the original, how many times a player opened a
    window shifted every subsequent roll in the galaxy.

    Ported with the draws intact, because the alternative is worse: a
    ``my_lord`` that did not draw would make *this* module's call sites
    diverge from the Pascal's for no gain. But it does mean the port's stream
    can only match the original's if the UI makes the same calls in the same
    order, which it cannot -- one more reason a DOS-era galaxy is not
    reproducible here (see CLAUDE.md on the LCG).
    """
    if game.Universe.EmpireData[emp].IsAnEmpress:
        return MY_LORD_EMPRESS[rnd(1, len(MY_LORD_EMPRESS)) - 1]
    return MY_LORD_EMPEROR[rnd(1, len(MY_LORD_EMPEROR)) - 1]


# --- Construction sites -------------------------------------------------------


def get_constr_type(game: GameEnvironment, con_id: IDNumber) -> TechnologyTypes:
    """What is being built. ``SRM`` for anything that is not a site, which is
    the original's fallback rather than an error."""
    if con_id.ObjTyp != ObjectTypes.Con:
        return TechnologyTypes.SRM
    return game.Universe.Constr[con_id.Index].CTyp


def get_constr_time_left(game: GameEnvironment, con_id: IDNumber) -> int:
    """Years still to run, or 0 for anything that is not a site."""
    if con_id.ObjTyp != ObjectTypes.Con:
        return 0
    return game.Universe.Constr[con_id.Index].TimeToCompletion


def get_capital(game: GameEnvironment, emp: Empire) -> IDNumber:
    return game.Universe.EmpireData[emp].Capital


def set_capital(game: GameEnvironment, emp: Empire, cap_id: IDNumber) -> None:
    game.Universe.EmpireData[emp].Capital = cap_id


def centralized_capital(game: GameEnvironment, emp: Empire) -> bool:
    """Whether losing the capital destroys the empire outright.

    Set from the scenario's empire modifiers. ``ConquerEmpire`` checks this
    before looking for a successor world.
    """
    return EmpireModifiers.CentralEMD in game.Universe.EmpireData[emp].Modifiers


def get_defense_settings(game: GameEnvironment, emp: Empire) -> DefenseRecord:
    """The empire's standing orders for spreading ships across the shells.

    Returns a copy: the original assigns the whole record, which in Pascal
    copies it, and ``GetEnemy`` would otherwise be able to rewrite the
    empire's settings through the value it was handed.
    """
    return deepcopy(game.Universe.EmpireData[emp].DefenseSettings)


def set_defense_settings(
    game: GameEnvironment, emp: Empire, defense: DefenseRecord
) -> None:
    game.Universe.EmpireData[emp].DefenseSettings = deepcopy(defense)


# --- Probes ------------------------------------------------------------------


def get_probe(game: GameEnvironment, player: Empire) -> int:
    """Highest-numbered probe that is ready to launch, or 0 when none is.

    Counts down from the top like the fleet and starbase allocators.
    """
    probes = game.Universe.EmpireData[player].Probe
    num = NO_OF_PROBES_PER_EMPIRE
    while num > 0 and probes[num].Status != ProbeStatus.PReady:
        num -= 1
    return num


def launch_probe(game: GameEnvironment, player: Empire, num: int, loc: XYCoord) -> None:
    """Send probe ``num`` to ``loc``. ``num`` must have come from
    :func:`get_probe`."""
    probe = game.Universe.EmpireData[player].Probe[num]
    probe.Dest = loc
    probe.Status = ProbeStatus.PInTrans


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
    """The Y axis is inverted relative to X: north is +Y for the player, but
    grid row 1 is at the top, so the capital's Y is subtracted rather than
    added. ``RelativeY`` inverts the same way."""
    return get_coord(game, get_capital(game, game.Player)).y - y


def relative_x(game: GameEnvironment, x: int) -> int:
    """Convert an absolute galaxy X to one relative to the player's capital."""
    return x - get_coord(game, get_capital(game, game.Player)).x


def relative_y(game: GameEnvironment, y: int) -> int:
    return get_coord(game, get_capital(game, game.Player)).y - y


# --- Fleets ------------------------------------------------------------------


def set_npe_data_index(game: GameEnvironment, flt_id: IDNumber, index: int) -> None:
    game.Universe.Fleet[flt_id.Index].NPEDataIndex = index


def npe_data_index(game: GameEnvironment, flt_id: IDNumber) -> int:
    return game.Universe.Fleet[flt_id.Index].NPEDataIndex


def type_of_fleet(game: GameEnvironment, flt_id: IDNumber) -> FleetTypes:
    """Classify a fleet by what it is *missing*.

    The tests are subtractive and ordered: a fleet is an HKFleet only if it
    holds nothing but hunter-killers, a JumpFleet if it has no sublight or
    warp-only hulls, and so on down to Standard, which is the catch-all.
    """
    if flt_id.ObjTyp != ObjectTypes.Flt:
        return FleetTypes.Standard

    ships = game.Universe.Fleet[flt_id.Index].Ships
    if ships[T.ssp] + ships[T.pen] + ships[T.jmp] + ships[T.fgt] + ships[T.jtn] + ships[T.trn] == 0:
        return FleetTypes.HKFleet
    if ships[T.ssp] + ships[T.pen] + ships[T.fgt] + ships[T.trn] == 0:
        return FleetTypes.JumpFleet
    if ships[T.ssp] + ships[T.jmp] + ships[T.jtn] + ships[T.trn] + ships[T.fgt] == 0:
        return FleetTypes.Penetrator
    if ships[T.ssp] + ships[T.fgt] + ships[T.trn] == 0:
        return FleetTypes.AdvWrpFleet
    return FleetTypes.Standard


def set_fleet_status(
    game: GameEnvironment, flt_id: IDNumber, new_status: FleetStatus
) -> None:
    """Set the status of a fleet or of a starbase in transit."""
    if flt_id.ObjTyp == ObjectTypes.Flt:
        game.Universe.Fleet[flt_id.Index].Status = new_status
    elif flt_id.ObjTyp == ObjectTypes.Base:
        game.Universe.Starbase[flt_id.Index].Status = new_status


def get_fleet_status(game: GameEnvironment, flt_id: IDNumber) -> FleetStatus:
    if flt_id.ObjTyp == ObjectTypes.Flt:
        return game.Universe.Fleet[flt_id.Index].Status
    if flt_id.ObjTyp == ObjectTypes.Base:
        return game.Universe.Starbase[flt_id.Index].Status
    return FleetStatus.FReady


def get_fleet_fuel(game: GameEnvironment, flt_id: IDNumber) -> float:
    """Fuel left in a fleet, recombined from the split 16-bit representation."""
    if flt_id.ObjTyp != ObjectTypes.Flt:
        return 0.0
    fleet = game.Universe.Fleet[flt_id.Index]
    return 1.0 * fleet.FuelHigh * MAXINT16 + fleet.Fuel


def set_fleet_fuel(game: GameEnvironment, flt_id: IDNumber, fuel_left: float) -> None:
    """Store fuel back into the split representation.

    Both halves truncate towards zero, following the Pascal ``Trunc``; this is
    not ``divmod``, which floors, and the two disagree for negative fuel.
    """
    if flt_id.ObjTyp != ObjectTypes.Flt:
        return
    fleet = game.Universe.Fleet[flt_id.Index]
    fleet.FuelHigh = trunc(fuel_left / MAXINT16)
    fleet.Fuel = trunc(fuel_left - 1.0 * fleet.FuelHigh * MAXINT16)


# --- Stargates ---------------------------------------------------------------


def get_gate_type(game: GameEnvironment, gate_id: IDNumber) -> TechnologyTypes:
    if gate_id.ObjTyp == ObjectTypes.Gate:
        return game.Universe.Stargate[gate_id.Index].GTyp
    return TechnologyTypes.gte


def get_warp_link_freq(game: GameEnvironment, emp: Empire, obj: IDNumber) -> int:
    """An empire's dialled frequency for a gate.

    A fleet may use a gate only when its empire's frequency matches the
    gate owner's, so the same call answers both "can I use this?" and, for
    disrupters, "is this thing pointed at me?".
    """
    return game.Universe.Stargate[obj.Index].WLF[emp]


def set_warp_link_freq(
    game: GameEnvironment, emp: Empire, obj: IDNumber, frequency: int
) -> None:
    game.Universe.Stargate[obj.Index].WLF[emp] = frequency


# --- Names -------------------------------------------------------------------
#
# Each empire keeps its own list of labels for places and fleets. The original
# is a linked list with a tail pointer and an explicit free/dispose discipline;
# a Python list serves the same purpose, so GetNewName, NAMDelete and
# DeleteAllNames collapse into ordinary list operations.


def location2index(
    game: GameEnvironment, emp: Empire, loc: Location
) -> NameRecord | None:
    """The name ``emp`` gave to ``loc``, or None if it is unnamed."""
    for name in game.Universe.EmpireData[emp].Names:
        if same_location(loc, name.Coord):
            return name
    return None


def name2index(
    game: GameEnvironment, emp: Empire, name_to_find: str
) -> NameRecord | None:
    """The name record matching ``name_to_find``, compared case-insensitively."""
    wanted = name_to_find.upper()
    for name in game.Universe.EmpireData[emp].Names:
        if name.Name.upper() == wanted:
            return name
    return None


def get_defined_name(name: NameRecord) -> tuple[str, Location]:
    return name.Name, name.Coord


def define_name(name: NameRecord, def_name: str, def_coord: Location) -> None:
    name.Name = def_name
    name.Coord = def_coord


def add_name(
    game: GameEnvironment, player: Empire, loc: Location, name_var: str
) -> bool:
    """Name a location, or rename it if it already has a name.

    Returns True on error, matching the ``VAR Error: Boolean`` the original
    passes back. Nothing can fail here now that the name list grows on
    demand -- the original ran out of heap.
    """
    if loc.ID.ObjTyp in (ObjectTypes.Con, ObjectTypes.Pln, ObjectTypes.Gate):
        loc.XY = get_coord(game, loc.ID)

    slot = location2index(game, player, loc)
    if slot is None:
        slot = NameRecord()
        game.Universe.EmpireData[player].Names.append(slot)

    define_name(slot, name_var, loc)
    return False


def delete_name(game: GameEnvironment, player: Empire, name_to_delete: str) -> None:
    """Drop a name. Silently does nothing when the name is not defined."""
    wanted = name_to_delete.upper()
    names = game.Universe.EmpireData[player].Names
    for i, name in enumerate(names):
        if name.Name.upper() == wanted:
            del names[i]
            return


def delete_all_fleet_dest_names(game: GameEnvironment, emp: Empire) -> None:
    """Forget the names of fleets that have been destroyed.

    Destroyed fleets keep their name for one turn under ``DestFlt`` so news
    items can still refer to them by name; this clears them afterwards.
    """
    names = game.Universe.EmpireData[emp].Names
    names[:] = [n for n in names if n.Coord.ID.ObjTyp != ObjectTypes.DestFlt]


def delete_all_names(game: GameEnvironment, emp: Empire) -> None:
    game.Universe.EmpireData[emp].Names.clear()


def get_fleet_name(game: GameEnvironment, emp: Empire, flt_id: IDNumber) -> str:
    """A fleet's default name: ``Fleet<n>`` if it is ours, ``Enemy<n>`` if not.

    The index is the same either way -- the prefix is the only thing that
    tells the viewer whose fleet it is.
    """
    if flt_id.ObjTyp == ObjectTypes.DestFlt or flt_id.Index in game.GlobalSets.SetOfFleetsOf[emp]:
        return f"Fleet{flt_id.Index}"
    return f"Enemy{flt_id.Index}"


def get_coord_name(game: GameEnvironment, coord: XYCoord) -> str:
    """``x,y`` relative to the active player's capital, which reads as 0,0."""
    return f"{relative_x(game, coord.x)},{relative_y(game, coord.y)}"


def name2fleet(game: GameEnvironment, emp: Empire, strg: str) -> IDNumber:
    """Parse ``Fleet12``/``Enemy12`` into a fleet ID, else EmptyQuadrant."""
    strg = strg.upper()
    if strg[:5] not in ("ENEMY", "FLEET") or len(strg) <= 5:
        return empty_quadrant()

    try:
        flt_index = int(strg[5:21])
    except ValueError:
        return empty_quadrant()

    if 0 < flt_index <= MAX_NO_OF_FLEETS:
        return IDNumber(ObjectTypes.Flt, flt_index)
    return empty_quadrant()


def name2coord(game: GameEnvironment, strg: str) -> XYCoord:
    """Parse an ``x,y`` string relative to the player's capital.

    Returns Limbo for anything that is not a coordinate or that lands outside
    the galaxy.
    """
    head, sep, tail = strg.partition(",")
    if not sep:
        return limbo()

    try:
        x = absolute_x(game, pascal_val(head))
        y = absolute_y(game, pascal_val(tail[:16]))
    except ValueError:
        return limbo()

    if game.Galaxy.in_galaxy(x, y):
        return XYCoord(x, y)
    return limbo()


def get_name(
    game: GameEnvironment, emp: Empire, loc: Location, long_format: bool = False
) -> str:
    """The best label for ``loc``: its given name, else its fleet ID, else
    its coordinates -- optionally prefixed with what kind of object it is.

    ``loc`` is normalised first, so a coordinate that happens to hold an
    object resolves to that object and matches a name given to it.
    """
    loc = Location(XYCoord(loc.XY.x, loc.XY.y), loc.ID)

    if loc.ID.ObjTyp in (ObjectTypes.Con, ObjectTypes.Pln, ObjectTypes.Gate):
        loc.XY = get_coord(game, loc.ID)
    elif not same_xy(loc.XY, limbo()):
        loc.ID = get_object(game, loc.XY)
        if loc.ID.ObjTyp == ObjectTypes.Base:
            # Starbases move, so a name pinned to one must not carry a
            # coordinate that will go stale.
            loc.XY = limbo()

    name = location2index(game, emp, loc)
    if name is not None:
        return name.Name

    if loc.ID.ObjTyp == ObjectTypes.Void:
        return get_coord_name(game, loc.XY)

    if loc.ID.ObjTyp in (ObjectTypes.Flt, ObjectTypes.DestFlt):
        return get_fleet_name(game, emp, loc.ID)

    strg = get_coord_name(game, get_coord(game, loc.ID))
    if long_format and known(game, emp, loc.ID):
        strg = f"{ObjName[loc.ID.ObjTyp]} at {strg}"
    return strg


def get_location(game: GameEnvironment, emp: Empire, strg: str) -> Location:
    """Resolve a player-typed string to a Location.

    Tried in order: a name the empire has defined, a ``Fleet<n>``/``Enemy<n>``
    fleet name, an ``x,y`` coordinate. A coordinate holding an object resolves
    to the object rather than the bare point.
    """
    name = name2index(game, emp, strg)
    if name is not None:
        return name.Coord

    loc = Location(limbo(), empty_quadrant())

    loc.ID = name2fleet(game, emp, strg)
    if not same_id(loc.ID, empty_quadrant()):
        return loc

    temp_coord = name2coord(game, strg)
    if same_xy(temp_coord, limbo()):
        return loc

    temp_id = get_object(game, temp_coord)
    if not same_id(temp_id, empty_quadrant()):
        loc.ID = temp_id
    else:
        loc.XY = temp_coord
    return loc


def object_name(
    game: GameEnvironment, emp: Empire, obj_id: IDNumber, long_format: bool = False
) -> str:
    return get_name(game, emp, Location(limbo(), obj_id), long_format)
