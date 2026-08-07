"""Naming, and the empire status report.

The Textual half of NAMES.PAS. What the commands do is :mod:`recreon.names`.

The status report is the interesting one. ``StatusHardcopy`` sent its lines to
``LST:`` after asking the player to ready the printer -- there is no
equivalent, but the report itself is a genuinely useful summary of everything
the empire knows, so it is shown on screen and can be written to a file.
"""

from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

from ..environ import GameEnvironment
from ..galaxy import limbo
from ..names import STATUS_HEADER, delete_name_command, status_report
from ..primintr import get_coord, object_name
from ..types import Empire, IDNumber
from .prologue import Attention, TextPrompt


class StatusReportScreen(Screen[None]):
    """Everything the empire knows, one line per world. ``StatusHardcopy``."""

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("s", "save", "Save to file"),
    ]

    CSS = """
    StatusReportScreen { layout: vertical; }
    #body { height: 1fr; padding: 1 2; }
    """

    def __init__(self, game: GameEnvironment, player: Empire) -> None:
        super().__init__()
        self.game = game
        self.player = player

    def compose(self) -> ComposeResult:
        yield Header()
        yield VerticalScroll(id="body")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Re:creon"
        self.lines = status_report(self.game, self.player)
        self.query_one("#body", VerticalScroll).mount(
            Static("\n".join(self.lines))
        )

    def action_close(self) -> None:
        self.dismiss(None)

    def action_save(self) -> None:
        """What the printer did, to a file instead."""
        def named(name: str | None) -> None:
            if not name:
                return
            path = Path(self.game.SavDirect or ".") / name
            try:
                path.write_text("\n".join(self.lines) + "\n", encoding="utf-8")
            except OSError as exc:
                self.app.push_screen(Attention("Could not write the report.", str(exc)))
                return
            self.app.push_screen(Attention(f"Report written to {path}."))

        self.app.push_screen(TextPrompt("Write the report to:", "status.txt"), named)


class RemoveNameScreen(Screen[None]):
    """Pick one of the empire's names and forget it. ``DeleteNameCommand``."""

    BINDINGS = [Binding("escape", "close", "Close")]

    CSS = """
    RemoveNameScreen { layout: vertical; }
    #heading { height: auto; padding: 1 2; text-style: bold; }
    #body { height: 1fr; padding: 0 2; }
    """

    def __init__(self, game: GameEnvironment, player: Empire) -> None:
        super().__init__()
        self.game = game
        self.player = player

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Remove name:", id="heading")
        yield VerticalScroll(id="body")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Re:creon"
        self.names = list(self.game.Universe.EmpireData[self.player].Names)
        body = self.query_one("#body", VerticalScroll)

        if not self.names:
            body.mount(Static("You have named nothing yet."))
            return

        body.mount(
            ListView(
                *[
                    ListItem(
                        Label(f"{record.Name:<20}{record.Coord.XY.x},{record.Coord.XY.y}"),
                        name=str(i),
                    )
                    for i, record in enumerate(self.names)
                ]
            )
        )
        self.set_focus(body.query_one(ListView))

    def action_close(self) -> None:
        self.dismiss(None)

    @on(ListView.Selected)
    def _selected(self, event: ListView.Selected) -> None:
        record = self.names[int(event.item.name)]
        message = delete_name_command(self.game, self.player, record.Name)
        self.dismiss(None)
        self.app.push_screen(Attention(message))
