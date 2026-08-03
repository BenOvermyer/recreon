"""Milestone 6: construction sites consume material and finish into real objects."""

from conftest import blank_game, place_world
from recreon.datacnst import ConsCargoNeeded, YearsToBuild
from recreon.fleet import deploy_fleet, move_fleet
from recreon.galaxy import XYCoord, limbo
from recreon.intrface import construction, destroy_construction, next_constr_slot
from recreon.news import NewsTypes, get_news_list
from recreon.primintr import (
    add_name,
    enemy_mine,
    get_base_type,
    get_cargo,
    get_efficiency,
    get_gate_type,
    get_name,
    get_object,
    get_population,
    get_status,
    get_tech,
    get_type,
    put_cargo,
    put_ships,
)
from recreon.types import (
    MAX_NO_OF_CONSTR_SITES,
    Empire,
    IDNumber,
    ObjectTypes,
    TechLevel,
    TechnologyTypes,
    WorldTypes,
    cargo_array,
    empty_quadrant,
    ship_array,
)
from recreon.update import (
    construct_starbase,
    construct_stargate,
    update_construction,
    update_universe,
)
from recreon.utils.pascal import set_rand_seed

T = TechnologyTypes

SITE_XY = XYCoord(9, 9)


def _builder(size: int = 20) -> tuple:
    """An empire with a home world, and an empty sector to build in."""
    game = blank_game(size=size, empires=1)
    home = place_world(game, 1, XYCoord(2, 2), emp=Empire.Empire1)
    return game, home


def _supply_fleet(game, home, xy: XYCoord, cargo: dict[T, int]) -> IDNumber:
    """Park a loaded transport fleet on ``xy``."""
    stock = get_cargo(game, home)
    for thing, amount in cargo.items():
        stock[thing] = stock.get(thing, 0) + amount
    put_cargo(game, home, stock)

    ships = ship_array()
    ships[T.trn] = 5000
    put_ships(game, home, ships)

    cr = cargo_array()
    for thing, amount in cargo.items():
        cr[thing] = amount

    sh = ship_array()
    sh[T.trn] = 5000
    flt = deploy_fleet(game, Empire.Empire1, home, sh, cr, xy)
    move_fleet(game, flt, xy)
    return flt


def _full_year_of(ctyp: T) -> dict[T, int]:
    return {thing: ConsCargoNeeded[ctyp][thing] for thing in T if thing in ConsCargoNeeded[ctyp]}


# --- Breaking ground ---------------------------------------------------------


def test_construction_claims_the_sector_immediately():
    """A site is a real object from day one -- scoutable, nameable, attackable
    long before it finishes."""
    game, _ = _builder()

    con_id = construction(game, Empire.Empire1, T.cmm, SITE_XY)

    assert con_id.ObjTyp == ObjectTypes.Con
    assert get_object(game, SITE_XY) == con_id
    assert con_id.Index in game.GlobalSets.SetOfActiveConstructionSites
    assert con_id.Index in game.GlobalSets.SetOfConstructionSitesOf[Empire.Empire1]


def test_construction_starts_the_clock_from_the_build_table():
    game, _ = _builder()

    con_id = construction(game, Empire.Empire1, T.frt, SITE_XY)

    assert game.Universe.Constr[con_id.Index].TimeToCompletion == YearsToBuild[T.frt]
    assert YearsToBuild[T.frt] == 12


def test_only_the_builder_knows_about_a_new_site():
    game, _ = _builder()

    con_id = construction(game, Empire.Empire1, T.out, SITE_XY)
    site = game.Universe.Constr[con_id.Index]

    assert site.ScoutedBy == {Empire.Empire1}
    assert site.KnownBy == {Empire.Empire1}


def test_slots_are_handed_out_from_the_top_down():
    game, _ = _builder()

    assert next_constr_slot(game) == MAX_NO_OF_CONSTR_SITES
    first = construction(game, Empire.Empire1, T.out, SITE_XY)
    second = construction(game, Empire.Empire1, T.out, XYCoord(8, 8))

    assert first.Index == MAX_NO_OF_CONSTR_SITES
    assert second.Index == MAX_NO_OF_CONSTR_SITES - 1


