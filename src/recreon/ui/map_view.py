"""Galaxy map widget.

Simplified port of MAPWIND.PAS: renders the sector grid with a movable
cursor. Fog of war, name labels, minefield and nebula shading, and the
close-up views come later.
"""

from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget

from ..datacnst import BaseTypeData, ClassStr, GateTypeData
from ..environ import GameEnvironment
from ..galaxy import XYCoord, nebula_of
from ..primintr import get_class, get_object
from ..types import ObjectTypes

#: Shown where a sector holds nothing.
EMPTY_GLYPH = "·"

#: Fallback glyphs for object kinds with no table of their own in DATACNST.
OBJECT_GLYPHS = {
    ObjectTypes.Con: "?",
    ObjectTypes.BlkHl: "*",
    ObjectTypes.Plsr: "!",
    ObjectTypes.WrmHl: "%",
    ObjectTypes.Flt: "+",
    ObjectTypes.Wndr: "&",
    ObjectTypes.ArtOBJ: "$",
}


#: Bytes 0x01-0x1F render as graphical symbols in the IBM PC font, but the
#: cp437 *codec* maps them to C0 control characters instead. The stargate
#: glyphs live in this range (0x12 and 0x18), so they need the real table.
_CP437_CONTROL_GLYPHS = (
    "\0☺☻♥♦♣♠•◘○◙♂♀♪♫☼►◄↕‼¶§▬↨↑↓→←∟↔▲▼"
)


def cp437(code: int) -> str:
    """Decode a DOS code page 437 byte to the character it drew on screen."""
    if 0 <= code < len(_CP437_CONTROL_GLYPHS):
        return _CP437_CONTROL_GLYPHS[code]
    return bytes((code,)).decode("cp437")


class MapView(Widget):
    """A scrolling view of the galaxy.

    The viewport follows the cursor rather than scrolling independently,
    which is how the original behaves.
    """

    cursor_x: reactive[int] = reactive(1)
    cursor_y: reactive[int] = reactive(1)

    def __init__(self, game: GameEnvironment) -> None:
        super().__init__()
        self.game = game

    def move_cursor(self, dx: int, dy: int) -> None:
        """Move the cursor, stopping at the galaxy edge."""
        size = self.game.Galaxy.size
        if size <= 0:
            return
        self.cursor_x = max(1, min(size, self.cursor_x + dx))
        self.cursor_y = max(1, min(size, self.cursor_y + dy))

    def glyph_at(self, xy: XYCoord) -> str:
        """The character the original would draw for this sector."""
        obj = get_object(self.game, xy)

        match obj.ObjTyp:
            case ObjectTypes.Void:
                return EMPTY_GLYPH
            case ObjectTypes.Pln:
                return ClassStr[get_class(self.game, obj)]
            case ObjectTypes.Base:
                entity = self.game.Universe.Starbase[obj.Index]
                return cp437(BaseTypeData[entity.STyp])
            case ObjectTypes.Gate:
                entity = self.game.Universe.Stargate[obj.Index]
                return cp437(GateTypeData[entity.GTyp])
            case _:
                return OBJECT_GLYPHS.get(obj.ObjTyp, "?")

    def render(self) -> Text:
        galaxy = self.game.Galaxy
        if galaxy.size <= 0:
            return Text("No galaxy loaded.", style="dim")

        width = max(1, self.size.width // 2)
        height = max(1, self.size.height)

        # Centre the viewport on the cursor, then pull it back inside the map.
        left = max(1, min(galaxy.size - width + 1, self.cursor_x - width // 2))
        top = max(1, min(galaxy.size - height + 1, self.cursor_y - height // 2))
        left = max(1, left)
        top = max(1, top)

        text = Text()
        for y in range(top, min(galaxy.size, top + height - 1) + 1):
            for x in range(left, min(galaxy.size, left + width - 1) + 1):
                xy = XYCoord(x, y)
                glyph = self.glyph_at(xy)

                if x == self.cursor_x and y == self.cursor_y:
                    text.append(glyph, style="reverse")
                elif nebula_of(galaxy.sector(xy).Special):
                    text.append(glyph, style="blue")
                elif glyph == EMPTY_GLYPH:
                    text.append(glyph, style="dim")
                else:
                    text.append(glyph, style="bold")
                text.append(" ")
            text.append("\n")

        return text
