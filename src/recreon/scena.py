"""Scenario background text: the authored prose behind a world. SCENA.PAS.

A scenario file can carry a ``WORLDBACKGROUNDINDEX``, mapping objects to blocks
of authored text, and two screens consult it: the close-up (CLSCOMM.PAS) and
the conquest message (ATTCOMM.PAS's ``EnemyConquered``). **Seven of the
thirteen shipped scenarios have one**, so this is not a corner feature -- until
it landed, every conquest in those scenarios got the generic victory speech in
place of the text the author wrote for it.

The index looks like this (`JAKARTA.SCN`)::

    WorldBackgroundIndex
    2:1 E:0          4      ; CloseUp: Empire 1 capital
    2:3 A:2          8      ; Attack: Jakarta
    2:6 E:0,1,8      3      ; CloseUp: Old empire capital
    EndIndex

First field is the object as ``type:index`` (``2:1`` is planet 1, matching
:class:`~recreon.types.ObjectTypes`); last field is the text block to show;
everything between is conditions, all of which must hold. **The conditions
split the two callers apart**: ``E`` fires only on a close-up, ``A`` only on a
conquest, ``O`` only on a close-up of a world the viewer owns. So one index
serves both screens without either needing to know about the other.

**The empire ordinals in an index are 0-based and include Indep as 8**, which
is `Empire`'s own numbering. ``E:8`` reads "while this world is independent".

**A conquest is evaluated before the conquest happens.** `CleanUp` calls
`EnemyConquered` and only then `ResolveAttack`, so ``GetStatus`` still returns
the *defender*. That is what makes ``A:8`` -- "attacking an independent world"
-- mean what its comment says it means.

**Nothing here writes to the screen, unlike the original.** `DisplayText` took
``x, y, Col`` and drove `WriteString` line by line; this returns the lines and
lets the caller place them. The rest of the unit -- reading the file, finding
the block, substituting into it -- ports directly.
"""

from __future__ import annotations

from pathlib import Path

from .environ import GameEnvironment
from .galaxy import limbo
from .misc import same_id, same_xy
from .primintr import get_coord, get_coord_name, get_status, object_name
from .types import Empire, IDNumber, ObjectTypes, empty_quadrant
from .utils.pascal import pascal_val

#: Whitespace `SplitLine` splits on. Tabs matter: `AWAKEN.SCN` and `Nebula.SCN`
#: both align their index columns with them.
WHITESPACE = "\t\n\r "

#: The line that opens the index, the one that closes it, and the marker that
#: ends a text block. All three are matched as *substrings* of a line, upper
#: cased, which is why a scenario can decorate them with comments.
INDEX_HEADER = "WORLDBACKGROUNDINDEX"
INDEX_FOOTER = "ENDINDEX"
TEXT_FOOTER = "ENDTEXT"


def _val(s: str) -> int | None:
    """``Val`` with its ``Error`` folded into the result.

    Every call in this unit is written ``Val(...); IF Error=0 THEN``, so a
    failed parse is a normal outcome rather than an exception -- an index full
    of comment rulers and blank lines depends on it.
    """
    try:
        return pascal_val(s)
    except ValueError:
        return None


def scenario_path(game: GameEnvironment) -> Path | None:
    """Where the scenario file for this game is. ``AddDefaultPath``.

    `ScenaFilename` is saved with the game (ENVIRON.PAS:133), so a save
    reloaded years later still knows which scenario to read its background
    text from. The port stores a full path there and `SceDirect` is only a
    fallback for a bare name.
    """
    if not game.ScenaFilename:
        return None

    path = Path(game.ScenaFilename)
    if not path.is_absolute() and game.SceDirect:
        path = Path(game.SceDirect) / path
    return path if path.is_file() else None


def read_lines(path: Path) -> list[str]:
    """The whole file, as lines.

    The original walks an open ``TEXT`` file with `ReadLn` and a live file
    position; this reads it once and carries an index instead, which is the
    same traversal without the handle. Latin-1 to match the loader -- scenario
    files are CP437 and every byte must round-trip.
    """
    with path.open("r", encoding="latin-1") as handle:
        return handle.read().splitlines()


def find_line(lines: list[str], start: int, to_find: str) -> int:
    """``FindLine``: the index *after* the first line containing ``to_find``.

    Returns -1 for the original's ``Error=100``. The match is a
    case-insensitive **substring** test, not equality -- which is why
    ``TEXT 1`` would also match a line reading ``TEXT 10``. Blocks are
    searched forward from where the last one left off, so in a file whose
    blocks run in order the right one is always found first.
    """
    wanted = to_find.upper()
    for i in range(start, len(lines)):
        if wanted in lines[i].upper():
            return i + 1
    return -1


