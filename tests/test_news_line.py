"""Rendering news items into prose, ported from INTRFACE.PAS GetNewsLine."""

import pytest
from conftest import blank_game, place_world

from recreon.galaxy import Location, XYCoord
from recreon.intrface import get_news_line
from recreon.news import NewsRecord, NewsTypes
from recreon.types import (
    Empire,
    IDNumber,
    IndusTypes,
    ObjectTypes,
    TechLevel,
    TechnologyTypes,
    WorldTypes,
)
from recreon.utils.pascal import set_rand_seed

T = TechnologyTypes
N = NewsTypes
WT = WorldTypes

HOME_XY = XYCoord(4, 4)


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


@pytest.fixture
def game():
    g = blank_game(size=20, empires=3)
    g.Universe.EmpireData[Empire.Empire1].EmpireName = "Sarkhon"
    g.Universe.EmpireData[Empire.Empire2].EmpireName = "Kaldor"
    g.Universe.EmpireData[Empire.Empire3].EmpireName = "Drachma"

    home = place_world(g, 1, HOME_XY, emp=Empire.Empire1, typ=WT.CapTyp)
    g.Universe.EmpireData[Empire.Empire1].Capital = home
    return g


@pytest.fixture
def home():
    return IDNumber(ObjectTypes.Pln, 1)


def line(game, headline, loc=None, p1=0, p2=0, p3=0, player=Empire.Empire1):
    item = NewsRecord(headline, loc or Location(XYCoord(0, 0), IDNumber()), p1, p2, p3)
    return get_news_line(game, player, item)


def at_home(home):
    return Location(XYCoord(0, 0), home)


# --- Substitution -------------------------------------------------------------


def test_the_location_marker_is_replaced(game, home):
    text = line(game, N.ConsDone, at_home(home))

    assert "*" not in text
    assert text.startswith("Construction at ")
    assert text.endswith(" has been completed.")


def test_the_empire_marker_is_replaced(game, home):
    text = line(game, N.BattleL, at_home(home), p1=int(Empire.Empire3))

    assert "@" not in text
    assert "Drachma" in text
    assert "has been conquered by the empire of" in text


def test_a_named_world_is_used_when_the_player_has_named_it(game, home):
    from recreon.primintr import add_name

    add_name(game, Empire.Empire1, Location(XYCoord(0, 0), home), "Trantor")

    assert "Trantor" in line(game, N.NoFuel, at_home(home))


def test_an_unnamed_world_falls_back_to_coordinates(game, home):
    text = line(game, N.NoFuel, at_home(home))

    # Coordinates are capital-relative, and the capital reads as 0,0.
    assert "0,0" in text


# --- Death tolls --------------------------------------------------------------


def test_small_death_tolls_are_reported_in_millions(game, home):
    """Parm1 is in hundreds of millions, so 7 is 70 million."""
    assert "70 million" in line(game, N.Starv, at_home(home), p1=7)


def test_large_death_tolls_are_reported_in_billions(game, home):
    """At 100 and above the figure switches to billions at one decimal, and
    Pascal's `:4:1` width leaves a leading space that is transcribed as-is."""
    text = line(game, N.Starv, at_home(home), p1=150)

    assert " 1.5 billion" in text


def test_the_billions_boundary_is_at_a_hundred(game, home):
    assert "990 million" in line(game, N.Starv, at_home(home), p1=99)
    assert "billion" in line(game, N.Starv, at_home(home), p1=100)


# --- Tables -------------------------------------------------------------------


def test_a_shortage_names_the_material(game, home):
    text = line(game, N.DefLack, at_home(home), p1=int(T.met))

    assert "metals" in text
    assert text.endswith("to build defenses.")


def test_the_lack_headline_varies_its_verb(game, home):
    """Five phrasings, drawn at random so a long-running shortage does not
    read identically every year."""
    seen = set()
    for seed in range(1, 40):
        set_rand_seed(seed)
        seen.add(line(game, N.Lack, at_home(home), p1=int(T.tri)))

    assert len(seen) == 5
    assert all("trillum" in s for s in seen)


