"""Status panels.

Simplified port of STAWIND.PAS / EMPWIND.PAS: what the cursor is over, and
how the player's empire is doing. The full multi-page world close-up is
Phase 8.
"""

from __future__ import annotations

from rich.text import Text
from textual.widget import Widget

from ..datacnst import ClassStr, IndusNames, TechN, ThingNames, TypeName
from ..environ import GameEnvironment
from ..galaxy import XYCoord
from ..misc import hi_lo, military_power
from ..news import NewsTypes
from ..primintr import (
    empire_name,
    get_object,
    get_status,
    scouted,
)
from ..types import CARGO_TYPES, SHIP_TYPES, IndusTypes, ObjectTypes


class WorldPanel(Widget):
    """Details of whatever the map cursor is over."""

    def __init__(self, game: GameEnvironment) -> None:
        super().__init__()
        self.game = game
        self.cursor = XYCoord(1, 1)

    def look_at(self, x: int, y: int) -> None:
        self.cursor = XYCoord(x, y)
        self.refresh()

    def render(self) -> Text:
        game = self.game
        text = Text()

        if not game.Galaxy.in_galaxy(self.cursor.x, self.cursor.y):
            return Text("—", style="dim")

        obj = get_object(game, self.cursor)
        if obj.ObjTyp == ObjectTypes.Void:
            return Text("deep space", style="dim")

        if obj.ObjTyp != ObjectTypes.Pln:
            text.append(f"{obj.ObjTyp.name}\n", style="bold")
            text.append(f"owner: {get_status(game, obj).name}\n")
            return text

        planet = game.Universe.Planet[obj.Index]
        owner = get_status(game, obj)

        text.append(f"World #{obj.Index}  ", style="bold")
        text.append(f"[{self.cursor.x},{self.cursor.y}]\n", style="dim")

        # Unscouted worlds show only what can be seen from a distance.
        if owner != game.Player and not scouted(game, game.Player, obj):
            text.append("class ")
            text.append(f"{ClassStr[planet.Cls]}\n", style="bold")
            text.append("not scouted\n", style="dim italic")
            return text

        name = empire_name(game, owner) or owner.name
        text.append(f"{name}\n", style="bold")
        text.append(f"{TypeName[planet.Typ]}\n")
        text.append(f"class {ClassStr[planet.Cls]}   {TechN[planet.Tech]}\n")
        text.append(f"pop {planet.Pop}   eff {planet.Eff}%\n")
        text.append(f"unrest {hi_lo(planet.RevIndex)} ({planet.RevIndex})\n")
        text.append(f"trillum reserve {planet.TriReserve}\n\n", style="dim")

        cargo = [
            f"{ThingNames[c]} {planet.Cargo[c]}"
            for c in CARGO_TYPES
            if planet.Cargo[c]
        ]
        if cargo:
            text.append("cargo\n", style="bold")
            for line in cargo:
                text.append(f"  {line}\n")

        ships = [
            f"{ThingNames[s]} {planet.Ships[s]}" for s in SHIP_TYPES if planet.Ships[s]
        ]
        if ships:
            text.append("ships\n", style="bold")
            for line in ships:
                text.append(f"  {line}\n")

        indus = [
            f"{IndusNames[i]} {planet.Indus[i]}"
            for i in IndusTypes
            if planet.Indus[i]
        ]
        if indus:
            text.append("industry\n", style="bold")
            for line in indus:
                text.append(f"  {line}\n")

        return text


class EmpirePanel(Widget):
    """Totals for the active player's empire."""

    def __init__(self, game: GameEnvironment) -> None:
        super().__init__()
        self.game = game

    def totals(self) -> tuple[int, int, int]:
        """Worlds held, total population, and total military power."""
        game = self.game
        worlds = 0
        population = 0
        power = 0

        for planet in game.Universe.Planet[1 : game.NoOfPlanets + 1]:
            if planet is None or planet.Emp != game.Player:
                continue
            worlds += 1
            population += planet.Pop
            power += military_power(planet.Ships, planet.Defns)

        return worlds, population, power

    def render(self) -> Text:
        game = self.game
        worlds, population, power = self.totals()
        data = game.Universe.EmpireData[game.Player]
        name = data.EmpireName or game.Player.name

        text = Text()
        text.append(f"{name}\n", style="bold")
        text.append(f"year {game.Year}\n")
        text.append(f"tech {TechN[data.TechnologyLevel]}\n")
        text.append(f"worlds {worlds}\n")
        text.append(f"population {population}\n")
        text.append(f"military power {power}\n")
        if data.TotalRevIndex:
            text.append(f"unrest {data.TotalRevIndex}\n", style="yellow")
        return text


class NewsPanel(Widget):
    """The year's headlines, rendered into prose.

    Simplified port of NWSWIND.PAS. The original pages through a scrolling
    window; this shows the tail of the feed, which is what matters when the
    list is short and is the part a player reads first when it is long.

    News is per-empire and cleared at the start of each of that empire's
    turns, so this is always "what happened since you last looked".
    """

    def __init__(self, game: GameEnvironment) -> None:
        super().__init__()
        self.game = game

    #: Headlines that are continuation lines for the item above them. The
    #: original indents them with three spaces; they are dimmed here so a long
    #: casualty list does not drown the headline it belongs to.
    DETAIL_HEADLINES = frozenset(
        {NewsTypes.DestDetail, NewsTypes.Trns2, NewsTypes.DthHolo, NewsTypes.IndDs}
    )

    def render(self) -> Text:
        from ..intrface import get_news_line
        from ..news import get_news_list

        feed = get_news_list(self.game, self.game.Player)
        if not feed:
            return Text("no news", style="dim italic")

        text = Text()
        for item in feed:
            rendered = get_news_line(self.game, self.game.Player, item)
            if not rendered:
                continue
            style = "dim" if item.Headline in self.DETAIL_HEADLINES else ""
            text.append(f"{rendered}\n", style=style)

        return text or Text("no news", style="dim italic")
