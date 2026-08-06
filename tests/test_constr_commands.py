"""Construction commands, ported from CONSTR.PAS.

The *mechanics* -- sites consuming material and finishing into real objects --
are `test_constr.py`, against `intrface.construction` and
`update.update_construction`. This is the four commands a player drives them
with.
"""

import pytest
from conftest import blank_game, place_world

from recreon.constr import (
    CONSTR_MATERIALS,
    MAX_WARP_LINK_FREQ,
    ConsName,
    FrequencyError,
    abort_construction_command,
    available_constr_types,
    constr_status_rows,
    construct_command,
    noun,
    sector_is_free,
    set_warp_link_frequency,
    warp_link_advice,
    warp_link_freq_list,
)
from recreon.datacnst import ConsCargoNeeded, TechDev, YearsToBuild
from recreon.galaxy import Location, XYCoord, limbo
from recreon.intrface import create_stargate, next_stargate_slot
from recreon.primintr import (
    add_name,
    get_warp_link_freq,
    location2index,
    put_cargo,
)
from recreon.types import (
    CONSTR_TYPES,
    Empire,
    IDNumber,
    ObjectTypes,
    TechLevel,
    TechnologyTypes,
    empty_quadrant,
)
from recreon.utils.pascal import set_rand_seed

T = TechnologyTypes


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


@pytest.fixture
def game():
    """One empire at gate technology, so everything is buildable."""
    g = blank_game(size=20, empires=1)
    place_world(g, 1, XYCoord(5, 5), emp=Empire.Empire1)
    data = g.Universe.EmpireData[Empire.Empire1]
    data.TechnologyLevel = TechLevel.GteTchLvl
    data.Technology = set(TechDev[TechLevel.GteTchLvl])
    data.Capital = IDNumber(ObjectTypes.Pln, 1)
    return g


PLAYER = Empire.Empire1


# --- What can be built -------------------------------------------------------


def test_construction_is_gated_on_technology_not_level(game):
    """`ConI IN Technology` -- so a scenario can grant one type on its own."""
    data = game.Universe.EmpireData[PLAYER]
    data.Technology = {T.out, T.gte}

    assert [kind for kind, _ in available_constr_types(game, PLAYER)] == [T.out, T.gte]


def test_a_warp_era_empire_can_build_nothing(game):
    """Which is not a bug: `TechDev` grants no construction type below
    bio-tech, so the command's "you don't have the technology to build
    anything!" branch is reachable in a normal early game."""
    data = game.Universe.EmpireData[PLAYER]
    data.Technology = set(TechDev[TechLevel.WrpTchLvl])

    assert available_constr_types(game, PLAYER) == []


def test_the_menu_labels_capitalise_the_first_letter(game):
    labels = dict(available_constr_types(game, PLAYER))
    assert labels[T.cmm] == "Command base"
    assert labels[T.dis] == "Jumpspace disrupter"


def test_every_construction_type_has_a_name():
    assert set(ConsName) == set(CONSTR_TYPES)


@pytest.mark.parametrize(
    "word,expected",
    [("fortress", "a fortress"), ("outpost", "an outpost"), ("stargate", "a stargate")],
)
def test_noun_picks_its_article(word, expected):
    assert noun(word) == expected


def test_noun_counts_y_as_a_vowel():
    """It would say "an yard". No construction name starts with one, so the
    quirk never shows -- but it is the original's rule."""
    assert noun("yard") == "an yard"


# --- Where -------------------------------------------------------------------


def test_an_occupied_sector_cannot_be_built_on(game):
    assert sector_is_free(game, XYCoord(6, 6))
    assert not sector_is_free(game, XYCoord(5, 5))


def test_another_empires_world_blocks_it_too(game):
    """The error is about the sector, not about permission -- one object per
    sector is the whole rule."""
    place_world(game, 2, XYCoord(8, 8), emp=Empire.Empire2)
    assert not sector_is_free(game, XYCoord(8, 8))


# --- Constructing ------------------------------------------------------------


def test_constructing_creates_a_site_and_reports_its_cost(game):
    report = construct_command(game, PLAYER, T.cmm, XYCoord(6, 6))

    assert report is not None
    assert report.con_id.ObjTyp is ObjectTypes.Con
    assert report.con_id.Index in game.GlobalSets.SetOfConstructionSitesOf[PLAYER]
    assert report.years == YearsToBuild[T.cmm]
    assert "command base" in report.headline()

    amounts = dict(
        (name, amount) for name, amount in report.materials
    )
    assert list(amounts.values()) == [
        ConsCargoNeeded[T.cmm][material] for material in CONSTR_MATERIALS
    ]


