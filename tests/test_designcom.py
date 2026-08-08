"""World and empire commands, ported from DESIGN.PAS.

The *mechanics* -- `designate_world`, `terraform_world`, `change_issp` -- are
`test_design.py`. This is the seven commands a player drives them with.
"""

import pytest
from conftest import blank_game, place_world

from recreon.datacnst import TechDev, TerraformPotentialClasses
from recreon.designcom import (
    ISSP_INDUSTRIES,
    UNDESIGNATABLE,
    ClassN,
    designate_command,
    designation_options,
    designation_warnings,
    grant_independence_command,
    inbox,
    independence_recipients,
    issp_settings,
    lam_targets,
    launch_lam,
    message_recipients,
    read_message,
    sell_technology,
    send_message_command,
    set_issp_settings,
    technology_recipients,
    terraform_command,
    terraform_options,
    tradeable_technologies,
)
from recreon.fleet import get_next_fleet, move_fleet
from recreon.galaxy import XYCoord
from recreon.intrface import create_starbase
from recreon.news import NewsTypes
from recreon.primintr import (
    get_defns,
    get_issp,
    get_status,
    get_type,
    put_defns,
    put_ships,
    set_tech,
)
from recreon.types import (
    Empire,
    IDNumber,
    IndusTypes,
    ObjectTypes,
    TechLevel,
    TechnologyTypes,
    WorldClass,
    WorldTypes,
    ship_array,
)
from recreon.utils.pascal import set_rand_seed

T = TechnologyTypes
IT = IndusTypes
P = Empire.Empire1
HOME = XYCoord(5, 5)


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


@pytest.fixture
def game():
    g = blank_game(size=20, empires=3)
    home = place_world(g, 1, HOME, emp=P)
    g.Universe.EmpireData[P].Capital = home
    return g


@pytest.fixture
def home():
    return IDNumber(ObjectTypes.Pln, 1)


# --- Designate ---------------------------------------------------------------


def test_the_starbase_variants_are_never_offered(game, home):
    offered = {typ for typ, _, _ in designation_options(game, home)}
    assert not (offered & UNDESIGNATABLE)


def test_designations_need_the_worlds_technology(game, home):
    set_tech(game, home, TechLevel.PrimitLvl)
    primitive = {typ for typ, _, _ in designation_options(game, home)}

    set_tech(game, home, TechLevel.GteTchLvl)
    advanced = {typ for typ, _, _ in designation_options(game, home)}

    assert primitive < advanced


def test_ambrosia_needs_an_ambrosia_or_paradise_class(game, home):
    """The class gate only matters once the tech gate is passed: AmbTyp needs
    bio-tech, so a warp-era world is excluded whatever its class."""
    set_tech(game, home, TechLevel.BioTchLvl)

    game.Universe.Planet[1].Cls = WorldClass.EthCls
    assert WorldTypes.AmbTyp not in {t for t, _, _ in designation_options(game, home)}

    game.Universe.Planet[1].Cls = WorldClass.ParCls
    assert WorldTypes.AmbTyp in {t for t, _, _ in designation_options(game, home)}


def test_research_and_raw_worlds_get_prose_not_an_industry(game, home):
    set_tech(game, home, TechLevel.GteTchLvl)
    labels = {typ: industry for typ, _, industry in designation_options(game, home)}

    assert labels.get(WorldTypes.RsrTyp) == "(research)"
    assert labels.get(WorldTypes.CapTyp) == "administration"


# --- The five warnings -------------------------------------------------------


def test_changing_the_capital_warns(game, home):
    warnings = designation_warnings(game, P, home, WorldTypes.CapTyp)
    assert "changing the capital" in warnings[0]


def test_a_trivial_use_of_an_industrial_complex_warns(game):
    base = IDNumber(ObjectTypes.Base, 1)
    create_starbase(game, base, P, XYCoord(8, 8), T.cmp)

    warnings = designation_warnings(game, P, base, WorldTypes.AgrTyp)
    assert "wasted on such a trivial" in warnings[0]