def test_destruction_details_name_the_thing(game, home):
    from recreon.datacnst import ThingNames

    text = line(game, N.DestDetail, at_home(home), p1=42, p2=int(T.fgt))

    assert text == f"   42 {ThingNames[T.fgt]} destroyed."


def test_industry_losses_name_the_industry(game, home):
    from recreon.datacnst import IndusNames

    text = line(game, N.IndDs, at_home(home), p1=3, p2=int(IndusTypes.MinInd))

    assert IndusNames[IndusTypes.MinInd] in text
    assert text.startswith("   3 ")


def test_technology_headlines_name_the_level(game, home):
    from recreon.datacnst import TechN

    text = line(game, N.NTech, at_home(home), p1=int(TechLevel.JmpTchLvl))

    assert TechN[TechLevel.JmpTchLvl] in text
    assert "advanced" in text


def test_a_regression_reads_differently_from_an_advance(game, home):
    up = line(game, N.NTech, at_home(home), p1=int(TechLevel.AtomicLvl))
    down = line(game, N.RTech, at_home(home), p1=int(TechLevel.AtomicLvl))

    assert "advanced" in up
    assert "regressed" in down


# --- Two-empire bulletins -----------------------------------------------------


def test_global_bulletins_name_both_empires(game, home):
    """The GLB* headlines carry the attacker in Parm1 and the victim in
    Parm2, so both names have to appear."""
    text = line(
        game,
        N.GLBConq,
        at_home(home),
        p1=int(Empire.Empire2),
        p2=int(Empire.Empire3),
    )

    assert "Kaldor" in text
    assert "Drachma" in text


def test_a_capital_falling_is_reported_without_a_location(game, home):
    text = line(
        game,
        N.GLBCapConq,
        at_home(home),
        p1=int(Empire.Empire2),
        p2=int(Empire.Empire3),
    )

    assert text == "Kaldor has attacked and conquered the Drachma capital."


# --- Coverage -----------------------------------------------------------------


@pytest.mark.parametrize(
    "headline",
    [h for h in NewsTypes if h != NewsTypes.NoNews],
)
def test_every_headline_renders_without_raising(game, home, headline):
    """Parm values are nonsense for most of these; what is being checked is
    that no headline blows up on a table lookup."""
    text = line(game, headline, at_home(home), p1=1, p2=1, p3=1)

    assert isinstance(text, str)
    assert "*" not in text and "@" not in text


UNHANDLED = {
    NewsTypes.GTech,
    NewsTypes.CLost,
    NewsTypes.LostP,
    NewsTypes.SMnR,
    NewsTypes.JumpDm,
    NewsTypes.JumpDs,
    NewsTypes.ELost,
    NewsTypes.TriAcc,
    NewsTypes.LostF,
}


def test_the_nine_vestigial_headlines_render_empty(game, home):
    """These are declared in NEWS.PAS, have no arm in GetNewsLine's CASE and
    no ELSE, and are never filed by anything. In the original they leave the
    caller's buffer untouched, so the previous line would show twice."""
    for headline in UNHANDLED:
        assert line(game, headline, at_home(home)) == ""


def test_every_other_headline_produces_prose(game, home):
    for headline in NewsTypes:
        if headline in UNHANDLED or headline == NewsTypes.NoNews:
            continue
        assert line(game, headline, at_home(home), p1=1, p2=1), headline.name


# --- Integration --------------------------------------------------------------


def test_a_real_game_feed_renders(scenario_path):
    """Every item a real game produces should come out as a readable line."""
    from recreon.main import update_turn
    from recreon.newgame import load_scenario
    from recreon.news import get_news_list
    from recreon.types import PLAYER_EMPIRES

    g = load_scenario(scenario_path, {Empire.Empire1: "A"})

    rendered = 0
    for _ in range(40):
        update_turn(g)
        for emp in PLAYER_EMPIRES:
            for item in get_news_list(g, emp):
                text = get_news_line(g, emp, item)
                assert "*" not in text and "@" not in text
                if text:
                    rendered += 1

    assert rendered > 0, "40 turns should have produced some news"
