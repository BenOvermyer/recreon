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
        Binding("g", "prologue", "Menu"),
        Binding("b", "construction", "Build"),
        Binding("w", "warp_links", "Warp links"),
        Binding("z", "close_up", "Close-up"),
        Binding("i", "production", "Production"),
        Binding("f", "fleets", "Fleets"),
        Binding("d", "defenses", "Defenses"),
        Binding("x", "self_destruct", "Self-destruct", show=False),
        Binding("up,k", "move(0,-1)", "Up", show=False),
        Binding("down,j", "move(0,1)", "Down", show=False),
        Binding("left,h", "move(-1,0)", "Left", show=False),
        Binding("right,l", "move(1,0)", "Right", show=False),
    ]

    def __init__(
        self,
        game: GameEnvironment | None = None,
        scenario_dir: str | Path | None = None,
        save_dir: str | Path | None = None,
    ) -> None:
        super().__init__()
        from ..prolog import PrologueState

        #: A blank environment stands in until a game is started or loaded,
        #: so every widget has something to render against on first mount.
        self.game = game or GameEnvironment()
        self.started = game is not None
        self.scenario_dir = Path(scenario_dir) if scenario_dir else None
        self.save_dir = Path(save_dir) if save_dir else Path.cwd()

        #: PROLOG.PAS's two flags. A game handed in on the command line counts
        #: as loaded and unmodified -- nothing has happened to it yet.
        self.prologue = PrologueState(game_loaded=self.started)
        self.game.SavDirect = str(self.save_dir)
        if self.scenario_dir:
            self.game.SceDirect = str(self.scenario_dir)

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
        # ANACREON.PAS runs Prologue before anything else, every time round
        # the outer loop. A game handed in on the command line skips it.
        if not self.started:
            self.action_prologue()

    def action_prologue(self) -> None:
        """Open the prologue menu. ``Prologue`` in the main program."""
        from .prologue import PrologueScreen

        self.push_screen(
            PrologueScreen(
                self.game,
                self.prologue,
                self.scenario_dir or Path.cwd(),
                self.save_dir,
            ),
            self._prologue_closed,
        )

    def _prologue_closed(self, outcome: str | None) -> None:
        """The two ways ``Prologue``'s loop ends: Continue, or EndGame."""
        if outcome == "quit":
            self.exit()
            return

        self.started = self.prologue.game_loaded
        self._refresh_all()

    def adopt_game(self, game: GameEnvironment) -> None:
        """Point every widget at a newly started or loaded game.

        The environment is replaced wholesale rather than mutated -- loading
        builds a fresh one -- so the widgets holding the old reference have to
        be re-pointed or they keep rendering the previous galaxy.
        """
        self.game = game
        self.started = True
        game.SavDirect = str(self.save_dir)
        if self.scenario_dir:
            game.SceDirect = str(self.scenario_dir)

        for widget in (
            self.map_view,
            self.world_panel,
            self.empire_panel,
            self.news_panel,
            self.status_bar,
        ):
            widget.game = game
        self._refresh_all()

    def action_construction(self) -> None:
        """Construction status, with construct and abort on it (CONSTR.PAS).

        The original hangs this off the Build pull-down; MENU.PAS is still to
        come, so it is bound directly for now.
        """
        if not self.started:
            return
        from .construction import ConstructionScreen

        self.push_screen(
            ConstructionScreen(self.game, self.game.Player), self._after_command
        )

    def action_warp_links(self) -> None:
        """Warp link frequencies (CONSTR.PAS `WarpLinkFrequencyCommand`)."""
        if not self.started:
            return
        from .construction import WarpLinkScreen

        self.push_screen(
            WarpLinkScreen(self.game, self.game.Player), self._after_command
        )

    def _cursor_object(self) -> "IDNumber | None":
        """What the map cursor is over, if it is a world or a base.

        The close-up and production screens act on this, which is how the
        original reaches them: the map hands them an `IDNumber`.
        """
        from ..galaxy import XYCoord
        from ..primintr import get_object
        from ..types import ObjectTypes

        x, y = self.map_view.cursor_x, self.map_view.cursor_y
        if not self.game.Galaxy.in_galaxy(x, y):
            return None

        obj = get_object(self.game, XYCoord(x, y))
        if obj.ObjTyp not in (ObjectTypes.Pln, ObjectTypes.Base):
            return None
        return obj

    def action_close_up(self) -> None:
        """The world close-up (CLSCOMM.PAS), on whatever the cursor is over."""
        if not self.started:
            return
        obj = self._cursor_object()
        if obj is None:
            return
        from .closeup import CloseUpScreen

        self.push_screen(
            CloseUpScreen(self.game, self.game.Player, obj), self._after_command
        )

    def action_production(self) -> None:
        """The production screen (CLSCOMM.PAS), on whatever the cursor is over."""
        if not self.started:
            return
        obj = self._cursor_object()
        if obj is None:
            return
        from .closeup import ProductionScreen

        self.push_screen(
            ProductionScreen(self.game, self.game.Player, obj), self._after_command
        )

    def action_fleets(self) -> None:
        """The fleet list and its nine commands (FLTCOMM.PAS)."""
        if not self.started:
            return
        from .fleet import FleetScreen

        self.push_screen(
            FleetScreen(self.game, self.game.Player), self._after_command
        )

    def action_defenses(self) -> None:
        """The orbital shell distribution editor (MSCCOMM.PAS)."""
        if not self.started:
            return
        from .defenses import DefenseScreen

        self.push_screen(
            DefenseScreen(self.game, self.game.Player), self._after_command
        )

    def action_self_destruct(self) -> None:
        """Scuttle a starbase or stargate (MSCCOMM.PAS)."""
        if not self.started:
            return
        from .defenses import SelfDestructScreen

        self.push_screen(
            SelfDestructScreen(self.game, self.game.Player), self._after_command
        )

    def _after_command(self, _result=None) -> None:
        """A command screen closed: the galaxy may have changed under the map."""
        self.prologue.game_modified = True
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
        from ..loadsave import auto_backup
        from ..main import update_turn

        if not self.started:
            return

        update_turn(self.game)
        self.prologue.game_modified = True

        # ANACREON.PAS runs AutoBackup after every completed turn.
        for warning in auto_backup(self.game):
            from .prologue import Attention

            self.push_screen(Attention(warning))

        self._refresh_all()