def test_supplies_are_not_a_construction_material():
    """`ConstrStatusCommand` sweeps che..tri and skips sup -- supplies feed
    people, not building sites."""
    assert T.sup not in CONSTR_MATERIALS
    assert CONSTR_MATERIALS == (T.che, T.met, T.tri)


def test_a_name_on_the_sector_follows_the_site(game):
    """It has to: a finished site becomes a base or a gate, which then moves.

    So the label is moved off the bare coordinate and onto the site's ID.
    `AddName` then fills the coordinate back in (PRIMINTR.PAS:1256 does this
    for Con, Pln and Gate), so the stored location carries both -- which is
    why the lookup below uses the real XY rather than Limbo.
    """
    xy = XYCoord(6, 6)
    add_name(game, PLAYER, Location(XY=xy, ID=empty_quadrant()), "The Yards")

    report = construct_command(game, PLAYER, T.cmm, xy)

    assert location2index(game, PLAYER, Location(XY=xy, ID=empty_quadrant())) is None
    moved = location2index(game, PLAYER, Location(XY=xy, ID=report.con_id))
    assert moved is not None and moved.Name == "The Yards"


def test_an_unnamed_sector_gains_no_name(game):
    xy = XYCoord(7, 7)
    report = construct_command(game, PLAYER, T.out, xy)
    assert location2index(game, PLAYER, Location(XY=xy, ID=report.con_id)) is None


def test_running_out_of_slots_reports_nothing_built(game):
    """The original does not check: `Construction` hands back EmptyQuadrant
    and the command prints a report about a site that does not exist."""
    from recreon.types import MAX_NO_OF_CONSTR_SITES

    game.GlobalSets.SetOfActiveConstructionSites = set(
        range(1, MAX_NO_OF_CONSTR_SITES + 1)
    )
    assert construct_command(game, PLAYER, T.out, XYCoord(9, 9)) is None


# --- Aborting ----------------------------------------------------------------


def test_aborting_removes_the_site_and_frees_the_sector(game):
    report = construct_command(game, PLAYER, T.cmm, XYCoord(6, 6))
    assert not sector_is_free(game, XYCoord(6, 6))

    message = abort_construction_command(game, PLAYER, report.con_id)

    assert "aborted" in message
    assert report.con_id.Index not in game.GlobalSets.SetOfActiveConstructionSites
    assert sector_is_free(game, XYCoord(6, 6))


def test_the_abort_message_capitalises_the_site_name(game):
    report = construct_command(game, PLAYER, T.cmm, XYCoord(6, 6))
    message = abort_construction_command(game, PLAYER, report.con_id)

    assert message[0].isupper()


# --- Status ------------------------------------------------------------------


def test_a_player_with_no_sites_has_no_rows(game):
    assert constr_status_rows(game, PLAYER) == []


def test_a_row_reports_the_completion_year(game):
    report = construct_command(game, PLAYER, T.cmm, XYCoord(6, 6))
    (row,) = constr_status_rows(game, PLAYER)

    assert row.con_id == report.con_id
    assert row.kind is T.cmm
    assert row.completion_year == game.Year + YearsToBuild[T.cmm]


def test_the_shortfall_is_the_whole_requirement_with_nothing_delivered(game):
    construct_command(game, PLAYER, T.cmm, XYCoord(6, 6))
    (row,) = constr_status_rows(game, PLAYER)

    assert row.shortfall == [
        (material, ConsCargoNeeded[T.cmm][material]) for material in CONSTR_MATERIALS
    ]


def test_cargo_on_a_fleet_over_the_site_counts_against_the_shortfall(game):
    """Only fleets *parked on the site* supply it -- that is the mechanic the
    table exists to make legible."""
    from recreon.fleet import get_next_fleet, move_fleet

    xy = XYCoord(6, 6)
    construct_command(game, PLAYER, T.cmm, xy)

    flt = get_next_fleet(game, PLAYER)
    move_fleet(game, flt, xy)
    cargo = {material: 0 for material in CONSTR_MATERIALS}
    put_cargo(game, flt, {**game.Universe.Fleet[flt.Index].Cargo, T.met: 1000})

    (row,) = constr_status_rows(game, PLAYER)
    needed = dict(row.shortfall)

    assert needed[T.met] == max(0, ConsCargoNeeded[T.cmm][T.met] - 1000)
    assert needed[T.che] == ConsCargoNeeded[T.cmm][T.che]


