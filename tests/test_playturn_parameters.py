"""PLAYTURN.PAS's parameter table, and the validation it drives.

The table is the original's single statement of what each command requires, so
a good half of these tests are transcription checks: does the row say what the
Pascal says. The rest exercise the checks themselves, which is where the
interesting behaviour is -- and where two original bugs live, both pinned here
so that "fixing" one shows up as a failure rather than as a silent divergence.
"""

import pytest

from recreon.display import interpret_obj, interpret_xy
from recreon.fleet import get_next_fleet, move_fleet
from recreon.galaxy import Location, XYCoord
from recreon.main import new_game
from recreon.playturn import (
    ERROR_TEXT,
    PARAMETER_DATA,
    QUESTIONS,
    SILENT_ERRORS,
    UNCHECKED_ERRORS,
    Command,
    Errors,
    Parameters,
    ParameterSession,
    ParameterTypes,
    error_message,
    trap_command_errors,
    validate_parameter,
)
from recreon.primintr import (
    add_name,
    get_capital,
    get_coord,
    object_name,
    put_defns,
    set_status,
)
from recreon.types import (
    NO_OF_FLEETS_PER_EMPIRE,
    Empire,
    IDNumber,
    ObjectTypes,
    TechnologyTypes,
    defns_array,
    empty_quadrant,
)
from recreon.utils.pascal import set_rand_seed

E = Errors
P = ParameterTypes
T = TechnologyTypes
PLAYER = Empire.Empire1


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


@pytest.fixture
def game():
    return new_game()


@pytest.fixture
def capital(game):
    return get_capital(game, PLAYER)


def name_of(game, obj):
    return object_name(game, PLAYER, obj)


# --- The table ---------------------------------------------------------------


def test_every_command_has_a_row():
    """The original's array is `ARRAY[AllCommands]`, so it cannot have a gap.

    The port's dict can, which is why there is an import-time guard -- this
    only re-states it where a reader will see it.
    """
    assert set(PARAMETER_DATA) == set(Command)


def test_no_command_takes_more_than_three_parameters():
    """`ParmData: ARRAY [1..3]` is the hard limit on the original's row."""
    assert max(len(p) for p in PARAMETER_DATA.values()) == 3


def test_deploying_a_fleet_is_the_only_three_parameter_command():
    three = [c for c, p in PARAMETER_DATA.items() if len(p) == 3]
    assert three == [Command.FLaunchCom]


def test_every_live_parameter_asks_a_real_question():
    """Question 0 is the table's padding, and no live parameter uses it."""
    for command, parameters in PARAMETER_DATA.items():
        for parameter in parameters:
            assert 1 <= parameter.Question < len(QUESTIONS), command
            assert parameter.prompt.endswith(" "), command


def test_the_questions_are_the_originals_twenty_seven():
    assert len(QUESTIONS) - 1 == 27
    assert QUESTIONS[1] == "Which fleet shall we use to attack? "
    assert QUESTIONS[27] == "Where shall we begin construction? "


def test_deploy_asks_for_a_name_a_source_and_a_destination():
    """The one row worth reading out in full, because it is the only one that
    uses `IDParm2` -- the source world goes in `Obj2`, leaving `Obj1` free."""
    name, source, dest = PARAMETER_DATA[Command.FLaunchCom]

    assert (name.ParmTyp, name.Question) == (P.NewNameParm, 7)
    assert name.ErrorCond == frozenset({E.DupFltName})
    assert (source.ParmTyp, source.Question) == (P.IDParm2, 8)
    assert source.ErrorCond == frozenset({E.NotPartOfEmp, E.NotInUse})
    assert (dest.ParmTyp, dest.Question) == (P.XYParm, 9)
    assert dest.ErrorCond == frozenset()


def test_terraform_is_the_most_demanding_command():
    """Four separate things must be true of the world, plus the usual three."""
    (parameter,) = PARAMETER_DATA[Command.TerraCom]
    assert parameter.ErrorCond == frozenset(
        {
            E.NotPartOfEmp,
            E.NotInUse,
            E.NotAWorld,
            E.TerTech,
            E.TerCap,
            E.TerWrongCls,
            E.TerNotWarp,
        }
    )