def split_line(line: str) -> list[str]:
    """``SplitLine``: strip the ``;`` comment, split on whitespace.

    Returns the parameters with no empty entries, so ``len()`` is the
    original's ``NoOfParms``. A line that is nothing but a comment gives one
    empty parameter, as the original's does -- `Nebula.SCN` opens its index
    with a ``;ID Criteria Text`` ruler that relies on this being harmless.
    """
    comment = line.find(";")
    if comment >= 0:
        line = line[:comment]

    # Split on `SplitLine`'s own four characters rather than on `str.split()`'s
    # notion of whitespace, which also breaks on vertical tab and form feed. No
    # shipped scenario contains either, but a form feed is an ordinary page
    # break in a DOS-era text file and would split a field the original keeps
    # whole.
    parms: list[str] = []
    current = ""
    for char in line:
        if char in WHITESPACE:
            if current:
                parms.append(current)
                current = ""
        else:
            current += char
    if current:
        parms.append(current)

    return parms or [""]


def id_match(id_str: str) -> IDNumber:
    """``IDMatch``: ``type:index`` to an ID, or EmptyQuadrant if it is neither.

    ``2:6`` is planet 6. The numbers are `ObjectTypes` ordinals, so an index
    entry is written against the enum rather than against any name.
    """
    colon = id_str.find(":")
    if colon < 0:
        return empty_quadrant()

    typ = _val(id_str[:colon])
    index = _val(id_str[colon + 1 :])
    if typ is None or index is None:
        return empty_quadrant()

    try:
        return IDNumber(ObjectTypes(typ), index)
    except ValueError:
        # `ObjectTypes(a)` on an out-of-range ordinal is unchecked in the
        # original and yields a nonsense type that matches nothing. Refusing
        # it here reaches the same outcome without the nonsense.
        return empty_quadrant()


def interpret_set(parm: str) -> set[int]:
    """``InterpretSet``: ``0,1,8`` to ``{0, 1, 8}``.

    Anything that does not parse as 0..255 is dropped rather than reported,
    which is what makes ``E:ALL`` fall through to the special case in
    :func:`build_empire_set` with an empty set rather than an error.
    """
    numbers: set[int] = set()
    for piece in parm.split(","):
        value = _val(piece)
        if value is not None and 0 <= value <= 255:
            numbers.add(value)
    return numbers


def build_empire_set(parm: str) -> set[Empire]:
    """``BuildEmpireSet``: the empires named by an ``E:``/``A:`` condition.

    ``Copy(Parm,3,32)`` drops the two-character tag, so this is handed
    ``0,1,8`` or ``ALL``. ``ALL`` means every empire *including* Indep, and is
    tested after the numeric parse rather than instead of it.
    """
    parm = parm[2:]
    numbers = interpret_set(parm)

    if parm.upper() == "ALL":
        return set(Empire)
    return {emp for emp in Empire if int(emp) in numbers}


def satisfies_conditions(
    game: GameEnvironment,
    player: Empire,
    conquer: bool,
    obj_id: IDNumber,
    parms: list[str],
    first: int,
    last: int,
) -> bool:
    """``SatisfiesConditions``: do all of an entry's conditions hold?

    ``first`` and ``last`` are 1-based and inclusive, as the original's are.
    Three conditions exist and each one also decides *which caller* the entry
    is for:

    ``E:<empires>``
        Close-up only, and the object's owner must be in the set.
    ``A:<empires>``
        Conquest only, and the object's owner -- still the defender at this
        point -- must be in the set.
    ``O``
        Close-up only, and the viewing player must own the object.

    An unrecognised condition is **ignored rather than rejected**, so an entry
    whose conditions are all typos matches everything. Faithful; the original's
    ``CASE`` has no ``ELSE``.
    """
    ok = True
    for i in range(first, last + 1):
        if not 1 <= i <= len(parms):
            continue
        parm = parms[i - 1]
        if not parm:
            continue

        tag = parm[0].upper()
        if tag == "E":
            if conquer or get_status(game, obj_id) not in build_empire_set(parm):
                ok = False
        elif tag == "A":
            if not conquer or get_status(game, obj_id) not in build_empire_set(
                parm
            ):
                ok = False
        elif tag == "O":
            if conquer or player != get_status(game, obj_id):
                ok = False

    return ok


