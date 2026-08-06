"""The per-turn scouting sweep, ported from INTRFACE.PAS.

Fog of war has three levels, and most of these tests are about which one an
object lands in:

- **unknown** -- the empire has no idea it exists
- **known** -- it can see something is there, not what
- **scouted** -- it can see what it is made of
"""

import pytest
from conftest import blank_game, place_world

from recreon.fleet import deploy_fleet
from recreon.galaxy import XYCoord
from recreon.intrface import (
    determine_if_scouted,
    in_range_of_planet,
    in_range_of_starbase,
    scout_fleets,
    scout_objects,
)
from recreon.main import set_up_turn
from recreon.news import NewsTypes, get_news_list
from recreon.primintr import (
    clear_scout_set,
    known,
    put_cargo,
    put_nebula,
    put_ships,
    scout_object,
    scouted,
)
from recreon.types import (
    Empire,
    FleetTypes,
    IDNumber,
    NebulaTypes,
    ObjectTypes,
    TechnologyTypes,
    WorldTypes,
    cargo_array,
    ship_array,
)
from recreon.utils.pascal import set_rand_seed

T = TechnologyTypes
WT = WorldTypes

HOME_XY = XYCoord(10, 10)


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


def stock(game, obj, ships=None, cargo=None):
    sh = ship_array()
    sh.update(ships or {})
    cr = cargo_array()
    cr.update(cargo or {})
    put_ships(game, obj, sh)
    put_cargo(game, obj, cr)


@pytest.fixture
def game():
    """Empire1 holds one world at (10,10); Empire2 exists but owns nothing yet."""
    g = blank_game(size=30, empires=2)
    home = place_world(g, 1, HOME_XY, emp=Empire.Empire1, typ=WT.CapTyp)
    g.Universe.EmpireData[Empire.Empire1].Capital = home
    stock(g, home, {T.fgt: 500, T.jmp: 500, T.hkr: 500, T.jtn: 500}, {T.tri: 5000})
    return g


@pytest.fixture
def home():
    return IDNumber(ObjectTypes.Pln, 1)


def enemy_fleet(game, xy, ships, from_world=2):
    """An Empire2 fleet sitting at ``xy``."""
    src = place_world(game, from_world, xy, emp=Empire.Empire2)
    stock(game, src, ships, {T.tri: 5000})
    sh = ship_array()
    sh.update(ships)
    return deploy_fleet(game, Empire.Empire2, src, sh, cargo_array(), xy)


# --- in_range_of_starbase -----------------------------------------------------


def test_a_scanning_starbase_covers_five_sectors(game):
    from recreon.intrface import create_starbase

    base = IDNumber(ObjectTypes.Base, 1)
    create_starbase(game, base, Empire.Empire1, XYCoord(20, 20), T.cmm)

    assert in_range_of_starbase(game, Empire.Empire1, XYCoord(24, 20))
    assert not in_range_of_starbase(game, Empire.Empire1, XYCoord(27, 20))


def test_an_industrial_complex_does_not_scan(game):
    from recreon.intrface import create_starbase

    base = IDNumber(ObjectTypes.Base, 1)
    create_starbase(game, base, Empire.Empire1, XYCoord(20, 20), T.cmp)

    assert not in_range_of_starbase(game, Empire.Empire1, XYCoord(21, 20))


# --- in_range_of_planet -------------------------------------------------------


def test_a_world_detects_an_ordinary_fleet_at_five_sectors(game):
    assert in_range_of_planet(game, Empire.Empire1, FleetTypes.Standard, XYCoord(15, 10))
    assert not in_range_of_planet(
        game, Empire.Empire1, FleetTypes.Standard, XYCoord(16, 10)
    )


def test_hunter_killers_and_penetrators_slip_planetary_detection(game):
    for f_typ in (FleetTypes.HKFleet, FleetTypes.Penetrator):
        assert not in_range_of_planet(game, Empire.Empire1, f_typ, XYCoord(11, 10))


def test_any_nebula_defeats_planetary_detection(game):
    put_nebula(game, XYCoord(11, 10), NebulaTypes.DarkNebula)

    assert not in_range_of_planet(
        game, Empire.Empire1, FleetTypes.Standard, XYCoord(11, 10)
    )


# --- scout_fleets -------------------------------------------------------------


def test_an_empire_always_sees_its_own_fleets(game, home):
    sh = ship_array()
    sh[T.fgt] = 100
    flt = deploy_fleet(game, Empire.Empire1, home, sh, cargo_array(), XYCoord(25, 25))

    scout_fleets(game, Empire.Empire1)

    assert scouted(game, Empire.Empire1, flt)
    assert known(game, Empire.Empire1, flt)


def test_a_fleet_beside_your_world_is_scouted(game):
    flt = enemy_fleet(game, XYCoord(11, 10), {T.fgt: 100})

    scout_fleets(game, Empire.Empire1)

    assert scouted(game, Empire.Empire1, flt)


