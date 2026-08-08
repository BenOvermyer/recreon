"""The help window (F1), ported from HLPWIND.PAS.

**The help text itself does not exist.** `ANACREON.HLP` is not in the tree and
never was -- the original opens it at `HlpDirect`, a path the player configures
in the prologue, and ships it alongside the executable rather than in source.
So the branch this port can actually run is the *other* one: the fallback
`DisplayPage` writes when the file is missing, which is a summary of the
function keys. That is a real screen a real player saw, not a stub.

What is transcribed regardless is the **index**: fifteen topics and the page
each lived on. That is a genuine record of what the manual covered, and it is
what a reader would need to reconstruct the file. The reader is here too, so a
recovered `ANACREON.HLP` drops straight in.
"""

from __future__ import annotations

from pathlib import Path

#: The help file's own name, from ENVIRON.PAS.
HELP_FILENAME = "ANACREON.HLP"

#: Lines per page, from `HelpPage = ARRAY [1..19] OF LineStr`.
LINES_PER_PAGE = 19

#: Bytes per line: a Pascal `STRING[80]` is a length byte plus 80 characters.
BYTES_PER_LINE = 81

#: Bytes per page record, which is what `FILE OF HelpPage` seeks in.
BYTES_PER_PAGE = LINES_PER_PAGE * BYTES_PER_LINE

#: The index menu: topic, and the page it opens. Transcribed from
#: `GetIndexEntry`'s menu lines paired with `IndexPageNo`.
#:
#: Note the indented entries -- "Map" and "World Status" sit under "Windows" --
#: and that two pairs share a page: raw materials with materials (7), and ships
#: with defenses (6). The manual evidently treated each pair as one topic.
HELP_INDEX: tuple[tuple[str, int], ...] = (
    ("Combat", 11),
    ("Construction", 10),
    ("Defenses", 6),
    ("Fleet Orders", 12),
    ("Function Keys", 2),
    ("ISSP", 13),
    ("Materials", 7),
    ("Raw Materials", 7),
    ("Ships", 6),
    ("Technology Levels", 5),
    ("Windows", 2),
    ("   Map", 8),
    ("   World Status", 9),
    ("World Classes", 4),
    ("World Types", 3),
)

#: What the window shows when there is no help file. Transcribed from
#: `DisplayPage`'s else branch.
#:
#: It lists F2 and F6 where :data:`recreon.swindows.WINDOW_KEYS` does not: F2
#: returns to the menu bar rather than opening a window, and F6 is folded into
#: F5's window. It also splits F3 and F4 into "Planetary" and "Military",
#: naming the two tables that share one window.
FALLBACK_PAGE: tuple[str, ...] = (
    "ANACREON Help file not available.",
    "",
    "<F1>    Help Window",
    "<F2>    Return to Menu",
    "<F3>    Planetary Status Window",
    "<F4>    Military Status Window",
    "<F5>    Fleet Status Window",
    "<F7>    News Window",
    "<F8>    Empire Status Window",
    "<F9>    Names Window",
    "<F10>   Map Window",
)


def read_help_page(path: Path | str, page_no: int) -> list[str] | None:
    """One page out of an `ANACREON.HLP`, or ``None`` if it cannot be read.

    The format is Turbo Pascal's `FILE OF HelpPage`: fixed 1539-byte records of
    nineteen `STRING[80]`s, each a length byte followed by 80 bytes of text.
    `Seek` is by record, so page *n* starts at ``n * 1539``.

    **Page 0 is unreachable from the UI.** `PageNo` starts at 1 and
    :func:`page_bounds` never lets it below that, so whatever occupies the
    first record was never displayed.
    """
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError:
        return None

    start = page_no * BYTES_PER_PAGE
    if start < 0 or start + BYTES_PER_PAGE > len(data):
        return None

    page = []
    for i in range(LINES_PER_PAGE):
        offset = start + i * BYTES_PER_LINE
        length = data[offset]
        page.append(data[offset + 1 : offset + 1 + length].decode("cp437", "replace"))
    return page


def page_count(path: Path | str) -> int:
    """How many page records a help file holds. Pascal's ``FileSize``."""
    try:
        return Path(path).stat().st_size // BYTES_PER_PAGE
    except OSError:
        return 0


def page_bounds(page_no: int, total_pages: int, forward: bool) -> int:
    """Step a page number. Port of ``PageUp``/``PageDown``.

    The names in the original are inverted against the keys: `PageUpWCM` calls
    the procedure named `PageDown`, which *decrements*. Pressing Page Up moves
    towards page 1, which is the natural reading -- it is only the procedure
    names that are backwards.

    The top bound is ``FileSize - 1``, the last valid record index.
    """
    if forward:
        return page_no + 1 if page_no < total_pages - 1 else page_no
    return page_no - 1 if page_no > 1 else page_no


__all__ = [
    "BYTES_PER_LINE",
    "BYTES_PER_PAGE",
    "FALLBACK_PAGE",
    "HELP_FILENAME",
    "HELP_INDEX",
    "LINES_PER_PAGE",
    "page_bounds",
    "page_count",
    "read_help_page",
]