def parse_line(game: GameEnvironment, player: Empire, line: str) -> str:
    """``ParseLine``: expand the ``[C…]`` and ``[N…]`` substitutions.

    ``[C2:6]`` becomes planet 6's coordinates and ``[N2:6]`` its name, both as
    this player would see them -- so authored text can point at a world without
    knowing where the generator put it. An object that is nowhere becomes five
    spaces, which is how a scenario referring to something that was never
    created degrades instead of breaking. `Nebula.SCN` leans on this: it names
    twenty starbases and eighteen stargates that a given game may not have.

    **A bracket without its partner hangs the original** -- see issue #77. The
    port stops instead, leaving the rest of the line as written.
    """
    while True:
        open_b = line.find("[")
        close_b = line.find("]")
        if open_b < 0 and close_b < 0:
            break
        if open_b < 0 or close_b < open_b:
            # The original loops forever here. Nothing to expand; stop.
            break

        old = line[open_b : close_b + 1]
        line = line[:open_b] + line[close_b + 1 :]

        tag = old[1:2].upper()
        replacement = ""
        if tag in ("C", "N"):
            obj_id = id_match(old[2:-1])
            xy = get_coord(game, obj_id)
            if same_xy(xy, limbo()):
                replacement = "     "
            elif tag == "C":
                replacement = get_coord_name(game, xy)
            else:
                replacement = object_name(game, player, obj_id, long_format=True)

        line = line[:open_b] + replacement + line[open_b:]

    return line


def display_text(
    game: GameEnvironment,
    player: Empire,
    lines: list[str],
    start: int,
    text_number: int,
) -> list[str]:
    """``DisplayText``: the numbered block, with substitutions expanded.

    Searching starts at ``start`` -- the line after the index entry that
    matched, not after the index -- because that is where the original's file
    position is. Every text block therefore has to sit *below* the index, and
    in all seven shipped scenarios it does.

    The ``ENDTEXT`` line closes the block and is not part of it. A block whose
    ``ENDTEXT`` is missing runs to the end of the file here; the original reads
    past EOF and raises an I/O error.
    """
    pos = find_line(lines, start, f"TEXT {text_number}")
    if pos < 0:
        return []

    out: list[str] = []
    while pos < len(lines):
        line = lines[pos]
        if TEXT_FOOTER in line.upper():
            break
        out.append(parse_line(game, player, line))
        pos += 1

    return out


def display_background(
    game: GameEnvironment,
    player: Empire,
    world_id: IDNumber,
    conquer: bool,
) -> list[str] | None:
    """``DisplayBackground``: the authored text for this object, if any.

    Returns the lines, or **None** for the original's ``Found := False`` --
    which is the signal both callers key off. The conquest message shows its
    generic speech only when this comes back empty-handed, and the close-up
    simply appends nothing.

    **The first matching entry wins**, and the scan stops there. `EASTWEST.SCN`
    depends on it: worlds 2 through 7 appear twice, once under ``E:0`` and once
    under ``E:1``, so which text a player gets depends on who owns the world
    rather than on which line came first.

    A missing file, a scenario with no index, or no matching entry all give
    None. None of them is an error -- six of the thirteen shipped scenarios
    have no index at all.
    """
    path = scenario_path(game)
    if path is None:
        return None

    try:
        lines = read_lines(path)
    except OSError:
        return None

    pos = find_line(lines, 0, INDEX_HEADER)
    if pos < 0:
        return None

    while pos < len(lines):
        entry = lines[pos].upper()
        pos += 1

        parms = split_line(entry)
        if same_id(id_match(parms[0]), world_id) and satisfies_conditions(
            game, player, conquer, world_id, parms, 2, len(parms) - 1
        ):
            text_number = _val(parms[-1])
            if text_number is not None:
                return display_text(game, player, lines, pos, text_number)

        if INDEX_FOOTER in entry:
            break

    return None


def load_scena_text(game: GameEnvironment, text_number: int) -> list[str]:
    """``LoadScenaText``: a text block by number, with no index lookup.

    **No live caller.** The only one is CODE.PAS's ``Display`` action, part of
    the artifact scripting VM that is commented out of the scenario dispatch in
    v2.0 -- the same dead subsystem that leaves `cdetypes.py` with no caller.
    Ported because it is in the unit's interface.

    Note this one does *not* expand substitutions: `DisplayBackground`'s path
    runs `ParseLine` over every line and this one does not, so ``[C2:6]`` would
    reach the screen literally. That asymmetry is the original's.
    """
    path = scenario_path(game)
    if path is None:
        # The original calls `Close` on the unopened file here and crashes with
        # runtime error 103. See issue #78.
        return []

    try:
        lines = read_lines(path)
    except OSError:
        return []

    pos = find_line(lines, 0, f"TEXT {text_number}")
    if pos < 0:
        return []

    out: list[str] = []
    while pos < len(lines):
        if TEXT_FOOTER in lines[pos].upper():
            break
        out.append(lines[pos])
        pos += 1

    return out


__all__ = [
    "INDEX_FOOTER",
    "INDEX_HEADER",
    "TEXT_FOOTER",
    "WHITESPACE",
    "build_empire_set",
    "display_background",
    "display_text",
    "find_line",
    "id_match",
    "interpret_set",
    "load_scena_text",
    "parse_line",
    "read_lines",
    "satisfies_conditions",
    "scenario_path",
    "split_line",
]