def test_a_surplus_shows_as_zero_not_a_negative(game):
    from recreon.fleet import get_next_fleet, move_fleet

    xy = XYCoord(6, 6)
    construct_command(game, PLAYER, T.out, xy)

    flt = get_next_fleet(game, PLAYER)
    move_fleet(game, flt, xy)
    put_cargo(
        game,
        flt,
        {**game.Universe.Fleet[flt.Index].Cargo, T.met: 60000, T.che: 60000, T.tri: 60000},
    )

    (row,) = constr_status_rows(game, PLAYER)
    assert all(amount == 0 for _, amount in row.shortfall)


def test_another_empires_fleet_does_not_supply_your_site(game):
    from recreon.fleet import get_next_fleet, move_fleet

    xy = XYCoord(6, 6)
    construct_command(game, PLAYER, T.cmm, xy)

    theirs = get_next_fleet(game, Empire.Empire2)
    move_fleet(game, theirs, xy)
    put_cargo(
        game, theirs, {**game.Universe.Fleet[theirs.Index].Cargo, T.met: 5000}
    )

    (row,) = constr_status_rows(game, PLAYER)
    assert dict(row.shortfall)[T.met] == ConsCargoNeeded[T.cmm][T.met]


def test_the_status_line_keeps_the_originals_columns(game):
    construct_command(game, PLAYER, T.cmm, XYCoord(6, 6))
    (row,) = constr_status_rows(game, PLAYER)
    line = row.as_line()

    # Site name is 10 wide, then the type through column 32, then the year.
    assert line[10:22].startswith("command base")
    assert str(row.completion_year) in line[32:47]


# --- Warp link frequency -----------------------------------------------------


def make_gate(game, xy, owner=Empire.Empire1):
    slot = next_stargate_slot(game)
    gate = IDNumber(ObjectTypes.Gate, slot)
    create_stargate(game, gate, owner, T.gte, xy)
    return gate


def test_only_known_stargates_are_listed(game):
    seen = make_gate(game, XYCoord(9, 9))
    make_gate(game, XYCoord(12, 12))

    game.Universe.Stargate[seen.Index].KnownBy.add(PLAYER)

    listed = warp_link_freq_list(game, PLAYER)
    assert [entry.obj.Index for entry in listed] == [seen.Index]


def test_another_empires_gate_is_listed_too(game):
    """The point of the command: matching their frequency is how you get to
    use their gate."""
    theirs = make_gate(game, XYCoord(9, 9), owner=Empire.Empire2)
    game.Universe.Stargate[theirs.Index].KnownBy.add(PLAYER)

    (entry,) = warp_link_freq_list(game, PLAYER)
    assert entry.owner is Empire.Empire2


def test_a_frequency_is_per_empire_per_gate(game):
    gate = make_gate(game, XYCoord(9, 9))

    set_warp_link_frequency(game, PLAYER, gate, 1234)
    set_warp_link_frequency(game, Empire.Empire2, gate, 4321)

    assert get_warp_link_freq(game, PLAYER, gate) == 1234
    assert get_warp_link_freq(game, Empire.Empire2, gate) == 4321


@pytest.mark.parametrize("bad", [-1, MAX_WARP_LINK_FREQ + 1])
def test_a_frequency_outside_the_range_is_refused(game, bad):
    gate = make_gate(game, XYCoord(9, 9))
    with pytest.raises(FrequencyError, match="between 0 and 9999"):
        set_warp_link_frequency(game, PLAYER, gate, bad)


@pytest.mark.parametrize("ok", [0, MAX_WARP_LINK_FREQ])
def test_the_bounds_themselves_are_allowed(game, ok):
    gate = make_gate(game, XYCoord(9, 9))
    set_warp_link_frequency(game, PLAYER, gate, ok)
    assert get_warp_link_freq(game, PLAYER, gate) == ok


def test_the_advice_depends_on_whose_gate_it_is(game):
    mine = make_gate(game, XYCoord(9, 9))
    theirs = make_gate(game, XYCoord(12, 12), owner=Empire.Empire2)

    assert "divulge" in " ".join(warp_link_advice(game, PLAYER, mine))
    assert "same frequency" in " ".join(warp_link_advice(game, PLAYER, theirs))
