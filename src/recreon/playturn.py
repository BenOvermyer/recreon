"""The in-game command set and its seven menus.

Port of PLAYTURN.PAS's command layer. The unit is the spine of a player's
turn: it declares every command, builds the menu bar, parses typed commands,
validates their parameters, and dispatches. What is here is the first two --
the command enum and the menu structure -- with the dispatch wired up in
:mod:`recreon.ui.menu`.

**There is no typed-command parser in v2.0**, and this file used to say there
was. ``GetCommand`` (PLAYTURN.PAS:1064) reads a single keystroke and hands it
to ``ActivateMenuBar``; there is no string matching in it anywhere, and
``FillChar(Parm,SizeOf(Parm),0)`` on the next line means every command reaches
``GetParameters`` with all its parameters blank. The routine that split
``LAUNCH FLEET1`` into words, ``SplitCommandLine``, sits in DEADCODE.PAS, and
no ``CommandData`` array exists anywhere in the tree -- only the vestigial
``CommandDataRecord`` type and a ``NoOfCommands = 25`` with no table behind it.
So a player of the shipped build picked commands off the menu bar and answered
prompts, and could not type ``DES``. The menu bar is :data:`MENU_BAR`, already
ported; there is nothing else to port.

One consequence runs through everything below: **only the prompting half of
``GetParameters`` is reachable**. The branch that validates a parameter
supplied up front, and cancels the command outright on a bad one, can only be
entered from the parser that was removed. :class:`ParameterSession` implements
both, because the table describes both, but only the prompting path has a
caller.

Still not ported: `PlayerTakesTurn` itself, the loop. The UI's event loop
stands in for it.

Three commands are inside the ``(* ARTIFACTS ... *)`` block and unreachable in
v2.0: ``ArtfctCom``, ``TransCom``, ``HoloCom``. They keep their enum members,
as the original does, and are simply absent from the menus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto

from .datacnst import TRI_TO_LAUNCH
from .display import interpret_obj
from .environ import GameEnvironment
from .galaxy import Location, XYCoord, limbo
from .misc import same_id, same_xy
from .orders import fleet_next_statement
from .primintr import (
    delete_name,
    empire_name,
    get_base_type,
    get_class,
    get_coord,
    get_defined_name,
    get_defns,
    get_empire_technology,
    get_fleets,
    get_location,
    get_object,
    get_ships,
    get_status,
    get_tech,
    get_trillum,
    get_type,
    known,
    my_lord,
    name2index,
    scouted,
)
from .types import (
    NO_OF_FLEETS_PER_EMPIRE,
    Empire,
    IDNumber,
    ObjectTypes,
    TechLevel,
    TechnologyTypes,
    WorldClass,
    WorldTypes,
    empty_quadrant,
)


class Command(IntEnum):
    """Every command a player can give. Port of ``AllCommands``.

    Ordinals are not load-bearing here -- unlike the game's data enums, this
    one is never indexed into a table -- so it is declared in the original's
    order for diffability rather than for its numbering.
    """

    NullCom = 0
    ErrorCom = auto()
    EndCom = auto()
    ProdInfoCom = auto()
    AttackCom = auto()
    CAbortCom = auto()
    CAddCom = auto()
    ShellCom = auto()
    DesignateCom = auto()
    FLaunchCom = auto()
    FAbortCom = auto()
    FDestCom = auto()
    FTransCom = auto()
    FFuelCom = auto()
    GrantIndepCom = auto()
    AboutCom = auto()
    LAMCom = auto()
    MReadCom = auto()
    MSendCom = auto()
    NAddCom = auto()
    NDelCom = auto()
    ProbeCom = auto()
    SelfSufCom = auto()
    TerraCom = auto()
    HrdCopyCom = auto()
    InfoCom = auto()
    STechCom = auto()
    ConStaCom = auto()
    SRMSweepCom = auto()
    SelfDestCom = auto()
    DefnsCom = auto()
    HoloCom = auto()
    PauseCom = auto()
    OrderCom = auto()
    CancelOrdCom = auto()
    ArtfctCom = auto()
    TransCom = auto()
    AutoAttackCom = auto()
    WarpLinkFreqCom = auto()
    XXXCom = auto()


#: Commands inside the `(* ARTIFACTS ... *)` block -- declared, menued and
#: dispatched nowhere in v2.0. See CLAUDE.md on the dead artifact subsystem.
UNREACHABLE = frozenset({Command.ArtfctCom, Command.TransCom, Command.HoloCom})

#: Commands that only DOS could do, or that need hardware the port has no
#: equivalent for.
#: ``HrdCopyCom`` is *not* here: its printer is unportable but the report it
#: builds is shown on screen instead. See :mod:`recreon.names`.
NOT_PORTABLE = frozenset({Command.ShellCom})


@dataclass(slots=True, frozen=True)
class MenuItem:
    """One line of a pull-down: its label, its accelerator, its command.

    ``key`` is the letter the original underlines, and it is not always the
    first: "caNcel orders" is N, "auTo attack" is T. Both are cases where the
    obvious letter was already taken within the same menu.
    """

    label: str
    key: str
    command: Command


@dataclass(slots=True, frozen=True)
class MenuBarItem:
    """One pull-down on the bar."""

    title: str
    key: str
    items: tuple[MenuItem, ...]


#: The seven menus, transcribed from ``InitializeMainMenu``
#: (PLAYTURN.PAS:1262-1321), in the original's order with its accelerators.
#:
#: The first menu's title is a single CP437 glyph in the original -- the
#: system-menu box that DOS applications put at the far left. "Info" is what
#: IMPLEMENTATION_PLAN.md calls it, and it is what is used here.
MENU_BAR: tuple[MenuBarItem, ...] = (
    MenuBarItem(
        "Info",
        "I",
        (
            MenuItem("About Re:creon", "A", Command.AboutCom),
            MenuItem("DOS shell", "D", Command.ShellCom),
        ),
    ),
    MenuBarItem(
        "Game",
        "G",
        (
            MenuItem("Pause game", "P", Command.PauseCom),
            MenuItem("Status hardcopy", "S", Command.HrdCopyCom),
            MenuItem("Next turn", "N", Command.EndCom),
            MenuItem("Quit", "Q", Command.XXXCom),
        ),
    ),
    MenuBarItem(
        "Empire",
        "E",
        (
            MenuItem("Send message", "S", Command.MSendCom),
            MenuItem("Read messages", "R", Command.MReadCom),
            MenuItem("Trade technology", "T", Command.STechCom),
            MenuItem("Link frequencies", "L", Command.WarpLinkFreqCom),
        ),
    ),
    MenuBarItem(
        "Worlds",
        "W",
        (
            MenuItem("Close up", "C", Command.InfoCom),
            MenuItem("Designate", "D", Command.DesignateCom),
            MenuItem("Production", "P", Command.ProdInfoCom),
            MenuItem("ISSP", "I", Command.SelfSufCom),
            MenuItem("Name", "N", Command.NAddCom),
            MenuItem("Remove name", "R", Command.NDelCom),
            MenuItem("Liberate", "L", Command.GrantIndepCom),
            MenuItem("Self-destruct", "S", Command.SelfDestCom),
            MenuItem("Terraform", "T", Command.TerraCom),
        ),
    ),
    MenuBarItem(
        "Fleet",
        "F",
        (
            MenuItem("Deploy", "D", Command.FLaunchCom),
            MenuItem("Change destination", "C", Command.FDestCom),
            MenuItem("Transfer", "T", Command.FTransCom),
            MenuItem("Abort/join", "A", Command.FAbortCom),
            MenuItem("Refuel", "R", Command.FFuelCom),
            MenuItem("SRM sweep", "S", Command.SRMSweepCom),
            MenuItem("Orders", "O", Command.OrderCom),
            MenuItem("caNcel orders", "N", Command.CancelOrdCom),
            MenuItem("Probe", "P", Command.ProbeCom),
        ),
    ),
    MenuBarItem(
        "Build",
        "B",
        (
            MenuItem("Site status", "S", Command.ConStaCom),
            MenuItem("New construction site", "N", Command.CAddCom),
            MenuItem("Abort construction", "A", Command.CAbortCom),
        ),
    ),
    MenuBarItem(
        "Ministry of War",
        "M",
        (
            MenuItem("Attack", "A", Command.AttackCom),
            MenuItem("auTo attack", "T", Command.AutoAttackCom),
            MenuItem("Launch LAMs", "L", Command.LAMCom),
            MenuItem("Defenses", "D", Command.DefnsCom),
        ),
    ),
)


def menu_for(command: Command) -> MenuBarItem | None:
    """Which pull-down a command hangs off, or None if it is on none."""
    for bar_item in MENU_BAR:
        if any(item.command == command for item in bar_item.items):
            return bar_item
    return None


def all_menu_commands() -> list[Command]:
    """Every command reachable from the bar, in menu order."""
    return [item.command for bar in MENU_BAR for item in bar.items]


# --- The parameter table -----------------------------------------------------
#
# `GetParameters` is one loop over a static table. Each command declares up to
# three parameters; each parameter declares what kind of thing it is
# (`ParameterTypes`), which question to ask for it (an index into
# `QuestionArray`), and which of forty-odd checks apply to the answer
# (`SetOfErrors`). Everything specific to a command lives in the table, and the
# code below is generic over it.
#
# This is the original's single statement of what every command requires. The
# ported command screens each collect their own parameters -- they had to, they
# landed before this did -- so the table is not on the critical path for any of
# them. It is worth having anyway: it is the only place the game says, in one
# piece, that refuelling a fleet needs somewhere to refuel and that terraforming
# needs four separate things to be true of the world.


class ParameterTypes(IntEnum):
    """What kind of thing a parameter is.

    The last four are declared, have error codes reserved for them
    (``IllSymb``, ``IllCons``, ``IllSwitch``, ``IllEmpSet``), and are used by no
    command in the table -- and ``InterpretParameter`` has no case branch for
    them either, so a command that did request one would silently receive the
    default. Kept because the enum is the original's.
    """

    NoParm = 0
    AllCoordParm = auto()
    IDParm = auto()
    IDParm2 = auto()
    XYParm = auto()
    NameParm = auto()
    NewNameParm = auto()
    TypParm = auto()
    ConsParm = auto()
    SwitchParm = auto()
    EmpSetParm = auto()


class Errors(IntEnum):
    """Everything a parameter can be wrong about.

    Declared in the original's order and grouping. Not all of them are live:
    see :data:`UNCHECKED_ERRORS` and :data:`SILENT_ERRORS`.
    """

    NoError = 0
    NotAFlt = auto()
    NotPartOfEmp = auto()
    InUse = auto()
    NotInUse = auto()
    NotEnoughTri = auto()
    NotMoving = auto()
    NoPlaceToTra = auto()
    NotScouted = auto()
    NotKnown = auto()
    NoTri = auto()
    NoPlaceToRef = auto()
    NotAWorld = auto()
    NotConsSite = auto()
    NoTarget = auto()
    NotEmpty = auto()

    NotEnoughTech = auto()
    IsACap = auto()
    CapDes = auto()
    TerDes = auto()
    OutDes = auto()
    TerTech = auto()
    TerCap = auto()
    TerWrongCls = auto()
    TerNotWarp = auto()
    NoLAMs = auto()
    NoLAMTargets = auto()
    NameNotInUse = auto()
    IllName = auto()
    NameTooLong = auto()
    DuplicateName = auto()
    DupFltName = auto()
    NoFltAtSite = auto()
    NoRoomToBuild = auto()
    NoStr1 = auto()
    NoOrders = auto()
    NoFltToTrans = auto()

    EmptQuad = auto()
    NotName = auto()
    NoObj = auto()
    UndefCoord = auto()

    IllSymb = auto()
    IllCons = auto()
    IllSwitch = auto()
    IllEmpSet = auto()


#: The 27 prompts, 1-based to match the table's ``Question`` field. Index 0 is
#: the table's "no question", and no live parameter uses it.
QUESTIONS: tuple[str, ...] = (
    "",
    "Which fleet shall we use to attack? ",
    "Which construction site do you wish to stop? ",
    "Sweep SRM field with which fleet? ",
    "Production information for which world? ",
    "Which world do you wish to designate? ",
    "Which fleet do you want to order? ",
    "What name shall we use for this fleet? ",
    "Where shall we deploy the fleet from? ",
    "What shall its destination be? ",
    "Which fleet do you wish to abort/join? ",
    "Change the destination of which fleet/starbase? ",
    "What shall its new destination be? ",
    "Which fleet do you wish to transfer? ",
    "Which fleet do you wish to refuel? ",
    "Which world shall you grant independence to? ",
    "Which world do you wish to destroy? ",
    "Cancel orders for which fleet? ",
    "What do you wish to name? ",
    "What shall its new name be? ",
    "Which name do you wish to delete? ",
    "Where shall we send a probe? ",
    "Change ISSP of which world? ",
    "Transact with which world? ",
    "Which world do you wish to terraform? ",
    "Where shall we launch the LAMs from? ",
    "Close up on which world? ",
    "Where shall we begin construction? ",
)


@dataclass(slots=True, frozen=True)
class Parameter:
    """One parameter of one command: its kind, its prompt, its checks."""

    ParmTyp: ParameterTypes
    Question: int
    ErrorCond: frozenset[Errors] = frozenset()

    @property
    def prompt(self) -> str:
        return QUESTIONS[self.Question]


def _p(
    parm_typ: ParameterTypes, question: int, *errors: Errors
) -> Parameter:
    return Parameter(parm_typ, question, frozenset(errors))


E = Errors
P = ParameterTypes

#: What each command needs, transcribed from ``ParameterData``
#: (PLAYTURN.PAS:158-412).
#:
#: The original's rows are a fixed three slots plus a ``NoOfParm`` count, with
#: the unused slots padded to ``(NoParm, 0, [])``. Every row pads identically
#: and the padding carries no information, so the port stores only the live
#: parameters and lets ``len()`` be ``NoOfParm``. A command absent from this
#: dict takes no parameters, which is the same as the original's zero rows --
#: they are listed explicitly anyway, because "this command asks nothing" is
#: worth being able to read off the table rather than infer from a gap.
PARAMETER_DATA: dict[Command, tuple[Parameter, ...]] = {
    Command.NullCom: (),
    Command.ErrorCom: (),
    Command.EndCom: (),
    Command.ProdInfoCom: (_p(P.IDParm, 4, E.NotPartOfEmp, E.NotAWorld),),
    Command.AttackCom: (
        _p(P.IDParm, 1, E.NotAFlt, E.NotPartOfEmp, E.NotInUse, E.NoTarget),
    ),
    Command.CAbortCom: (_p(P.IDParm, 2, E.NotPartOfEmp, E.NotConsSite),),
    Command.CAddCom: (_p(P.XYParm, 27, E.NotEmpty),),
    Command.ShellCom: (),
    Command.DesignateCom: (
        _p(
            P.IDParm,
            5,
            E.NotPartOfEmp,
            E.NotInUse,
            E.NotAWorld,
            E.CapDes,
            E.TerDes,
            E.OutDes,
        ),
    ),
    Command.FLaunchCom: (
        _p(P.NewNameParm, 7, E.DupFltName),
        _p(P.IDParm2, 8, E.NotPartOfEmp, E.NotInUse),
        _p(P.XYParm, 9),
    ),
    Command.FAbortCom: (
        _p(P.IDParm, 10, E.NotPartOfEmp, E.NotInUse, E.NotAFlt, E.NoPlaceToTra),
    ),
    Command.FDestCom: (
        _p(P.IDParm, 11, E.NotPartOfEmp, E.NotInUse, E.NotMoving),
        _p(P.XYParm, 12),
    ),
    Command.FTransCom: (
        _p(P.IDParm, 13, E.NotAFlt, E.NotPartOfEmp, E.NotInUse, E.NoPlaceToTra),
    ),
    Command.FFuelCom: (
        _p(
            P.IDParm,
            14,
            E.NotAFlt,
            E.NotPartOfEmp,
            E.NotInUse,
            E.NoPlaceToRef,
            E.NoTri,
        ),
    ),
    Command.GrantIndepCom: (
        _p(P.IDParm, 15, E.NotPartOfEmp, E.NotInUse, E.NotAWorld, E.IsACap),
    ),
    Command.AboutCom: (),
    Command.LAMCom: (_p(P.IDParm, 25, E.NotPartOfEmp, E.NotAWorld, E.NoLAMs),),
    Command.MReadCom: (),
    Command.MSendCom: (),
    Command.NAddCom: (
        _p(P.AllCoordParm, 18),
        _p(P.NewNameParm, 19, E.DuplicateName),
    ),
    Command.NDelCom: (_p(P.NameParm, 20),),
    Command.ProbeCom: (_p(P.XYParm, 21),),
    Command.SelfSufCom: (_p(P.IDParm, 22, E.NotPartOfEmp, E.NotAWorld),),
    Command.TerraCom: (
        _p(
            P.IDParm,
            24,
            E.NotPartOfEmp,
            E.NotInUse,
            E.NotAWorld,
            E.TerTech,
            E.TerCap,
            E.TerWrongCls,
            E.TerNotWarp,
        ),
    ),
    Command.HrdCopyCom: (),
    # `InfoCom` is the close-up screen, not an "info" command -- the enum's own
    # comment says `{ INFO }` and the table's says `{ Close Up }`, and the
    # question settles it: "Close up on which world?".
    Command.InfoCom: (_p(P.IDParm, 26, E.NotKnown),),
    Command.STechCom: (),
    Command.ConStaCom: (),
    Command.SRMSweepCom: (
        _p(P.IDParm, 3, E.NotPartOfEmp, E.NotInUse, E.NotAFlt, E.NoStr1),
    ),
    Command.SelfDestCom: (),
    Command.DefnsCom: (),
    Command.HoloCom: (),
    Command.PauseCom: (),
    Command.OrderCom: (_p(P.IDParm, 6, E.NotPartOfEmp, E.NotInUse, E.NotAFlt),),
    Command.CancelOrdCom: (
        _p(P.IDParm, 17, E.NotPartOfEmp, E.NotInUse, E.NotAFlt, E.NoOrders),
    ),
    Command.ArtfctCom: (),
    Command.TransCom: (_p(P.IDParm, 23, E.NotAWorld, E.NoFltToTrans),),
    Command.AutoAttackCom: (
        _p(P.IDParm, 1, E.NotAFlt, E.NotPartOfEmp, E.NotInUse, E.NoTarget),
    ),
    Command.WarpLinkFreqCom: (),
    Command.XXXCom: (),
}

_missing = [c for c in Command if c not in PARAMETER_DATA]
if _missing:  # pragma: no cover -- import-time guard, as `datacnst._table` is
    raise ValueError(f"PARAMETER_DATA is missing {_missing}")
del _missing


#: Errors that ``CheckForObjectErrors`` has no branch for. ``NoTri`` is the one
#: that matters: ``FFuelCom`` asks for it and it is never run. See issue #74.
#: The rest are reserved codes no command requests.
UNCHECKED_ERRORS = frozenset(
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

#: Errors that can be raised but have no line in ``WriteError``'s case, so the
#: original prints nothing for them. Only ``NoObj`` is reachable, and it is
#: silent on purpose: ``InterpretObj`` has already written a message of its own
#: by the time the code is assigned. See :mod:`recreon.display`.
SILENT_ERRORS = frozenset({E.NoObj})


#: The error text, transcribed from ``WriteError`` (PLAYTURN.PAS:916-970).
#: ``@`` is replaced with how the staff address the ruler and ``*`` with the
#: parameter the player typed, in that order.
ERROR_TEXT: dict[Errors, str] = {
    E.NoError: "",
    E.NotAFlt: "* is not a fleet, @.",
    E.NotPartOfEmp: "@, * is not part of ",  # + EmpireName(Player)
    E.InUse: "* has already been deployed, @.",
    E.NotInUse: "@, * has not yet been deployed.",
    E.NotEnoughTri: "There isn't enough trillum on * to launch a fleet, @.",
    E.NotMoving: "What an idea!  Unfortunately, @, * is immobile.",
    E.NoPlaceToTra: "There is no place to transfer to, @.",
    E.NoTri: "There is no trillum on *, @.",
    E.NoPlaceToRef: "There is no place to refuel a fleet in this sector, @.",
    E.NotAWorld: "* is not a world, @.",
    E.NotConsSite: "* is not a construction site, @.",
    E.NoTarget: "* has no targets, @.",
    E.NotEmpty: "* is not empty, @.",
    E.NotKnown: "There's no information available on *, @.",
    E.NotScouted: "There's no information available on *, @.",
    E.IllName: 'I can not use "*" as a name, @.',
    E.DuplicateName: '"*" is already defined, @.',
    E.DupFltName: '"*" is already defined, @.',
    E.NameTooLong: (
        "That name is too long, please restrict yourself to 8 characters, @."
    ),
    E.IsACap: (
        "Not your capital, @.  If you wish for a coup d'grace, try abdicating."
    ),
    E.CapDes: "@ is surely joking!  * is your capital!",
    E.TerDes: "@, * cannot be designated, for it is being terraformed.",
    E.OutDes: "@, * cannot be designated, for it has no industrial capacity.",
    E.TerTech: "We have not yet developed Terraforming technology, @.",
    E.TerCap: (
        "That would be far too great a disruption to administration, @!"
    ),
    E.TerWrongCls: (
        "That class of planet is not suitable for terraforming, @."
    ),
    E.TerNotWarp: (
        "@, a planet must be warp-level or above to be terraformed."
    ),
    E.EmptQuad: "That is an empty sector, @.",
    E.NotName: 'I have not heard of "*", @.',
    E.UndefCoord: "Those coordinates are undefined, @.",
    E.NoLAMs: "There are no LAMs at *, @.",
    E.NoStr1: "You need at least 100 starships to sweep an SRM field, @.",
    E.NoOrders: "* has no orders, @.",
    E.NoFltToTrans: (
        "@, we need to have a fleet in the sector before we can transact."
    ),
}


def error_message(
    game: GameEnvironment, player: Empire, error: Errors, parm: str
) -> str:
    """Render an error code as the line the player reads.

    Returns ``""`` for any code with no text -- which the original does too,
    by leaving ``Line`` empty and skipping the write. **This draws from the
    generator** when there is a message, because ``MyLord`` does.
    """
    line = ERROR_TEXT.get(error, "")
    if not line:
        return ""

    if error == E.NotPartOfEmp:
        line += empire_name(game, player)

    line = line.replace("@", my_lord(game, player))
    return line.replace("*", parm)


# --- Validating one answer ---------------------------------------------------


@dataclass(slots=True)
class Parameters:
    """Everything ``GetParameters`` hands back, with the original's defaults.

    ``Typ``, ``Cons``, ``Setting`` and ``EmpSet`` are initialised and never
    written: only ``TypParm``/``ConsParm``/``SwitchParm``/``EmpSetParm`` would
    write them, and no command asks for those. They are here so the record
    matches the original's ``VAR`` list rather than because anything reads them.
    """

    Obj1: IDNumber = field(default_factory=empty_quadrant)
    Obj2: IDNumber = field(default_factory=empty_quadrant)
    Coord: XYCoord = field(default_factory=limbo)
    NewName: str = ""
    Typ: WorldTypes = WorldTypes.IndTyp
    Cons: TechnologyTypes = TechnologyTypes.out
    Setting: bool = True
    EmpSet: frozenset[Empire] = frozenset()


def _interpret_location(
    game: GameEnvironment, player: Empire, parm: str
) -> tuple[Location, Errors]:
    """``InterpretLocation``: a location the player has at least heard of."""
    loc = get_location(game, player, parm)
    if same_id(loc.ID, empty_quadrant()) and same_xy(loc.XY, limbo()):
        return loc, E.UndefCoord
    if loc.ID.ObjTyp != ObjectTypes.Void and not known(game, player, loc.ID):
        return loc, E.UndefCoord
    return loc, E.NoError


def _interpret_coord(
    game: GameEnvironment, player: Empire, parm: str
) -> tuple[XYCoord, Errors]:
    """``InterpretCoord``: :func:`recreon.display.interpret_xy` without a voice.

    Same resolution, an ``UndefCoord`` code where the other writes a line.
    """
    loc = get_location(game, player, parm)
    if not same_id(loc.ID, empty_quadrant()):
        return get_coord(game, loc.ID), E.NoError
    if not same_xy(loc.XY, limbo()):
        return loc.XY, E.NoError
    return limbo(), E.UndefCoord


def _interpret_new_name(parm: str) -> tuple[str, Errors]:
    """``InterpretNewName``: 8 characters, non-empty, no comma.

    The comma is barred because names are stored in a comma-separated line by
    the order compiler; a name containing one would split in two.
    """
    if len(parm) > 8:
        return "", E.NameTooLong
    if parm == "" or "," in parm:
        return "", E.IllName
    return parm, E.NoError


def interpret_parameter(
    game: GameEnvironment,
    player: Empire,
    parm_typ: ParameterTypes,
    parm: str,
    result: Parameters,
) -> tuple[Errors, str]:
    """Turn one typed string into one field of ``result``, in place.

    Returns ``(error, message)``. The message is non-empty only for ``IDParm``
    and ``IDParm2``, where :func:`recreon.display.interpret_obj` has already
    produced text of its own and the resulting ``NoObj`` code is deliberately
    silent.
    """
    if parm_typ == P.AllCoordParm:
        loc, error = _interpret_location(game, player, parm)
        result.Obj1 = loc.ID
        result.Coord = loc.XY
        return error, ""

    if parm_typ in (P.IDParm, P.IDParm2):
        obj, message = interpret_obj(game, player, parm)
        if parm_typ == P.IDParm:
            result.Obj1 = obj
        else:
            result.Obj2 = obj
        return (E.NoObj, message) if message else (E.NoError, "")

    if parm_typ == P.XYParm:
        result.Coord, error = _interpret_coord(game, player, parm)
        return error, ""

    if parm_typ == P.NameParm:
        # `InterpretNameID`: the name must already exist.
        if name2index(game, player, parm) is None:
            return E.NotName, ""
        result.NewName = parm
        return E.NoError, ""

    if parm_typ == P.NewNameParm:
        name, error = _interpret_new_name(parm)
        if error == E.NoError:
            result.NewName = name
        return error, ""

    # NoParm, and the four types no command requests.
    return E.NoError, ""


def _check_object(
    game: GameEnvironment,
    player: Empire,
    obj: IDNumber,
    error_cond: frozenset[Errors],
) -> Errors:
    """``CheckForObjectErrors``: the checks, in the original's order.

    Order matters -- the first failure wins and the rest are skipped -- so
    these stay in source order rather than being grouped by what they test.
    """
    sets = game.GlobalSets

    if E.NotKnown in error_cond:
        if obj.ObjTyp not in (
            ObjectTypes.Pln,
            ObjectTypes.Flt,
            ObjectTypes.Base,
        ) or (
            not known(game, player, obj) and not scouted(game, player, obj)
        ) or (
            obj.ObjTyp == ObjectTypes.Flt
            and obj.Index not in sets.SetOfActiveFleets
        ):
            return E.NotKnown

    if E.InUse in error_cond:
        if obj.ObjTyp == ObjectTypes.Flt and obj.Index in sets.SetOfActiveFleets:
            return E.InUse

    if E.NotInUse in error_cond:
        if (
            obj.ObjTyp == ObjectTypes.Flt
            and obj.Index not in sets.SetOfActiveFleets
        ):
            return E.NotInUse

    if E.NotMoving in error_cond:
        if obj.ObjTyp not in (ObjectTypes.Flt, ObjectTypes.Base):
            return E.NotMoving

    if E.NotAFlt in error_cond:
        if obj.ObjTyp != ObjectTypes.Flt:
            return E.NotAFlt

    if E.NotAWorld in error_cond:
        # A starbase counts as a world here: command bases are designatable
        # and carry an industry, which is what the callers of this actually
        # want to know.
        if obj.ObjTyp not in (ObjectTypes.Pln, ObjectTypes.Base):
            return E.NotAWorld

    if E.NoFltToTrans in error_cond:
        xy1 = get_coord(game, obj)
        if not (get_fleets(game, xy1) & sets.SetOfFleetsOf[player]):
            return E.NoFltToTrans

    if E.NotConsSite in error_cond:
        if obj.ObjTyp != ObjectTypes.Con:
            return E.NotConsSite

    if E.NotScouted in error_cond:
        if not scouted(game, player, obj):
            return E.NotScouted

    if E.NotPartOfEmp in error_cond:
        if get_status(game, obj) != player:
            return E.NotPartOfEmp

    if E.NoStr1 in error_cond:
        if get_ships(game, obj)[TechnologyTypes.ssp] < 100:
            return E.NoStr1

    if E.NoPlaceToTra in error_cond:
        xy1 = get_coord(game, obj)
        under = get_object(game, xy1)
        if under.ObjTyp not in (ObjectTypes.Pln, ObjectTypes.Base):
            # Somewhere to transfer to means another *scouted* fleet of any
            # empire in the sector -- the original does not filter by owner.
            others = get_fleets(game, xy1) - {obj.Index}
            if not any(
                scouted(game, player, IDNumber(ObjectTypes.Flt, i))
                for i in others
            ):
                return E.NoPlaceToTra

    if E.NoPlaceToRef in error_cond:
        xy1 = get_coord(game, obj)
        under = get_object(game, xy1)
        if (
            under.ObjTyp not in (ObjectTypes.Pln, ObjectTypes.Base)
            or get_status(game, under) != player
            or get_trillum(game, under) == 0
        ):
            refuelling = [
                IDNumber(ObjectTypes.Flt, i) for i in get_fleets(game, xy1)
            ]
            if not any(
                get_status(game, f) == player and get_trillum(game, f) > 0
                for f in refuelling
            ):
                return E.NoPlaceToRef

    if E.NotEnoughTri in error_cond:
        # Inert: `TriToLaunch` is 0 and trillum cannot go below it. Requested
        # by no command either, so doubly so.
        if get_trillum(game, obj) < TRI_TO_LAUNCH:
            return E.NotEnoughTri

    if E.NoTarget in error_cond:
        xy1 = get_coord(game, obj)
        under = get_object(game, xy1)
        if get_status(game, under) == player or same_id(under, empty_quadrant()):
            enemy = get_fleets(game, xy1) - sets.SetOfFleetsOf[player]
            if not any(
                scouted(game, player, IDNumber(ObjectTypes.Flt, i))
                for i in enemy
            ):
                return E.NoTarget

    if E.NoLAMs in error_cond:
        if get_defns(game, obj)[TechnologyTypes.LAM] == 0:
            return E.NoLAMs

    if E.IsACap in error_cond:
        if get_type(game, obj) == WorldTypes.CapTyp:
            return E.IsACap

    if E.CapDes in error_cond:
        if get_type(game, obj) == WorldTypes.CapTyp:
            return E.CapDes

    if E.TerDes in error_cond:
        if get_type(game, obj) == WorldTypes.TerTyp:
            return E.TerDes

    if E.OutDes in error_cond:
        if obj.ObjTyp == ObjectTypes.Base and get_base_type(game, obj) != (
            TechnologyTypes.cmp
        ):
            return E.OutDes

    if E.TerTech in error_cond:
        _, techs = get_empire_technology(game, player)
        if TechnologyTypes.ter not in techs:
            return E.TerTech

    if E.TerNotWarp in error_cond:
        if get_tech(game, obj) < TechLevel.WrpTchLvl:
            return E.TerNotWarp

    if E.TerCap in error_cond:
        if get_type(game, obj) == WorldTypes.CapTyp:
            return E.TerCap

    if E.TerWrongCls in error_cond:
        if get_class(game, obj) in (WorldClass.ArtCls, WorldClass.TerCls):
            return E.TerWrongCls

    if E.NoOrders in error_cond:
        if obj.ObjTyp == ObjectTypes.Flt and fleet_next_statement(game, obj) == 0:
            return E.NoOrders

    return E.NoError


def _check_new_name(
    game: GameEnvironment,
    player: Empire,
    new_name: str,
    error_cond: frozenset[Errors],
) -> Errors:
    """``CheckForNewNameErrors``.

    ``DupFltName`` is the interesting one, because it can *delete*: a name left
    behind by a fleet that has since stood down is silently freed and reused,
    while a name belonging to anything else -- or to a fleet still in space --
    is refused. That is how a player gets to call the new fleet "Home" again
    after the old "Home" came back.
    """
    if E.DuplicateName in error_cond:
        if name2index(game, player, new_name) is not None:
            return E.DuplicateName

    if E.DupFltName in error_cond:
        index = name2index(game, player, new_name)
        if index is not None:
            _, loc = get_defined_name(index)
            if loc.ID.ObjTyp not in (ObjectTypes.Flt, ObjectTypes.DestFlt):
                return E.DupFltName
            if (
                loc.ID.ObjTyp != ObjectTypes.DestFlt
                and loc.ID.Index in game.GlobalSets.SetOfActiveFleets
            ):
                return E.DupFltName
            delete_name(game, player, new_name)

    return E.NoError


def _check_xy(
    game: GameEnvironment, xy: XYCoord, error_cond: frozenset[Errors]
) -> Errors:
    """``CheckForXYErrors``: only ever asks whether the sector is free."""
    if E.NotEmpty in error_cond:
        if not same_id(get_object(game, xy), empty_quadrant()):
            return E.NotEmpty
    return E.NoError


def check_for_errors(
    game: GameEnvironment,
    player: Empire,
    parm_typ: ParameterTypes,
    error_cond: frozenset[Errors],
    result: Parameters,
) -> Errors:
    """``CheckForErrors``: dispatch on the parameter's kind.

    ``AllCoordParm`` and ``NameParm`` have no branch, so their checks never
    run -- which costs nothing, as no command declares any error for either.
    """
    if parm_typ == P.IDParm:
        return _check_object(game, player, result.Obj1, error_cond)
    if parm_typ == P.IDParm2:
        return _check_object(game, player, result.Obj2, error_cond)
    if parm_typ == P.NewNameParm:
        return _check_new_name(game, player, result.NewName, error_cond)
    if parm_typ == P.XYParm:
        return _check_xy(game, result.Coord, error_cond)
    return E.NoError


def validate_parameter(
    game: GameEnvironment,
    player: Empire,
    parameter: Parameter,
    text: str,
    result: Parameters,
) -> tuple[Errors, str]:
    """Interpret one answer and check it. Returns ``(error, message)``.

    The two halves are inseparable in the original -- ``CheckForErrors`` runs
    only ``if Error=NoError``, and reads the fields ``InterpretParameter`` has
    just written -- so they are one call here.
    """
    error, message = interpret_parameter(
        game, player, parameter.ParmTyp, text, result
    )
    if error == E.NoError:
        error = check_for_errors(
            game, player, parameter.ParmTyp, parameter.ErrorCond, result
        )
    if error != E.NoError and not message:
        message = error_message(game, player, error, text)
    return error, message


# --- Asking the questions ----------------------------------------------------


class ParameterSession:
    """``GetParameters``, inverted so the UI can drive it.

    The original blocks: for each parameter it prompts, validates, and repeats
    until the answer is good or the player presses Escape, at which point the
    whole command is abandoned. Textual cannot block, so this is a state
    machine over the same table -- :meth:`question` says what to ask,
    :meth:`answer` takes a reply, and :attr:`done` and :attr:`cancelled` say
    where things stand.

    Escape at *any* prompt cancels the whole command, including one already
    half-answered. The original sets ``Comm := NullCom`` and jumps clear of the
    loop; there is no going back one question.
    """

    def __init__(
        self, game: GameEnvironment, player: Empire, command: Command
    ) -> None:
        self.game = game
        self.player = player
        self.command = command
        self.parameters = PARAMETER_DATA[command]
        self.result = Parameters()
        self.index = 0
        self.cancelled = False
        #: The last error line, for a UI that wants to keep it on screen.
        self.message = ""

    @property
    def done(self) -> bool:
        """True when every parameter is answered, or the command was dropped."""
        return self.cancelled or self.index >= len(self.parameters)

    def question(self) -> str:
        """The prompt for the outstanding parameter, or ``""`` when done."""
        if self.done:
            return ""
        return self.parameters[self.index].prompt

    def answer(self, text: str) -> Errors:
        """Supply one answer. Returns the error, ``NoError`` if it was taken.

        An empty answer is Escape, and cancels the command -- which is why a
        parameter can never legitimately be blank, and why ``InterpretNewName``
        rejects the empty string with ``IllName`` rather than accepting it.
        """
        if self.done:
            return E.NoError

        if text == "":
            self.cancelled = True
            self.message = ""
            return E.NoError

        parameter = self.parameters[self.index]
        error, message = validate_parameter(
            self.game, self.player, parameter, text, self.result
        )
        self.message = message
        if error == E.NoError:
            self.index += 1
        return error


def trap_command_errors(
    game: GameEnvironment, player: Empire, command: Command
) -> str:
    """``TrapCommandErrors``: refuse a command outright, before its parameters.

    Only one command has anything to trap. An empire may have
    ``NoOfFleetsPerEmpire`` fleets in space at once and no more, and this is
    where a player is told so -- the AI honours the same cap in its own launch
    routines. Returns the refusal, or ``""`` to go ahead.

    **This draws from the generator** on the refusal path, via ``MyLord``.
    """
    if command != Command.FLaunchCom:
        return ""

    deployed = len(
        game.GlobalSets.SetOfFleetsOf[player] & game.GlobalSets.SetOfActiveFleets
    )
    if deployed >= NO_OF_FLEETS_PER_EMPIRE:
        return (
            f"I'm sorry, {my_lord(game, player)}, there are too many fleets "
            "in space already."
        )
    return ""


__all__ = [
    "ERROR_TEXT",
    "MENU_BAR",
    "NOT_PORTABLE",
    "PARAMETER_DATA",
    "QUESTIONS",
    "SILENT_ERRORS",
    "UNCHECKED_ERRORS",
    "UNREACHABLE",
    "Command",
    "Errors",
    "MenuBarItem",
    "MenuItem",
    "Parameter",
    "ParameterSession",
    "ParameterTypes",
    "Parameters",
    "all_menu_commands",
    "check_for_errors",
    "error_message",
    "interpret_parameter",
    "menu_for",
    "trap_command_errors",
    "validate_parameter",
]