def test_a_hunter_killer_group_beside_your_world_is_not_scouted(game):
    """The one exemption in the adjacency rule: an HK fleet is only pure
    hunter-killers, and those slip the check entirely."""
    flt = enemy_fleet(game, XYCoord(11, 10), {T.hkr: 100})

    scout_fleets(game, Empire.Empire1)

    assert not scouted(game, Empire.Empire1, flt)
    assert not known(game, Empire.Empire1, flt), "and planetary detection skips it too"


def test_a_distant_fleet_is_known_but_not_scouted(game):
    """Within 5 sectors of a world but not adjacent: you see it is there."""
    flt = enemy_fleet(game, XYCoord(14, 10), {T.fgt: 100})

    scout_fleets(game, Empire.Empire1)

    assert known(game, Empire.Empire1, flt)
    assert not scouted(game, Empire.Empire1, flt)


def test_a_fleet_out_of_range_is_neither(game):
    flt = enemy_fleet(game, XYCoord(25, 25), {T.fgt: 100})

    scout_fleets(game, Empire.Empire1)

    assert not known(game, Empire.Empire1, flt)
    assert not scouted(game, Empire.Empire1, flt)


def test_a_starbase_scan_scouts_a_fleet_a_world_could_only_detect(game):
    from recreon.intrface import create_starbase

    base = IDNumber(ObjectTypes.Base, 1)
    create_starbase(game, base, Empire.Empire1, XYCoord(20, 20), T.cmm)
    flt = enemy_fleet(game, XYCoord(23, 20), {T.hkr: 100})

    scout_fleets(game, Empire.Empire1)

    assert scouted(game, Empire.Empire1, flt), "a base scan sees even hunter-killers"


def test_spotting_a_fleet_files_a_headline(game):
    enemy_fleet(game, XYCoord(11, 10), {T.fgt: 100})

    scout_fleets(game, Empire.Empire1)

    feed = get_news_list(game, Empire.Empire1)
    assert any(item.Headline == NewsTypes.FltDet for item in feed)
    detected = next(i for i in feed if i.Headline == NewsTypes.FltDet)
    assert detected.Parm1 == int(Empire.Empire2)


def test_a_fleet_that_leaves_is_forgotten(game):
    """Scouting is recomputed from scratch, not accumulated."""
    flt = enemy_fleet(game, XYCoord(11, 10), {T.fgt: 100})
    scout_fleets(game, Empire.Empire1)
    assert scouted(game, Empire.Empire1, flt)

    game.Universe.Fleet[flt.Index].XY = XYCoord(28, 28)
    clear_scout_set(game, Empire.Empire1)
    scout_fleets(game, Empire.Empire1)

    assert not scouted(game, Empire.Empire1, flt)


# --- determine_if_scouted -----------------------------------------------------


def test_your_own_worlds_are_always_scouted(game, home):
    """Via the sweep, which is how it actually happens: `scout` starts at
    `NoDir`, so the ring around a world includes the world itself."""
    clear_scout_set(game, Empire.Empire1)
    scout_objects(game, Empire.Empire1)

    assert scouted(game, Empire.Empire1, home)


def test_determine_if_scouted_needs_the_object_to_be_known_first(game, home):
    """Even for your own world. The `known` test gates the whole first branch,
    and an unknown object can only be picked up by the starbase-scan path."""
    game.Universe.Planet[home.Index].KnownBy.discard(Empire.Empire1)
    clear_scout_set(game, Empire.Empire1)

    determine_if_scouted(game, Empire.Empire1, home)

    assert not scouted(game, Empire.Empire1, home)


def test_a_known_world_near_the_capital_is_scouted(game):
    other = place_world(game, 2, XYCoord(13, 10), emp=Empire.Empire2)
    scout_object(game, Empire.Empire1, other)  # sets KnownBy too
    clear_scout_set(game, Empire.Empire1)

    determine_if_scouted(game, Empire.Empire1, other)

    assert scouted(game, Empire.Empire1, other)


def test_a_known_world_far_from_everything_stays_unscouted(game):
    other = place_world(game, 2, XYCoord(28, 28), emp=Empire.Empire2)
    scout_object(game, Empire.Empire1, other)
    clear_scout_set(game, Empire.Empire1)

    determine_if_scouted(game, Empire.Empire1, other)

    assert known(game, Empire.Empire1, other), "knowledge persists"
    assert not scouted(game, Empire.Empire1, other)


