"""Defense settings and self-destruct.

The Textual half of MSCCOMM.PAS's live commands. What they do is
:mod:`recreon.msccomm`; this draws the grid and collects the confirmations.

The defense grid is the one screen that shapes every future battle: it holds
the empire's standing orders for spreading each ship type across the five
orbital shells, and combat reads them whenever a world or base is attacked.

Reached from the map with ``d`` (defenses) and ``x`` (self-destruct). The
original hangs them off the Ministry of War and Worlds pull-downs, which are
MENU.PAS and still to come.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from ..datacnst import ThingNames
from ..environ import GameEnvironment
from ..msccomm import (
    SHELL_HEADINGS,
    SelfDestructError,
    can_self_destruct,
    clamp_percent,
    defense_settings_for_editing,
    destructible_objects,
    illegal_amounts,
    normalize_defenses,
    save_defense_settings,
    self_destruct_aborted,
    self_destruct_command,
    self_destruct_warning,
    shell_total,
)
from ..types import SHIP_TYPES, Empire, ShellPos
from .prologue import Attention, ChooseFrom, TextPrompt


class DefenseScreen(Screen[None]):
    """The orbital shell distribution grid. Port of ``DefenseCommand``.

    Arrow keys move the cursor, digits start an entry, Esc normalises and
    leaves -- the same shape as the original, whose Esc runs the legality
    check, shows what it found, normalises, and only exits once the grid is
    clean. So the first Esc on a bad grid fixes it and tells you; the second
    leaves.
    """

    BINDINGS = [
        Binding("escape", "leave", "Normalize / close"),
        Binding("up", "move_ship(-1)", "Up", show=False),
        Binding("down", "move_ship(1)", "Down", show=False),
        Binding("left", "move_shell(-1)", "Left", show=False),
        Binding("right", "move_shell(1)", "Right", show=False),
    ]

    CSS = """
    DefenseScreen { layout: vertical; }
    #heading { height: auto; padding: 1 2; text-style: bold; }
    #grid { height: 1fr; padding: 0 2; }
    #note { height: auto; padding: 0 2; color: $warning; }
    """

    def __init__(self, game: GameEnvironment, player: Empire) -> None:
        super().__init__()
        self.game = game
        self.player = player
        self.defense = defense_settings_for_editing(game, player)
        self.ship_index = 0
        self.shell_index = 0
        self.note = ""

    @property
    def dist(self):
        return self.defense.ShellDefDist

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Defenses:", id="heading")
        yield VerticalScroll(id="grid")
        yield Static(id="note")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Re:creon"
        self._rebuild()

    def _rebuild(self) -> None:
        grid = self.query_one("#grid", VerticalScroll)
        grid.remove_children()

        header = " " * 12 + "".join(f"{name:>10}" for name in SHELL_HEADINGS)
        lines = [Static(header + f"{'(Total)':>10}")]

        for row, ship in enumerate(SHIP_TYPES):
            cells = []
            for column, shell in enumerate(ShellPos):
                # Pad first, then mark up the last three characters -- the
                # number itself -- so the columns line up whether or not the
                # cursor is on this cell.
                cell = f"{self.dist[shell][ship]:>3}".rjust(10)
                if row == self.ship_index and column == self.shell_index:
                    cell = f"{cell[:-3]}[reverse]{cell[-3:]}[/reverse]"
                cells.append(cell)
            total = shell_total(self.dist, ship)
            lines.append(
                Static(f"{ThingNames[ship][:10]:<12}" + "".join(cells) + f"{total:>10}")
            )

        grid.mount(*lines)
        self.query_one("#note", Static).update(self.note)

    # --- Moving ---------------------------------------------------------------

    def action_move_ship(self, delta: int) -> None:
        """Wraps at both ends, as the original's Up/Down explicitly do."""
        self.ship_index = (self.ship_index + delta) % len(SHIP_TYPES)
        self._rebuild()

    def action_move_shell(self, delta: int) -> None:
        self.shell_index = (self.shell_index + delta) % len(ShellPos)
        self._rebuild()

    # --- Editing --------------------------------------------------------------

    def on_key(self, event) -> None:
        if event.key.isdigit() or event.key in ("plus", "minus"):
            event.stop()
            self._prompt_percent(event.key if event.key.isdigit() else "")

    def _prompt_percent(self, first: str) -> None:
        ship = SHIP_TYPES[self.ship_index]
        shell = list(ShellPos)[self.shell_index]

        def entered(text: str | None) -> None:
            if not text:
                return
            try:
                value = int(text)
            except ValueError:
                return
            # Anything out of range becomes 0, not the nearest bound.
            self.dist[shell][ship] = clamp_percent(value)
            self._rebuild()

        self.app.push_screen(
            TextPrompt(
                "New setting:",
                first,
                detail=f"{ThingNames[ship]} in {SHELL_HEADINGS[self.shell_index]}",
            ),
            entered,
        )

    # --- Leaving --------------------------------------------------------------

    def action_leave(self) -> None:
        problem = illegal_amounts(self.dist)
        if problem is not None:
            normalize_defenses(self.dist)
            self.note = problem
            self.ship_index = 0
            self.shell_index = 0
            self._rebuild()
            return

        save_defense_settings(self.game, self.player, self.defense)
        self.dismiss(None)


class SelfDestructScreen(Screen[None]):
    """Scuttle a starbase or stargate. Port of ``SelfDestructCommand``."""

    BINDINGS = [Binding("escape", "close", "Close")]

    CSS = """
    SelfDestructScreen { layout: vertical; }
    #heading { height: auto; padding: 1 2; text-style: bold; }
    #body { height: 1fr; padding: 0 2; }
    """

    def __init__(self, game: GameEnvironment, player: Empire) -> None:
        super().__init__()
        self.game = game
        self.player = player

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Self-Destruct:", id="heading")
        yield VerticalScroll(id="body")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Re:creon"
        self.targets = destructible_objects(self.game, self.player)

        if not self.targets:
            self.query_one("#body", VerticalScroll).mount(
                Static("There is nothing that can be destroyed.")
            )
            return

        self.app.push_screen(
            ChooseFrom("What object do you wish to destroy?", self.targets),
            self._chosen,
        )

    def action_close(self) -> None:
        self.dismiss(None)

    def _chosen(self, obj) -> None:
        if obj is None:
            self.dismiss(None)
            return

        try:
            can_self_destruct(self.game, self.player, obj)
        except SelfDestructError as exc:
            # Dismiss before reporting: the message belongs on top of whatever
            # this screen was covering, not on top of this screen.
            self.dismiss(None)
            self.app.push_screen(Attention(str(exc)))
            return

        warning = self_destruct_warning(self.game, self.player, obj)
        self.query_one("#body", VerticalScroll).mount(Static("\n".join(warning)))

        def confirmed(yes: bool) -> None:
            if yes:
                message = self_destruct_command(self.game, self.player, obj)
            else:
                message = self_destruct_aborted(self.game, self.player)
            self.dismiss(None)
            self.app.push_screen(Attention(message))

        self.app.push_screen(
            Attention(
                warning[0],
                "\n".join(warning[1:]) + "\n\nGive destruct confirmation?",
                confirm=True,
            ),
            confirmed,
        )
