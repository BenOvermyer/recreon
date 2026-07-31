"""Main Textual application.

The skeleton called for by Phase 2.5: shows the galaxy map, the current year
and empire, and can advance a turn. The seven pull-down menus of MENU.PAS and
the status windows are Phase 8.
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Static

from ..environ import GameEnvironment
from ..primintr import empire_name, get_object
from ..types import ObjectTypes
from .map_view import MapView


class StatusBar(Static):
    """Year, empire, and what the cursor is over."""

    def __init__(self, game: GameEnvironment, map_view: MapView) -> None:
        super().__init__()
        self.game = game
        self.map_view = map_view

    def refresh_status(self) -> None:
        game = self.game
        name = empire_name(game, game.Player) or game.Player.name
        x, y = self.map_view.cursor_x, self.map_view.cursor_y

        from ..galaxy import XYCoord

        obj = get_object(game, XYCoord(x, y))
        where = "empty space" if obj.ObjTyp == ObjectTypes.Void else obj.ObjTyp.name

        self.update(f"Year {game.Year}   {name}   [{x},{y}] {where}")


class RecreonApp(App):
    """Re:creon's terminal UI."""

    TITLE = "Re:creon"

    CSS = """
    Screen { layout: vertical; }
    #map { width: 1fr; height: 1fr; padding: 0 1; }
    StatusBar { dock: bottom; height: 1; background: $panel; color: $text; padding: 0 1; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("n", "next_turn", "Next turn"),
        Binding("up,k", "move(0,-1)", "Up", show=False),
        Binding("down,j", "move(0,1)", "Down", show=False),
        Binding("left,h", "move(-1,0)", "Left", show=False),
        Binding("right,l", "move(1,0)", "Right", show=False),
    ]

    def __init__(self, game: GameEnvironment) -> None:
        super().__init__()
        self.game = game

    def compose(self) -> ComposeResult:
        yield Header()
        self.map_view = MapView(self.game)
        self.map_view.id = "map"
        self.status_bar = StatusBar(self.game, self.map_view)
        yield Horizontal(self.map_view)
        yield self.status_bar
        yield Footer()

    def on_mount(self) -> None:
        self.status_bar.refresh_status()

    def action_move(self, dx: int, dy: int) -> None:
        self.map_view.move_cursor(dx, dy)
        self.map_view.refresh()
        self.status_bar.refresh_status()

    def action_next_turn(self) -> None:
        from ..main import update_turn

        update_turn(self.game)
        self.map_view.refresh()
        self.status_bar.refresh_status()
