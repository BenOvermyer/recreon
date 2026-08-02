"""Fleet standing orders: compiling, storing and reading back.

Port of ORDERS.PAS.

The original compiles order text into a heap block and type-puns the fleet's
six-byte ``OrderData`` field onto an ``OrderStructure`` (a length plus a
pointer into that block). Here an :class:`OrderStructure` is just a list of
:class:`CommandRecord`, so ``AddOrders``, ``DisposeOrders``, ``GetFleetCode``
and ``SetFleetCode`` reduce to ordinary list operations -- but they are kept
as named functions because FLEET.PAS calls them by name, and dropping them
would make that module stop reading like the original.

``AbortCOM`` survives as an enum member with no parser or executor: the
'ABOR' branch is commented out of ``ParseLine`` in v2.0, so no compiled order
can carry it, and ``ExecuteFleetOrders`` has no case for it either.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING

from .datacnst import _table
from .galaxy import Location, limbo
from .misc import same_id, same_xy
from .primintr import get_location
from .types import Empire, IDNumber, TechnologyTypes, empty_quadrant, tech_range
from .utils.pascal import pascal_val

if TYPE_CHECKING:
    from .environ import GameEnvironment

# --- Order errors ------------------------------------------------------------

NO_OER = 0
BAD_COMMAND_OER = 1
BAD_DEST_OER = 2
BAD_RESOURCE_OER = 3
BAD_TRANSFER_OER = 4


class CommandTypes(IntEnum):
    NoCOM = 0
    DestCOM = 1  # set new destination
    TransCOM = 2  # transfer
    RepeatCOM = 3  # repeat orders
    AbortCOM = 4  # abort the fleet
    SweepCOM = 5  # sweep SRMs
    StopCOM = 6  # end orders
    WaitCOM = 7  # wait


@dataclass(slots=True)
class CommandRecord:
    """One compiled order.

    A variant record in the original: ``Loc`` and the ``Res``/``Trns`` pair
    share storage, and which half is live depends on ``Typ``. Both are plain
    fields here; only the pair that matches ``Typ`` is ever read.
    """

    Typ: CommandTypes = CommandTypes.NoCOM
    Loc: Location = field(default_factory=Location)
    Res: TechnologyTypes = TechnologyTypes.fgt
    Trns: int = 0


#: A fleet's compiled orders. The Pascal record carries an explicit byte
#: length; a list carries its own.
OrderStructure = list


#: Three-letter mnemonic for each thing a fleet can carry, as typed in orders.
#: Spans ships and cargo in one table because ``TRANsfer`` takes either --
#: ``ARRAY [fgt..tri]`` in the original, one contiguous subrange.
#:
#: Transcribed rather than derived from the member names: starships are
#: ``ssp`` in the enum but 'STR' here, so a player types ``TRAN 100 STR``.
ResourceName: dict[TechnologyTypes, str] = _table(
    tech_range(TechnologyTypes.fgt, TechnologyTypes.tri),
    (
        "FGT",
        "HKR",
        "JMP",
        "JTN",
        "PEN",
        "STR",
        "TRN",
        "MEN",
        "NNJ",
        "AMB",
        "CHE",
        "MET",
        "SUP",
        "TRI",
    ),
)


def initialize_orders() -> OrderStructure:
    return []


def number_of_commands(code: OrderStructure) -> int:
    return len(code)


def get_command_record(code: OrderStructure, c_num: int) -> CommandRecord:
    """Fetch a command by its 1-based number, as the original indexes them."""
    return code[c_num - 1]


def add_orders(code: OrderStructure, new_comm: CommandRecord) -> None:
    code.append(new_comm)


def dispose_orders(code: OrderStructure) -> None:
    """Discard a compiled order list, emptying it in place.

    In place because the original frees the heap block and zeroes the
    structure the caller handed in; callers rely on seeing it empty
    afterwards without a store-back.
    """
    code.clear()


# --- Parsing -----------------------------------------------------------------


def split_line(line: str) -> list[str]:
    """Split an order line into at most four parameters.

    Everything past the fourth runs together into the fourth, because the
    original stops incrementing at ``MaxNoOfParms``. Trailing parameters are
    padded with empty strings so indexing is unconditional.
    """
    parts: list[str] = [""]
    skip_blanks = True
    for char in line:
        if char == " ":
            if not skip_blanks:
                if len(parts) < 4:
                    parts.append("")
                skip_blanks = True
        else:
            skip_blanks = False
            parts[-1] += char

    return parts + [""] * (4 - len(parts))


def get_resource_type(line: str) -> tuple[TechnologyTypes, int]:
    """Look up a three-letter resource mnemonic. Longer words are truncated,
    so 'METALS' and 'MET' both resolve."""
    wanted = line.upper()[:3]
    for res, name in ResourceName.items():
        if name == wanted:
            return res, NO_OER
    return TechnologyTypes.fgt, BAD_RESOURCE_OER


def get_transfer(line: str) -> tuple[int, int]:
    try:
        return pascal_val(line), NO_OER
    except ValueError:
        return 0, BAD_TRANSFER_OER


def get_destination(
    game: GameEnvironment, emp: Empire, line: str
) -> tuple[Location, int]:
    loc = get_location(game, emp, line)
    if same_id(loc.ID, empty_quadrant()) and same_xy(loc.XY, limbo()):
        return loc, BAD_DEST_OER
    return loc, NO_OER


def parse_line(
    game: GameEnvironment, emp: Empire, line: str
) -> tuple[CommandRecord, int]:
    """Turn one line of order text into a command.

    Only the first four characters of the verb are significant, which is why
    'DEST', 'DESTination' and 'DESTROY' all compile to the same order.
    """
    comm = CommandRecord()
    error = NO_OER
    parm = split_line(line.upper())
    verb = parm[0][:4]

    if verb == "TRAN":
        comm.Typ = CommandTypes.TransCOM
        comm.Res, error = get_resource_type(parm[2])
        # The original overwrites Error with the second call's result, so a
        # bad resource is masked by a good count. Kept: order-of-evaluation
        # here decides which error a player is shown, nothing more.
        comm.Trns, error = get_transfer(parm[1])
    elif verb == "SRMS":
        comm.Typ = CommandTypes.SweepCOM
    elif verb == "DEST":
        comm.Typ = CommandTypes.DestCOM
        comm.Loc, error = get_destination(game, emp, parm[1])
    elif verb == "REPE":
        comm.Typ = CommandTypes.RepeatCOM
    elif verb == "WAIT":
        comm.Typ = CommandTypes.WaitCOM
    elif verb == "":
        comm.Typ = CommandTypes.NoCOM
    else:
        error = BAD_COMMAND_OER
        comm.Typ = CommandTypes.NoCOM

    return comm, error


def compile_orders(
    game: GameEnvironment, emp: Empire, source: list[str], code: OrderStructure
) -> tuple[int, int]:
    """Compile order text into ``code``, appending to whatever is there.

    Returns ``(error, line_no)``; ``line_no`` is meaningless when there is no
    error. Compilation stops at the first bad line, so ``code`` holds the
    orders up to that point -- the original leaves that partial result too.
    """
    error = NO_OER
    i = 1
    for i, line in enumerate(source, start=1):
        comm, error = parse_line(game, emp, line)
        if comm.Typ != CommandTypes.NoCOM:
            add_orders(code, comm)
        if error != NO_OER:
            break

    return error, i


def decompile_orders(
    game: GameEnvironment, emp: Empire, code: OrderStructure
) -> list[str]:
    """Render compiled orders back to editable text.

    The verbs come back in the original's mixed case, where the capitals are
    the four characters the parser actually reads.
    """
    from .primintr import get_name

    source: list[str] = []
    for comm in code:
        match comm.Typ:
            case CommandTypes.SweepCOM:
                source.append("SRMSweep")
            case CommandTypes.DestCOM:
                source.append("DESTination " + get_name(game, emp, comm.Loc))
            case CommandTypes.TransCOM:
                source.append(f"TRANsfer {comm.Trns} {ResourceName[comm.Res]}")
            case CommandTypes.RepeatCOM:
                source.append("REPEat")
            case CommandTypes.WaitCOM:
                source.append("WAIT")

    return source


# --- Fleet order storage -----------------------------------------------------


def fleet_next_statement(game: GameEnvironment, flt_id: IDNumber) -> int:
    """Which order the fleet runs next, 1-based. 0 means it has none."""
    return game.Universe.Fleet[flt_id.Index].NextOrder


def set_fleet_next_statement(game: GameEnvironment, flt_id: IDNumber, com: int) -> None:
    game.Universe.Fleet[flt_id.Index].NextOrder = com


def get_fleet_code(game: GameEnvironment, flt_id: IDNumber) -> OrderStructure:
    """The fleet's compiled orders. Aliases the fleet's own list, as the
    original aliases its heap block -- mutating the result mutates the
    fleet's orders."""
    return game.Universe.Fleet[flt_id.Index].OrderData


def set_fleet_code(
    game: GameEnvironment, flt_id: IDNumber, code: OrderStructure
) -> None:
    game.Universe.Fleet[flt_id.Index].OrderData = code
