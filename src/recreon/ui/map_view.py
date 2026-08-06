"""Galaxy map widget.

Port of MAPWIND.PAS's map buffer. **Every sector is three columns wide** --
``[player fleet][world][enemy fleet]`` -- which is not a display choice but the
structure of the original's `MapCell`: six contiguous bytes (three characters
each with a colour attribute) that `DrawMapWindow` blits straight into video
memory with a single `Move`. It is also why the map cursor draws its corner
brackets at ±1 column: they bracket the middle, world column.

The buffer is composed by a fixed sequence of draw passes, and the order is
load-bearing because each one overwrites the last:

1. clear
2. the capital-relative grid
3. nebulae and minefields
4. worlds
5. the player's own fleets
6. starbases, stargates, construction sites
7. enemy fleets

So a starbase hides the nebula it sits in, and an enemy fleet is drawn over
everything -- in its own column, so it never hides a world.

**Fog of war here keys on ``KnownBy``, not ``ScoutedBy``.** The distinction
matters: an object you have merely *detected* still appears on the map. What
``Scouted`` buys is the detail panels, not the glyph. Worlds are the exception
that proves it -- an unknown world still shows as a generic ``p``, because
stars are visible from a distance even when nothing is known about them, but
that fallback is suppressed inside a nebula.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget

from ..datacnst import BaseTypeData, GateTypeData, TypeStr
from ..environ import GameEnvironment
from ..galaxy import XYCoord, nebula_of, srm_owner_of
from ..types import Empire, NebulaTypes

#: Sectors between grid rules, counted out from the capital.
GRID_SEP = 5

#: Glyphs, from MAPWIND.PAS's CONST block. The nebula table is indexed by
#: NebulaTypes: none, nebula, dark, dense.
NEBULA_CHAR = {
    NebulaTypes.NoNeb: " ",
    NebulaTypes.Nebula: "▒",
    NebulaTypes.DarkNebula: "░",
    NebulaTypes.DenseNebula: "░",
}
MINE_CHAR = "+"
PLAYER_FLEET_CHAR = "►"  # #016
ENEMY_FLEET_CHAR = "▼"  # #031
CONS_CHAR = "#"
BLANK_CHAR = " "
UNK_PLANET_CHAR = "p"

HORZ_CHAR = "·"  # #250
VERT_CHAR = "·"
CROSS_CHAR_1 = "─"  # #196
CROSS_CHAR_2 = "┼"  # #197
CROSS_CHAR_3 = "─"

#: The original's colour slots, as Rich styles. The DOS palette is 4-bit, so
#: these are an interpretation rather than a transcription -- what has to
#: survive is that the six roles stay visually distinct.
PLAYER_STYLE = "bold white"
PLAYER_FLEET_STYLE = "bold white"
ENEMY_STYLE = "bright_black"
UNSCOUTED_STYLE = "red"
NEBULA_STYLE = "magenta"
GRID_STYLE = "dim white"
BACKGROUND_STYLE = "dim"


@dataclass(slots=True)
class MapCell:
    """One sector's three columns and their colours."""

    player_flt: str = BLANK_CHAR
    player_flt_style: str = BACKGROUND_STYLE
    world: str = BLANK_CHAR
    world_style: str = BACKGROUND_STYLE
    enemy_flt: str = BLANK_CHAR
    enemy_flt_style: str = BACKGROUND_STYLE


def build_map(game: GameEnvironment, player: Empire) -> list[list[MapCell]]:
    """Compose the whole map buffer as ``player`` sees it.

    Indexed ``[y][x]`` with row and column 0 unused, matching the sector grid.
    Rebuilt in full rather than patched, as the original does: the draw passes
    iterate objects rather than sectors, so there is no cheaper incremental
    form that stays faithful.
    """
    size = game.Galaxy.size
    buffer = [[MapCell() for _ in range(size + 1)] for _ in range(size + 1)]

    _draw_grid(game, buffer, player)
    _draw_nebula_and_mines(game, buffer, player)
    _draw_planets(game, buffer, player)
    _draw_own_fleets(game, buffer, player)
    _draw_starbases(game, buffer, player)
    _draw_stargates(game, buffer, player)
    _draw_constructions(game, buffer, player)
    _draw_enemy_fleets(game, buffer, player)

    return buffer