def test_attack_and_auto_attack_ask_exactly_the_same_thing():
    """Two rows, identical down to the question number. The difference between
    the commands is who picks the targets, not what they need."""
    assert PARAMETER_DATA[Command.AttackCom] == PARAMETER_DATA[
        Command.AutoAttackCom
    ]


def test_info_com_is_the_close_up_screen():
    """The enum's comment says `{ INFO }` and the table's says `{ Close Up }`.
    The question settles which one the command actually is."""
    (parameter,) = PARAMETER_DATA[Command.InfoCom]
    assert parameter.prompt == "Close up on which world? "


def test_the_commands_that_ask_nothing():
    """Every command whose whole screen collects its own input. Worth pinning:
    a row gaining a parameter would be a real change to the command."""
    silent = {c for c, p in PARAMETER_DATA.items() if not p}
    assert silent == {
        Command.NullCom,
        Command.ErrorCom,
        Command.EndCom,
        Command.ShellCom,
        Command.AboutCom,
        Command.MReadCom,
        Command.MSendCom,
        Command.HrdCopyCom,
        Command.STechCom,
        Command.ConStaCom,
        Command.SelfDestCom,
        Command.DefnsCom,
        Command.HoloCom,
        Command.PauseCom,
        Command.ArtfctCom,
        Command.WarpLinkFreqCom,
        Command.XXXCom,
    }


# --- The error texts ---------------------------------------------------------


def test_every_error_a_command_can_raise_has_something_to_say():
    """Bar the ones that are deliberately silent or deliberately unchecked."""
    requested = {
        error
        for parameters in PARAMETER_DATA.values()
        for parameter in parameters
        for error in parameter.ErrorCond
    }
    for error in requested - UNCHECKED_ERRORS:
        assert ERROR_TEXT.get(error), error


def test_no_obj_is_silent_because_the_interpreter_already_spoke(game):
    """`InterpretObj` writes its own message and PLAYTURN maps it to `NoObj`,
    which has no line in `WriteError`'s case. Both halves are needed."""
    assert E.NoObj in SILENT_ERRORS
    assert error_message(game, PLAYER, E.NoObj, "nowhere") == ""

    _, message = interpret_obj(game, PLAYER, "nowhere")
    assert message.startswith("There is no object at that location, ")


def test_an_error_line_substitutes_the_ruler_then_the_parameter(game):
    line = error_message(game, PLAYER, E.NotAFlt, "Home")
    assert line.startswith("Home is not a fleet, ")
    assert "@" not in line and "*" not in line


def test_not_part_of_emp_appends_the_empire_name(game):
    """The one message built by concatenation rather than substitution."""
    line = error_message(game, PLAYER, E.NotPartOfEmp, "Home")
    assert line.endswith(game.Universe.EmpireData[PLAYER].EmpireName)


def test_a_message_starting_with_the_ruler_is_not_recapitalised(game):
    """`CapDes` is '@ is surely joking!' -- the original substitutes and writes,
    with no fix-up, so the line opens with whatever `MyLord` returned."""
    line = error_message(game, PLAYER, E.CapDes, "Home")
    assert " is surely joking!  Home is your capital!" in line


# --- Interpreting an answer --------------------------------------------------


def test_a_coordinate_resolves_to_the_object_standing_on_it(game, capital):
    result = Parameters()
    error, _ = validate_parameter(
        game,
        PLAYER,
        PARAMETER_DATA[Command.ProbeCom][0],
        name_of(game, capital),
        result,
    )

    assert error == E.NoError
    assert result.Coord == get_coord(game, capital)


def test_an_unresolvable_coordinate_is_undefined(game):
    result = Parameters()
    error, message = validate_parameter(
        game, PLAYER, PARAMETER_DATA[Command.ProbeCom][0], "wherever", result
    )

    assert error == E.UndefCoord
    assert message.startswith("Those coordinates are undefined")