def test_a_university_behind_the_capital_warns(game, home):
    place_world(game, 2, XYCoord(9, 9), emp=P, tech=TechLevel.GteTchLvl)
    game.Universe.EmpireData[P].Capital = IDNumber(ObjectTypes.Pln, 2)
    set_tech(game, home, TechLevel.WrpTchLvl)

    warnings = designation_warnings(game, P, home, WorldTypes.RsrTyp)
    assert "not yet as advanced as the capital" in warnings[0]


def test_mining_a_gas_giant_warns(game, home):
    game.Universe.Planet[1].Cls = WorldClass.GsGCls
    warnings = designation_warnings(game, P, home, WorldTypes.MinTyp)
    assert "not really suited to" in warnings[0]


def test_farming_an_ice_world_warns(game, home):
    game.Universe.Planet[1].Cls = WorldClass.IceCls
    warnings = designation_warnings(game, P, home, WorldTypes.AgrTyp)
    assert "would not be" in warnings[0]


def test_a_sensible_designation_warns_about_nothing(game, home):
    game.Universe.Planet[1].Cls = WorldClass.EthCls
    assert designation_warnings(game, P, home, WorldTypes.AgrTyp) == []


def test_only_the_first_matching_warning_fires(game, home):
    """The original's chain is ELSE IF, so a capital designation never also
    warns about the class."""
    game.Universe.Planet[1].Cls = WorldClass.IceCls
    warnings = designation_warnings(game, P, home, WorldTypes.CapTyp)

    assert "changing the capital" in warnings[0]
    assert not any("agricultural" in line for line in warnings)


def test_designating_redistributes_industry(game, home):
    lines = designate_command(game, P, home, WorldTypes.MinTyp)

    assert get_type(game, home) is WorldTypes.MinTyp
    assert "designated as" in lines[0]
    assert "re-distributed" in lines[1]


def test_redesignating_to_the_same_type_changes_nothing(game, home):
    """`designate_world` redistributes every industry, so re-confirming an
    existing designation would otherwise reset the world's efficiency."""
    from recreon.primintr import get_efficiency

    designate_command(game, P, home, WorldTypes.MinTyp)
    before = get_efficiency(game, home)

    designate_command(game, P, home, WorldTypes.MinTyp)
    assert get_efficiency(game, home) == before


# --- Terraform ---------------------------------------------------------------


def test_every_class_has_a_full_name():
    assert set(ClassN) == set(WorldClass)


def test_terraform_options_come_from_the_table(game, home):
    game.Universe.Planet[1].Cls = WorldClass.ClsJ
    offered = {cls for cls, _ in terraform_options(game, home)}

    expected = {
        c
        for c in TerraformPotentialClasses[WorldClass.ClsJ]
        if c is not None and c != WorldClass.ClsJ
    }
    assert offered == expected


def test_the_worlds_own_class_is_not_offered(game, home):
    """Which is also how the table's padding is filtered -- unused slots
    repeat the source class."""
    for cls in (WorldClass.ClsJ, WorldClass.EthCls, WorldClass.ArdCls):
        game.Universe.Planet[1].Cls = cls
        assert cls not in {c for c, _ in terraform_options(game, home)}


def test_an_artificial_world_cannot_be_terraformed(game, home):
    game.Universe.Planet[1].Cls = WorldClass.ArtCls
    assert terraform_options(game, home) == []


def test_terraforming_starts_the_work(game, home):
    game.Universe.Planet[1].Cls = WorldClass.ClsJ
    lines = terraform_command(game, P, home, WorldClass.EthCls)

    assert lines
    assert game.Universe.Planet[1].TerraformTarget is WorldClass.EthCls


# --- ISSP --------------------------------------------------------------------


def test_issp_covers_the_four_traded_industries():
    assert ISSP_INDUSTRIES == (IT.CheInd, IT.MinInd, IT.SupInd, IT.TriInd)


def test_issp_settings_round_trip(game, home):
    set_issp_settings(game, home, {IT.CheInd: 8, IT.TriInd: 2})
    settings = issp_settings(game, home)

    assert settings[IT.CheInd] == 8
    assert settings[IT.TriInd] == 2


