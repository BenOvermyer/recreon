"""Compiling, storing and reading back fleet standing orders."""

import pytest
from conftest import blank_game, place_world

from recreon.galaxy import XYCoord
from recreon.orders import (
    BAD_COMMAND_OER,
    BAD_DEST_OER,
    BAD_TRANSFER_OER,
    NO_OER,
    CommandRecord,
    CommandTypes,
    ResourceName,
    add_orders,
    compile_orders,
    decompile_orders,
    dispose_orders,
    get_command_record,
    initialize_orders,
    number_of_commands,
    split_line,
)
from recreon.primintr import add_name
from recreon.types import Empire, TechnologyTypes, tech_range

T = TechnologyTypes


@pytest.fixture
def game():
    """One empire with a capital, so relative coordinates resolve."""
    g = blank_game(size=20)
    world = place_world(g, 1, XYCoord(10, 10), emp=Empire.Empire1)
    g.Universe.EmpireData[Empire.Empire1].Capital = world
    return g


def compile_text(game, lines):
    code = initialize_orders()
    error, line_no = compile_orders(game, Empire.Empire1, lines, code)
    return code, error, line_no


# --- The mnemonic table ------------------------------------------------------


def test_resource_name_spans_ships_and_cargo():
    assert set(ResourceName) == set(tech_range(T.fgt, T.tri))


def test_starships_are_spelled_str_not_ssp():
    """The enum member is ``ssp`` but players type STR; the table is
    transcribed rather than derived from member names."""
    assert ResourceName[T.ssp] == "STR"


# --- Tokenising --------------------------------------------------------------


def test_split_line_pads_to_four_parameters():
    assert split_line("DEST 1,1") == ["DEST", "1,1", "", ""]


def test_split_line_runs_overflow_into_the_fourth_parameter():
    """Past the fourth the original stops advancing and keeps appending, so
    the extra words arrive concatenated with no separator."""
    assert split_line("A B C D E")[3] == "DE"


def test_split_line_collapses_runs_of_blanks():
    assert split_line("TRAN   100   MET") == ["TRAN", "100", "MET", ""]


# --- Parsing -----------------------------------------------------------------


def test_only_the_first_four_characters_of_a_verb_matter(game):
    code, error, _ = compile_text(game, ["DESTination 0,0", "REPEat"])
    assert error == NO_OER
    assert [c.Typ for c in code] == [CommandTypes.DestCOM, CommandTypes.RepeatCOM]


def test_transfer_compiles_count_and_resource(game):
    code, error, _ = compile_text(game, ["TRAN 100 MET"])
    assert error == NO_OER
    assert code[0].Typ == CommandTypes.TransCOM
    assert code[0].Res == T.met
    assert code[0].Trns == 100


def test_negative_transfer_means_drop_off(game):
    code, _, _ = compile_text(game, ["TRAN -250 SUP"])
    assert code[0].Trns == -250


def test_resource_names_are_truncated_to_three_characters(game):
    code, _, _ = compile_text(game, ["TRAN 5 METALS"])
    assert code[0].Res == T.met


def test_blank_lines_compile_to_nothing(game):
    code, error, _ = compile_text(game, ["", "   ", "WAIT"])
    assert error == NO_OER
    assert number_of_commands(code) == 1


def test_unknown_verb_is_an_error(game):
    code, error, line_no = compile_text(game, ["WAIT", "FROBNICATE"])
    assert error == BAD_COMMAND_OER
    assert line_no == 2


def test_unparseable_transfer_count_is_an_error(game):
    _, error, _ = compile_text(game, ["TRAN lots MET"])
    assert error == BAD_TRANSFER_OER


def test_destination_that_names_nothing_is_an_error(game):
    _, error, _ = compile_text(game, ["DEST nowhere"])
    assert error == BAD_DEST_OER


def test_compilation_stops_at_the_first_bad_line(game):
    code, error, line_no = compile_text(game, ["WAIT", "NONSENSE", "REPE"])
    assert error != NO_OER
    assert line_no == 2
    assert number_of_commands(code) == 1


# --- Destinations ------------------------------------------------------------


def test_destination_resolves_relative_to_the_capital(game):
    """0,0 is the player's own capital, at absolute (10, 10)."""
    code, _, _ = compile_text(game, ["DEST 0,0"])
    assert code[0].Loc.ID.Index == 1


def test_destination_y_axis_is_inverted(game):
    """Relative +1 in Y is one row *up* the grid, so absolute Y decreases."""
    code, _, _ = compile_text(game, ["DEST 2,1"])
    assert (code[0].Loc.XY.x, code[0].Loc.XY.y) == (12, 9)


def test_destination_outside_the_galaxy_is_an_error(game):
    _, error, _ = compile_text(game, ["DEST 500,500"])
    assert error == BAD_DEST_OER


def test_destination_can_be_a_name_the_empire_defined(game):
    from recreon.galaxy import Location, limbo
    from recreon.types import IDNumber, ObjectTypes

    target = Location(limbo(), IDNumber(ObjectTypes.Pln, 1))
    add_name(game, Empire.Empire1, target, "Homeworld")

    code, error, _ = compile_text(game, ["DEST Homeworld"])
    assert error == NO_OER
    assert code[0].Loc.ID.Index == 1


# --- Storage -----------------------------------------------------------------


def test_commands_are_numbered_from_one():
    code = initialize_orders()
    add_orders(code, CommandRecord(Typ=CommandTypes.WaitCOM))
    add_orders(code, CommandRecord(Typ=CommandTypes.RepeatCOM))

    assert get_command_record(code, 1).Typ == CommandTypes.WaitCOM
    assert get_command_record(code, 2).Typ == CommandTypes.RepeatCOM


def test_dispose_empties_the_list_in_place():
    """Callers keep their reference and expect to see it cleared, because the
    original frees the block the structure points at."""
    code = initialize_orders()
    add_orders(code, CommandRecord(Typ=CommandTypes.WaitCOM))
    alias = code

    dispose_orders(code)
    assert number_of_commands(alias) == 0


# --- Round trip --------------------------------------------------------------


def test_decompiled_orders_recompile_to_the_same_code(game):
    text = ["DESTination 3,-2", "TRANsfer 400 CHE", "SRMSweep", "REPEat", "WAIT"]
    code, error, _ = compile_text(game, text)
    assert error == NO_OER

    assert decompile_orders(game, Empire.Empire1, code) == text

    again, error, _ = compile_text(game, decompile_orders(game, Empire.Empire1, code))
    assert error == NO_OER
    assert [c.Typ for c in again] == [c.Typ for c in code]