def test_construction_gives_up_quietly_when_every_slot_is_taken():
    game, _ = _builder()
    game.GlobalSets.SetOfActiveConstructionSites.update(
        range(1, MAX_NO_OF_CONSTR_SITES + 1)
    )

    assert construction(game, Empire.Empire1, T.out, SITE_XY) == empty_quadrant()
    assert get_object(game, SITE_XY) == empty_quadrant()


def test_destroying_a_site_frees_its_slot_and_sector():
    game, _ = _builder()
    con_id = construction(game, Empire.Empire1, T.cmm, SITE_XY)

    destroy_construction(game, con_id)

    assert get_object(game, SITE_XY) == empty_quadrant()
    assert con_id.Index not in game.GlobalSets.SetOfActiveConstructionSites
    assert con_id.Index not in game.GlobalSets.SetOfConstructionSitesOf[Empire.Empire1]
    assert next_constr_slot(game) == con_id.Index


# --- Paying for it -----------------------------------------------------------


def test_a_site_with_no_supply_fleet_makes_no_progress():
    """Progress is bought, not waited out."""
    game, _ = _builder()
    con_id = construction(game, Empire.Empire1, T.out, SITE_XY)
    before = game.Universe.Constr[con_id.Index].TimeToCompletion

    update_construction(game, con_id.Index)

    assert game.Universe.Constr[con_id.Index].TimeToCompletion == before


def test_a_shortfall_is_reported_and_costs_a_year():
    game, home = _builder()
    con_id = construction(game, Empire.Empire1, T.out, SITE_XY)
    before = game.Universe.Constr[con_id.Index].TimeToCompletion
    _supply_fleet(game, home, SITE_XY, {T.che: 10})  # nowhere near enough

    update_construction(game, con_id.Index)

    assert game.Universe.Constr[con_id.Index].TimeToCompletion == before
    headlines = [item.Headline for item in get_news_list(game, Empire.Empire1)]
    assert NewsTypes.ConsLack in headlines


def test_a_shortfall_consumes_nothing_at_all():
    """All or nothing: a half-supplied site must not quietly eat what did
    arrive, or the material is lost for no progress."""
    game, home = _builder()
    con_id = construction(game, Empire.Empire1, T.out, SITE_XY)
    # Enough chemicals, no metals -- the draw must roll back.
    flt = _supply_fleet(
        game, home, SITE_XY, {T.che: ConsCargoNeeded[T.out][T.che], T.met: 0}
    )

    update_construction(game, con_id.Index)

    assert get_cargo(game, flt)[T.che] == ConsCargoNeeded[T.out][T.che]


def test_a_supplied_site_advances_a_year_and_pays_for_it():
    game, home = _builder()
    con_id = construction(game, Empire.Empire1, T.out, SITE_XY)
    before = game.Universe.Constr[con_id.Index].TimeToCompletion
    flt = _supply_fleet(game, home, SITE_XY, _full_year_of(T.out))

    update_construction(game, con_id.Index)

    assert game.Universe.Constr[con_id.Index].TimeToCompletion == before - 1
    cargo = get_cargo(game, flt)
    assert cargo[T.che] == 0
    assert cargo[T.met] == 0
    assert cargo[T.tri] == 0


def test_only_the_owners_fleets_can_supply_a_site():
    """An enemy transport parked on the site contributes nothing."""
    game, home = _builder()
    enemy_home = place_world(game, 2, XYCoord(3, 3), emp=Empire.Empire2)
    con_id = construction(game, Empire.Empire1, T.out, SITE_XY)
    before = game.Universe.Constr[con_id.Index].TimeToCompletion

    stock = get_cargo(game, enemy_home)
    for thing, amount in _full_year_of(T.out).items():
        stock[thing] = amount
    put_cargo(game, enemy_home, stock)
    ships = ship_array()
    ships[T.trn] = 5000
    put_ships(game, enemy_home, ships)
    cr = cargo_array()
    for thing, amount in _full_year_of(T.out).items():
        cr[thing] = amount
    sh = ship_array()
    sh[T.trn] = 5000
    enemy_flt = deploy_fleet(game, Empire.Empire2, enemy_home, sh, cr, SITE_XY)
    move_fleet(game, enemy_flt, SITE_XY)

    update_construction(game, con_id.Index)

    assert game.Universe.Constr[con_id.Index].TimeToCompletion == before
    assert get_cargo(game, enemy_flt)[T.met] == ConsCargoNeeded[T.out][T.met]


