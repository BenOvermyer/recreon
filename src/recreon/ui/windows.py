"""The status windows, F1 through F10.

The Textual half of §8.3: SWINDOWS.PAS's seven overlays. What each one *shows*
lives in its own module -- :mod:`recreon.stawind`, :mod:`recreon.fltwind`,
:mod:`recreon.empwind`, :mod:`recreon.nwswind`, :mod:`recreon.nmswind`,
:mod:`recreon.hlpwind` -- and this is the part that puts it on screen.

**These are read-only.** Every one of the original's windows is too: they scroll
and they close, and nothing in them changes the game. That is why they can all
be one small screen class with a list of lines.

The one structural thing worth knowing is that **F3/F4 and F5/F6 are each a
single window showing two stacked tables**, not two windows. The port keeps
that -- both keys open the same screen, and both tables are on it -- because
splitting them would lose the fact that the two tables list the same objects in
the same order, which is what makes them readable together.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from ..empwind import EMPIRE_HEADER, empire_rows
from ..environ import GameEnvironment
from ..fltwind import CONTENTS_HEADER, POSITION_HEADER, fleet_rows
from ..hlpwind import (
    FALLBACK_PAGE,
    HELP_FILENAME,
    HELP_INDEX,
    page_bounds,
    page_count,
    read_help_page,
)
from ..intrface import (
    get_fleet_position_status,
    get_fleet_status_line,
    get_military_status,
    get_world_status,
)
from ..nmswind import name_lines
from ..nwswind import news_lines
from ..stawind import MILITARY_HEADER, STATUS_HEADER, status_rows
from ..swindows import WindowTypes
from ..types import Empire


class WindowScreen(Screen[None]):
    """One status overlay. Escape or F10 returns to the map.

    F10 closes rather than opening anything, because the map *is* the base
    screen here; the original's `ScanWND` is a window over a blank background,
    and Textual's equivalent of raising it is dismissing whatever is on top.
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("f10", "close", "Map"),
    ]

    CSS = """
    WindowScreen { layout: vertical; }
    #body { height: 1fr; padding: 1 2; }
    """

    #: Subclasses set this; it names the window in the header.
    window: WindowTypes = WindowTypes.NoWND

    def __init__(self, game: GameEnvironment, player: Empire) -> None:
        super().__init__()
        self.game = game
        self.player = player

    def compose(self) -> ComposeResult:
        yield Header()
        yield VerticalScroll(Static(id="sheet"), id="body")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Re:creon"
        self.redraw()

    def redraw(self) -> None:
        self.query_one("#sheet", Static).update("\n".join(self.lines()))

    def lines(self) -> list[str]:
        raise NotImplementedError

    def action_close(self) -> None:
        self.dismiss(None)


class StatusWindowScreen(WindowScreen):
    """F3/F4: world status over military status. STAWIND.PAS."""

    window = WindowTypes.StatusWND

    def lines(self) -> list[str]:
        rows = status_rows(self.game, self.player)
        if not rows:
            return ["No worlds."]

        out = ["World status", "", STATUS_HEADER]
        out += [get_world_status(self.game, self.player, r) for r in rows]
        out += ["", "Military status", "", MILITARY_HEADER]
        out += [get_military_status(self.game, self.player, r) for r in rows]
        return out


class FleetWindowScreen(WindowScreen):
    """F5/F6: where the fleets are, over what is aboard them. FLTWIND.PAS."""

    window = WindowTypes.FleetWND

    def lines(self) -> list[str]:
        rows = fleet_rows(self.game, self.player)
        if not rows:
            # Both halves say so, as `DrawFleetWindow` writes it twice.
            return ["No fleets have been deployed.", "", "No fleets have been deployed."]

        out = ["Fleet position", "", POSITION_HEADER]
        out += [get_fleet_position_status(self.game, self.player, r) for r in rows]
        out += ["", "Fleet contents", "", CONTENTS_HEADER]
        out += [get_fleet_status_line(self.game, self.player, r) for r in rows]
        return out


class EmpireWindowScreen(WindowScreen):
    """F8: the player's empire and every rival whose capital it has found."""

    window = WindowTypes.EmpireWND

    def lines(self) -> list[str]:
        return [EMPIRE_HEADER, ""] + empire_rows(self.game, self.player)


class NewsWindowScreen(WindowScreen):
    """F7: the year's headlines, galaxy news before housekeeping."""

    window = WindowTypes.NewsWND

    def lines(self) -> list[str]:
        return news_lines(self.game, self.player) or ["No news."]


class NamesWindowScreen(WindowScreen):
    """F9: everything the player has named, and where it is now."""

    window = WindowTypes.NamesWND

    def lines(self) -> list[str]:
        return name_lines(self.game, self.player)


class HelpWindowScreen(WindowScreen):
    """F1: the manual, if it is there.

    `ANACREON.HLP` does not ship with the source, so the usual outcome is the
    fallback list of function keys -- which is exactly what a player without
    the file saw. If a help file *is* present in the configured directory it is
    read in the original's record format and paged with PgUp/PgDn.

    The index is shown either way. It is a record of what the manual covered,
    and it is the only surviving description of the file's contents.
    """

    window = WindowTypes.HelpWND

    # `priority` matters: the body is a focused `VerticalScroll`, which binds
    # the page keys for scrolling and would swallow them. Here they move
    # between pages of a file, which is navigation the scroll cannot do.
    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("f10", "close", "Map"),
        Binding("pageup", "page(False)", "Prev page", priority=True),
        Binding("pagedown", "page(True)", "Next page", priority=True),
    ]

    def __init__(self, game: GameEnvironment, player: Empire) -> None:
        super().__init__(game, player)
        self.page_no = 1
        self.help_path = self._locate()
        self.total_pages = page_count(self.help_path) if self.help_path else 0

    def _locate(self) -> str | None:
        from pathlib import Path

        directory = Path(self.game.HlpDirect) if self.game.HlpDirect else Path.cwd()
        candidate = directory / HELP_FILENAME
        return str(candidate) if candidate.is_file() else None

    def lines(self) -> list[str]:
        if self.help_path:
            page = read_help_page(self.help_path, self.page_no)
            if page is not None:
                return [
                    f"Page {self.page_no} of {self.total_pages - 1}",
                    "",
                    *page,
                ]

        return [
            *FALLBACK_PAGE,
            "",
            "Index (topic, and the page it was on):",
            *[f"  {topic:<20}{page:>3}" for topic, page in HELP_INDEX],
        ]

    def action_page(self, forward: bool) -> None:
        if not self.help_path:
            return
        self.page_no = page_bounds(self.page_no, self.total_pages, forward)
        self.redraw()


#: Which screen each window type opens.
WINDOW_SCREENS: dict[WindowTypes, type[WindowScreen]] = {
    WindowTypes.HelpWND: HelpWindowScreen,
    WindowTypes.StatusWND: StatusWindowScreen,
    WindowTypes.FleetWND: FleetWindowScreen,
    WindowTypes.NewsWND: NewsWindowScreen,
    WindowTypes.EmpireWND: EmpireWindowScreen,
    WindowTypes.NamesWND: NamesWindowScreen,
}


__all__ = [
    "WINDOW_SCREENS",
    "EmpireWindowScreen",
    "FleetWindowScreen",
    "HelpWindowScreen",
    "NamesWindowScreen",
    "NewsWindowScreen",
    "StatusWindowScreen",
    "WindowScreen",
]
