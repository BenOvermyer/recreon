"""Main Textual application.

The skeleton called for by Phase 2.5: shows the galaxy map, the current year
and empire, and can advance a turn. The seven pull-down menus of MENU.PAS and
the status windows are Phase 8.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Static

from ..environ import GameEnvironment
from ..primintr import empire_name, get_object
from ..types import ObjectTypes
from .map_view import MapView
from .status import EmpirePanel, NewsPanel, WorldPanel


class StatusBar(Static):
    """Year, empire, and what the cursor is over."""

    def __init__(self, game: GameEnvironment, map_view: MapView) -> None:
        super().__init__()
        self.game = game
        self.map_view = map_view

    def refresh_status(self) -> None:
        game = self.game
        x, y = self.map_view.cursor_x, self.map_view.cursor_y

        # Before a scenario is chosen the galaxy is unallocated, and asking it
        # for a sector raises rather than wrapping to the far edge.
        if not game.Galaxy.in_galaxy(x, y):
            self.update("No game loaded -- press G to start one")
            return

        from ..galaxy import XYCoord

        name = empire_name(game, game.Player) or game.Player.name
        obj = get_object(game, XYCoord(x, y))
        where = "empty space" if obj.ObjTyp == ObjectTypes.Void else obj.ObjTyp.name

        self.update(f"Year {game.Year}   {name}   [{x},{y}] {where}")


class RecreonApp(App):
    """Re:creon's terminal UI."""

    TITLE = "Re:creon"

    CSS = """
    Screen { layout: vertical; }
    #map { width: 1fr; height: 1fr; padding: 0 1; }
    #side { width: 34; height: 1fr; border-left: solid $panel; padding: 0 1; }
    WorldPanel { height: 1fr; }
    EmpirePanel { height: auto; border-top: solid $panel; }
    #news { height: 10; border-top: solid $panel; padding: 0 1; overflow-y: auto; }
    StatusBar { dock: bottom; height: 1; background: $panel; color: $text; padding: 0 1; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("n", "next_turn", "Next turn"),
        Binding("g", "new_game", "New game"),
        Binding("up,k", "move(0,-1)", "Up", show=False),
        Binding("down,j", "move(0,1)", "Down", show=False),
        Binding("left,h", "move(-1,0)", "Left", show=False),
        Binding("right,l", "move(1,0)", "Right", show=False),
    ]

    def __init__(
        self,
        game: GameEnvironment | None = None,
        scenario_dir: str | Path | None = None,
    ) -> None:
        super().__init__()
        #: A blank environment stands in until the picker builds a real one,
        #: so every widget has something to render against on first mount.
        self.game = game or GameEnvironment()
        self.started = game is not None
        self.scenario_dir = Path(scenario_dir) if scenario_dir else None

    def compose(self) -> ComposeResult:
        yield Header()
        self.map_view = MapView(self.game)
        self.map_view.id = "map"
        self.world_panel = WorldPanel(self.game)
        self.empire_panel = EmpirePanel(self.game)
        self.news_panel = NewsPanel(self.game)
        self.news_panel.id = "news"
        self.status_bar = StatusBar(self.game, self.map_view)

        yield Horizontal(
            self.map_view,
            Vertical(self.world_panel, self.empire_panel, id="side"),
        )
        yield self.news_panel
        yield self.status_bar
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_all()
        if not self.started and self.scenario_dir is not None:
            self.action_new_game()

    def action_new_game(self) -> None:
        """Open the scenario picker. ``StartANewGame`` in the prologue menu."""
        from .newgame import NewGameScreen

        self.push_screen(
            NewGameScreen(self.scenario_dir or Path.cwd()), self._game_started
        )

    def _game_started(self, game: GameEnvironment | None) -> None:
        """The picker dismissed. ``None`` means the player backed out.

        Backing out with no game to return to leaves the app on an empty
        galaxy rather than quitting, which is where the original's prologue
        menu sits when you cancel out of ``StartANewGame``.
        """
        if game is None:
            return

        self.game = game
        self.started = True
        for widget in (
            self.map_view,
            self.world_panel,
            self.empire_panel,
            self.news_panel,
            self.status_bar,
        ):
            widget.game = game
        self._refresh_all()

    def _refresh_all(self) -> None:
        self.map_view.refresh()
        self.world_panel.look_at(self.map_view.cursor_x, self.map_view.cursor_y)
        self.empire_panel.refresh()
        self.news_panel.refresh()
        self.status_bar.refresh_status()

    def action_move(self, dx: int, dy: int) -> None:
        self.map_view.move_cursor(dx, dy)
        self._refresh_all()

    def action_next_turn(self) -> None:
        from ..main import update_turn

        update_turn(self.game)
        self._refresh_all()