def test_material_is_drawn_from_the_lowest_numbered_fleet_first():
    game, home = _builder()
    con_id = construction(game, Empire.Empire1, T.out, SITE_XY)
    need = _full_year_of(T.out)

    first = _supply_fleet(game, home, SITE_XY, need)
    second = _supply_fleet(game, home, SITE_XY, need)
    low, high = sorted((first.Index, second.Index))

    update_construction(game, con_id.Index)

    # The lower index is emptied; the higher one is untouched.
    assert get_cargo(game, IDNumber(ObjectTypes.Flt, low))[T.met] == 0
    assert (
        get_cargo(game, IDNumber(ObjectTypes.Flt, high))[T.met]
        == ConsCargoNeeded[T.out][T.met]
    )


# --- Completion --------------------------------------------------------------


def _build_to_completion(game, home, ctyp: T) -> IDNumber:
    con_id = construction(game, Empire.Empire1, ctyp, SITE_XY)
    for _ in range(YearsToBuild[ctyp]):
        _supply_fleet(game, home, SITE_XY, _full_year_of(ctyp))
        update_construction(game, con_id.Index)
    return con_id


def test_an_srm_site_finishes_as_a_minefield():
    set_rand_seed(5)
    game, home = _builder()

    con_id = _build_to_completion(game, home, T.SRM)

    assert enemy_mine(game, SITE_XY) == Empire.Empire1
    assert con_id.Index not in game.GlobalSets.SetOfActiveConstructionSites
    assert get_object(game, SITE_XY) == empty_quadrant()


def test_an_outpost_finishes_as_a_one_caretaker_starbase():
    set_rand_seed(5)
    game, home = _builder()

    _build_to_completion(game, home, T.out)

    base = get_object(game, SITE_XY)
    assert base.ObjTyp == ObjectTypes.Base
    assert get_base_type(game, base) == T.out
    assert get_type(game, base) == WorldTypes.OutTyp
    assert get_population(game, base) == 1
    assert get_status(game, base) == Empire.Empire1
    assert 10 <= get_efficiency(game, base) <= 20


def test_a_command_base_finishes_with_a_garrison():
    set_rand_seed(5)
    game, home = _builder()

    _build_to_completion(game, home, T.cmm)

    base = get_object(game, SITE_XY)
    assert get_base_type(game, base) == T.cmm
    assert get_type(game, base) == WorldTypes.BseTyp
    assert 10 <= get_population(game, base) <= 20


def test_an_industrial_complex_arrives_populated_and_running():
    """Ten years of material buys a working economy, not an empty shell."""
    set_rand_seed(5)
    game, home = _builder()

    _build_to_completion(game, home, T.cmp)

    base = get_object(game, SITE_XY)
    assert get_base_type(game, base) == T.cmp
    assert 400 <= get_population(game, base) <= 700
    assert sum(game.Universe.Starbase[base.Index].Indus.values()) > 0


def test_a_new_starbase_inherits_the_empires_technology():
    set_rand_seed(5)
    game, home = _builder()
    game.Universe.EmpireData[Empire.Empire1].TechnologyLevel = TechLevel.StrTchLvl

    _build_to_completion(game, home, T.cmm)

    assert get_tech(game, get_object(game, SITE_XY)) == TechLevel.StrTchLvl


def test_a_stargate_site_finishes_as_a_stargate():
    set_rand_seed(5)
    game, home = _builder()

    _build_to_completion(game, home, T.gte)

    gate = get_object(game, SITE_XY)
    assert gate.ObjTyp == ObjectTypes.Gate
    assert get_gate_type(game, gate) == T.gte
    assert gate.Index in game.GlobalSets.SetOfActiveGates


def test_completion_is_announced():
    set_rand_seed(5)
    game, home = _builder()

    _build_to_completion(game, home, T.out)

    items = [item for item in get_news_list(game, Empire.Empire1)]
    done = [item for item in items if item.Headline == NewsTypes.ConsDone]
    assert done
    # The original reports the coordinate, not the object -- the site is gone
    # by the time the item is filed.
    assert done[-1].Loc1.XY == SITE_XY
    assert done[-1].Parm1 == int(T.out)