@pytest.mark.parametrize(
    "name,expected",
    [
        ("", E.IllName),
        ("Home,2", E.IllName),
        ("Muchtoolonganame", E.NameTooLong),
        ("Home", E.NoError),
        ("Exactly8", E.NoError),
    ],
)
def test_a_new_name_is_eight_characters_and_holds_no_comma(game, name, expected):
    """The comma is barred because the order compiler stores names in a
    comma-separated line; one inside a name would split it in two."""
    result = Parameters()
    error, _ = validate_parameter(
        game, PLAYER, PARAMETER_DATA[Command.NAddCom][1], name, result
    )
    assert error == expected


def test_deleting_a_name_requires_the_name_to_exist(game, capital):
    result = Parameters()
    parameter = PARAMETER_DATA[Command.NDelCom][0]

    error, message = validate_parameter(game, PLAYER, parameter, "Home", result)
    assert error == E.NotName
    assert message.startswith('I have not heard of "Home"')

    add_name(game, PLAYER, Location(get_coord(game, capital), capital), "Home")
    assert validate_parameter(game, PLAYER, parameter, "Home", result)[0] == (
        E.NoError
    )


def test_a_name_is_matched_without_regard_to_case(game, capital):
    add_name(game, PLAYER, Location(get_coord(game, capital), capital), "Home")
    result = Parameters()
    error, _ = validate_parameter(
        game, PLAYER, PARAMETER_DATA[Command.NDelCom][0], "HOME", result
    )
    assert error == E.NoError


# --- Checking an object ------------------------------------------------------


def test_a_world_is_not_a_fleet(game, capital):
    result = Parameters()
    error, message = validate_parameter(
        game,
        PLAYER,
        PARAMETER_DATA[Command.FTransCom][0],
        name_of(game, capital),
        result,
    )

    assert error == E.NotAFlt
    assert "is not a fleet" in message


def test_designating_your_own_capital_is_refused(game, capital):
    result = Parameters()
    error, message = validate_parameter(
        game,
        PLAYER,
        PARAMETER_DATA[Command.DesignateCom][0],
        name_of(game, capital),
        result,
    )

    assert error == E.CapDes
    assert "is your capital" in message


def test_a_world_you_do_not_own_is_not_part_of_your_empire(game, capital):
    """`NotPartOfEmp` is checked after the type checks, so a foreign *world*
    reaches it while a foreign fleet would have failed `NotAFlt` first."""
    set_status(game, capital, Empire.Empire2)
    result = Parameters()
    error, _ = validate_parameter(
        game,
        PLAYER,
        PARAMETER_DATA[Command.ProdInfoCom][0],
        name_of(game, capital),
        result,
    )
    assert error == E.NotPartOfEmp


def test_launching_lams_needs_lams(game, capital):
    result = Parameters()
    parameter = PARAMETER_DATA[Command.LAMCom][0]

    defns = defns_array()
    put_defns(game, capital, defns)
    error, message = validate_parameter(
        game, PLAYER, parameter, name_of(game, capital), result
    )
    assert error == E.NoLAMs
    assert "There are no LAMs at" in message

    defns[T.LAM] = 5
    put_defns(game, capital, defns)
    assert validate_parameter(
        game, PLAYER, parameter, name_of(game, capital), result
    )[0] == E.NoError


def test_terraforming_needs_the_technology(game, capital):
    """A new empire has no `ter`, so this is the first thing terraform hits --
    and it is checked before the world's own suitability."""
    result = Parameters()
    error, message = validate_parameter(
        game,
        PLAYER,
        PARAMETER_DATA[Command.TerraCom][0],
        name_of(game, capital),
        result,
    )

    assert error == E.TerTech
    assert "not yet developed Terraforming" in message