# --- Liberate ----------------------------------------------------------------


def test_independence_is_always_on_offer(game, home):
    assert [emp for emp, _ in independence_recipients(game, P, home)] == [
        Empire.Indep
    ]


def test_only_an_empire_present_can_be_given_a_world(game, home):
    """You cannot gift a world to someone who is not there to take it."""
    theirs = get_next_fleet(game, Empire.Empire2)
    move_fleet(game, theirs, HOME)

    assert Empire.Empire2 not in [e for e, _ in independence_recipients(game, P, home)]

    game.Universe.Fleet[theirs.Index].ScoutedBy.add(P)
    assert Empire.Empire2 in [e for e, _ in independence_recipients(game, P, home)]


def test_liberating_makes_a_world_independent_and_industrial(game, home):
    message = grant_independence_command(game, P, home, Empire.Indep)

    assert get_status(game, home) is Empire.Indep
    assert get_type(game, home) is WorldTypes.IndTyp
    assert "now independent" in message


def test_giving_a_world_away_keeps_its_designation(game, home):
    designate_command(game, P, home, WorldTypes.MinTyp)

    message = grant_independence_command(game, P, home, Empire.Empire2)

    assert get_status(game, home) is Empire.Empire2
    assert get_type(game, home) is WorldTypes.MinTyp
    assert "part of the empire" in message
    assert any(
        item.Headline is NewsTypes.GInd for item in game.News[Empire.Empire2]
    )


def test_the_new_owner_inherits_no_trade_arrangements(game, home):
    set_issp_settings(game, home, {IT.CheInd: 9})
    grant_independence_command(game, P, home, Empire.Empire2)

    assert get_issp(game, home, IT.CheInd) != 9


# --- Trade technology --------------------------------------------------------


def test_only_the_recipients_own_tier_can_be_given(game):
    other = Empire.Empire2
    game.Universe.EmpireData[other].TechnologyLevel = TechLevel.WrpTchLvl
    game.Universe.EmpireData[other].Technology = set(TechDev[TechLevel.PreWrpLvl])

    offered = tradeable_technologies(game, P, other)
    tier = set(TechDev[TechLevel.WrpTchLvl]) - set(TechDev[TechLevel.PreWrpLvl])

    assert offered
    assert offered <= tier


def test_you_cannot_advance_anyone_a_level(game):
    other = Empire.Empire2
    game.Universe.EmpireData[other].TechnologyLevel = TechLevel.PreWrpLvl
    game.Universe.EmpireData[other].Technology = set(TechDev[TechLevel.PreWrpLvl])

    offered = tradeable_technologies(game, P, other)
    above = set(TechDev[TechLevel.GteTchLvl]) - set(TechDev[TechLevel.PreWrpLvl])

    assert not (offered & above)


def test_the_offer_does_not_check_what_they_already_have(game):
    """The intersection is with what the *player* holds, not with what the
    other empire lacks -- so two empires at the same level are always offered
    each other's whole tier. Reproduced."""
    other = Empire.Empire2
    assert (
        game.Universe.EmpireData[other].Technology
        == game.Universe.EmpireData[P].Technology
    )
    assert tradeable_technologies(game, P, other)


def test_transferring_grows_the_set_but_not_the_level(game):
    other = Empire.Empire2
    game.Universe.EmpireData[other].TechnologyLevel = TechLevel.WrpTchLvl
    game.Universe.EmpireData[other].Technology = set(TechDev[TechLevel.PreWrpLvl])
    gift = next(iter(tradeable_technologies(game, P, other)))

    message = sell_technology(game, P, other, gift)

    assert gift in game.Universe.EmpireData[other].Technology
    assert game.Universe.EmpireData[other].TechnologyLevel is TechLevel.WrpTchLvl
    assert "Transfer of" in message
    assert any(
        item.Headline is NewsTypes.NSellTech for item in game.News[other]
    )


def test_recipients_are_active_empires_other_than_you(game):
    offered = [emp for emp, _ in technology_recipients(game, P)]
    assert P not in offered
    assert Empire.Empire2 in offered