def test_a_named_site_loses_its_name_on_completion():
    """The original tries to hand the site's name to what it becomes, and the
    lookup can never match: add_name stores a Con location with its real
    coordinate, update_construction searches with XY = Limbo, and
    SameLocation compares both fields. Faithful, not a porting slip -- see the
    docstring on update_construction."""
    set_rand_seed(5)
    game, home = _builder()
    con_id = construction(game, Empire.Empire1, T.out, SITE_XY)
    add_name(game, Empire.Empire1, _loc(con_id), "Bastion")

    for _ in range(YearsToBuild[T.out]):
        _supply_fleet(game, home, SITE_XY, _full_year_of(T.out))
        update_construction(game, con_id.Index)

    base = get_object(game, SITE_XY)
    # Falls back to the coordinate name, not "Bastion".
    assert get_name(game, Empire.Empire1, _loc(base)) != "Bastion"
    # And the site's own name record is left behind rather than deleted.
    assert any(n.Name == "Bastion" for n in game.Universe.EmpireData[Empire.Empire1].Names)


def test_news_locations_name_the_object_not_the_coordinate():
    """Location is (XY, ID). Swapping them type-checks -- both fields hold
    dataclasses -- and silently breaks every name lookup that reads a news
    item, so it is worth pinning."""
    game, home = _builder()
    con_id = construction(game, Empire.Empire1, T.out, SITE_XY)
    _supply_fleet(game, home, SITE_XY, {T.che: 10})

    update_construction(game, con_id.Index)

    lack = [
        item
        for item in get_news_list(game, Empire.Empire1)
        if item.Headline == NewsTypes.ConsLack
    ]
    assert lack[-1].Loc1.ID == con_id
    assert lack[-1].Loc1.XY == limbo()


def _loc(obj: IDNumber):
    from recreon.galaxy import Location

    return Location(XY=limbo(), ID=obj)


# --- Direct construction helpers ---------------------------------------------


def test_construct_starbase_reports_failure_when_no_slot_is_free():
    set_rand_seed(5)
    game, _ = _builder()
    game.GlobalSets.SetOfActiveStarbases.update(
        range(1, len(game.Universe.Starbase))
    )

    assert construct_starbase(game, Empire.Empire1, T.out, SITE_XY) == empty_quadrant()


def test_construct_stargate_reports_failure_when_no_slot_is_free():
    game, _ = _builder()
    from recreon.types import MAX_NO_OF_STARGATES

    game.GlobalSets.SetOfActiveGates.update(range(1, MAX_NO_OF_STARGATES + 1))

    assert construct_stargate(game, Empire.Empire1, T.gte, SITE_XY) == empty_quadrant()


# --- Wired into the annual tick ----------------------------------------------


def test_update_universe_advances_construction():
    set_rand_seed(5)
    game, home = _builder()
    con_id = construction(game, Empire.Empire1, T.out, SITE_XY)
    before = game.Universe.Constr[con_id.Index].TimeToCompletion
    _supply_fleet(game, home, SITE_XY, _full_year_of(T.out))

    update_universe(game)

    assert game.Universe.Constr[con_id.Index].TimeToCompletion == before - 1


def test_a_starbase_is_an_artificial_world_for_industry_purposes():
    """GetClass answers ArtCls for anything that is not a planet. That row of
    ClassIndAdj is shipyard-heavy, which is the whole point of a complex --
    BarCls would size it as a mining world instead."""
    from recreon.datacnst import ClassIndAdj
    from recreon.intrface import create_starbase
    from recreon.primintr import get_class
    from recreon.types import IndusTypes, WorldClass

    game, _ = _builder()
    base = IDNumber(ObjectTypes.Base, 1)
    create_starbase(game, base, Empire.Empire1, SITE_XY, T.cmp)

    assert get_class(game, base) == WorldClass.ArtCls
    assert (
        ClassIndAdj[WorldClass.ArtCls][IndusTypes.SYSInd]
        > ClassIndAdj[WorldClass.BarCls][IndusTypes.SYSInd]
    )