def test_the_first_failing_check_wins(game, capital):
    """`CheckForObjectErrors` exits on the first error, so the order of the
    blocks is behaviour. Designate lists both `NotAWorld` and `CapDes`; the
    capital is a world, so the one that fires is the later `CapDes`."""
    result = Parameters()
    error, _ = validate_parameter(
        game,
        PLAYER,
        PARAMETER_DATA[Command.DesignateCom][0],
        name_of(game, capital),
        result,
    )
    assert error == E.CapDes


def test_a_starbase_counts_as_a_world(game):
    """`NotAWorld` accepts `[Pln,Base]`. Command bases are designatable and
    carry an industry, which is what the callers actually want to know."""
    from recreon.playturn import _check_object

    base = IDNumber(ObjectTypes.Base, 1)
    assert _check_object(game, PLAYER, base, frozenset({E.NotAWorld})) == (
        E.NoError
    )


# --- The two original bugs ---------------------------------------------------


def test_the_not_known_check_lets_a_stood_down_fleet_through(game, capital):
    """Original bug #75. The guard reads

        (Obj.ObjTyp = Flt) AND (NOT Obj.Index IN SetOfActiveFleets)

    which Turbo Pascal parses as `(NOT Obj.Index) IN ...` -- NOT binds tighter
    than IN -- so it is always false. Close-up is the only command that asks
    for `NotKnown`, and it therefore accepts a fleet that is no longer in
    space, so long as the stale record is still marked known.

    Do not "fix" this by adding the disjunct: that is a behaviour change, not
    a transcription repair.
    """
    from recreon.playturn import _check_object

    flt = get_next_fleet(game, PLAYER)
    move_fleet(game, flt, get_coord(game, capital))
    record = game.Universe.Fleet[flt.Index]
    record.KnownBy.add(PLAYER)

    game.GlobalSets.SetOfActiveFleets.discard(flt.Index)

    assert flt.Index not in game.GlobalSets.SetOfActiveFleets
    assert _check_object(game, PLAYER, flt, frozenset({E.NotKnown})) == E.NoError


def test_refuel_asks_for_a_check_that_does_not_exist():
    """Original bug #74. `FFuelCom` declares `NoTri` and `CheckForObjectErrors`
    has no branch for it, so it never runs -- masked in practice by the
    `NoPlaceToRef` check beside it."""
    (parameter,) = PARAMETER_DATA[Command.FFuelCom]

    assert E.NoTri in parameter.ErrorCond
    assert E.NoTri in UNCHECKED_ERRORS


def test_the_unchecked_errors_are_exactly_the_seven_with_no_branch():
    assert UNCHECKED_ERRORS == frozenset(
        {
            E.NoTri,
            E.NotEnoughTech,
            E.NoLAMTargets,
            E.NameNotInUse,
            E.NoFltAtSite,
            E.NoRoomToBuild,
            E.EmptQuad,
        }
    )


def test_only_no_tri_is_both_unchecked_and_requested():
    """The other six are reserved codes no command asks for, which is why #74
    is one issue rather than seven."""
    requested = {
        error
        for parameters in PARAMETER_DATA.values()
        for parameter in parameters
        for error in parameter.ErrorCond
    }
    assert requested & UNCHECKED_ERRORS == {E.NoTri}


# --- The session -------------------------------------------------------------


def test_a_command_with_no_parameters_is_done_before_it_starts(game):
    session = ParameterSession(game, PLAYER, Command.ConStaCom)

    assert session.done
    assert session.question() == ""


def test_the_session_asks_each_question_in_turn(game, capital):
    session = ParameterSession(game, PLAYER, Command.FLaunchCom)
    asked = []

    for answer in ("Home", name_of(game, capital), name_of(game, capital)):
        asked.append(session.question())
        assert session.answer(answer) == E.NoError

    assert asked == [
        "What name shall we use for this fleet? ",
        "Where shall we deploy the fleet from? ",
        "What shall its destination be? ",
    ]
    assert session.done
    assert session.result.NewName == "Home"
    assert session.result.Obj2 == capital
    assert session.result.Coord == get_coord(game, capital)