def test_an_unknown_world_is_discovered_only_by_a_starbase_scan(game):
    """And only on a coin flip, so a new base maps its surroundings over a few
    years rather than all at once."""
    from recreon.intrface import create_starbase

    base = IDNumber(ObjectTypes.Base, 1)
    create_starbase(game, base, Empire.Empire1, XYCoord(20, 20), T.cmm)
    other = place_world(game, 2, XYCoord(22, 20), emp=Empire.Empire2)

    assert not known(game, Empire.Empire1, other)

    for _ in range(20):
        determine_if_scouted(game, Empire.Empire1, other)
        if scouted(game, Empire.Empire1, other):
            break

    assert scouted(game, Empire.Empire1, other)
    assert any(
        item.Headline == NewsTypes.OutProbe
        for item in get_news_list(game, Empire.Empire1)
    )


def test_an_unknown_world_out_of_scan_range_is_never_discovered(game):
    other = place_world(game, 2, XYCoord(28, 28), emp=Empire.Empire2)

    for _ in range(50):
        determine_if_scouted(game, Empire.Empire1, other)

    assert not known(game, Empire.Empire1, other)


# --- scout_objects ------------------------------------------------------------


def test_the_sweep_reveals_the_ring_around_your_worlds(game):
    neighbour = place_world(game, 2, XYCoord(11, 11), emp=Empire.Empire2)

    scout_objects(game, Empire.Empire1)

    assert scouted(game, Empire.Empire1, neighbour)


def test_the_sweep_reaches_out_from_your_fleets_too(game, home):
    far = place_world(game, 2, XYCoord(25, 25), emp=Empire.Empire2)
    sh = ship_array()
    sh[T.fgt] = 100
    deploy_fleet(game, Empire.Empire1, home, sh, cargo_array(), XYCoord(25, 24))
    game.Universe.Fleet[
        max(game.GlobalSets.SetOfFleetsOf[Empire.Empire1])
    ].XY = XYCoord(25, 24)

    scout_objects(game, Empire.Empire1)

    assert scouted(game, Empire.Empire1, far)


def test_a_dark_nebula_blocks_the_ring_sweep(game):
    """`scout` bails out of the whole loop on hitting one, so what gets
    revealed depends on scan order -- issue #13."""
    # Directions run NoDir, No, Ne, Ea, Se, ... so a nebula at Ne (11,9) is
    # hit before Se (11,11) and the sweep never gets there.
    put_nebula(game, XYCoord(11, 9), NebulaTypes.DarkNebula)
    behind = place_world(game, 2, XYCoord(11, 11), emp=Empire.Empire2)
    before = place_world(game, 3, XYCoord(10, 9), emp=Empire.Empire2)

    scout_objects(game, Empire.Empire1)

    assert scouted(game, Empire.Empire1, before), "No comes before the nebula"
    assert not scouted(game, Empire.Empire1, behind), "Se comes after it"


# --- set_up_turn --------------------------------------------------------------


def test_set_up_turn_runs_the_whole_sweep(game, home):
    neighbour = place_world(game, 2, XYCoord(11, 11), emp=Empire.Empire2)
    flt = enemy_fleet(game, XYCoord(11, 10), {T.fgt: 100}, from_world=3)

    set_up_turn(game, Empire.Empire1)

    assert scouted(game, Empire.Empire1, home)
    assert scouted(game, Empire.Empire1, neighbour)
    assert scouted(game, Empire.Empire1, flt)


def test_set_up_turn_lands_probes(game):
    from recreon.primintr import get_probe, launch_probe
    from recreon.types import ProbeStatus

    far = place_world(game, 2, XYCoord(25, 25), emp=Empire.Empire2)
    num = get_probe(game, Empire.Empire1)
    launch_probe(game, Empire.Empire1, num, XYCoord(25, 25))

    set_up_turn(game, Empire.Empire1)

    assert scouted(game, Empire.Empire1, far)
    assert (
        game.Universe.EmpireData[Empire.Empire1].Probe[num].Status == ProbeStatus.PReady
    )


def test_the_ai_sees_more_than_probes_alone():
    """Regression on the whole point of this change: before the sweep landed,
    an NPE's only information channel was its ten probes."""
    import pathlib

    from recreon.main import update_turn
    from recreon.newgame import load_scenario
    from recreon.primintr import empire_active
    from recreon.types import PLAYER_EMPIRES

    scn = pathlib.Path(__file__).resolve().parent.parent / "original" / "scenarios"
    g = load_scenario(scn / "INTRO.SCN", {Empire.Empire1: "A"})

    for _ in range(30):
        update_turn(g)

    npes = [
        e
        for e in PLAYER_EMPIRES
        if empire_active(g, e) and g.NPEData[e].Typ.name != "NoNPE"
    ]
    seen = max(
        sum(
            1
            for i in range(1, g.NoOfPlanets + 1)
            if known(g, e, IDNumber(ObjectTypes.Pln, i))
        )
        for e in npes
    )
    assert seen > 10, f"an NPE knows only {seen} worlds -- probes alone would give ~10"