def _draw_grid(
    game: GameEnvironment, buffer: list[list[MapCell]], player: Empire
) -> None:
    """Rule the map every 5 sectors, aligned so the capital sits on a crossing.

    Player-facing coordinates are relative to the capital, so the rules are
    what makes a typed destination findable by eye.
    """
    size = game.Galaxy.size
    cap = game.Universe.EmpireData[player].Capital
    cap_xy = game.Universe.Planet[cap.Index].XY if cap.Index else XYCoord(1, 1)

    start_horz = cap_xy.x % GRID_SEP or GRID_SEP
    start_vert = cap_xy.y % GRID_SEP or GRID_SEP

    for x in range(start_horz, size + 1, GRID_SEP):
        for y in range(1, size + 1):
            cell = buffer[y][x]
            cell.world = VERT_CHAR
            cell.player_flt = BLANK_CHAR
            cell.enemy_flt = BLANK_CHAR
            cell.world_style = GRID_STYLE

    for y in range(start_vert, size + 1, GRID_SEP):
        for x in range(1, size + 1):
            cell = buffer[y][x]
            cell.world_style = GRID_STYLE
            cell.player_flt_style = GRID_STYLE
            cell.enemy_flt_style = GRID_STYLE

            if cell.world == VERT_CHAR:
                cell.enemy_flt = CROSS_CHAR_1
                cell.world = CROSS_CHAR_2
                cell.player_flt = CROSS_CHAR_3
            else:
                cell.world = HORZ_CHAR
                cell.enemy_flt = BLANK_CHAR
                cell.player_flt = BLANK_CHAR


def _draw_nebula_and_mines(
    game: GameEnvironment, buffer: list[list[MapCell]], player: Empire
) -> None:
    """Shade nebulae, and mark minefields the player can see.

    A minefield is visible if the player has scouted it *or* owns it, and it
    takes the world column -- so inside a nebula the mine marker replaces the
    shading rather than sitting beside it.
    """
    size = game.Galaxy.size

    for x in range(1, size + 1):
        for y in range(1, size + 1):
            sector = game.Galaxy.sector(XYCoord(x, y))
            neb = NebulaTypes(nebula_of(sector.Special))
            owner = srm_owner_of(sector.Special)
            mined = player in sector.MineScout or owner == int(player)
            mine_style = PLAYER_STYLE if owner == int(player) else ENEMY_STYLE

            cell = buffer[y][x]
            if neb != NebulaTypes.NoNeb:
                cell.player_flt = NEBULA_CHAR[neb]
                cell.player_flt_style = NEBULA_STYLE
                cell.enemy_flt = NEBULA_CHAR[neb]
                cell.enemy_flt_style = NEBULA_STYLE
                if mined:
                    cell.world = MINE_CHAR
                    cell.world_style = mine_style
                else:
                    cell.world = NEBULA_CHAR[neb]
                    cell.world_style = NEBULA_STYLE
            elif mined:
                cell.world = MINE_CHAR
                cell.world_style = mine_style


def _draw_planets(
    game: GameEnvironment, buffer: list[list[MapCell]], player: Empire
) -> None:
    """Worlds: their designation glyph if known, a bare ``p`` if not.

    The unknown fallback is suppressed inside a nebula, which is the one place
    a world can be hidden outright.

    Note this draws ``TypeStr[Typ]`` -- the world's *designation* -- not its
    class. An earlier version of this widget drew ``ClassStr``, which showed
    the terrain rather than what the world is for.
    """
    for i in range(1, game.NoOfPlanets + 1):
        planet = game.Universe.Planet[i]
        cell = buffer[planet.XY.y][planet.XY.x]

        if player in planet.KnownBy:
            cell.world = TypeStr[planet.Typ]
            cell.world_style = PLAYER_STYLE if planet.Emp == player else ENEMY_STYLE
        elif nebula_of(game.Galaxy.sector(planet.XY).Special) == NebulaTypes.NoNeb:
            cell.world = UNK_PLANET_CHAR
            cell.world_style = UNSCOUTED_STYLE


