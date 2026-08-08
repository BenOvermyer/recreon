"""The status-window family, ported from SWINDOWS.PAS.

SWINDOWS.PAS is the dispatcher over the seven overlay windows a player could
raise on top of the map: it translates a function key into a window and a
command, and routes the command to that window's handler.

What survives the port is that translation table -- which key opens what -- and
the window enum. The rest of the unit is DOS machinery with no counterpart:
`GetInkey` and the input stream that feeds it, `UpdateClock`, `StopClock` /
`StartClock`, the window-handle bookkeeping of WND.PAS. Textual owns all of
that.

**The scroll commands are ported as an enum but the port does not dispatch on
them.** `PageUpWCM`, `CursorDownWCM` and their siblings exist because each
Pascal window hand-rolls its own scrolling over a fixed-height text buffer,
tracking `BeginIndex`/`EndIndex` itself. A Textual `VerticalScroll` does that,
so the commands are recorded here for reference rather than reimplemented --
with one exception: the help window's page keys, which move between *pages of a
file* rather than lines of a list, and so are real navigation. See
:mod:`recreon.hlpwind`.
"""

from __future__ import annotations

from enum import IntEnum


class WindowTypes(IntEnum):
    """The seven overlay windows. Ordinals are the original's."""

    NoWND = 0
    HelpWND = 1
    ScanWND = 2
    StatusWND = 3
    FleetWND = 4
    NewsWND = 5
    EmpireWND = 6
    NamesWND = 7


class WindowCommand(IntEnum):
    """Pascal's ``WCM`` constants from WNDTYPES.PAS, with their values."""

    NoWCM = 0
    OpenWCM = 1
    ActivateWCM = 2
    CloseWCM = 3
    ScrllUpWCM = 4
    ScrllDownWCM = 5
    ScrllLeftWCM = 6
    ScrllRightWCM = 7
    CenterWCM = 8
    SelectWCM = 9
    PageUpWCM = 10
    PageDownWCM = 11
    PageLeftWCM = 12
    PageRightWCM = 13
    CursorDownWCM = 14
    CursorLeftWCM = 15
    CursorRightWCM = 16
    CursorUpWCM = 17
    EndWCM = 18
    DeActWCM = 19


#: Which function key raises which window. Port of ``GetWindowCommand``'s
#: `CASE ExtCh OF`.
#:
#: Two pairs share a window, and the reason is worth knowing: **F3 and F4 open
#: the same window**, and so do **F5 and F6**, because each of those windows
#: shows two stacked tables -- world status over military status, fleet
#: position over fleet contents -- rather than two windows. The player has one
#: key per table out of habit; the code has one window.
#:
#: F2 is absent. The original's help text lists it as "Return to Menu", which
#: is PULLDOWN.PAS's bar, not a status window.
WINDOW_KEYS: dict[str, WindowTypes] = {
    "f1": WindowTypes.HelpWND,
    "f3": WindowTypes.StatusWND,
    "f4": WindowTypes.StatusWND,
    "f5": WindowTypes.FleetWND,
    "f6": WindowTypes.FleetWND,
    "f7": WindowTypes.NewsWND,
    "f8": WindowTypes.EmpireWND,
    "f9": WindowTypes.NamesWND,
    "f10": WindowTypes.ScanWND,
}

#: What each window is called on screen, from its unit's ``InitTitle``.
WINDOW_TITLES: dict[WindowTypes, str] = {
    WindowTypes.HelpWND: "ANACREON: Help",
    WindowTypes.ScanWND: "Map",
    WindowTypes.StatusWND: "World Status",
    WindowTypes.FleetWND: "Fleet Status",
    WindowTypes.NewsWND: "News",
    WindowTypes.EmpireWND: "Empire Status",
    WindowTypes.NamesWND: "Names",
}


def window_for_key(key: str) -> WindowTypes | None:
    """The window a function key raises, or ``None`` if it raises none."""
    return WINDOW_KEYS.get(key.lower())


__all__ = [
    "WINDOW_KEYS",
    "WINDOW_TITLES",
    "WindowCommand",
    "WindowTypes",
    "window_for_key",
]
