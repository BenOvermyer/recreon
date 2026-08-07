"""The in-game command set and its seven menus.

Port of PLAYTURN.PAS's command layer. The unit is the spine of a player's
turn: it declares every command, builds the menu bar, parses typed commands,
validates their parameters, and dispatches. What is here is the first two --
the command enum and the menu structure -- with the dispatch wired up in
:mod:`recreon.ui.menu`.

**Not ported yet**, and worth naming so nobody assumes otherwise:

* The **typed-command parser**. The original lets a player type ``LAUNCH`` or
  ``DES`` on a command line as well as picking from the menus, matching on the
  first few characters. `CommandDataRecord` and `GetCommand` are that.
* The **parameter table**. Each command declares which parameters it needs
  (`ParameterTypes`) and which errors apply to each (`SetOfErrors`), and
  `GetParameters` prompts for and validates them. The screens ported so far
  each collect their own parameters instead, which is why they work without
  it -- but the table is the original's single statement of what every command
  requires, and is worth transcribing when the last commands land.
* `PlayerTakesTurn` itself, the loop. The UI's event loop stands in for it.

Three commands are inside the ``(* ARTIFACTS ... *)`` block and unreachable in
v2.0: ``ArtfctCom``, ``TransCom``, ``HoloCom``. They keep their enum members,
as the original does, and are simply absent from the menus.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, auto


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


__all__ = [
    "MENU_BAR",
    "NOT_PORTABLE",
    "UNREACHABLE",
    "Command",
    "MenuBarItem",
    "MenuItem",
    "all_menu_commands",
    "menu_for",
]