def test_a_rejected_answer_leaves_the_question_standing(game):
    session = ParameterSession(game, PLAYER, Command.DesignateCom)
    question = session.question()

    assert session.answer("nowhere") == E.NoObj
    assert session.question() == question
    assert not session.done
    assert session.message


def test_an_empty_answer_cancels_the_whole_command(game, capital):
    """Escape at the second prompt drops the first answer too. The original
    sets `Comm := NullCom` and jumps clear of the loop; there is no going back
    one question."""
    session = ParameterSession(game, PLAYER, Command.FLaunchCom)
    session.answer("Home")
    assert not session.done

    session.answer("")

    assert session.cancelled
    assert session.done
    assert session.question() == ""


def test_answering_a_finished_session_does_nothing(game):
    session = ParameterSession(game, PLAYER, Command.ConStaCom)
    assert session.answer("anything") == E.NoError
    assert session.result == Parameters()


# --- Trapping a command before it starts -------------------------------------


def test_most_commands_have_nothing_to_trap(game):
    for command in Command:
        if command != Command.FLaunchCom:
            assert trap_command_errors(game, PLAYER, command) == ""


def test_an_empire_may_have_thirty_fleets_in_space(game):
    """`TrapCommandErrors`'s only case, and the one guard on the player's side
    of the fleet cap -- the AI honours the same limit in its launch routines."""
    assert trap_command_errors(game, PLAYER, Command.FLaunchCom) == ""

    game.GlobalSets.SetOfFleetsOf[PLAYER] |= set(
        range(1, NO_OF_FLEETS_PER_EMPIRE + 1)
    )
    game.GlobalSets.SetOfActiveFleets |= set(
        range(1, NO_OF_FLEETS_PER_EMPIRE + 1)
    )

    refusal = trap_command_errors(game, PLAYER, Command.FLaunchCom)
    assert "too many fleets in space already" in refusal


def test_the_cap_counts_only_this_empires_fleets(game):
    """`SetOfFleetsOf[Player]`, not `SetOfActiveFleets` -- a galaxy full of
    other empires' fleets does not stop you launching."""
    game.GlobalSets.SetOfFleetsOf[Empire.Empire2] |= set(range(1, 60))
    game.GlobalSets.SetOfActiveFleets |= set(range(1, 60))

    assert trap_command_errors(game, PLAYER, Command.FLaunchCom) == ""


# --- DISPLAY.PAS's two parsers -----------------------------------------------


def test_interpreting_an_object_that_is_not_there(game):
    obj, message = interpret_obj(game, PLAYER, "nowhere")

    assert obj == empty_quadrant()
    # How the message addresses the ruler is a draw from the generator, so
    # only the fixed half of the line can be asserted. See `my_lord`.
    assert message.startswith("There is no object at that location, ")


def test_interpreting_a_destroyed_starbase(game, capital):
    """A name outlives the thing it named, so this is what notices. The message
    capitalises the parameter, because the original upper-cases `Parm[1]`
    before writing it -- and after the lookup, so it does not affect matching.
    """
    base = IDNumber(ObjectTypes.Base, 1)
    game.GlobalSets.SetOfActiveStarbases.add(1)
    game.Universe.Starbase[1].XY = get_coord(game, capital)
    add_name(game, PLAYER, Location(XYCoord(0, 0), base), "outpost")

    obj, message = interpret_obj(game, PLAYER, "outpost")
    assert obj == base
    assert message == ""

    game.GlobalSets.SetOfActiveStarbases.discard(1)
    obj, message = interpret_obj(game, PLAYER, "outpost")

    assert obj == empty_quadrant()
    assert message == "Outpost has been destroyed."


def test_interpret_xy_speaks_where_interpret_coord_returns_a_code(game):
    """The same resolution twice over, split because the map screens have
    nowhere to put an error code and the parameter table has nowhere to put a
    message."""
    xy, message = interpret_xy(game, PLAYER, "wherever")

    assert xy == XYCoord(0, 0)
    assert message.startswith('"wherever" are undefined coordinates')