# --- Messages ----------------------------------------------------------------


def test_you_may_address_a_message_to_yourself(game):
    """`GetEmpires` applies no filter, and `send_message` never intercepts a
    message addressed only to its sender."""
    assert P in [emp for emp, _ in message_recipients(game)]


def test_sending_puts_it_in_their_inbox(game):
    send_message_command(game, P, {Empire.Empire2}, ["Header", "Body"])

    theirs = inbox(game, Empire.Empire2)
    assert len(theirs) == 1
    assert theirs[0].Sender is P


def test_reading_marks_it_read_once_everyone_has(game):
    send_message_command(game, P, {Empire.Empire2, Empire.Empire3}, ["Hi"])
    message = inbox(game, Empire.Empire2)[0]

    read_message(game, Empire.Empire2, message)
    assert not message.Read

    read_message(game, Empire.Empire3, message)
    assert message.Read


# --- LAMs --------------------------------------------------------------------


def a_base(game, xy, emp=P, styp=T.cmm, index=1, lams=500):
    base = IDNumber(ObjectTypes.Base, index)
    create_starbase(game, base, emp, xy, styp)
    stock = get_defns(game, base)
    stock[T.LAM] = lams
    put_defns(game, base, stock)
    return base


def test_lams_reach_five_sectors(game):
    base = a_base(game, XYCoord(5, 5))
    near = place_world(game, 2, XYCoord(9, 9), emp=Empire.Empire2)
    far = place_world(game, 3, XYCoord(15, 15), emp=Empire.Empire2)
    for world in (near, far):
        game.Universe.Planet[world.Index].KnownBy.add(P)

    reachable = [obj for obj, _ in lam_targets(game, P, base)]

    assert near in reachable
    assert far not in reachable


def test_an_unknown_target_is_not_offered(game):
    base = a_base(game, XYCoord(5, 5))
    place_world(game, 2, XYCoord(6, 6), emp=Empire.Empire2)

    assert lam_targets(game, P, base) == []


def test_knowing_is_enough_scouting_is_not_required(game):
    """A fleet you know is there but cannot see the composition of is still a
    legitimate target."""
    base = a_base(game, XYCoord(5, 5))
    theirs = get_next_fleet(game, Empire.Empire2)
    move_fleet(game, theirs, XYCoord(6, 6))
    game.Universe.Fleet[theirs.Index].KnownBy.add(P)

    assert theirs in [obj for obj, _ in lam_targets(game, P, base)]


def test_your_own_things_are_not_targets(game):
    base = a_base(game, XYCoord(5, 5))
    mine = place_world(game, 2, XYCoord(6, 6), emp=P)
    game.Universe.Planet[mine.Index].KnownBy.add(P)

    assert mine not in [obj for obj, _ in lam_targets(game, P, base)]


def test_launching_spends_the_missiles(game):
    base = a_base(game, XYCoord(5, 5), lams=500)
    theirs = get_next_fleet(game, Empire.Empire2)
    move_fleet(game, theirs, XYCoord(6, 6))
    ships = ship_array()
    ships[T.fgt] = 200
    put_ships(game, theirs, ships)

    launch_lam(game, P, base, theirs, 100)

    assert get_defns(game, base)[T.LAM] == 400


def test_you_cannot_launch_more_than_you_have(game):
    base = a_base(game, XYCoord(5, 5), lams=50)
    theirs = get_next_fleet(game, Empire.Empire2)
    move_fleet(game, theirs, XYCoord(6, 6))
    put_ships(game, theirs, ship_array())

    launch_lam(game, P, base, theirs, 9999)

    assert get_defns(game, base)[T.LAM] == 0


def test_launching_nothing_does_nothing(game):
    base = a_base(game, XYCoord(5, 5), lams=50)
    theirs = get_next_fleet(game, Empire.Empire2)
    move_fleet(game, theirs, XYCoord(6, 6))

    result = launch_lam(game, P, base, theirs, 0)

    assert not result.hit_anything
    assert get_defns(game, base)[T.LAM] == 50
