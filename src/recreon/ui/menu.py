"""The in-game menu bar.

Draws PLAYTURN.PAS's seven pull-downs and dispatches them to the screens
ported so far. The menu *structure* -- titles, order, accelerator letters --
is :mod:`recreon.playturn`; this is the part that opens things.

The original's bar is always on screen and reached with Alt. Textual has no
equivalent that works everywhere, so the bar opens as a screen on ``m`` (or
F10, the DOS convention), and the direct keys the earlier branches bound stay
as shortcuts.

**Commands whose implementation has not landed yet report so rather than
being hidden.** Leaving them visible keeps the menu a faithful picture of what
the game offers, and makes the gap legible.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

from ..playturn import MENU_BAR, NOT_PORTABLE, Command, MenuBarItem
from .prologue import Attention

#: What each unimplemented command says when chosen. Named individually so the
#: message tells the player *why*, rather than a blanket "not implemented".
PENDING = {
    Command.NAddCom: "Naming a place is not yet wired to a screen.",
    Command.NDelCom: "Removing a name is not yet wired to a screen.",
    Command.AboutCom: (
        "Re:creon -- a Python recreation of Anacreon: Reconstruction 4021 "
        "(v2.0, January 2004)."
    ),
}


class MenuScreen(Screen[None]):
    """The seven pull-downs. Pick a menu, then a command."""

    BINDINGS = [Binding("escape", "back", "Back")]

    CSS = """
    MenuScreen { layout: vertical; }
    #bar { height: auto; padding: 1 2; text-style: bold; }
    #items { height: 1fr; padding: 0 2; }
    #hint { height: auto; padding: 0 2; color: $text-muted; }
    """

    def __init__(self, game, player) -> None:
        super().__init__()
        self.game = game
        self.player = player
        self.menu: MenuBarItem | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="bar")
        # One ListView for the whole screen, refilled rather than remounted:
        # removing it and mounting another leaves focus on the removed widget,
        # so the bar would open but its items would not run.
        yield ListView(id="items")
        yield Static(id="hint")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Re:creon"
        self._show_bar()

    # --- The bar --------------------------------------------------------------

    def _fill(self, rows: list[tuple[str, str]], hint: str) -> None:
        """Refill the one list with (key, label) rows."""
        listing = self.query_one("#items", ListView)
        listing.clear()
        listing.extend(
            [
                ListItem(Label(f"{key}   {label}"), name=str(i))
                for i, (key, label) in enumerate(rows)
            ]
        )
        listing.index = 0
        self.query_one("#hint", Static).update(hint)
        self.set_focus(listing)

    def _show_bar(self) -> None:
        self.menu = None
        self.query_one("#bar", Static).update(
            "   ".join(bar.title for bar in MENU_BAR)
        )
        self._fill(
            [(bar.key, bar.title) for bar in MENU_BAR], "Enter: open   Esc: close"
        )

    def _show_menu(self, bar: MenuBarItem) -> None:
        self.menu = bar
        self.query_one("#bar", Static).update(bar.title)
        self._fill(
            [(item.key, item.label) for item in bar.items], "Enter: run   Esc: back"
        )

    @on(ListView.Selected)
    def _selected(self, event: ListView.Selected) -> None:
        index = int(event.item.name)
        if self.menu is None:
            self._show_menu(MENU_BAR[index])
        else:
            self.run_command(self.menu.items[index].command)

    def action_back(self) -> None:
        if self.menu is None:
            self.dismiss(None)
        else:
            self._show_bar()

    # --- Dispatch -------------------------------------------------------------

    def run_command(self, command: Command) -> None:
        """Port of ``PlayerTakesTurn``'s `CASE Comm OF`, for what exists.

        Commands that open a screen dismiss the menu first, so the screen
        lands on the map rather than on top of the bar.
        """
        app = self.app

        if command in NOT_PORTABLE:
            self.app.push_screen(
                Attention("That was a DOS feature with no equivalent here.")
            )
            return

        if command in PENDING:
            self.app.push_screen(Attention(PENDING[command]))
            return

        # Game
        if command is Command.EndCom:
            self._close_then(app.action_next_turn)
            return
        if command is Command.XXXCom:
            self._close_then(app.action_prologue)
            return
        if command is Command.PauseCom:
            from ..prolog import toggle_pause

            self.app.push_screen(Attention(toggle_pause(self.game, app.prologue)))
            return

        # Worlds
        if command is Command.DesignateCom:
            self._close_then(app.action_designate)
        elif command is Command.TerraCom:
            self._close_then(app.action_terraform)
        elif command is Command.SelfSufCom:
            self._close_then(app.action_issp)
        elif command is Command.GrantIndepCom:
            self._close_then(app.action_liberate)
        # Empire
        elif command is Command.STechCom:
            self._close_then(app.action_trade_technology)
        elif command is Command.MSendCom:
            self._close_then(app.action_send_message)
        elif command is Command.MReadCom:
            self._close_then(app.action_read_messages)
        elif command is Command.InfoCom:
            self._close_then(app.action_close_up)
        elif command is Command.ProdInfoCom:
            self._close_then(app.action_production)
        elif command is Command.SelfDestCom:
            self._close_then(app.action_self_destruct)
        # Empire
        elif command is Command.WarpLinkFreqCom:
            self._close_then(app.action_warp_links)
        # Fleet -- every fleet command lives on the one screen
        elif command in (
            Command.FLaunchCom,
            Command.FDestCom,
            Command.FTransCom,
            Command.FAbortCom,
            Command.FFuelCom,
            Command.SRMSweepCom,
            Command.OrderCom,
            Command.CancelOrdCom,
            Command.ProbeCom,
        ):
            self._close_then(app.action_fleets)
        # Build
        elif command in (Command.ConStaCom, Command.CAddCom, Command.CAbortCom):
            self._close_then(app.action_construction)
        # Ministry of War
        elif command is Command.LAMCom:
            self._close_then(app.action_launch_lams)
        elif command is Command.AttackCom:
            self._close_then(app.action_attack)
        elif command is Command.AutoAttackCom:
            self._close_then(app.action_auto_attack)
        elif command is Command.DefnsCom:
            self._close_then(app.action_defenses)

    def _close_then(self, action) -> None:
        """Dismiss the menu, then run ``action``.

        Deferred rather than run straight after `dismiss`: the pop is
        processed on the next refresh, so pushing immediately would land the
        new screen *under* the menu and it would be popped along with it.
        """
        self.dismiss(None)
        self.app.call_after_refresh(action)
