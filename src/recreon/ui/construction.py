"""Construction screens.

The Textual half of CONSTR.PAS. What the commands do is
:mod:`recreon.constr`; this draws the status table and collects the two things
the player has to supply -- what to build, and where.

Reached from the map with ``b`` (construction) and ``w`` (warp link
frequencies). The original hangs them off the Build and Empire pull-downs;
those are MENU.PAS and still to come, so these are bound directly for now.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

from ..constr import (
    CONSTR_STATUS_HEADER,
    ConsName,
    FrequencyError,
    abort_construction_command,
    available_constr_types,
    constr_status_rows,
    construct_command,
    no_construction_sites_message,
    no_stargates_message,
    sector_is_free,
    set_warp_link_frequency,
    warp_link_advice,
    warp_link_freq_list,
)
from ..environ import GameEnvironment
from ..galaxy import XYCoord
from ..primintr import absolute_x, absolute_y, my_lord
from ..types import Empire
from .prologue import Attention, ChooseFrom, TextPrompt


class ConstructionScreen(Screen[None]):
    """Construction status, with the construct and abort commands on it.

    Port of ``ConstrStatusCommand``'s table, plus the entry points to
    ``ConstructCommand`` and ``AbortConstructionCommand``.
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("c", "construct", "Construct"),
        Binding("a", "abort", "Abort site"),
    ]

    CSS = """
    ConstructionScreen { layout: vertical; }
    #heading { height: auto; padding: 1 2; text-style: bold; }
    #table { height: 1fr; padding: 0 2; }
    .header { text-style: bold; }
    """

    def __init__(self, game: GameEnvironment, player: Empire) -> None:
        super().__init__()
        self.game = game
        self.player = player

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Construction Status:", id="heading")
        yield VerticalScroll(id="table")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Re:creon"
        self._rebuild()

    def _rebuild(self) -> None:
        table = self.query_one("#table", VerticalScroll)
        table.remove_children()

        self.rows = constr_status_rows(self.game, self.player)
        if not self.rows:
            table.mount(
                Static(no_construction_sites_message(self.game, self.player))
            )
            return

        table.mount(
            *[Static(line, classes="header") for line in CONSTR_STATUS_HEADER],
            ListView(
                *[
                    ListItem(Label(row.as_line()), name=str(i))
                    for i, row in enumerate(self.rows)
                ]
            ),
        )
        self.set_focus(table.query_one(ListView))

    def action_close(self) -> None:
        self.dismiss(None)

    # --- Construct ------------------------------------------------------------

    def action_construct(self) -> None:
        options = available_constr_types(self.game, self.player)
        if not options:
            self.app.push_screen(
                Attention(
                    f"{my_lord(self.game, self.player)}, you don't have the "
                    "technology to build anything!"
                )
            )
            return

        self.app.push_screen(
            ChooseFrom(
                "What kind of construction do you wish to start?",
                [(kind, label) for kind, label in options],
            ),
            self._type_chosen,
        )

    def _type_chosen(self, kind) -> None:
        if kind is None:
            return

        def located(text: str | None) -> None:
            if not text:
                return
            xy = self._interpret_xy(text)
            if xy is None:
                self.app.push_screen(
                    Attention("Please give a coordinate as x,y.")
                )
                return
            if not sector_is_free(self.game, xy):
                self.app.push_screen(
                    Attention(
                        f"{my_lord(self.game, self.player)}, that sector is "
                        "already occupied."
                    )
                )
                return

            report = construct_command(self.game, self.player, kind, xy)
            if report is None:
                self.app.push_screen(
                    Attention("There is no room for another construction site.")
                )
                return

            self._rebuild()
            self.app.push_screen(
                Attention(report.headline(), "\n".join(report.lines()))
            )

        self.app.push_screen(
            TextPrompt(
                "Where do you wish to begin the construction?",
                detail=f"Starting {ConsName[kind]}. Coordinates are relative "
                "to your capital.",
            ),
            located,
        )

    def _interpret_xy(self, text: str) -> XYCoord | None:
        """Port of DISPLAY.PAS ``InterpretXY``, for the one form it needs.

        Player-facing coordinates are relative to the capital, and the two
        axes do not convert the same way -- +Y is north for the player while
        row 1 is at the top -- so this goes through the pair that knows.
        """
        parts = text.replace(" ", "").split(",")
        if len(parts) != 2:
            return None
        try:
            rel_x, rel_y = int(parts[0]), int(parts[1])
        except ValueError:
            return None

        xy = XYCoord(absolute_x(self.game, rel_x), absolute_y(self.game, rel_y))
        return xy if self.game.Galaxy.in_galaxy(xy.x, xy.y) else None

    # --- Abort ----------------------------------------------------------------

    def action_abort(self) -> None:
        if not self.rows:
            return

        try:
            listing = self.query_one("#table", VerticalScroll).query_one(ListView)
        except Exception:
            return

        row = self.rows[listing.index or 0]

        def confirmed(yes: bool) -> None:
            if not yes:
                return
            message = abort_construction_command(self.game, self.player, row.con_id)
            self._rebuild()
            self.app.push_screen(Attention(message))

        self.app.push_screen(
            Attention(
                f"Are you sure you want to abort {row.name}?",
                ConsName[row.kind],
                confirm=True,
            ),
            confirmed,
        )


class WarpLinkScreen(Screen[None]):
    """Every stargate the player knows of, and the frequency tuned to it.

    Port of ``WarpLinkFrequencyCommand``. Other empires' gates are listed too:
    matching your frequency to theirs is how you get to use their gate.
    """

    BINDINGS = [Binding("escape", "close", "Close")]

    CSS = """
    WarpLinkScreen { layout: vertical; }
    #heading { height: auto; padding: 1 2; text-style: bold; }
    #list { height: 1fr; padding: 0 2; }
    """

    def __init__(self, game: GameEnvironment, player: Empire) -> None:
        super().__init__()
        self.game = game
        self.player = player

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Warp Link Frequencies:", id="heading")
        yield VerticalScroll(id="list")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Re:creon"
        self._rebuild()

    def _rebuild(self) -> None:
        listing = self.query_one("#list", VerticalScroll)
        listing.remove_children()

        self.entries = warp_link_freq_list(self.game, self.player)
        if not self.entries:
            listing.mount(Static(no_stargates_message(self.game, self.player)))
            return

        listing.mount(
            ListView(
                *[
                    ListItem(Label(entry.as_line()), name=str(i))
                    for i, entry in enumerate(self.entries)
                ]
            )
        )
        self.set_focus(listing.query_one(ListView))

    def action_close(self) -> None:
        self.dismiss(None)

    @on(ListView.Selected)
    def _selected(self, event: ListView.Selected) -> None:
        entry = self.entries[int(event.item.name)]

        def entered(text: str | None) -> None:
            if text is None:
                return
            try:
                set_warp_link_frequency(
                    self.game, self.player, entry.obj, int(text)
                )
            except (ValueError, FrequencyError) as exc:
                message = (
                    str(exc)
                    if isinstance(exc, FrequencyError)
                    else "Frequency must be between 0 and 9999."
                )
                self.app.push_screen(Attention(message))
                return

            self._rebuild()
            self.app.push_screen(
                Attention(
                    f"Our warp link frequency for {entry.name} has been set to "
                    f"{text}.",
                    "\n".join(warp_link_advice(self.game, self.player, entry.obj)),
                )
            )

        self.app.push_screen(
            TextPrompt(
                "Please enter the new frequency :",
                str(entry.frequency),
                detail=f"Our current frequency for {entry.name} is "
                f"{entry.frequency}.",
            ),
            entered,
        )