def _draw_own_fleets(
    game: GameEnvironment, buffer: list[list[MapCell]], player: Empire
) -> None:
    active = game.GlobalSets.SetOfActiveFleets & game.GlobalSets.SetOfFleetsOf[player]
    for i in active:
        fleet = game.Universe.Fleet[i]
        if fleet is None:
            continue
        cell = buffer[fleet.XY.y][fleet.XY.x]
        cell.player_flt = PLAYER_FLEET_CHAR
        cell.player_flt_style = PLAYER_FLEET_STYLE


def _draw_starbases(
    game: GameEnvironment, buffer: list[list[MapCell]], player: Empire
) -> None:
    for i in game.GlobalSets.SetOfActiveStarbases:
        base = game.Universe.Starbase[i]
        if player not in base.KnownBy:
            continue
        cell = buffer[base.XY.y][base.XY.x]
        cell.world = cp437(BaseTypeData[base.STyp])
        cell.world_style = PLAYER_STYLE if base.Emp == player else ENEMY_STYLE


def _draw_stargates(
    game: GameEnvironment, buffer: list[list[MapCell]], player: Empire
) -> None:
    for i in game.GlobalSets.SetOfActiveGates:
        gate = game.Universe.Stargate[i]
        if player not in gate.KnownBy:
            continue
        cell = buffer[gate.XY.y][gate.XY.x]
        cell.world = cp437(GateTypeData[gate.GTyp])
        cell.world_style = PLAYER_STYLE if gate.Emp == player else ENEMY_STYLE


def _draw_constructions(
    game: GameEnvironment, buffer: list[list[MapCell]], player: Empire
) -> None:
    for i in game.GlobalSets.SetOfActiveConstructionSites:
        site = game.Universe.Constr[i]
        if player not in site.KnownBy:
            continue
        cell = buffer[site.XY.y][site.XY.x]
        cell.world = CONS_CHAR
        cell.world_style = PLAYER_STYLE if site.Emp == player else ENEMY_STYLE


def _draw_enemy_fleets(
    game: GameEnvironment, buffer: list[list[MapCell]], player: Empire
) -> None:
    """Everyone else's fleets, in the third column.

    Gated on ``KnownBy``, so a hunter-killer group that has slipped detection
    leaves the column blank -- which is the whole point of flying one.
    """
    to_check = game.GlobalSets.SetOfActiveFleets - game.GlobalSets.SetOfFleetsOf[player]
    for i in to_check:
        fleet = game.Universe.Fleet[i]
        if fleet is None or player not in fleet.KnownBy:
            continue
        cell = buffer[fleet.XY.y][fleet.XY.x]
        cell.enemy_flt = ENEMY_FLEET_CHAR
        cell.enemy_flt_style = ENEMY_STYLE


#: Bytes 0x01-0x1F render as graphical symbols in the IBM PC font, but the
#: cp437 *codec* maps them to C0 control characters instead. The stargate
#: glyphs live in this range (0x12 and 0x18), so they need the real table.
_CP437_CONTROL_GLYPHS = "\0☺☻♥♦♣♠•◘○◙♂♀♪♫☼►◄↕‼¶§▬↨↑↓→←∟↔▲▼"


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
        """The world-column character for one sector, as the player sees it."""
        return build_map(self.game, self.game.Player)[xy.y][xy.x].world

    def render(self) -> Text:
        galaxy = self.game.Galaxy
        if galaxy.size <= 0:
            return Text("No galaxy loaded.", style="dim")

        buffer = build_map(self.game, self.game.Player)

        # Three columns per sector, as the original lays them out.
        width = max(1, self.size.width // 3)
        height = max(1, self.size.height)

        left = max(1, min(max(1, galaxy.size - width + 1), self.cursor_x - width // 2))
        top = max(1, min(max(1, galaxy.size - height + 1), self.cursor_y - height // 2))

        text = Text()
        for y in range(top, min(galaxy.size, top + height - 1) + 1):
            for x in range(left, min(galaxy.size, left + width - 1) + 1):
                cell = buffer[y][x]
                if x == self.cursor_x and y == self.cursor_y:
                    text.append("[", style="bold yellow")
                    text.append(cell.world, style=cell.world_style)
                    text.append("]", style="bold yellow")
                else:
                    text.append(cell.player_flt, style=cell.player_flt_style)
                    text.append(cell.world, style=cell.world_style)
                    text.append(cell.enemy_flt, style=cell.enemy_flt_style)
            text.append("\n")

        return text
